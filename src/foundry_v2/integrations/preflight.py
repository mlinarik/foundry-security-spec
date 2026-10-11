"""Capability evidence is explicit; missing bindings never count as passing."""
import secrets


def plain(value):
    return value.model_dump() if hasattr(value,'model_dump') else value


async def probe_ollama(client,model='qwen3-coder:30b'):
    errors=[]; marker=secrets.token_hex(8)
    tags=plain(await client.list())
    matching=[m for m in tags.get('models',[]) if m.get('model',m.get('name'))==model]
    digest=matching[0].get('digest') if len(matching)==1 else None
    if not digest: errors.append('model_digest_unavailable')
    response=plain(await client.chat(model=model,messages=[{'role':'system','content':'Reply with exactly '+marker},
                                                         {'role':'user','content':'State the required marker.'}],stream=False))
    if response.get('message',{}).get('content','').strip()!=marker: errors.append('system_prompt_conditioning_failed')
    if any(type(response.get(k)) is not int or response[k]<0 for k in ('prompt_eval_count','eval_count')):
        errors.append('terminal_token_counts_unavailable')
    response=plain(await client.chat(model=model,messages=[{'role':'system','content':'Call foundry_probe with marker '+marker},
                                                         {'role':'user','content':'Use the required tool.'}],
                                    tools=[{'type':'function','function':{'name':'foundry_probe','description':'Protocol probe only',
                                           'parameters':{'type':'object','properties':{'marker':{'type':'string'}},'required':['marker']}}}],stream=False))
    calls=response.get('message',{}).get('tool_calls',[])
    if not any(c.get('function',{}).get('name')=='foundry_probe' and c['function'].get('arguments',{}).get('marker')==marker for c in calls):
        errors.append('representative_tool_call_failed')
    return {'model':model,'digest':digest,'passed':not errors,'errors':errors}


class Preflight:
    required=frozenset({'identity','storage','admission','policy','source','github','rules','ollama'})

    def __init__(self,probes):
        self.probes=probes

    async def run(self,configuration):
        results={}
        required=self.required | ({'testbed'} if configuration.get('testbed') is not None else set())
        for name in sorted(required):
            if name not in self.probes:
                results[name]={'passed':False,'errors':['binding_unavailable']}; continue
            try:
                result=await self.probes[name](configuration)
                results[name]=result if isinstance(result,dict) and type(result.get('passed')) is bool else {'passed':False,'errors':['invalid_probe_result']}
            except Exception:
                results[name]={'passed':False,'errors':['dependency_unavailable']}
        return {'passed':all(r['passed'] for r in results.values()),'checks':results}
