"""Commit-pinned source acquisition; source is data, never executable configuration."""
import fnmatch
from pathlib import Path,PurePosixPath
import re
import subprocess
from urllib.parse import urlparse
import base64
import hashlib
import httpx


def pattern_match(path,pattern):
    return fnmatch.fnmatchcase(path,pattern) or (pattern.startswith('**/') and fnmatch.fnmatchcase(path,pattern[3:]))


def in_scope(path,include,exclude):
    p=PurePosixPath(path)
    if p.is_absolute() or '..' in p.parts or '\\' in path or '.git' in p.parts: return False
    return any(pattern_match(path,pattern) for pattern in include) and not any(pattern_match(path,pattern) for pattern in exclude)


def discover(root,include,exclude):
    root=Path(root).resolve(); files={}; skipped=[]
    for path in sorted(root.rglob('*')):
        name=path.relative_to(root).as_posix()
        if not in_scope(name,include,exclude) or path.suffix not in ('.py','.go'): continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            skipped.append({'path':name,'reason':'source_symlink_excluded'}); continue
        if path.is_file():
            if path.stat().st_size>64*1024*1024:
                skipped.append({'path':name,'reason':'source_file_size_excluded'}); continue
            files[name]=path.read_bytes()
    return files,skipped


def acquire(repository,revision,destination,include=('**',),exclude=(),client=None,token=None,api_version='2026-03-10'):
    url=urlparse(repository)
    if url.scheme!='https' or url.hostname!='github.com' or url.username or url.password:
        raise ValueError('Credential-free HTTPS GitHub source URL required')
    if not re.fullmatch('[0-9a-f]{40}',revision) or revision=='0'*40:
        raise ValueError('Full non-placeholder source commit required')
    destination=Path(destination).resolve()
    if destination.exists(): raise ValueError('Source staging destination must be new')
    parts=url.path.strip('/').removesuffix('.git').split('/')
    if len(parts)!=2 or not all(re.fullmatch('[A-Za-z0-9_.-]+',p) for p in parts): raise ValueError('Owner/repository source URL required')
    owned=client is None
    if owned: client=httpx.Client(timeout=30,trust_env=False,follow_redirects=False)
    headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':api_version}
    if token: headers['Authorization']='Bearer '+token
    root='https://api.github.com/repos/'+'/'.join(parts)
    def get(path):
        response=client.get(root+path,headers=headers); response.raise_for_status(); return response.json()
    try:
        commit=get('/git/commits/'+revision)
        if commit.get('sha')!=revision: raise ValueError('Source commit mismatch')
        tree=get('/git/trees/'+commit['tree']['sha']+'?recursive=1')
        if tree.get('truncated'): raise ValueError('Complete source tree unavailable; truncated inventory cannot pass')
        destination.mkdir(parents=True,mode=0o700)
        for entry in tree['tree']:
            path=entry['path']
            if entry['type']!='blob' or entry.get('mode')=='120000' or not in_scope(path,include,exclude): continue
            if entry.get('size',0)>64*1024*1024: raise ValueError('Source blob exceeds acquisition limit')
            blob=get('/git/blobs/'+entry['sha'])
            if blob.get('encoding')!='base64': raise ValueError('Unsupported GitHub blob encoding')
            data=base64.b64decode(blob['content'].replace('\n',''),validate=True)
            if len(data)>64*1024*1024 or hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=entry['sha']:
                raise ValueError('Source blob integrity mismatch')
            output=destination/path; output.parent.mkdir(parents=True,exist_ok=True)
            output.write_bytes(data)
        return destination
    finally:
        if owned: client.close()
