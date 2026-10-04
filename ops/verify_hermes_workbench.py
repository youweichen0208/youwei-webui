"""Offline bridge acceptance against the pinned native Hermes checkout; temporary home only."""

import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import sys

import httpx
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from open_webui.utils.hermes import Settings, create_router

REVISION = 'f97608f178d1ffeca59860195ab7da295f7c8e5f'


class Model(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        message = {'role': 'assistant', 'content': 'Workbench native reply'}
        if body.get('stream'):
            content = (
                'data: '
                + json.dumps(
                    {
                        'id': 'mock',
                        'object': 'chat.completion.chunk',
                        'model': 'mock',
                        'choices': [{'index': 0, 'delta': message, 'finish_reason': None}],
                    }
                )
                + '\n\ndata: '
                + json.dumps({'id': 'mock', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})
                + '\n\ndata: [DONE]\n\n'
            ).encode()
            kind = 'text/event-stream'
        else:
            content = json.dumps(
                {
                    'id': 'mock',
                    'model': 'mock',
                    'choices': [{'message': message, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
                }
            ).encode()
            kind = 'application/json'
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def verify(checkout, skills_reader):
    assert subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip() == REVISION
    model = ThreadingHTTPServer(('127.0.0.1', 0), Model)
    threading.Thread(target=model.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='workbench-native-') as tmp:
        home = Path(tmp)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            skills_port = sock.getsockname()[1]
        skill = home / 'skills/workbench-fixture/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text(
            '---\nname: workbench-fixture\ndescription: offline test skill\n---\n# Fixture\n!`touch /tmp/workbench-must-not-execute`\n'
        )
        config = {
            'model': {
                'default': 'mock',
                'provider': 'custom',
                'base_url': f'http://127.0.0.1:{model.server_port}/v1',
                'api_key': 'offline-mock-key',
            },
            'platform_toolsets': {'api_server': []},
            'memory': {'memory_enabled': False, 'user_profile_enabled': False},
            'auxiliary': {'background_review': {'enabled': False}},
            'platforms': {'api_server': {'enabled': True, 'host': '127.0.0.1', 'port': port}},
        }
        (home / 'config.yaml').write_text(json.dumps(config))
        env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'TMPDIR'}}
        env.update(
            HOME=tmp,
            HERMES_HOME=tmp,
            API_SERVER_ENABLED='true',
            API_SERVER_KEY='workbench-offline-key-123456',
            HERMES_DISABLE_LAZY_INSTALLS='1',
            HERMES_ENABLE_PROJECT_PLUGINS='false',
        )
        env['PATH'] = str(checkout / '.venv/bin') + os.pathsep + env.get('PATH', '')
        with (home / 'gateway.log').open('w+') as log:
            process = subprocess.Popen(
                [str(checkout / '.venv/bin/hermes'), 'gateway', 'run'], env=env, cwd=tmp, stdout=log, stderr=log
            )
            env['WORKBENCH_PORT'] = str(skills_port)
            reader = subprocess.Popen(
                [str(checkout / '.venv/bin/python'), str(skills_reader)], env=env, cwd=tmp, stdout=log, stderr=log
            )
            try:
                for _ in range(160):
                    try:
                        if httpx.get(f'http://127.0.0.1:{port}/health').status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if process.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(log.read()[-4000:])
                    time.sleep(0.25)
                else:
                    raise RuntimeError('native gateway startup timed out')
                asyncio.run(check_bridge(port, skills_port, env['API_SERVER_KEY']))
            finally:
                reader.terminate()
                reader.wait(timeout=10)
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                model.shutdown()
                model.server_close()


async def check_bridge(port, skills_port, key):
    async def owner():
        return SimpleNamespace(id='offline-owner')

    app = FastAPI()
    app.include_router(
        create_router(
            owner,
            settings=lambda: Settings(
                f'http://127.0.0.1:{port}', key, 'offline-owner', f'http://127.0.0.1:{skills_port}'
            ),
        )
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://workbench', timeout=90) as client:

        async def call(method, path, **kwargs):
            response = await client.request(method, path, **kwargs)
            assert response.is_success, (path, response.status_code, response.text)
            return response.json()

        for endpoint in ['capabilities', 'gateway', 'models', 'toolsets', 'sessions']:
            await call('GET', '/' + endpoint)
        session = (await call('POST', '/sessions', json={'title': 'Offline workbench'}))['session']['id']
        body = {'input': 'hello', 'session_id': session}
        headers = {'Idempotency-Key': 'offline-workbench-123456'}
        run = (await call('POST', '/runs', json=body, headers=headers))['run_id']
        assert (await call('POST', '/runs', json=body, headers=headers))['run_id'] == run
        response = await client.get(f'/runs/{run}/events')
        assert response.is_success and 'run.completed' in response.text, response.text
        result = await call('GET', f'/runs/{run}')
        assert result['status'] == 'completed' and 'Workbench native reply' in result['output'], result
        messages = await call('GET', f'/sessions/{session}/messages')
        assert any(m['role'] == 'assistant' for m in messages['data'])
        job = (
            await call(
                'POST',
                '/jobs',
                json={'name': 'Offline future job', 'schedule': '0 9 1 1 *', 'prompt': 'hello', 'deliver': 'local'},
            )
        )['job']
        await call('POST', f'/jobs/{job["id"]}/pause', json={})
        assert not (await call('GET', f'/jobs/{job["id"]}'))['job']['enabled']
        await call('POST', f'/jobs/{job["id"]}/resume', json={})
        await call('DELETE', f'/jobs/{job["id"]}')
        print('PASS native bridge: discovery, session, run, idempotency, SSE, history, cron lifecycle')
        skills = await client.get('/skills')
        assert skills.is_success, skills.text
        assert any(s['name'] == 'workbench-fixture' for s in skills.json()['data'])
        content = await call('GET', '/skills/workbench-fixture')
        assert '!`touch' in content['content']
        assert not Path('/tmp/workbench-must-not-execute').exists()
        print('PASS read-only native skill catalogue/content; preprocessing disabled')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--hermes-checkout', type=Path, required=True)
    parser.add_argument('--skills-reader', type=Path, required=True)
    args = parser.parse_args()
    verify(args.hermes_checkout.resolve(), args.skills_reader.resolve())
