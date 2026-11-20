"""Repeatable, non-mutating source checks for the Odoo 20 port."""
import ast
import csv
from pathlib import Path
import re
import subprocess

from lxml import etree


root = Path(__file__).resolve().parents[1]
manifest = ast.literal_eval((root / '__manifest__.py').read_text())
assert manifest['version'].startswith('20.0.')
for filename in manifest['data'] + manifest['demo']:
    assert (root / filename).is_file(), filename

counts = {'python': 0, 'xml': 0, 'javascript': 0}
for path in root.rglob('*.py'):
    if '__pycache__' in path.parts:
        continue
    text = path.read_text()
    ast.parse(text, filename=str(path))
    if 'tests' not in path.parts and 'migrations' not in path.parts:
        assert not re.search(r'\.(get_param|set_param|check_access_rights|check_access_rule)\(', text), path
    counts['python'] += 1
for path in root.rglob('*.xml'):
    etree.parse(str(path))
    assert 't-esc=' not in path.read_text(), path
    counts['xml'] += 1
for path in (root / 'static/src').glob('*.js'):
    text = path.read_text()
    assert not re.search(r'\b(useState|useRef|useRecordObserver)\b|static props\s*=', text), path
    subprocess.run(['node', '--check', str(path)], check=True, capture_output=True)
    counts['javascript'] += 1
with (root / 'security/ir.access.csv').open() as handle:
    for row in csv.DictReader(handle):
        assert row['operation'] and set(row['operation']) <= set('crud'), row['id']
        assert row['group_id/id'], row['id']
print('Static checks passed:', counts)
