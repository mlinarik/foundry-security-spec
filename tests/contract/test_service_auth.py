import pytest

from foundry_v2.api.auth import OperatorAuth, Principal
from foundry_v2.contracts.models import DomainError
from foundry_v2.substrate.auth import SessionAuth
from foundry_v2.substrate.owner import Owner


def test_tokenreview_requires_audience_and_operator_allowlist():
    def reviewer(token):
        return {'authenticated': True, 'audiences': ['foundry-v2'],
                'user': {'username': token, 'groups': ['readers']}}
    auth = OperatorAuth(reviewer, subjects=['alice'], groups=[], audience='foundry-v2')
    assert auth.authenticate('alice').subject == 'alice'
    with pytest.raises(DomainError) as failure:
        auth.authenticate('bob')
    assert failure.value.status == 403
    missing = OperatorAuth(lambda _: {'authenticated': True, 'user': {'username': 'alice'}},
                           subjects=['alice'], groups=[], audience='foundry-v2')
    with pytest.raises(DomainError):
        missing.authenticate('alice')


def test_worker_credentials_are_hashed_scoped_expiring_and_revocable(tmp_path):
    with Owner(tmp_path) as owner:
        evaluation = owner.reserve_evaluation(0)
        with owner.transaction() as db:
            db.execute('INSERT INTO sessions(session_id,evaluation_id,role,slot,incarnation,pod_name,state,heartbeat_at) VALUES(?,?,?,?,?,?,?,?)',
                       ('s1', evaluation, 'detector', 0, 0, 'worker', 'running', 100))
        auth = SessionAuth(owner, clock=lambda: 100)
        auth.issue(evaluation, 's1', 'detector', 'x' * 48, 200)
        principal = auth.authenticate('x' * 48, evaluation)
        assert principal.role == 'detector' and principal.session_id == 's1'
        with owner.transaction() as db:
            assert 'x' * 48 not in str([dict(r) for r in db.execute('SELECT * FROM credentials')])
        with pytest.raises(DomainError):
            auth.authenticate('x' * 48, 'another-evaluation')
        auth.revoke_session('s1')
        with pytest.raises(DomainError):
            auth.authenticate('x' * 48, evaluation)


def test_expired_credentials_and_wrong_session_roles_fail_closed(tmp_path):
    now=[100]
    with Owner(tmp_path) as owner:
        evaluation=owner.reserve_evaluation(0)
        with owner.transaction() as db:
            db.execute('INSERT INTO sessions(session_id,evaluation_id,role,slot,incarnation,pod_name,state,heartbeat_at) VALUES(?,?,?,?,?,?,?,?)',
                       ('s',evaluation,'indexer',0,0,'p','registered',100))
        auth=SessionAuth(owner,clock=lambda:now[0])
        with pytest.raises(DomainError):
            auth.issue(evaluation,'s','reporter','x'*48,200)
        auth.issue(evaluation,'s','indexer','x'*48,200)
        now[0]=200
        with pytest.raises(DomainError):
            auth.authenticate('x'*48,evaluation)


def test_infrastructure_identity_never_becomes_operator():
    assert Principal('controller', 'infrastructure').kind != 'operator'
