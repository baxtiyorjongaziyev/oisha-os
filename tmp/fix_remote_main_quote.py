from pathlib import Path
path = Path('/home/baxti/oisha-os/src/main.py')
text = path.read_text(encoding='utf-8')
old = "f\"Loyiha: {workflow.get('project_name') or 'noma\\'lum'}\""
new = "f\"Loyiha: {workflow.get('project_name') or 'noma-lum'}\""
path.write_text(text.replace(old, new), encoding='utf-8')
print('fixed quote')
