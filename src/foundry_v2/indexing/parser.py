"""Deterministic Python/Go inventory, conservative direct/alias call resolution."""
from collections import Counter
import hashlib
from bisect import bisect_right
from uuid import uuid5,NAMESPACE_URL

from tree_sitter import Language,Parser
import tree_sitter_go
import tree_sitter_python


def parse_files(target,files):
    units=[]; calls=[]; bodies={}; skipped=[]; inventory=[]; imports={}; packages={}
    for path,source in sorted(files.items()):
        language='python' if path.endswith('.py') else 'go' if path.endswith('.go') else None
        if language is None: continue
        grammar=tree_sitter_python if language=='python' else tree_sitter_go
        file_hash=hashlib.sha256(source).hexdigest(); bodies[file_hash]=source
        inventory.append({'path':path,'file_hash':file_hash,'digest':file_hash,'language':language})
        parser_language=Language(grammar.language())
        parser=Parser(parser_language)
        tree=parser.parse(source)
        if tree.root_node.has_error:
            skipped.append({'path':path,'reason':'deterministic_parse_error'}); continue
        try: source.decode('utf-8')
        except UnicodeError:
            skipped.append({'path':path,'reason':'unsupported_source_encoding'}); continue
        counts=Counter()
        line_offsets=[0]+[i+1 for i,byte in enumerate(source) if byte==10]
        def text(node):
            if node is None: return ''
            return source[node.start_byte:node.end_byte].decode('utf-8')
        imports[path]={}
        packages[path]=next((text(n.named_children[0]) for n in tree.root_node.named_children if n.type=='package_clause' and n.named_children),'')
        if language=='python':
            for statement in tree.root_node.named_children:
                if statement.type=='import_statement':
                    for item in statement.named_children:
                        module=text(item.child_by_field_name('name')) if item.type=='aliased_import' else text(item)
                        alias=text(item.child_by_field_name('alias')) if item.type=='aliased_import' else module.split('.')[0]
                        imports[path][alias]=('module',module if item.type=='aliased_import' else module.split('.')[0])
                elif statement.type=='import_from_statement':
                    module_node=statement.child_by_field_name('module_name'); module=text(module_node)
                    if module.startswith('.'):
                        level=len(module)-len(module.lstrip('.')); parent=path.split('/')[:-1]
                        module='.'.join(parent[:max(0,len(parent)-level+1)]+[module.lstrip('.')]).strip('.')
                    for item in statement.named_children:
                        if item==module_node: continue
                        name=text(item.child_by_field_name('name')) if item.type=='aliased_import' else text(item)
                        alias=text(item.child_by_field_name('alias')) if item.type=='aliased_import' else name
                        if name.isidentifier(): imports[path][alias]=('symbol',module+'.'+name)
        def walk(node,scope=(),caller=None,aliases=None):
            aliases={} if aliases is None else aliases
            if node.type in ('if_statement','for_statement','while_statement','switch_statement'):
                aliases=dict(aliases)
            if node.type in ('function_definition','function_declaration','method_declaration'):
                name=text(node.child_by_field_name('name'))
                receiver_alias=None
                if node.type=='method_declaration':
                    receiver=node.child_by_field_name('receiver')
                    parameter=receiver.named_children[0] if receiver and receiver.named_children else None
                    receiver_type=text(parameter.child_by_field_name('type')).lstrip('*') if parameter else ''
                    receiver_name=text(parameter.child_by_field_name('name')) if parameter else ''
                    scope=(*scope,receiver_type)
                    receiver_alias=(receiver_name,receiver_type)
                qualified='.'.join((*scope,name)); counts[qualified]+=1
                symbol=qualified+(f'@definition:{counts[qualified]}' if counts[qualified]>1 else '')
                identity=str(uuid5(NAMESPACE_URL,target+':'+path+':'+symbol))
                body=source[node.start_byte:node.end_byte]; digest=hashlib.sha256(body).hexdigest(); bodies[digest]=body
                units.append({'unit_id':identity,'path':path,'symbol':symbol,'language':language,
                              'ranges':{'start_line':bisect_right(line_offsets,node.start_byte),'end_line':bisect_right(line_offsets,max(node.start_byte,node.end_byte-1))},
                              'body_digest':digest,'file_hash':file_hash})
                scope=(*scope,name); caller=identity; aliases={}
                if receiver_alias: aliases[receiver_alias[0]]=receiver_alias[1]
            elif node.type=='class_definition':
                scope=(*scope,text(node.child_by_field_name('name')))
            if node.type in ('assignment','short_var_declaration'):
                left=node.child_by_field_name('left'); right=node.child_by_field_name('right')
                if left and right and text(left).isidentifier() and text(right).isidentifier(): aliases[text(left)]=text(right)
            if caller and node.type in ('call','call_expression'):
                function=text(node.child_by_field_name('function'))
                calls.append((caller,path,scope,function,dict(aliases)))
            for child in node.named_children:
                if child.type in ('assignment','short_var_declaration'):
                    left=child.child_by_field_name('left'); right=child.child_by_field_name('right')
                    if left and right and text(left).isidentifier() and text(right).isidentifier(): aliases[text(left)]=text(right)
                walk(child,scope,caller,aliases)
        walk(tree.root_node)
    edges=[]
    for caller,path,scope,function,aliases in calls:
        name=aliases.get(function,function)
        if '.' in name and name.split('.',1)[0] in aliases:
            name=aliases[name.split('.',1)[0]]+'.'+name.split('.',1)[1]
        kind='resolved_indirect' if name!=function else 'static'
        candidates=[]
        for depth in range(len(scope),-1,-1):
            wanted='.'.join((*scope[:depth],name))
            candidates=[u for u in units if u['path']==path and u['symbol'].split('@definition:')[0]==wanted]
            if candidates: break
        if not candidates and name.startswith(('self.','cls.')):
            wanted='.'.join((*scope[:-1],name.split('.',1)[1])); candidates=[u for u in units if u['path']==path and u['symbol']==wanted]
        if not candidates and name.split('.',1)[0] in imports[path]:
            imported_kind,module=imports[path][name.split('.',1)[0]]
            qualified=module+('.'+name.split('.',1)[1] if imported_kind=='module' and '.' in name else '')
            if '.' in qualified:
                module_name,symbol=qualified.rsplit('.',1); suffix=module_name.replace('.','/')
                candidates=[u for u in units if u['language']=='python' and u['symbol']==symbol and
                            any(u['path']==p or u['path'].endswith('/'+p) for p in (suffix+'.py',suffix+'/__init__.py'))]
        if len(candidates)!=1:
            candidates=[u for u in units if u['language']=='go' and u['symbol']==name and packages[u['path']]==packages[path] and '/'.join(u['path'].split('/')[:-1])=='/'.join(path.split('/')[:-1])]
        callee=candidates[0]['unit_id'] if len(candidates)==1 else None
        edge={'caller_id':caller,'callee_id':callee,'unresolved_name':None if callee else function,'kind':kind if callee else 'unresolved'}
        if edge not in edges: edges.append(edge)
    return {'units':units,'edges':edges,'bodies':bodies,'files':inventory,'skipped':skipped,'parsed_files':len(files)-len(skipped)}
