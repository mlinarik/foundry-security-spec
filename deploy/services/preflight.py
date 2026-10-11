"""Read-only deployment input checks; never create storage or broaden policies."""
import argparse
import base64
import json
import subprocess
import sys
from urllib.parse import urlparse

from render import render


def resource(*args):
    result=subprocess.run(['kubectl','get',*args,'-o','json'],capture_output=True,text=True)
    if result.returncode:
        raise ValueError('Required Kubernetes resource absent: '+' '.join(args))
    return json.loads(result.stdout)


def check(image,config):
    render(image,config)
    version=json.loads(subprocess.run(['kubectl','version','-o','json'],capture_output=True,text=True,check=True).stdout)['serverVersion']
    major=int(version['major']); minor=int(version['minor'].rstrip('+'))
    if (major,minor)<(1,30):
        raise ValueError('Kubernetes >=1.30 required')
    sc=resource('storageclass',config['storage_class'])
    provisioner=sc['provisioner']
    if config['storage_mode']=='local-rwo':
        if provisioner!='kubernetes.io/no-provisioner':
            raise ValueError('Expected the explicitly selected static local class')
        node=resource('node',config['local_node'])
        if not any(c['type']=='Ready' and c['status']=='True' for c in node['status']['conditions']):
            raise ValueError('Selected local-storage node is not Ready')
    else:
        if provisioner=='kubernetes.io/no-provisioner' or any(word in provisioner.lower() for word in ('smb','nfs')):
            raise ValueError('Selected storage is not CSI block-backed storage')
        resource('csidriver',provisioner)
    cilium=resource('daemonset','cilium','-n','kube-system')
    if cilium['status'].get('numberReady')!=cilium['status'].get('desiredNumberScheduled'):
        raise ValueError('Cilium is not ready on all scheduled nodes')
    ns=config['namespace']
    # Secret contents stay in process memory and are never printed.
    if config['transport']=='https':
        tls=resource('secret',config['tls_secret'],'-n',ns)
        if not {'tls.crt','tls.key','ca.crt'}<=set(tls.get('data',{})):
            raise ValueError('TLS Secret must contain tls.crt, tls.key and ca.crt')
    infrastructure=resource('secret',config['infrastructure_secret'],'-n',ns)
    try:
        if len(base64.b64decode(infrastructure['data']['token'],validate=True))<32:
            raise ValueError()
    except (KeyError,ValueError):
        raise ValueError('Infrastructure Secret must contain a strong dedicated token') from None
    registry=resource('secret',config['registry_secret'],'-n',ns)
    if registry.get('type')!='kubernetes.io/dockerconfigjson':
        raise ValueError('Harbor pull Secret has the wrong type')
    rootca=resource('configmap','kube-root-ca.crt','-n',ns)
    if not rootca.get('data',{}).get('ca.crt'):
        raise ValueError('Kubernetes trust root missing')
    return {'kubernetes':version['gitVersion'],'storage_class':config['storage_class'],'csi_driver':provisioner,
            'transport':config['transport'],'storage_mode':config['storage_mode'],
            'status':'deployment inputs present; storage/fencing and effective policy probes remain required before evaluation start'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True); parser.add_argument('--config',required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(check(args.image,json.load(open(args.config,encoding='utf-8'))),indent=2))
    except (ValueError,subprocess.CalledProcessError) as error:
        print(str(error),file=sys.stderr); sys.exit(1)
