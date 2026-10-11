"""Consistent safe errors and bounded mutation identifiers."""
import sqlite3

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from foundry_v2.contracts.models import DomainError, new_id


def configure(app):
    @app.middleware('http')
    async def request_identity(request, call_next):
        request.state.request_id = new_id()
        response = await call_next(request)
        response.headers['X-Request-ID'] = request.state.request_id
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return JSONResponse(error.response(request.state.request_id), status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # Pydantic input errors can echo tokens or target-controlled strings.
        return JSONResponse({'code': 'invalid_request', 'message': 'Request does not match the API schema',
                             'request_id': request.state.request_id}, status_code=422)

    @app.exception_handler(sqlite3.IntegrityError)
    async def constraint_error(request, error):
        return JSONResponse({'code': 'constraint_conflict', 'message': 'Resource identity or state conflicts',
                             'request_id': request.state.request_id}, status_code=409)


def idempotency(request: Request):
    key = request.headers.get('idempotency-key')
    if not key or len(key) > 200 or not key.isascii() or any(ord(c) < 33 for c in key):
        raise DomainError('idempotency_key_required', 'Supply an ASCII Idempotency-Key of at most 200 characters')
    return key
