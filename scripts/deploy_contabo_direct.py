"""Deploy explicitly selected committed source files over SSH, without GitHub."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
HOST = 'root@109.199.100.137'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', help='Repository-relative Python source paths')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    manifest = {}
    for name in args.files:
        path = (ROOT / name).resolve()
        rel = path.relative_to(ROOT).as_posix()
        if not rel.startswith(('src/', 'scripts/')) or path.suffix != '.py':
            raise SystemExit('Only explicitly selected Python source files are supported')
        if any(part.startswith('.') for part in Path(rel).parts):
            raise SystemExit('Hidden files are forbidden')
        committed = subprocess.check_output(['git', 'show', f'HEAD:{rel}'], cwd=ROOT)
        data = path.read_bytes()
        if committed.replace(b'\r\n', b'\n') != data.replace(b'\r\n', b'\n'):
            raise SystemExit(f'Commit this file first: {rel}')
        compile(data, rel, 'exec')
        manifest[rel] = hashlib.sha256(data).hexdigest()
    print(json.dumps({'files': manifest, 'apply': args.apply}, indent=2))
    if not args.apply:
        return
    with tempfile.TemporaryDirectory(prefix='oisha-deploy-') as folder:
        bundle = Path(folder) / 'bundle.tar'
        with tarfile.open(bundle, 'w') as archive:
            for rel in manifest:
                archive.add(ROOT / rel, arcname=rel)
        remote = '/tmp/oisha-direct-' + uuid.uuid4().hex + '.tar'
        run('scp', '-o', 'BatchMode=yes', str(bundle), f'{HOST}:{remote}')
        helper = ROOT / 'scripts' / 'deploy_contabo_receiver.py'
        remote_helper = remote + '.py'
        run('scp', '-o', 'BatchMode=yes', str(helper), f'{HOST}:{remote_helper}')
        run('ssh', '-o', 'BatchMode=yes', HOST, 'python3', remote_helper, remote)


if __name__ == '__main__':
    main()
