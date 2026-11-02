from pathlib import Path
import difflib

root = Path(__file__).resolve().parents[1]
source = root / 'node_modules/.pnpm/deepmerge@4.3.1/node_modules/deepmerge'
chunks = []
for name in ['index.js', 'dist/cjs.js', 'dist/umd.js']:
    old = (source / name).read_text()
    new = old.replace('return propertyIsOnObject(target, key) //', "return key === '__proto__' || propertyIsOnObject(target, key) //")
    indent = '\t' if name == 'dist/umd.js' else ''
    marker = indent + '\t\tgetKeys(target).forEach(function(key) {\n'
    assert marker in new
    new = new.replace(marker, marker + indent + "\t\t\tif (key === '__proto__') {\n" + indent + '\t\t\t\treturn\n' + indent + '\t\t\t}\n')
    assert new != old
    chunks.append('diff --git a/' + name + ' b/' + name + '\n')
    chunks.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='a/' + name, tofile='b/' + name))
(root / 'patches/deepmerge@4.3.1.patch').write_text(''.join(chunks), newline='\n')
for name in ['pnpm-workspace.yaml', 'apps/web/package.json', 'salescoach-ai/package.json', 'salescoach-ai/apps/web/package.json']:
    p = root / name
    p.write_text(p.read_text().replace('16.4.1', '16.4.3'), newline='\n')
