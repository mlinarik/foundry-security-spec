"""Render foundation services with explicit storage/transport choices.

Evaluation workers and public ingress are deliberately not installed at this stage.
Operator inputs contain Secret names only, never Secret values.
"""
import argparse
import json
import re
import sys

import yaml


def dns(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',value):
        raise ValueError('Use a DNS label for names')
    return value


def render(image, config):
    if not re.fullmatch(r'harbor\.mlinarik\.com/mlinarik/foundry-v2@sha256:[0-9a-f]{64}',image):
        raise ValueError('Immutable Harbor image required')
    required={'namespace','storage_class','storage_size','operator_subjects','operator_groups',
              'kubernetes_api_url','tokenreview_audience','tls_secret','infrastructure_secret',
              'registry_secret','stale_seconds','release_limit','reaper_seconds',
              'storage_mode','transport','local_node','local_path'}
    if set(config)-{'orchestrator_service_type'}!=required:
        raise ValueError('Supply exactly the documented deployment inputs')
    service_type=config.get('orchestrator_service_type','ClusterIP')
    if service_type not in ('ClusterIP','LoadBalancer'):
        raise ValueError('Orchestrator service type must be ClusterIP or LoadBalancer')
    namespace=dns(config['namespace'])
    for key in ('storage_class','infrastructure_secret','registry_secret'):
        dns(config[key])
    if config['storage_mode'] not in ('csi-rwop','local-rwo') or config['transport'] not in ('http','https'):
        raise ValueError('Explicit storage and transport modes required')
    if config['transport']=='https':
        dns(config['tls_secret'])
    if config['storage_mode']=='local-rwo':
        dns(config['local_node'])
        if config['local_path']!='/data/foundry-v2' or config['storage_class']!='local-storage':
            raise ValueError('Local override requires the dedicated /data/foundry-v2 path and local-storage class')
    elif config['storage_class']=='local-storage' or 'smb' in config['storage_class'].lower() or 'nfs' in config['storage_class'].lower():
        raise ValueError('CSI block-backed RWOP storage required; no local or network filesystem fallback')
    for key in ('operator_subjects','operator_groups'):
        if not isinstance(config[key],list) or any(not isinstance(v,str) or not v for v in config[key]):
            raise ValueError('Explicit operator identity lists required')
    if not (config['operator_subjects'] or config['operator_groups']):
        raise ValueError('At least one authorized operator subject/group required')
    if not config['kubernetes_api_url'].startswith('https://') or not config['tokenreview_audience']:
        raise ValueError('HTTPS Kubernetes API and TokenReview audience required')
    if not re.fullmatch(r'[1-9][0-9]*(?:Mi|Gi|Ti)',config['storage_size']):
        raise ValueError('Positive explicit storage size required')
    if any(type(config[k]) is not int or config[k]<=0 for k in ('stale_seconds','release_limit','reaper_seconds')) or config['reaper_seconds']>=config['stale_seconds']:
        raise ValueError('Positive runtime bounds with reaper below stale threshold required')
    labels={'app.kubernetes.io/part-of':'foundry-v2'}
    def meta(name):
        return {'name':name,'namespace':namespace,'labels':labels}
    port=8443 if config['transport']=='https' else 8080
    service_config={key:config[key] for key in ('kubernetes_api_url','tokenreview_audience','operator_subjects','operator_groups','stale_seconds','release_limit','reaper_seconds','transport')}
    service_config['substrate_url']=f'{config["transport"]}://substrate.{namespace}.svc:{port}'
    objects=[{'apiVersion':'v1','kind':'Namespace','metadata':{'name':namespace,'labels':dict(labels,**{
        'pod-security.kubernetes.io/enforce':'restricted','pod-security.kubernetes.io/enforce-version':'v1.30'})}},
        {'apiVersion':'v1','kind':'ServiceAccount','metadata':meta('operator'),'automountServiceAccountToken':False},
        {'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':meta('deny-all'),
         'spec':{'podSelector':{},'policyTypes':['Ingress','Egress']}},
        {'apiVersion':'v1','kind':'ConfigMap','metadata':meta('service-config'),
         'data':{'service.json':json.dumps(service_config,indent=2)}},
        {'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':meta('substrate-data'),
         'spec':{'accessModes':['ReadWriteOnce' if config['storage_mode']=='local-rwo' else 'ReadWriteOncePod'],'volumeMode':'Filesystem','storageClassName':config['storage_class'],
                 'resources':{'requests':{'storage':config['storage_size']}}}},
        {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'ClusterRole',
         'metadata':{'name':namespace+'-tokenreview','labels':labels},
         'rules':[{'apiGroups':['authentication.k8s.io'],'resources':['tokenreviews'],'verbs':['create']}]},
        {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'ClusterRoleBinding',
         'metadata':{'name':namespace+'-tokenreview','labels':labels},
         'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':namespace+'-tokenreview'},
         'subjects':[{'kind':'ServiceAccount','name':name,'namespace':namespace} for name in ('orchestrator','substrate')]},
        {'apiVersion':'cilium.io/v2','kind':'CiliumNetworkPolicy','metadata':meta('control-tokenreview'),
         'spec':{'endpointSelector':{'matchLabels':labels},'egress':[{'toEntities':['kube-apiserver'],
                  'toPorts':[{'ports':[{'port':'443','protocol':'TCP'},{'port':'6443','protocol':'TCP'}]}]}]}},
        {'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':meta('control-dns'),
         'spec':{'podSelector':{'matchLabels':labels},'policyTypes':['Egress'],'egress':[{
             'to':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'kube-system'}},
                    'podSelector':{'matchLabels':{'k8s-app':'kube-dns'}}}],
             'ports':[{'port':53,'protocol':'UDP'},{'port':53,'protocol':'TCP'}]}]}},
        {'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':meta('orchestrator-to-substrate'),
         'spec':{'podSelector':{'matchLabels':{'app.kubernetes.io/name':'orchestrator'}},'policyTypes':['Egress'],
                 'egress':[{'to':[{'podSelector':{'matchLabels':{'app.kubernetes.io/name':'substrate'}}}],
                            'ports':[{'port':port,'protocol':'TCP'}]}]}},
        {'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':meta('substrate-from-orchestrator'),
         'spec':{'podSelector':{'matchLabels':{'app.kubernetes.io/name':'substrate'}},'policyTypes':['Ingress'],
                 'ingress':[{'from':[{'podSelector':{'matchLabels':{'app.kubernetes.io/name':'orchestrator'}}}],
                             'ports':[{'port':port,'protocol':'TCP'}]}]}}]
    if config['storage_mode']=='local-rwo':
        pv_name=namespace+'-substrate-local'
        next(item for item in objects if item['kind']=='PersistentVolumeClaim')['spec']['volumeName']=pv_name
        objects.append({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':pv_name,'labels':labels},
                        'spec':{'capacity':{'storage':config['storage_size']},'accessModes':['ReadWriteOnce'],
                                'volumeMode':'Filesystem','storageClassName':config['storage_class'],
                                'persistentVolumeReclaimPolicy':'Retain','local':{'path':config['local_path']},
                                'claimRef':{'namespace':namespace,'name':'substrate-data'},
                                'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{
                                    'key':'kubernetes.io/hostname','operator':'In','values':[config['local_node']]}]}]}}}})
    if service_type=='LoadBalancer':
        objects.append({'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':meta('orchestrator-client-access'),
                        'spec':{'podSelector':{'matchLabels':{'app.kubernetes.io/name':'orchestrator'}},
                                'policyTypes':['Ingress'],'ingress':[{'ports':[{'port':port,'protocol':'TCP'}]}]}})
    for name in ('substrate','orchestrator'):
        pod_labels=dict(labels,**{'app.kubernetes.io/name':name})
        objects.append({'apiVersion':'v1','kind':'ServiceAccount','metadata':meta(name),'automountServiceAccountToken':False})
        objects.append({'apiVersion':'v1','kind':'Service','metadata':meta(name),
                        'spec':{'selector':pod_labels,'ports':[{'name':'web','port':port,'targetPort':'web'}]}})
        if name=='orchestrator' and service_type=='LoadBalancer':
            objects[-1]['spec'].update(type='LoadBalancer',externalTrafficPolicy='Local',allocateLoadBalancerNodePorts=False)
        volumes=[{'name':'config','configMap':{'name':'service-config','defaultMode':0o444}},
                 {'name':'kubernetes-ca','configMap':{'name':'kube-root-ca.crt','defaultMode':0o444}},
                 {'name':'tokenreview','projected':{'defaultMode':0o440,'sources':[{'serviceAccountToken':{'path':'token','expirationSeconds':3600}}]}},
                 {'name':'scratch','emptyDir':{'sizeLimit':'256Mi'}}]
        mounts=[{'name':'config','mountPath':'/etc/foundry','readOnly':True},
                {'name':'kubernetes-ca','mountPath':'/run/kubernetes-ca','readOnly':True},
                {'name':'tokenreview','mountPath':'/run/tokenreview','readOnly':True},
                {'name':'scratch','mountPath':'/scratch'}]
        env={'FOUNDRY_SERVICE_CONFIG':'/etc/foundry/service.json','FOUNDRY_KUBERNETES_CA':'/run/kubernetes-ca/ca.crt',
             'FOUNDRY_TOKENREVIEW_TOKEN_FILE':'/run/tokenreview/token','TMPDIR':'/scratch','HOME':'/scratch'}
        if config['transport']=='https':
            volumes.append({'name':'tls','secret':{'secretName':config['tls_secret'],'defaultMode':0o440}})
            mounts.append({'name':'tls','mountPath':'/run/tls','readOnly':True})
            env.update(FOUNDRY_TLS_CERT_FILE='/run/tls/tls.crt',FOUNDRY_TLS_KEY_FILE='/run/tls/tls.key')
        if name=='substrate':
            volumes.extend([{'name':'data','persistentVolumeClaim':{'claimName':'substrate-data'}},
                            {'name':'infrastructure','secret':{'secretName':config['infrastructure_secret'],'defaultMode':0o440}}])
            mounts.extend([{'name':'data','mountPath':'/data'},{'name':'infrastructure','mountPath':'/run/infrastructure','readOnly':True}])
            env.update(FOUNDRY_DATA_DIR='/data',FOUNDRY_INFRASTRUCTURE_TOKEN_FILE='/run/infrastructure/token')
        elif config['transport']=='https':
            env['FOUNDRY_SUBSTRATE_CA']='/run/tls/ca.crt'
        container={'name':name,'image':image,'imagePullPolicy':'Always','command':['python','-m','foundry_v2.'+name],
                   'ports':[{'name':'web','containerPort':port}], 'env':[{'name':k,'value':v} for k,v in env.items()],
                   'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'1','memory':'512Mi'}},
                   'securityContext':{'readOnlyRootFilesystem':True,'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
                   'volumeMounts':mounts,
                   'startupProbe':{'httpGet':{'path':'/healthz','port':'web','scheme':config['transport'].upper()},'periodSeconds':5,'failureThreshold':24},
                   'livenessProbe':{'httpGet':{'path':'/healthz','port':'web','scheme':config['transport'].upper()},'periodSeconds':10},
                   'readinessProbe':{'httpGet':{'path':'/readyz','port':'web','scheme':config['transport'].upper()},'periodSeconds':5}}
        objects.append({'apiVersion':'apps/v1','kind':'Deployment','metadata':meta(name),'spec':{
            'replicas':1,'strategy':{'type':'Recreate'},'selector':{'matchLabels':pod_labels},
            'template':{'metadata':{'labels':pod_labels},'spec':{'serviceAccountName':name,
                'automountServiceAccountToken':False,'enableServiceLinks':False,
                'securityContext':{'runAsNonRoot':True,'runAsUser':10001,'runAsGroup':10001,'fsGroup':10001,
                                   'fsGroupChangePolicy':'OnRootMismatch','seccompProfile':{'type':'RuntimeDefault'}},
                'imagePullSecrets':[{'name':config['registry_secret']}],'containers':[container],'volumes':volumes}}}})
    return objects


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--config',required=True)
    args=parser.parse_args()
    yaml.safe_dump_all(render(args.image,json.load(open(args.config,encoding='utf-8'))),sys.stdout,sort_keys=False)
