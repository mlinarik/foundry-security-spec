"""Atomic mutation receipts and opaque stable-order list cursors."""
import base64
import hashlib
import json

from foundry_v2.contracts.models import Conflict


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def mutate(owner, actor, method, path, key, payload, effect, status=200):
    if not key or not actor or method not in ('POST','PUT','PATCH','DELETE'):
        raise ValueError('Actor, mutation method and idempotency key are required')
    digest = hashlib.sha256(canonical(payload).encode()).hexdigest()
    with owner.transaction() as db:
        previous = db.execute('SELECT request_digest,response_json FROM idempotency_keys WHERE actor_id=? AND method=? AND path=? AND key=?',
                              (actor,method,path,key)).fetchone()
        if previous:
            if previous['request_digest']!=digest:
                raise Conflict('idempotency_payload_changed')
            return json.loads(previous['response_json'])
        result = effect(db)
        response = canonical(result)
        db.execute('INSERT INTO idempotency_keys VALUES(?,?,?,?,?,?,?)',(actor,method,path,key,digest,response,status))
        return json.loads(response)


def assert_version(actual, expected):
    if actual != expected:
        raise Conflict('stale_version')


def encode_cursor(resource_id):
    return base64.urlsafe_b64encode(canonical({'after':resource_id}).encode()).decode()


def decode_cursor(value):
    try:
        decoded = json.loads(base64.b64decode(value,altchars=b'-_',validate=True))
        if set(decoded) != {'after'} or not isinstance(decoded['after'],str) or not decoded['after']:
            raise ValueError()
        return decoded['after']
    except (ValueError,TypeError,UnicodeError):
        raise ValueError('Invalid list cursor') from None
