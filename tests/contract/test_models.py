import json
from importlib.resources import files

import pytest
from pydantic import ValidationError
from foundry_v2.contracts import models
from pathlib import Path


def test_every_contract_schema_and_operation_is_bundled():
    api = json.loads(files('foundry_v2.contracts').joinpath('openapi.json').read_text())
    assert set(models.MODELS) == set(api['components']['schemas'])
    operations = {operation['operationId'] for item in api['paths'].values() for operation in item.values()}
    assert len(operations) == 41
    assert models.OPERATION_IDS == operations
    specification = json.loads((Path(__file__).parents[2]/'specs/001-foundry/contracts/openapi.json').read_text())
    assert api == specification


def test_dto_rejects_unknown_fields_coercions_and_empty_required_text():
    model = models.MODELS['TaskCreate']
    good = {'role':'detector','title':'Investigate entry','description':'Trace attacker input','priority':0}
    assert model(**good).model_dump(exclude_unset=True) == good
    for bad in [dict(good,priority='0'),dict(good,priority=-1),dict(good,title=''),
                dict(good,role='self-improver'),dict(good,extra='untrusted')]:
        with pytest.raises(ValidationError):
            model(**bad)


def test_nested_checkpoint_writes_are_strict_and_typed():
    model = models.MODELS['CheckpointWrites']
    payload = {'task_id':'t', 'task_path':'graph/step', 'writes':[{'write_index':0,'channel':'result','value':{'ok':True}}]}
    assert model(**payload).writes[0].channel == 'result'
    payload['writes'][0]['write_index'] = '0'
    with pytest.raises(ValidationError):
        model(**payload)
