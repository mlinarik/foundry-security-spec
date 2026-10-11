"""Local package information; operational commands arrive with their stories."""
import argparse
import json
from pathlib import Path
import httpx
import yaml
from urllib.parse import urlparse,quote
from foundry_v2 import __version__
from foundry_v2.roles.registry import Role


def main():
    parser = argparse.ArgumentParser(prog="foundry-v2")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("roles", help="List the eight core role identities")
    for name in ('up','preflight','status','stop','drain'):
        command=commands.add_parser(name)
        command.add_argument('--url',required=True)
        command.add_argument('--token-file',required=True)
        command.add_argument('--ca-file')
        command.add_argument('--private-http',action='store_true')
        if name in ('up','preflight'): command.add_argument('--config',required=True)
        else: command.add_argument('--evaluation')
    args = parser.parse_args()
    if args.command == "roles":
        print("\n".join(Role))
        return
    endpoint=urlparse(args.url)
    if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or (endpoint.scheme!='https' and not (args.private_http and endpoint.scheme=='http')):
        parser.error('Use a credential-free HTTPS URL or explicit --private-http override')
    token=Path(args.token_file).read_text().strip()
    with httpx.Client(base_url=args.url.rstrip('/'),verify=args.ca_file or True,timeout=30,trust_env=False,
                      headers={'Authorization':'Bearer '+token}) as client:
        def call(method,path,payload=None):
            from foundry_v2.contracts.models import new_id
            response=client.request(method,path,json=payload,headers={'Idempotency-Key':new_id()} if method!='GET' else {})
            if response.is_error:
                parser.exit(1,'Foundry API request failed: '+str(response.status_code)+'\n')
            return response.json()
        if args.command in ('up','preflight'):
            with open(args.config,encoding='utf-8') as stream: configuration=yaml.safe_load(stream)
            if args.command=='preflight': result=call('POST','/v1/preflight',{'configuration':configuration})
            else:
                installation=call('GET','/v1/installation')
                result=call('POST','/v1/evaluations',{'configuration':configuration,'expected_installation_version':installation['version']})
        else:
            evaluation=args.evaluation or call('GET','/v1/installation')['active_evaluation_id']
            if not evaluation: parser.exit(1,'No active evaluation\n')
            path='/v1/evaluations/'+quote(evaluation,safe='')
            result=call('GET',path+'/status')
            if args.command!='status':
                # Snapshot version is supplied by a separate aggregate read until the
                # status schema carries it; the operator control API rejects stale CAS.
                metadata=call('GET',path)
                result=call('POST',path+'/control',{'action':args.command,'reason':'operator CLI '+args.command,'expected_version':metadata['version']})
        print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
