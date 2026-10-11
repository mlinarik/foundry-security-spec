"""Versioned data-only serializer: no dynamic imports, pickle or object hooks."""
import base64
from collections import deque
from datetime import datetime
import json
import math
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Interrupt, Send


MESSAGES={c.__name__:c for c in (AIMessage,HumanMessage,SystemMessage,ToolMessage)}


class SafeCodec:
    version='foundry-json-v1'
    maximum_bytes=8*1024*1024

    def encode(self,value,depth=0):
        if depth>64:
            raise ValueError('Checkpoint nesting exceeds supported depth')
        child=lambda v:self.encode(v,depth+1)
        if value is None or type(value) in (bool,int,str):
            return {'type':'scalar','value':value}
        if type(value) is float:
            if not math.isfinite(value): raise ValueError('Nonfinite number')
            return {'type':'scalar','value':value}
        if isinstance(value,dict):
            if not all(isinstance(k,str) for k in value): raise ValueError('String keys required')
            return {'type':'dict','value':[[k,child(v)] for k,v in sorted(value.items())]}
        if type(value) in (list,tuple,set,frozenset,deque):
            items=[child(v) for v in value]
            if isinstance(value,(set,frozenset)):
                items.sort(key=lambda v:json.dumps(v,sort_keys=True))
            return {'type':type(value).__name__,'value':items}
        if type(value) is bytes:
            return {'type':'bytes','value':base64.b64encode(value).decode()}
        if type(value) in (datetime,UUID):
            return {'type':type(value).__name__,'value':str(value)}
        if type(value).__name__ in MESSAGES and type(value) is MESSAGES[type(value).__name__]:
            return {'type':type(value).__name__,'value':child(value.model_dump())}
        if isinstance(value,Send):
            return {'type':'Send','value':child({'node':value.node,'arg':value.arg})}
        if isinstance(value,Interrupt):
            return {'type':'Interrupt','value':child({'value':value.value,'id':value.id})}
        if isinstance(value,Exception) and type(value).__module__=='builtins':
            from foundry_v2.workers.transcripts import Redactor
            return {'type':'exception','value':child({'name':type(value).__name__,'message':Redactor().redact(str(value))})}
        raise ValueError('Unsupported checkpoint value type')

    def decode(self,value,depth=0):
        if depth>64 or not isinstance(value,dict) or set(value)!={'type','value'}:
            raise ValueError('Invalid controlled checkpoint encoding')
        kind,payload=value['type'],value['value']
        child=lambda v:self.decode(v,depth+1)
        if kind=='scalar':
            if payload is not None and type(payload) not in (bool,int,str,float): raise ValueError('Invalid scalar')
            if type(payload) is float and not math.isfinite(payload): raise ValueError('Nonfinite scalar')
            return payload
        if kind=='dict':
            if not isinstance(payload,list) or any(not isinstance(pair,list) or len(pair)!=2 or not isinstance(pair[0],str) for pair in payload): raise ValueError('Invalid dictionary')
            if len({pair[0] for pair in payload})!=len(payload): raise ValueError('Duplicate dictionary key')
            return {k:child(v) for k,v in payload}
        collections={'list':list,'tuple':tuple,'set':set,'frozenset':frozenset,'deque':deque}
        if kind in collections:
            if not isinstance(payload,list): raise ValueError('Invalid collection')
            return collections[kind](child(v) for v in payload)
        if kind=='bytes': return base64.b64decode(payload,validate=True)
        if kind=='datetime': return datetime.fromisoformat(payload)
        if kind=='UUID': return UUID(payload)
        if kind in MESSAGES: return MESSAGES[kind].model_validate(child(payload))
        if kind=='Send':
            data=child(payload)
            if set(data)!={'node','arg'} or not isinstance(data['node'],str): raise ValueError('Invalid Send')
            return Send(data['node'],data['arg'])
        if kind=='Interrupt':
            data=child(payload)
            if set(data)!={'id','value'} or not isinstance(data['id'],str): raise ValueError('Invalid Interrupt')
            return Interrupt(value=data['value'],id=data['id'])
        if kind=='exception':
            data=child(payload)
            if set(data)!={'name','message'} or not all(isinstance(v,str) for v in data.values()): raise ValueError('Invalid exception summary')
            return RuntimeError(data['name']+': '+data['message'])
        raise ValueError('Unsupported checkpoint encoding')

    def dumps_typed(self,value):
        data=json.dumps(self.encode(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if len(data)>self.maximum_bytes: raise ValueError('Checkpoint exceeds size limit')
        return self.version,data

    def loads_typed(self,data):
        version,blob=data
        if version!=self.version or len(blob)>self.maximum_bytes: raise ValueError('Unsupported checkpoint codec or size')
        return self.decode(json.loads(blob))
