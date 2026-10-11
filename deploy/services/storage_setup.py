"""Narrow, one-shot initializer for the operator-selected dedicated local path.

This maintenance pod is separate from application/worker admission, has no API
token and exposes only the new Foundry directory from the selected node.
"""
def render(image,node,namespace='foundry-v2-storage-setup'):
    return [
        {'apiVersion':'v1','kind':'Namespace','metadata':{'name':namespace,'labels':{
            'app.kubernetes.io/part-of':'foundry-v2','pod-security.kubernetes.io/enforce':'privileged'}}},
        {'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':'deny-all','namespace':namespace},
         'spec':{'podSelector':{},'policyTypes':['Ingress','Egress']}},
        {'apiVersion':'batch/v1','kind':'Job','metadata':{'name':'initialize-local-data','namespace':namespace},
         'spec':{'backoffLimit':0,'activeDeadlineSeconds':120,'template':{'spec':{
             'nodeSelector':{'kubernetes.io/hostname':node},'restartPolicy':'Never','automountServiceAccountToken':False,
             'imagePullSecrets':[{'name':'harbor-pull-secret'}],
             'securityContext':{'runAsUser':0,'seccompProfile':{'type':'RuntimeDefault'}},
             'containers':[{'name':'prepare','image':image,'command':['python','-c',
                 "import os; p='/volume'; assert not os.listdir(p), 'Foundry directory must be empty for initial provisioning'; s=os.statvfs(p); assert s.f_bavail*s.f_frsize>=10*1024**3, 'Insufficient local disk'; os.chown(p,10001,10001); os.chmod(p,0o700); f=os.open(p,os.O_RDONLY|os.O_DIRECTORY); os.fsync(f); os.close(f); print('Dedicated local directory initialized; owner 10001; mode 0700; free disk >=10Gi')"],
                 'resources':{'requests':{'cpu':'50m','memory':'32Mi'},'limits':{'cpu':'250m','memory':'128Mi'}},
                 'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,
                                     'capabilities':{'drop':['ALL'],'add':['CHOWN']}},
                 'volumeMounts':[{'name':'data','mountPath':'/volume'}]}],
             'volumes':[{'name':'data','hostPath':{'path':'/data/foundry-v2','type':'DirectoryOrCreate'}}]}}}}
    ]
