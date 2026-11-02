from pathlib import Path
import json
import re
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / '.tmp/dependabot-main'
out.mkdir(exist_ok=True)
def git(*args):
    return subprocess.check_output(['git', *args], cwd=root)
base = git('rev-parse', 'origin/main').decode().strip()
(root / '.tmp/dependabot-base.txt').write_text(base)
names = git('ls-tree', '-r', '--name-only', base).decode().splitlines()
selected = [n for n in names if re.fullmatch(r'(salescoach-ai/)?(apps|packages)/[^/]+/package.json', n)]
selected += ['package.json', 'pnpm-workspace.yaml', 'pnpm-lock.yaml', 'salescoach-ai/package.json', 'salescoach-ai/pnpm-workspace.yaml', 'salescoach-ai/pnpm-lock.yaml', 'patches/braces@3.0.3.patch', '.github/workflows/test.yml']
for name in selected:
    p = out / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(git('show', f'{base}:{name}'))
p = out / 'pnpm-workspace.yaml'
data = p.read_text().replace('  braces@3.0.3: patches/braces@3.0.3.patch', '  braces@3.0.3: patches/braces@3.0.3.patch\n  deepmerge@4.3.1: patches/deepmerge@4.3.1.patch')
data = re.sub(r'  next: .*', '  next: 16.4.3', data).replace('  qs: ^6.16.0', "  qs: ^6.16.1\n  body-parser@<1.20.9: '>=1.20.9 <2'")
p.write_text(data, newline='\n')
p = out / 'salescoach-ai/package.json'
data = json.loads(p.read_text())
data['pnpm']['overrides'].update({'next': '16.4.3', 'qs': '^6.16.1', 'body-parser@<1.20.9': '>=1.20.9 <2'})
data['pnpm']['patchedDependencies']['deepmerge@4.3.1'] = '../patches/deepmerge@4.3.1.patch'
p.write_text(json.dumps(data, indent=2) + '\n', newline='\n')
for name in ['apps/web/package.json', 'salescoach-ai/apps/web/package.json']:
    p = out / name
    data = json.loads(p.read_text())
    data['dependencies']['next'] = '16.4.3'
    p.write_text(json.dumps(data, indent=2) + '\n', newline='\n')
for name in ['patches/deepmerge@4.3.1.patch', 'scripts/check_deepmerge_security.cjs']:
    p = out / name
    p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / name, p)
p = out / '.github/workflows/test.yml'
data = p.read_text().replace('        run: node scripts/check_braces_security.cjs\n', '        run: node scripts/check_braces_security.cjs\n\n      - name: Verify deepmerge prototype protection\n        run: node scripts/check_deepmerge_security.cjs\n').replace('      - run: node ../scripts/check_braces_security.cjs\n', '      - run: node ../scripts/check_braces_security.cjs\n      - run: node ../scripts/check_deepmerge_security.cjs\n')
p.write_text(data, newline='\n')
print('Prepared dependency-only main inputs at', base)
