"""Owner-only, allowlisted bridge to the pinned Hermes native gateway.

No browser-supplied URL, credential, provider or tool override crosses this seam.
Hermes remains the authority for sessions, runs, approvals and schedules.
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.background import BackgroundTask

MAX_BODY = 128 * 1024
ID = r'[A-Za-z0-9_-]{1,128}'


class Form(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class SessionForm(Form):
    title: str = Field(default='', max_length=200)


class RunForm(Form):
    input: str = Field(min_length=1, max_length=32000)
    session_id: str = Field(pattern=f'^{ID}$')


class ApprovalForm(Form):
    choice: Literal['once', 'session', 'deny']
    request_id: str = Field(min_length=1, max_length=256)


class SteerForm(Form):
    input: str = Field(min_length=1, max_length=32000)


class JobForm(Form):
    name: str = Field(min_length=1, max_length=200)
    schedule: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=32000)
    deliver: str = Field(default='local', min_length=1, max_length=200)


# Exact route/method pairs: never a general-purpose reverse proxy.
ROUTES = [
    ('GET', r'capabilities', '/v1/capabilities', None),
    ('GET', r'gateway', '/health/detailed', None),
    ('GET', r'skills', '/v1/skills', None),
    ('GET', r'skills/([A-Za-z0-9_.:-]{1,200})', '/skills/{0}', None),
    ('GET', r'toolsets', '/v1/toolsets', None),
    ('GET', r'models', '/v1/models', None),
    ('GET', r'sessions', '/api/sessions', None),
    ('POST', r'sessions', '/api/sessions', SessionForm),
    ('GET', rf'sessions/({ID})/messages', '/api/sessions/{0}/messages', None),
    ('GET', rf'sessions/({ID})', '/api/sessions/{0}', None),
    ('POST', r'runs', '/v1/runs', RunForm),
    ('GET', rf'runs/({ID})', '/v1/runs/{0}', None),
    ('GET', rf'runs/({ID})/events', '/v1/runs/{0}/events', None),
    ('POST', rf'runs/({ID})/approval', '/v1/runs/{0}/approval', ApprovalForm),
    ('POST', rf'runs/({ID})/steer', '/v1/runs/{0}/steer', SteerForm),
    ('POST', rf'runs/({ID})/stop', '/v1/runs/{0}/stop', Form),
    ('GET', r'jobs', '/api/jobs', None),
    ('POST', r'jobs', '/api/jobs', JobForm),
    ('GET', rf'jobs/({ID})', '/api/jobs/{0}', None),
    ('PATCH', rf'jobs/({ID})', '/api/jobs/{0}', JobForm),
    ('DELETE', rf'jobs/({ID})', '/api/jobs/{0}', None),
    ('POST', rf'jobs/({ID})/(pause|resume|run)', '/api/jobs/{0}/{1}', Form),
]


@dataclass(frozen=True)
class Settings:
    url: str
    key: str
    owner: str
    skills_url: str = ''

    @classmethod
    def load(cls):
        return cls(
            *(
                os.environ.get(k, '').strip()
                for k in (
                    'HERMES_WORKBENCH_URL',
                    'HERMES_WORKBENCH_KEY',
                    'HERMES_WORKBENCH_OWNER_ID',
                    'HERMES_WORKBENCH_SKILLS_URL',
                )
            )
        )

    @property
    def enabled(self):
        parsed = urlsplit(self.url)
        return bool(
            parsed.scheme in {'http', 'https'}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.path in {'', '/'}
            and len(self.key) >= 16
            and self.owner
        )


def route_for(method, path):
    for verb, pattern, target, form in ROUTES:
        match = re.fullmatch(pattern, path)
        if verb == method and match:
            return target.format(*match.groups()), form
    raise HTTPException(404, '工作台未开放此操作')


def create_router(verified_user, *, settings=Settings.load, transport=None):
    router = APIRouter()

    @router.get('/config')
    async def config(user=Depends(verified_user)):
        cfg = settings()
        return {'enabled': cfg.enabled and user.id == cfg.owner}

    async def owner(user=Depends(verified_user)):
        cfg = settings()
        if not cfg.enabled:
            raise HTTPException(503, '管理员尚未配置 Hermes 工作台连接')
        if user.id != cfg.owner:
            raise HTTPException(403, '仅工作台所有者可以访问')
        return cfg

    @router.api_route('/{path:path}', methods=['GET', 'POST', 'PATCH', 'DELETE'])
    async def proxy(path: str, request: Request, cfg=Depends(owner)):
        target, form = route_for(request.method, path)
        base_url = cfg.url
        if path == 'skills' or path.startswith('skills/'):
            if not cfg.skills_url:
                raise HTTPException(503, 'Hermes skill reader is not configured')
            base_url = cfg.skills_url
            target = '/' + path
        payload = None
        if form:
            data = bytearray()
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data) > MAX_BODY:
                    raise HTTPException(413, '请求内容过大')
            try:
                payload = form.model_validate_json(bytes(data) or b'{}').model_dump()
            except ValidationError:
                raise HTTPException(422, '请求字段或格式不正确') from None
        params = {}
        allowed_query = {'limit', 'offset', 'order', 'include_disabled', 'source'}
        if set(request.query_params) - allowed_query:
            raise HTTPException(422, '不支持的查询参数')
        for name, value in request.query_params.items():
            if len(value) > 128:
                raise HTTPException(422, '查询参数过长')
            params[name] = value
        headers = {'Authorization': f'Bearer {cfg.key}'}
        if path == 'runs' and request.method == 'POST':
            key = request.headers.get('Idempotency-Key', '')
            if not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', key):
                raise HTTPException(422, '运行请求需要有效的幂等标识')
            headers['Idempotency-Key'] = key
        client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            transport=transport,
            timeout=httpx.Timeout(90, connect=10),
            follow_redirects=False,
            trust_env=False,
        )
        upstream = None

        async def close():
            if upstream is not None:
                await upstream.aclose()
            await client.aclose()

        try:
            upstream = await client.send(
                client.build_request(request.method, target, json=payload, params=params), stream=True
            )
            if upstream.status_code >= 300:
                status = upstream.status_code if upstream.status_code in {400, 404, 409, 422, 429} else 502
                raise HTTPException(status, f'Hermes 未接受此操作（{upstream.status_code}）')
            if target.endswith('/events'):
                if not upstream.headers.get('content-type', '').startswith('text/event-stream'):
                    raise HTTPException(502, 'Hermes 返回了非事件流响应')

                async def stream():
                    try:
                        async for chunk in upstream.aiter_bytes():
                            yield chunk
                    except httpx.TransportError:
                        yield b'data: {"event":"connection.error"}\n\n'
                    finally:
                        await close()

                return StreamingResponse(
                    stream(),
                    media_type='text/event-stream',
                    headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'},
                    background=BackgroundTask(close),
                )
            body = bytearray()
            async for chunk in upstream.aiter_bytes():
                body.extend(chunk)
                if len(body) > 4 * 1024 * 1024:
                    raise HTTPException(502, 'Hermes 响应过大')
            result = json.loads(body)
            await close()
            return JSONResponse(result, status_code=upstream.status_code, headers={'Cache-Control': 'no-store'})
        except (httpx.TransportError, ValueError):
            await close()
            raise HTTPException(502, '无法连接 Hermes，请检查连接配置或稍后重试') from None
        except BaseException:
            await close()
            raise

    return router
