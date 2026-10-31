"""Fixed Contabo deployment target with backups and rollback."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

ROOT = Path('/home/ubuntu/oisha-os')


def healthy():
    for _ in range(20):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=5) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main():
    bundle = Path(sys.argv[1])
    backup = ROOT / 'data' / 'deploy-backups' / bundle.stem
    backup.mkdir(parents=True, exist_ok=False)
    originals = {}
    with tempfile.TemporaryDirectory(prefix='oisha-stage-') as temp:
        staged = Path(temp)
        with tarfile.open(bundle) as archive:
            for member in archive.getmembers():
                rel = Path(member.name)
                target = (ROOT / rel).resolve()
                if not member.isfile() or not target.is_relative_to(ROOT) or rel.parts[0] not in ('src', 'scripts') or rel.suffix != '.py':
                    raise RuntimeError('Invalid deployment member')
                data = archive.extractfile(member).read()
                compile(data, str(rel), 'exec')
                destination = staged / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                originals[rel] = target.exists()
        try:
            for rel, existed in originals.items():
                target = ROOT / rel
                if existed:
                    saved = backup / rel
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, saved)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged / rel, target)
                if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256((staged / rel).read_bytes()).digest():
                    raise RuntimeError('Read-back mismatch')
            subprocess.run(['systemctl', 'restart', 'oisha-os'], check=True, timeout=150)
            if not healthy():
                raise RuntimeError('Health verification failed')
        except BaseException:
            for rel, existed in originals.items():
                target = ROOT / rel
                saved = backup / rel
                if existed and saved.exists():
                    shutil.copy2(saved, target)
                elif not existed:
                    target.unlink(missing_ok=True)
            subprocess.run(['systemctl', 'restart', 'oisha-os'], check=True, timeout=150)
            raise
    bundle.unlink(missing_ok=True)
    print('DEPLOYED: file hashes verified, healthz=200; backup:', backup)


if __name__ == '__main__':
    main()
