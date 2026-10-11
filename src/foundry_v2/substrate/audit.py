import time

from foundry_v2.contracts.models import new_id


def event(db, actor, evaluation, action, resource, prior=None, version=None, reason=None, clock=time.time):
    """Append within the aggregate mutation transaction; callers never log credentials."""
    db.execute('INSERT INTO audit_events(event_id,evaluation_id,actor_kind,actor_id,action,resource,prior_version,new_version,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
               (new_id(),evaluation,actor.kind,actor.subject,action,resource,prior,version,reason,clock()))
