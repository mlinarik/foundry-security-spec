"""One owner transaction provides a consistent status projection."""
import json

from foundry_v2.contracts.models import DomainError, Snapshot


class Missing(DomainError):
    status = 404


def require_evaluation(db, evaluation):
    row = db.execute('SELECT * FROM evaluations WHERE evaluation_id=?', (evaluation,)).fetchone()
    if row is None:
        raise Missing('evaluation_not_found')
    return row


def sequence(db):
    return db.execute('SELECT COALESCE(MAX(sequence),0) FROM audit_events').fetchone()[0]


def snapshot(owner, evaluation):
    with owner.transaction() as db:
        row = require_evaluation(db, evaluation)
        agents = [dict(item) for item in db.execute('SELECT session_id,role,slot,incarnation,pod_name,state,heartbeat_at,restart_count,version FROM sessions WHERE evaluation_id=? ORDER BY role,slot,incarnation', (evaluation,))]
        claims = [dict(item) for item in db.execute('SELECT resource_type,resource_id,holder_session_id,generation FROM claims WHERE evaluation_id=? AND holder_session_id IS NOT NULL', (evaluation,))]
        for agent in agents:
            agent['claims'] = [c for c in claims if c['holder_session_id'] == agent['session_id']]
        counts = dict(db.execute('SELECT COALESCE(verdict,\'candidate\'),COUNT(*) FROM finding_observations WHERE evaluation_id=? GROUP BY verdict', (evaluation,)).fetchall())
        coverage = {'revision': row['goals_revision'], 'complete': bool(row['coverage_complete']),
                    'items': dict(db.execute('SELECT state,COUNT(*) FROM coverage_items WHERE evaluation_id=? AND goals_revision=? GROUP BY state', (evaluation,row['goals_revision'])).fetchall())}
        calls = dict(db.execute('SELECT usage_status,COUNT(*) FROM model_calls WHERE evaluation_id=? GROUP BY usage_status', (evaluation,)).fetchall())
        # No inferred zero spend when no ledger or price configuration exists.
        budget = {'usage_status': 'unknown' if not calls or calls.get('unknown') else 'estimated' if calls.get('estimated') else 'known',
                  'call_counts': calls, 'spend': None}
        return Snapshot(snapshot_id=sequence(db), evaluation_id=evaluation, state=row['state'],
                        agents=agents, counts=counts, coverage=coverage, budget=budget,
                        degraded=json.loads(row['degraded_json'])).model_dump()
