const { spawn } = require('child_process');

const cp = spawn('C:\\WINDOWS\\System32\\OpenSSH\\ssh.exe', [
  '-T',
  '-i', 'C:/Users/baxti/.ssh/oracle_free_tier_ed25519',
  '-o', 'StrictHostKeyChecking=no',
  '-o', 'BatchMode=yes',
  '-o', 'ConnectTimeout=15',
  '-o', 'ServerAliveInterval=15',
  '-o', 'ServerAliveCountMax=6',
  '-o', 'TCPKeepAlive=yes',
  'ubuntu@163.192.10.104',
  '/home/ubuntu/oisha-os/venv/bin/python3',
  '-u',
  '/home/ubuntu/oisha-os/scripts/oisha_mcp_server.py'
], { stdio: ['pipe', 'pipe', 'pipe'] });

cp.on('error', err => console.log('ERROR EVENT:', err));
cp.stdout.on('data', d => console.log('OUT:', d.toString()));
cp.stderr.on('data', d => console.log('ERR:', d.toString()));
cp.on('close', code => console.log('CLOSE:', code));

setTimeout(() => {
  cp.stdin.write(JSON.stringify({
    jsonrpc: "2.0",
    id: 0,
    method: "initialize",
    params: {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "t", version: "1" }
    }
  }) + '\n');
}, 3000);

setTimeout(() => process.exit(0), 10000);
