import os
import sys
import time
import socket
import queue
import threading
import paramiko

class ReconnectingSSHBridge:
    def __init__(self, host, username, key_filename, command, keepalive_interval=15):
        self.host = host
        self.username = username
        self.key_filename = key_filename
        self.command = command
        self.keepalive_interval = keepalive_interval
        
        # Thread-safe queue to persist stdin bytes across reconnections
        self.stdin_queue = queue.Queue()
        self.running = True
        self.client = None
        self.channel = None
        self.lock = threading.Lock()

    def start(self):
        # 1. Start the local stdin reader thread (Producer)
        t_stdin = threading.Thread(target=self._read_local_stdin, daemon=True)
        t_stdin.start()
        
        # 2. Run the connection & writer loop (Consumer)
        try:
            self._bridge_loop()
        except KeyboardInterrupt:
            sys.stderr.write("Bridge stopped by user.\n")
            sys.stderr.flush()
        finally:
            self.running = False
            self.cleanup_connection()

    def _read_local_stdin(self):
        """Reads from local stdin.buffer (binary) and queues it."""
        try:
            while self.running:
                # Use read1 to get data immediately without blocking latency (crucial for streaming JSON-RPC)
                if hasattr(sys.stdin.buffer, 'read1'):
                    chunk = sys.stdin.buffer.read1(4096)
                else:
                    chunk = sys.stdin.buffer.read(1)
                
                if not chunk:
                    # EOF from client (e.g., ChatGPT Desktop app shutdown)
                    self.stdin_queue.put(None) # Sentinel for EOF
                    break
                self.stdin_queue.put(chunk)
        except Exception as e:
            sys.stderr.write(f"Local stdin reader error: {e}\n")
            sys.stderr.flush()

    def _configure_socket_keepalives(self, sock):
        """Enables TCP-level keepalives on the socket for early connection death detection."""
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Linux & macOS parameters
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, self.keepalive_interval)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5) # 5 seconds probe interval
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3) # 3 missed probes before exit
            # Windows parameters
            if hasattr(socket, "SIO_KEEPALIVE_VALS"):
                sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, self.keepalive_interval * 1000, 5000))
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to set TCP keepalive options: {e}\n")
            sys.stderr.flush()

    def _read_remote_stream(self, channel, dest_stream, is_stderr, stop_event):
        """Reads from remote SSH channel stdout/stderr and writes to local stdout/stderr."""
        try:
            while not stop_event.is_set():
                if is_stderr:
                    data = channel.recv_stderr(4096)
                else:
                    data = channel.recv(4096)
                
                if not data:
                    break # Connection or command closed
                
                dest_stream.buffer.write(data)
                dest_stream.flush()
        except Exception:
            pass
        finally:
            stop_event.set()

    def cleanup_connection(self):
        with self.lock:
            if self.channel:
                try:
                    self.channel.close()
                except Exception:
                    pass
                self.channel = None
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass
                self.client = None

    def _bridge_loop(self):
        while self.running:
            self.client = paramiko.SSHClient()
            self.client.load_system_host_keys()
            self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
            
            sys.stderr.write(f"Connecting to remote Oracle VM ({self.host})...\n")
            sys.stderr.flush()
            
            try:
                self.client.connect(
                    hostname=self.host,
                    username=self.username,
                    key_filename=self.key_filename,
                    timeout=15,
                    banner_timeout=15
                )
                
                transport = self.client.get_transport()
                # SSH-level keepalive
                transport.set_keepalive(self.keepalive_interval)
                
                # TCP-level socket keepalive
                sock = transport.sock
                if sock:
                    self._configure_socket_keepalives(sock)
                
                # Open channel session & execute remote process
                self.channel = transport.open_session()
                self.channel.exec_command(self.command)
                
                sys.stderr.write("SSH Connection established and remote Telegram MCP server started successfully! ✅\n")
                sys.stderr.flush()
                
                stop_event = threading.Event()
                
                # Start reading remote stdout and stderr
                t_stdout = threading.Thread(
                    target=self._read_remote_stream,
                    args=(self.channel, sys.stdout, False, stop_event),
                    daemon=True
                )
                t_stderr = threading.Thread(
                    target=self._read_remote_stream,
                    args=(self.channel, sys.stderr, True, stop_event),
                    daemon=True
                )
                
                t_stdout.start()
                t_stderr.start()
                
                # Main writing loop (Consumer)
                while not stop_event.is_set():
                    try:
                        # Fetch stdin data from the queue buffer
                        chunk = self.stdin_queue.get(timeout=1.0)
                        
                        if chunk is None:
                            # EOF sentinel: local stdin has closed (e.g. app shutdown)
                            sys.stderr.write("Local stdin EOF. Gracefully closing connection.\n")
                            sys.stderr.flush()
                            with self.lock:
                                if self.channel:
                                    self.channel.shutdown_write()
                                    self.channel.recv_exit_status()
                            self.running = False
                            return
                        
                        # Forward data to remote channel
                        with self.lock:
                            if self.channel:
                                self.channel.sendall(chunk)
                        self.stdin_queue.task_done()
                        
                    except queue.Empty:
                        # Check liveness when idle
                        with self.lock:
                            if not self.channel or self.channel.closed or not transport.is_active():
                                sys.stderr.write("SSH Channel or transport became inactive.\n")
                                sys.stderr.flush()
                                break
                    except (socket.error, paramiko.SSHException) as e:
                        sys.stderr.write(f"Transmission error: {e}\n")
                        sys.stderr.flush()
                        break
                        
            except Exception as e:
                sys.stderr.write(f"Connection error: {e}\n")
                sys.stderr.flush()
            finally:
                stop_event.set()
                self.cleanup_connection()
                
            if self.running:
                sys.stderr.write("Disconnected. Attempting to reconnect in 5 seconds...\n")
                sys.stderr.flush()
                time.sleep(5)

if __name__ == "__main__":
    HOST = "163.192.10.104"
    USERNAME = "ubuntu"
    KEY_FILENAME = r"C:\Users\baxti\.ssh\oracle_free_tier_ed25519"
    # Execute the remote MCP server on Oracle VM
    COMMAND = "/opt/oisha-os/.venv/bin/python3 -u /opt/oisha-os/scripts/telegram_mcp_server.py"

    bridge = ReconnectingSSHBridge(HOST, USERNAME, KEY_FILENAME, COMMAND)
    bridge.start()
