"""Operator HTTP lane, isolated from database files and worker execution."""
from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from foundry_v2.api.auth import bearer
from foundry_v2.api.common import configure, idempotency
from foundry_v2.contracts.models import ConfigUpdate,Control,StartEvaluation, Unavailable
from foundry_v2.api.evaluations import PreflightRequest


def create_app(operator_auth, substrate, require_tls=True,runtime_available=False,preflight=None,local_storage=False):
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
        return dict(state, evaluation_start_enabled=runtime_available,
                    blockers=[] if runtime_available else ['Worker lifecycle, budget safeguards and sandbox preflight are incomplete'])

    @app.get('/v1/evaluations/{evaluation_id}/status', operation_id='getStatus')
    def status(evaluation_id: str, request: Request):
        _, token = operator(request)
        from urllib.parse import quote
        return substrate.get('/substrate/v1/evaluations/' + quote(evaluation_id, safe='') + '/snapshot', token)

    @app.get('/v1/evaluations/{evaluation_id}')
    def metadata(evaluation_id: str,request: Request):
        from urllib.parse import quote
        _,token=operator(request)
        return substrate.get('/substrate/v1/evaluations/'+quote(evaluation_id,safe=''),token)

    @app.post('/v1/preflight')
    async def run_preflight(payload: PreflightRequest,request: Request):
        import asyncio
        from foundry_v2.config import validate,ConfigurationError
        from foundry_v2.contracts.models import DomainError
        await asyncio.to_thread(operator,request)
        try: configuration=validate(payload.configuration,private_http=not require_tls,local_storage=local_storage)
        except ConfigurationError as error: raise DomainError('invalid_configuration',str(error)) from None
        if preflight is None: raise Unavailable('preflight_bindings_unavailable')
        return await preflight.run(configuration)

    @app.post('/v1/evaluations',status_code=202, operation_id='startEvaluation')
    def start(payload: StartEvaluation, request: Request):
        _,token=operator(request)
        key=idempotency(request)
        if not runtime_available:
            raise Unavailable('evaluation_runtime_incomplete',
                              'Evaluation start is disabled until lifecycle, budget, sandbox and integration gates pass')
        return substrate.request('POST','/substrate/v1/evaluations',bearer=token,payload=payload.model_dump(),key=key)

    @app.post('/v1/evaluations/{evaluation_id}/control',operation_id='controlEvaluation')
    def control(evaluation_id: str,payload: Control,request: Request):
        from urllib.parse import quote
        _,token=operator(request)
        return substrate.request('POST',f'/substrate/v1/evaluations/{quote(evaluation_id,safe="")}/control',bearer=token,payload=payload.model_dump(),key=idempotency(request))

    @app.put('/v1/evaluations/{evaluation_id}/configuration',operation_id='updateConfiguration')
    def configuration(evaluation_id: str,payload: ConfigUpdate,request: Request):
        from urllib.parse import quote
        _,token=operator(request)
        return substrate.request('PUT',f'/substrate/v1/evaluations/{quote(evaluation_id,safe="")}/configuration',bearer=token,payload=payload.model_dump(),key=idempotency(request))

    return app
