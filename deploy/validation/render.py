"""Render an isolated, ephemeral foundation validation Job, not the application.

No credentials are included. Supply the immutable Harbor image reference after
build/push; namespace-scoped registry credentials must already exist separately.
"""
import argparse
from pathlib import Path
import re
import sys

import yaml


def render(image, revision, namespace='foundry-v2-validation'):
    if not re.fullmatch(r'harbor\.mlinarik\.com/mlinarik/foundry-v2@sha256:[0-9a-f]{64}',image):
        raise ValueError('Use the immutable pushed Harbor manifest digest')
    if not re.fullmatch(r'[0-9a-f]{7,40}',revision):
        raise ValueError('Use a Git source revision')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',namespace):
        raise ValueError('Invalid namespace name')
    root = Path(__file__).resolve().parents[2]
    files = [root/'tests/conftest.py',root/'pyproject.toml',root/'specs/001-foundry/contracts/openapi.json']
    for directory in ('unit','contract','integration'):
        files.extend(sorted((root/'tests'/directory).glob('test_*.py')))
    data = {f'file-{index}':file.read_text(encoding='utf-8') for index,file in enumerate(files)}
    items = [{'key':f'file-{index}','path':file.relative_to(root).as_posix()} for index,file in enumerate(files)]
    config_name = 'foundation-tests-'+revision[:12]
    labels = {'app.kubernetes.io/name':'foundry-v2','foundry-v2-stage':'validation'}
    objects = [
        {'apiVersion':'v1','kind':'Namespace','metadata':{'name':namespace,'labels':dict(labels,**{
            'pod-security.kubernetes.io/enforce':'restricted','pod-security.kubernetes.io/enforce-version':'v1.30'})}},
        {'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy',
         'metadata':{'name':'deny-all','namespace':namespace},'spec':{'podSelector':{},'policyTypes':['Ingress','Egress']}},
        {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':config_name,'namespace':namespace,'labels':labels},
         'immutable':True,'data':data},
        {'apiVersion':'batch/v1','kind':'Job','metadata':{'name':'foundry-v2-foundation-'+revision[:12],
            'namespace':namespace,'labels':labels,'annotations':{'foundry-v2/source-revision':revision}},
         'spec':{'backoffLimit':0,'activeDeadlineSeconds':300,
          'template':{'metadata':{'labels':labels},'spec':{
            'restartPolicy':'Never','automountServiceAccountToken':False,
            'imagePullSecrets':[{'name':'harbor-pull-secret'}],
            'securityContext':{'runAsNonRoot':True,'runAsUser':10001,'runAsGroup':10001,
                'fsGroup':10001,'seccompProfile':{'type':'RuntimeDefault'}},
            'containers':[{'name':'foundation-validation','image':image,'imagePullPolicy':'Always',
                'command':['python','-m','pytest'],
                'args':['/validation/tests/unit','/validation/tests/contract','/validation/tests/integration',
                        '-q','-p','no:cacheprovider','--basetemp=/scratch/pytest'],
                'workingDir':'/validation',
                'env':[{'name':'TMPDIR','value':'/scratch'},{'name':'HOME','value':'/scratch'},
                       {'name':'PYTHONDONTWRITEBYTECODE','value':'1'}],
                'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,
                                   'capabilities':{'drop':['ALL']}},
                'resources':{'requests':{'cpu':'250m','memory':'256Mi'},'limits':{'cpu':'2','memory':'1Gi'}},
                'volumeMounts':[{'name':'validation','mountPath':'/validation','readOnly':True},
                                {'name':'scratch','mountPath':'/scratch'}]}],
            'volumes':[{'name':'validation','configMap':{'name':config_name,'items':items,'defaultMode':0o444}},
                       {'name':'scratch','emptyDir':{'sizeLimit':'512Mi'}}]}}}}]
    return objects


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--namespace',default='foundry-v2-validation')
    args = parser.parse_args()
    yaml.safe_dump_all(render(args.image,args.revision,args.namespace),sys.stdout,sort_keys=False)
