from foundry_v2.indexing.parser import parse_files
from foundry_v2.indexing.source import in_scope


def test_python_go_inventory_static_alias_and_unresolved_calls():
    files={'code.py':b'def leaf():\n return 1\ndef caller():\n alias=leaf\n alias()\n missing()\n',
           'code.go':b'package fixture\nfunc Leaf() {}\nfunc Caller() { Leaf(); unknown() }\n'}
    index=parse_files('target',files)
    assert {u['symbol'] for u in index['units']}=={'leaf','caller','Leaf','Caller'}
    kinds={e['kind'] for e in index['edges']}
    assert 'static' in kinds and 'resolved_indirect' in kinds and 'unresolved' in kinds
    assert any(e['unresolved_name']=='missing' for e in index['edges'])
    shifted=parse_files('target',{p:b'\n\n'+body for p,body in files.items()})
    assert {u['unit_id'] for u in index['units']}=={u['unit_id'] for u in shifted['units']}


def test_scope_and_parse_failure_are_visible():
    assert in_scope('top.py',['**/*.py'],[])
    assert in_scope('src/code.py',['**/*.py'],['vendor/**'])
    assert not in_scope('vendor/code.py',['**/*.py'],['vendor/**'])
    assert not in_scope('../escape.py',['**/*.py'],[])
    index=parse_files('target',{'broken.py':b'def broken(:\n','valid.py':b'def ok():\n return 1\n'})
    assert index['skipped'][0]['path']=='broken.py'
    assert {u['symbol'] for u in index['units']}=={'ok'}


def test_receiver_qualified_methods_resolve_conservatively():
    index=parse_files('t',{'methods.py':b'class Server:\n def read(self):\n  return 1\n def handle(self):\n  return self.read()\n',
                           'methods.go':b'package f\ntype Server struct{}\nfunc (s *Server) Read() {}\nfunc (s *Server) Handle() { s.Read() }\n'})
    assert {u['symbol'] for u in index['units']}=={'Server.read','Server.handle','Server.Read','Server.Handle'}
    assert all(edge['callee_id'] for edge in index['edges'])


def test_commit_pinned_github_acquisition_checks_blob_hash_and_scope(tmp_path):
    import base64,hashlib,httpx
    from foundry_v2.indexing.source import acquire
    data=b'def f():\n return 1\n'; digest=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    requested=[]
    def handler(request):
        requested.append(request.url.path)
        if '/commits/' in request.url.path: body={'sha':'a'*40,'tree':{'sha':'b'*40}}
        elif '/trees/' in request.url.path:
            body={'truncated':False,'tree':[{'type':'blob','mode':'100644','path':'source.py','sha':digest},
                                            {'type':'blob','mode':'100644','path':'vendor/outside.py','sha':digest}]}
        else: body={'encoding':'base64','content':base64.b64encode(data).decode()}
        return httpx.Response(200,json=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        root=acquire('https://github.com/fixture/source','a'*40,tmp_path/'source',include=['**/*.py'],exclude=['vendor/**'],client=client)
    assert (root/'source.py').read_bytes()==data and not (root/'vendor').exists()
    assert sum('/blobs/' in path for path in requested)==1


def test_python_import_alias_and_nested_direct_calls_resolve():
    index=parse_files('t',{'pkg/helper.py':b'def leaf():\n return 1\n',
                           'pkg/main.py':b'from .helper import leaf as imported\ndef outer():\n def inner():\n  return imported()\n return inner()\n'})
    assert len(index['edges'])==2
    assert all(edge['callee_id'] for edge in index['edges'])


def test_large_inventory_uses_byte_offsets_without_native_point_access():
    index=parse_files('t',{'large.py':b'def f():\n return 1\n'*1000})
    assert len(index['units'])==1000
    assert index['units'][-1]['ranges']=={'start_line':1999,'end_line':2000}
