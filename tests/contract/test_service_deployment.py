import importlib.util
from pathlib import Path

import pytest


def renderer():
    path=Path(__file__).resolve().parents[2]/'deploy/services/render.py'
    spec=importlib.util.spec_from_file_location('service_render',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configuration():
    return {'namespace':'foundry-v2','storage_class':'fixture-csi-block','storage_size':'10Gi',
            'operator_subjects':['fixture-operator'],'operator_groups':[],
            'kubernetes_api_url':'https://kubernetes.default.svc:443',
            'tokenreview_audience':'foundry-v2','tls_secret':'foundry-service-tls',
            'storage_mode':'csi-rwop','transport':'https','local_node':None,'local_path':None,
            'infrastructure_secret':'foundry-infrastructure','registry_secret':'harbor-pull-secret',
            'stale_seconds':60,'release_limit':3,'reaper_seconds':5}


def test_services_have_one_owner_and_no_worker_or_public_ingress():
    objects=renderer().render('harbor.mlinarik.com/mlinarik/foundry-v2@sha256:'+'a'*64,configuration())
    workloads=[item for item in objects if item['kind']=='Deployment']
    assert len(workloads)==2
    substrate=next(item for item in workloads if item['metadata']['name']=='substrate')
    assert substrate['spec']['replicas']==1
    assert substrate['spec']['strategy']['type']=='Recreate'
    pvc=next(item for item in objects if item['kind']=='PersistentVolumeClaim')
    assert pvc['spec']['accessModes']==['ReadWriteOncePod']
    for workload in workloads:
        pod=workload['spec']['template']['spec']
        assert pod['automountServiceAccountToken'] is False
        for container in pod['containers']:
            assert container['securityContext']['readOnlyRootFilesystem'] is True
            assert container['securityContext']['allowPrivilegeEscalation'] is False
            assert container['securityContext']['capabilities']['drop']==['ALL']
        has_database=any('persistentVolumeClaim' in volume for volume in pod['volumes'])
        assert has_database==(workload['metadata']['name']=='substrate')
    assert not any(item['kind'] in ('Ingress','Job') for item in objects)
    role=next(item for item in objects if item['kind']=='ClusterRole')
    assert role['rules']==[{'apiGroups':['authentication.k8s.io'],'resources':['tokenreviews'],'verbs':['create']}]


def test_renderer_rejects_storage_fallback_and_guessed_identity():
    module=renderer(); image='harbor.mlinarik.com/mlinarik/foundry-v2@sha256:'+'a'*64
    for changes in ({'storage_class':'local-storage'},{'operator_subjects':[], 'operator_groups':[]}, {'namespace':'../other'}):
        with pytest.raises(ValueError):
            module.render(image,dict(configuration(),**changes))


def test_explicit_operator_override_uses_local_volume_and_private_http():
    config=dict(configuration(),storage_mode='local-rwo',storage_class='local-storage',
                local_node='fixture-node',local_path='/data/foundry-v2',transport='http',tls_secret=None)
    objects=renderer().render('harbor.mlinarik.com/mlinarik/foundry-v2@sha256:'+'a'*64,config)
    pvc=next(item for item in objects if item['kind']=='PersistentVolumeClaim')
    assert pvc['spec']['accessModes']==['ReadWriteOnce']
    pv=next(item for item in objects if item['kind']=='PersistentVolume')
    assert pv['spec']['persistentVolumeReclaimPolicy']=='Retain'
    assert pv['spec']['local']['path']=='/data/foundry-v2'
    assert pv['spec']['claimRef']['namespace']=='foundry-v2'
    for item in objects:
        if item['kind']=='Deployment':
            container=item['spec']['template']['spec']['containers'][0]
            assert container['readinessProbe']['httpGet']['scheme']=='HTTP'
            assert not any(v['name']=='tls' for v in item['spec']['template']['spec']['volumes'])
