"""Replace the production check-in generation block with factual rendering."""
from pathlib import Path
import shutil

path = Path('/home/ubuntu/oisha-os/src/schedulers/remote_staff_checkin_scheduler.py')
source = path.read_text()
start = source.index('    text = build_checkin_message(seller_name, tg_handle, now, calls_info)')
end = source.index('    from src.services.response_quality.checkin_gate import evaluate', start)
replacement = '''    from src.services.response_quality.staff_checkin import render
    body = render(calls_info)
    if body is None:
        logger.warning("[CHECKIN] Missing or inconsistent evidence; held")
        return False
    text = f"{addressee(seller_name, format_handle(tg_handle))}, {body}"

'''
shutil.copy2(path, path.with_suffix('.py.bak-factual-20261029'))
path.write_text(source[:start] + replacement + source[end:])
print('Factual renderer installed; generated prose bypass removed')
