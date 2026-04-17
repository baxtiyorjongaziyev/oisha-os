from pathlib import Path
path = Path('/home/baxti/oisha-os/src/main.py')
text = path.read_text(encoding='utf-8')
old = '                    f"Loyiha: {workflow.get(\'project_name\') or \'noma-lum\'}",\n'
new = '                    "Loyiha: " + str(workflow.get(\'project_name\') or \'noma-lum\'),\n'
path.write_text(text.replace(old, new), encoding='utf-8')
print('replaced line')
