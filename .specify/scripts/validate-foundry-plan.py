"""Validate planning schemas, references, decisions, and artifact completeness."""
from pathlib import Path
import copy
import json
import re
from jsonschema import Draft202012Validator, ValidationError
from openapi_spec_validator import validate

root=Path(__file__).resolve().parents[2]
feature=root/'specs/001-foundry'
contracts=feature/'contracts'
schema=json.loads((contracts/'config.schema.json').read_text(encoding='utf-8'))
example=json.loads((contracts/'example-config.json').read_text(encoding='utf-8'))
api=json.loads((contracts/'openapi.json').read_text(encoding='utf-8'))
Draft202012Validator.check_schema(schema)
validator=Draft202012Validator(schema)
validator.validate(example)
validate(api)
bad_cases=[]
bad=copy.deepcopy(example); bad['unexpected']=True; bad_cases.append(bad)
bad=copy.deepcopy(example); bad['budget']['yield_enabled']=True; bad_cases.append(bad)
bad=copy.deepcopy(example); bad['integrations']['ollama']['model']='unapproved-model'; bad_cases.append(bad)
bad=copy.deepcopy(example); bad['fleet']['heartbeat_seconds']=0; bad_cases.append(bad)
bad=copy.deepcopy(example); del bad['sandbox']; bad_cases.append(bad)
for bad in bad_cases:
    try: validator.validate(bad)
    except ValidationError: pass
    else: raise AssertionError('Invalid example accepted')
operation_ids=[]
for path,item in api['paths'].items():
    for method,op in item.items():
        operation_ids.append(op['operationId'])
        expected='OperatorBearer' if path.startswith('/v1/') else 'AgentBearer'
        assert op['security']==[{expected:[]}],path
        if method!='get': assert any(p['name']=='Idempotency-Key' and p['required'] for p in op['parameters']),path
assert len(operation_ids)==len(set(operation_ids))
assert len(operation_ids)==41
spec=(feature/'spec.md').read_text(encoding='utf-8')
fr=set(re.findall(r'^- \*\*(FR-\d{3})\*\*:',spec,re.M))
required=['plan.md','research.md','data-model.md','quickstart.md','contracts/README.md','contracts/runtime.md','checklists/plan.md']
for rel in required:
    p=feature/rel; text=p.read_text(encoding='utf-8')
    assert 'NEEDS CLARIFICATION' not in text and '[FEATURE]' not in text,p
    refs=set(re.findall(r'\bFR-\d{3}\b',text)); assert refs<=fr,(p,refs-fr)
    assert all(line.rstrip()==line for line in text.splitlines()),p
    for link in re.findall(r'\]\(([^)]+)\)',text):
        if '://' in link or link.startswith('#'): continue
        assert (p.parent/link.split('#')[0]).exists(),(p,link)
plan=(feature/'plan.md').read_text(encoding='utf-8')
assert len(re.findall(r'^\| [IVX]+\.',plan,re.M))==11
assert (feature/'checklists/plan.md').read_text(encoding='utf-8').count('- [x]')==15
assert 'specs/001-foundry/plan.md' in (root/'AGENTS.md').read_text(encoding='utf-8')
# Planning artifacts remain valid after the subsequent tasks phase is generated.
print(json.dumps({'openapi':'valid 3.1.0','operations':41,'schema':'valid Draft 2020-12','positive_config_fixtures':1,'rejected_config_fixtures':len(bad_cases),'constitution_gates':11,'planning_checks':'15/15','references':'valid','unresolved_design_markers':0},indent=2))
