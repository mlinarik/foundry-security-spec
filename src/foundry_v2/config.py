"""Schema and semantic validation with safe, aggregated field diagnostics."""
import argparse
import copy
from importlib.resources import files
import ipaddress
import json
import math
from pathlib import PurePosixPath
import re
from urllib.parse import urlparse

import jsonschema
import yaml


class ConfigurationError(ValueError):
    def __init__(self,errors):
        self.errors=sorted(set(errors)); super().__init__('; '.join(self.errors))


def validate(value,*,private_http=False,local_storage=False):
    schema=json.loads(files('foundry_v2.contracts').joinpath('config.schema.json').read_text())
    errors=[]
    for error in jsonschema.Draft202012Validator(schema).iter_errors(value):
        path='.'.join(str(p) for p in error.absolute_path) or 'configuration'
        if error.validator=='required' and isinstance(error.instance,dict):
            errors += [path+'.'+key+': required' for key in error.schema['required'] if key not in error.instance]
        else: errors.append(path+': invalid '+error.validator)
    if errors: raise ConfigurationError(errors)
    def invalid(path,reason): errors.append(path+': '+reason)
    def revision(value,path):
        if not re.fullmatch('[0-9a-f]{40}',value) or value=='0'*40: invalid(path,'full non-placeholder commit required')
    def repo_url(value,path):
        url=urlparse(value)
        if url.scheme!='https' or not url.hostname or url.username or url.password or 'REPLACE_' in value:
            invalid(path,'credential-free HTTPS repository required')
    for i,target in enumerate(value['target']):
        repo_url(target['repository'],f'target.{i}.repository'); revision(target['revision'],f'target.{i}.revision')
        if not target['include']: invalid(f'target.{i}.include','at least one scope pattern required')
        for pattern in (*target['include'],*target['exclude']):
            p=PurePosixPath(pattern)
            if p.is_absolute() or '..' in p.parts or '\\' in pattern: invalid(f'target.{i}.scope','relative POSIX patterns required')
    detection=value['detection']; repo_url(detection['corpus_repository'],'detection.corpus_repository')
    revision(detection['corpus_revision'],'detection.corpus_revision')
    fleet=value['fleet']
    for greater,less in (('stale_seconds','heartbeat_seconds'),('hard_session_seconds','soft_session_seconds')):
        if fleet[greater]<=fleet[less]: invalid('fleet.'+greater,'must exceed '+less)
    if fleet['backoff_max_seconds']<fleet['backoff_initial_seconds']: invalid('fleet.backoff_max_seconds','must be at least backoff_initial_seconds')
    if fleet['monitor_seconds']>=fleet['stale_seconds']: invalid('fleet.monitor_seconds','must be below stale_seconds')
    sandbox=value['sandbox']; networks=[]
    if not local_storage and ('REPLACE_' in sandbox['storage_class'] or sandbox['storage_class']=='local-storage'):
        invalid('sandbox.storage_class','explicit CSI RWOP class required')
    for i,entry in enumerate(sandbox['external_allowlist']):
        try:
            network=ipaddress.ip_network(entry['cidr'],strict=True)
            if network.prefixlen==0 or network.is_loopback or network.is_link_local or network.is_multicast:
                raise ValueError()
            networks.append((network,entry['ports']))
        except ValueError: invalid(f'sandbox.external_allowlist.{i}.cidr','bounded valid network required')
    readonly=set(sandbox['read_only_paths']); writable=set(sandbox['writable_paths'])
    if readonly!={'/target','/config','/prompts','/policy'} or writable!={'/scratch','/artifacts'}:
        invalid('sandbox.paths','use the fixed read-only and scratch/artifact mount boundaries')
    integrations=value['integrations']; ollama=integrations['ollama']; url=urlparse(ollama['base_url'])
    try:
        address=ipaddress.ip_address(url.hostname)
        if url.scheme!='http' or not address.is_private or address.is_loopback or address.is_link_local or url.username or url.password or url.query or url.fragment:
            raise ValueError()
        documentation=[ipaddress.ip_network(n) for n in ('192.0.2.0/24','198.51.100.0/24','203.0.113.0/24')]
        if any(address.version==n.version and address in n for n in documentation): raise ValueError()
        port=url.port or 80
        if not any(address.version==n.version and address in n and any(p['port']==port and p['protocol']=='TCP' for p in ports) for n,ports in networks):
            invalid('integrations.ollama.base_url','IP and TCP port must match the approved allowlist')
    except ValueError: invalid('integrations.ollama.base_url','explicit private Ollama IP/HTTP endpoint required')
    if ollama['model']!='qwen3-coder:30b': invalid('integrations.ollama.model','use operator-selected qwen3-coder:30b')
    github=integrations['github']
    if not github['source_token_ref'].startswith('k8s-secret:') or 'REPLACE_' in github['source_token_ref']:
        invalid('integrations.github.source_token_ref','Kubernetes Secret reference required')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',github['report_repository']) or 'REPLACE_' in github['report_repository']:
        invalid('integrations.github.report_repository','explicit owner/repository required')
    auth=integrations['operator_auth']
    if not (auth['allowed_subjects'] or auth['allowed_groups']) or any('REPLACE_' in s for s in (*auth['allowed_subjects'],*auth['allowed_groups'])):
        invalid('integrations.operator_auth','explicit authorized subjects/groups required')
    if not private_http and (auth['ingress_host'].endswith('.invalid') or 'REPLACE_' in auth['tls_secret_ref']):
        invalid('integrations.operator_auth','configured ingress and TLS Secret required')
    def numbers(node,path='configuration'):
        if isinstance(node,dict):
            for k,v in node.items(): numbers(v,path+'.'+k)
        elif isinstance(node,list):
            for i,v in enumerate(node): numbers(v,path+'.'+str(i))
        elif type(node) is float and not math.isfinite(node): invalid(path,'finite number required')
    numbers(value)
    if errors: raise ConfigurationError(errors)
    return copy.deepcopy(value)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['validate']); parser.add_argument('--file',required=True)
    parser.add_argument('--private-http',action='store_true'); parser.add_argument('--local-storage',action='store_true')
    args=parser.parse_args()
    with open(args.file,encoding='utf-8') as stream: document=yaml.safe_load(stream)
    try: validate(document,private_http=args.private_http,local_storage=args.local_storage)
    except ConfigurationError as error: parser.exit(2,str(error)+'\n')
    print('Configuration shape and semantics valid; live capabilities still require preflight')


if __name__=='__main__': main()
