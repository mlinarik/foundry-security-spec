"""Validate generated backlog format, references and coverage without running application tests."""
from pathlib import Path
import json
import re

root = Path(__file__).resolve().parents[2]
feature = root/'specs/001-foundry'
metadata = json.loads((feature/'task-metadata.json').read_text(encoding='utf-8'))
text = (feature/'tasks.md').read_text(encoding='utf-8')
tasks = metadata['tasks']
ids = [t['id'] for t in tasks]
assert ids == [f'T{i:03}' for i in range(1,len(tasks)+1)]
lines = [line for line in text.splitlines() if line.startswith('- [')]
assert len(lines) == len(tasks)
pattern = r'^- \[ \] (T\d{3})(?: \[P\])?(?: \[US(\d+)\])? .+'
for line, task in zip(lines,tasks):
    match = re.fullmatch(pattern,line)
    assert match and match[1]==task['id'], line
    expected = str(task['group']) if isinstance(task['group'],int) else None
    assert match[2]==expected, line
    assert re.search(r'(?:src/|tests/|deploy/|docs/|rules/|examples/|specs/|\.github/)[\w./-]+|pyproject\.toml|requirements\.lock',line), line
    assert ('[P]' in line)==task['parallel']
    assert line.rstrip()==line
assert {t['group'] for t in tasks if isinstance(t['group'],int)}==set(range(1,15))
required = set(re.findall(r'^- \*\*((?:FR|NFR)-\d{3})',(feature/'spec.md').read_text(encoding='utf-8'), re.M))
assert set(metadata['coverage'])==required and len(required)==158
for req, mapping in metadata['coverage'].items():
    assert mapping['implementation'] and mapping['verification'], req
    for kind, references in mapping.items():
        for reference in references:
            task = next(t for t in tasks if t['id']==reference)
            assert req in task['refs'].split(','), (req,reference)
            assert task['kind']== 'implementation' if kind=='implementation' else task['kind'] in ('test','verification')
for task in tasks:
    assert set(task['refs'].split(',')) <= required
# Acyclic dependencies and conservative task phase order.
positions = {str(t['group']):i for i,t in enumerate(tasks)}
for story, deps in metadata['dependencies'].items():
    for dep in deps:
        assert positions[str(dep)] < positions[story], (story,dep)
api = json.loads((feature/'contracts/openapi.json').read_text(encoding='utf-8'))
operations = {v['operationId'] for item in api['paths'].values() for k,v in item.items() if k in ('get','post','put','patch','delete')}
assert {entry['operation'] for entry in metadata['operations']} == operations
assert len(metadata['operations'])==len(operations)==41
for entry in metadata['operations']:
    assert entry['task'] in ids
for target in re.findall(r'\]\(([^)]+)\)',text):
    assert (feature/target).exists(),target
assert not re.search(r'NEEDS CLARIFICATION|TXXX|\[FEATURE NAME\]',text)
assert 'hooks:\n' in (root/'.specify/extensions.yml').read_text(encoding='utf-8').replace('\r\n','\n')
print(json.dumps({'tasks':len(tasks),'format':'all valid','stories':14,'requirements':len(required),
                  'api_operations':len(operations),'parallel_tasks':sum(t['parallel'] for t in tasks),
                  'dependency_order':'valid','references':'valid','application_tests':'not run'},indent=2))
