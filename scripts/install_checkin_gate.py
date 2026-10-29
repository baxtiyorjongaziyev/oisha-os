"""Install the reviewed boundary into the existing Contabo scheduler."""
from pathlib import Path
import shutil

root = Path('/home/ubuntu/oisha-os')
target = root / 'src/schedulers/remote_staff_checkin_scheduler.py'
source = target.read_text()
marker = '    # Persistent deduplication check\n'
guard = '''    from src.services.response_quality.checkin_gate import evaluate
    verdict = evaluate(text)
    if not verdict.allowed:
        logger.warning("[CHECKIN] Quality gate blocked: %s", verdict.reasons)
        return False

'''
if 'Quality gate blocked' not in source:
    if source.count(marker) != 1:
        raise SystemExit('Unexpected scheduler; no changes made')
    shutil.copy2(target, target.with_suffix('.py.bak-quality-20261029'))
    target.write_text(source.replace(marker, guard + marker))
composer = root / 'src/services/core/checkin_composer.py'
source = composer.read_text()
old = '''    if same_day and ctx.get("last_checkin"):
        prompt_parts.append(f"Sening oldingi xabaring:\\n{ctx['last_checkin']}")
'''
if old in source:
    shutil.copy2(composer, composer.with_suffix('.py.bak-quality-20261029'))
    composer.write_text(source.replace(old, ''))
print('Quality gate installed; prior check-in removed from generation input')
