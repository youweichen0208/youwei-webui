import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from open_webui.utils.hermes import Settings, create_router


CONFIG = Settings('http://hermes:8642', 'isolated-test-key-123456789', 'owner')


def request(method, path, *, user='owner', body=None, handler=None, settings=CONFIG, headers=None):
    calls = []

    def native(req):
        calls.append(req)
        return handler(req) if handler else httpx.Response(200, json={'ok': True})

    async def identity():
        if user is None:
            raise HTTPException(401)
        return SimpleNamespace(id=user)

    app = FastAPI()
    app.include_router(create_router(identity, settings=lambda: settings, transport=httpx.MockTransport(native)))

    async def send():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
            return await client.request(method, path, json=body, headers=headers)

    return asyncio.run(send()), calls


@pytest.mark.parametrize('user,status', [(None, 401), ('stranger', 403)])
def test_owner_gate_precedes_network(user, status):
    response, calls = request('GET', '/sessions', user=user)
    assert response.status_code == status
    assert not calls


def test_disabled_and_nonowner_config_do_not_disclose_connection():
    response, calls = request('GET', '/config', user='stranger')
    assert response.json() == {'enabled': False}
    assert not calls
    response, calls = request('GET', '/sessions', settings=Settings('', '', ''))
    assert response.status_code == 503 and not calls


@pytest.mark.parametrize(
    'path,method',
    [
        ('/anything', 'GET'),
        ('/gateway/restart', 'POST'),
        ('/runs/run_1/approval', 'DELETE'),
        ('/sessions/x/chat', 'POST'),
        ('/skills', 'POST'),
    ],
)
def test_allowlist(path, method):
    response, calls = request(method, path, body={})
    assert response.status_code == 404 and not calls


def test_runs_require_idempotency_and_reject_privilege_overrides():
    body = {'input': 'hello', 'session_id': 'api_test'}
    response, calls = request('POST', '/runs', body=body)
    assert response.status_code == 422 and not calls
    headers = {'Idempotency-Key': 'workbench-test-123456'}
    response, calls = request('POST', '/runs', body={**body, 'provider': 'custom'}, headers=headers)
    assert response.status_code == 422 and not calls
    response, calls = request('POST', '/runs', body=body, headers=headers)
    assert response.status_code == 200
    assert calls[0].url.path == '/v1/runs'
    assert calls[0].headers['authorization'] == f'Bearer {CONFIG.key}'
    assert calls[0].headers['idempotency-key'] == headers['Idempotency-Key']
    assert CONFIG.key not in response.text


@pytest.mark.parametrize('choice', ['always', 'approve', 'arbitrary'])
def test_no_permanent_or_implicit_approval(choice):
    response, calls = request('POST', '/runs/run_1/approval', body={'choice': choice, 'request_id': 'req_1'})
    assert response.status_code == 422 and not calls


def test_approval_exact_request_and_stop():
    response, calls = request('POST', '/runs/run_1/approval', body={'choice': 'once', 'request_id': 'req_1'})
    assert response.status_code == 200
    assert calls[0].url.path == '/v1/runs/run_1/approval'
    response, calls = request('POST', '/runs/run_1/stop', body={})
    assert response.status_code == 200


def test_upstream_errors_and_redirects_never_disclose_secrets():
    for status in [302, 401, 500]:
        response, calls = request(
            'GET',
            '/gateway',
            handler=lambda r: httpx.Response(
                status, json={'error': CONFIG.key}, headers={'Location': 'https://example.com'}
            ),
        )
        assert response.status_code == 502
        assert CONFIG.key not in response.text
        assert len(calls) == 1


def test_sse_is_forwarded_without_buffering_or_reformatting():
    content = b'data: {"event":"message.delta","delta":"hi"}\n\ndata: {"event":"run.completed"}\n\n'
    response, calls = request(
        'GET',
        '/runs/run_1/events',
        handler=lambda r: httpx.Response(200, content=content, headers={'Content-Type': 'text/event-stream'}),
    )
    assert response.content == content
    assert response.headers['x-accel-buffering'] == 'no'
    assert response.headers['cache-control'] == 'no-store'


def test_cron_fields_validated_and_native_scheduler_used():
    response, calls = request(
        'POST', '/jobs', body={'name': 'summary', 'schedule': '0 9 * * 1-5', 'prompt': 'summarize', 'deliver': 'local'}
    )
    assert response.status_code == 200 and calls[0].url.path == '/api/jobs'
    response, calls = request('POST', '/jobs', body={'name': 'bad'})
    assert response.status_code == 422 and not calls


def test_unavailable_upstream_has_actionable_error():
    def failure(req):
        raise httpx.ConnectError('secret-host', request=req)

    response, calls = request('GET', '/gateway', handler=failure)
    assert response.status_code == 502
    assert 'secret-host' not in response.text


def test_skills_use_separate_readonly_service():
    settings = Settings(CONFIG.url, CONFIG.key, CONFIG.owner, 'http://skills:8643')
    response, calls = request('GET', '/skills/sample', settings=settings)
    assert response.status_code == 200
    assert str(calls[0].url) == 'http://skills:8643/skills/sample'
    response, calls = request('GET', '/skills')
    assert response.status_code == 503 and not calls


def test_approval_without_exact_request_is_rejected():
    response, calls = request('POST', '/runs/run_1/approval', body={'choice': 'once'})
    assert response.status_code == 422 and not calls


def test_oversized_prompt_and_unrecognized_query_rejected_before_network():
    response, calls = request('POST', '/sessions', body={'title': 'x' * 140000})
    assert response.status_code == 413 and not calls
    response, calls = request('GET', '/sessions?url=https://example.com')
    assert response.status_code == 422 and not calls
