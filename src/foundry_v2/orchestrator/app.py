"""Operator HTTP lane, isolated from database files and worker execution."""
from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from foundry_v2.api.auth import bearer
from foundry_v2.api.common import configure, idempotency
from foundry_v2.contracts.models import StartEvaluation, Unavailable


def create_app(operator_auth, substrate, require_tls=True):
    app = FastAPI(title='Foundry-v2 Orchestrator', docs_url=None, redoc_url=None)
    configure(app)

    def operator(request):
        token = bearer(request,require_tls)
        return operator_auth.authenticate(token), token

    @app.get('/healthz')
    def health():
        return {'status': 'alive'}

    @app.get('/readyz')
    def ready():
        if not substrate.ready():
            raise Unavailable('substrate_unavailable')
        return {'status': 'ready'}

    @app.get('/', response_class=HTMLResponse)
    def dashboard():
        response = HTMLResponse(files('foundry_v2').joinpath('templates/dashboard.html').read_text(encoding='utf-8'))
        response.headers['Content-Security-Policy'] = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'"
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @app.get('/static/dashboard.js')
    def script():
        from fastapi.responses import Response
        return Response(files('foundry_v2').joinpath('static/dashboard.js').read_text(encoding='utf-8'), media_type='application/javascript')

    @app.get('/v1/installation')
    def installation(request: Request):
        _, token = operator(request)
        state = substrate.get('/substrate/v1/installation', token)
        return dict(state, evaluation_start_enabled=False,
                    blockers=['Worker lifecycle, budget safeguards and sandbox preflight are incomplete'])

    @app.get('/v1/evaluations/{evaluation_id}/status', operation_id='getStatus')
    def status(evaluation_id: str, request: Request):
        _, token = operator(request)
        from urllib.parse import quote
        return substrate.get('/substrate/v1/evaluations/' + quote(evaluation_id, safe='') + '/snapshot', token)

    @app.post('/v1/evaluations', operation_id='startEvaluation')
    def start(payload: StartEvaluation, request: Request):
        operator(request)
        idempotency(request)
        raise Unavailable('evaluation_runtime_incomplete',
                          'Evaluation start is disabled until lifecycle, budget, sandbox and integration gates pass')

    return app
