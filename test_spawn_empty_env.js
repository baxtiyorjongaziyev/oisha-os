const { spawn } = require('child_process');

const args = [
  '-T',
  '-i',
  'C:/Users/baxti/.ssh/oracle_free_tier_ed25519',
  '-o',
  'StrictHostKeyChecking=no',
  '-o',
  'BatchMode=yes',
  '-o',
  'ConnectTimeout=15',
  '-o',
  'ServerAliveInterval=15',
  '-o',
  'ServerAliveCountMax=6',
  '-o',
  'TCPKeepAlive=yes',
  'ubuntu@163.192.10.104',
  '/home/ubuntu/oisha-os/venv/bin/python3',
  '-u',
  '/home/ubuntu/oisha-os/scripts/oisha_mcp_server.py'
];

const child = spawn('C:\\WINDOWS\\System32\\OpenSSH\\ssh.exe', args, { env: {} });

child.stdout.on('data', (data) => console.log(`[STDOUT] ${data.toString()}`));
child.stderr.on('data', (data) => console.log(`[STDERR] ${data.toString()}`));

child.on('close', (code) => {
  console.log(`[EXIT] child process exited with code ${code}`);
});

setTimeout(() => {
  console.log("Killing...");
  child.kill();
}, 2000);
