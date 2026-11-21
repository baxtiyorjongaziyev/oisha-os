"""Install only the reviewed task modules after verifying deployed base hashes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
from datetime import datetime, timezone

ROOT = Path("/home/deploy/oisha-os")
EXPECTED = {
    "src/services/core/crm/task_notifier/notifier.py": "4b12b5714ae643672d1f993582f628617d317eb63e6e6cc42d0bc2c0acbaa9c2",
    "src/services/core/crm/task_notifier/formatter.py": "36b077a9db00c11c93acbf1e2f8317cceed7361a96e0ef0e21896123de8dacf9",
    "src/services/core/crm/amocrm/tasks_notes.py": "ac56f6a536a276d401702530a227092231cddc6eb57393806808aa334dbc237c",
}
NEW = {
    "src/services/core/crm/task_notifier/routing.py",
    "src/services/core/crm/task_notifier/delivery.py",
    "src/services/core/crm/amocrm/task_reader.py",
    "scripts/prod/verify_seller_task_delivery.py",
}


def main():
    backup = ROOT.parent / "oisha-task-dm-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with tarfile.open(Path.home() / "oisha-seller-task-dm.tar") as bundle:
        members = {m.name: m for m in bundle.getmembers()}
        assert set(members) == set(EXPECTED) | NEW
        for path, digest in EXPECTED.items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
        for path in NEW:
            assert not (ROOT / path).exists(), path
        content = {p: bundle.extractfile(m).read() for p, m in members.items() if m.isfile()}
        assert len(content) == len(members)
        for path, data in content.items():
            compile(data, path, "exec")
        for path in EXPECTED:
            saved = backup / path
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, saved)
        for path, data in content.items():
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            pending = target.with_suffix(".pending")
            pending.write_bytes(data)
            os.replace(pending, target)
        receipt = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in content}
        (backup / "receipt.json").write_text(json.dumps(receipt))
        print(json.dumps({"backup": str(backup), "installed": receipt}))


if __name__ == "__main__":
    main()
