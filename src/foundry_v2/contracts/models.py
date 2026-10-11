"""Strict DTOs derived from the packaged canonical OpenAPI components."""
import json
from importlib.resources import files
from typing import Annotated, Any, Literal, Union
from uuid import uuid4

from pydantic import ConfigDict, Field, create_model

_API = json.loads(files(__package__).joinpath('openapi.json').read_text(encoding='utf-8'))
OPERATION_IDS = frozenset(operation['operationId'] for item in _API['paths'].values() for operation in item.values())


def _annotation(name, schema):
    if not schema:
        return Any
    if 'enum' in schema:
        return Literal[tuple(schema['enum'])]
    kind = schema.get('type')
    if isinstance(kind, list):
        return Union[tuple(_annotation(name, dict(schema,type=item)) for item in kind)]
    if kind == 'object':
        if schema.get('additionalProperties') is True:
            return dict[str, Any]
        fields = {}
        for key, property_schema in schema.get('properties', {}).items():
            fields[key] = (_annotation(name+'_'+key, property_schema),
                           ... if key in schema.get('required', []) else None)
        return create_model(name, __config__=ConfigDict(extra='forbid',strict=True), **fields)
    if kind == 'array':
        return list[_annotation(name+'_item', schema['items'])]
    base = {'string':str, 'integer':int, 'number':float, 'boolean':bool, 'null':type(None)}.get(kind)
    if base is None:
        raise ValueError(f'Unsupported DTO schema: {name}')
    bounds = {field:schema[key] for key,field in [('minimum','ge'),('maximum','le'),
              ('exclusiveMinimum','gt'),('minLength','min_length'),('pattern','pattern')] if key in schema}
    return Annotated[base, Field(**bounds)] if bounds else base


MODELS = {name:_annotation(name, schema) for name,schema in _API['components']['schemas'].items()}
globals().update(MODELS)


def new_id():
    return str(uuid4())


class DomainError(Exception):
    status = 400

    def __init__(self, code, message=None):
        self.code = code
        self.message = message or code.replace('_',' ')
        super().__init__(self.code + ': ' + self.message)

    def response(self, request_id):
        return {'code':self.code, 'message':self.message, 'request_id':request_id}


class Conflict(DomainError):
    status = 409


class Unavailable(DomainError):
    status = 503
