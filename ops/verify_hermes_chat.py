"""Offline acceptance: pinned native Hermes + synthetic model/tools + chat adapter.

Only temporary profiles and loopback endpoints. No supplier or paid model calls.
"""
import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from open_webui.utils.hermes_chat import prepare_request, stream_response, nonstream_response

REVISION = 'f97608f178d1ffeca59860195ab7da295f7c8e5f'
TOOLS = ['trading_price_history', 'trading_indicators', 'trading_financials']


def fixtures():
    base = dict(symbol='AAPL', source='offline fixture', fetched_at='2026-10-06T00:00:00Z', pit=False,
                warnings=['Synthetic data'], period={'start':'2026-09-01','end_exclusive':'2026-10-01'})
    rows = [dict(date=f'2026-09-{n:02}', open=100+n, high=102+n, low=99+n, close=101+n,
                 adjusted_close=100+n, volume=1000+n) for n in range(1, 29)]
    return dict(zip(TOOLS, [
        dict(base, rows=rows, currency='USD', adjustment='OHLC and adjusted close remain separate'),
        dict(base, sample_size=28, metrics={k: {'value': None, 'reason':'requires_200_prices'} for k in
             ('sma20','sma50','sma200','rsi14','period_return','annualized_volatility','max_drawdown')}),
        dict(base, frequency='quarterly', periods=[{'end':'2026-06-30','metrics':{'revenue':{
            'value':123456789,'reason':None,'unit':'USD','filed':'2026-08-01',
            'source_url':'https://www.sec.gov/Archives/edgar/data/320193/fixture-index.html'}}}]),
    ]))


class Model(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if 'messages' not in body:
            self.send_response(404); self.end_headers(); return
        messages = body['messages']
        last = max(i for i,m in enumerate(messages) if m['role'] == 'user')
        query = messages[last]['content']
        if isinstance(query, list):
            query = ''.join(p.get('text','') for p in query)
        tool = next((t for t in TOOLS if t in query), None)
        if tool and not any(m['role'] == 'tool' for m in messages[last+1:]):
            message = {'role':'assistant','content':None,'tool_calls':[{'id':'call-fixture','type':'function',
                       'function':{'name':tool,'arguments':'{}'}}]}
            finish = 'tool_calls'
        else:
            message = {'role':'assistant','content':'开始 mock 流式。' if query == 'SLOW' else '已取得数据，中文回答。'}
            finish = 'stop'
        self.send_response(200)
        self.send_header('Content-Type','text/event-stream' if body.get('stream') else 'application/json')
        self.end_headers()
        if body.get('stream'):
            if tool and 'tool_calls' in message:
                message['tool_calls'][0]['index'] = 0
            for delta, reason in [(message,None),({},finish)]:
                self.wfile.write(('data: '+json.dumps({'id':'mock','choices':[{'index':0,'delta':delta,'finish_reason':reason}]})+'\n\n').encode())
                self.wfile.flush()
                if query == 'SLOW' and reason is None:
                    time.sleep(10)
            self.wfile.write(b'data: [DONE]\n\n')
        else:
            self.wfile.write(json.dumps({'id':'mock','choices':[{'message':message,'finish_reason':finish}],
                                        'usage':{'prompt_tokens':1,'completion_tokens':1}}).encode())


async def check(port):
    config = {'hermes_chat':True,'hermes_owner_id':'owner'}
    async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', timeout=60) as client:
        for tool, expected in fixtures().items():
            request, headers = prepare_request({'model':'mock','stream':True,'messages':[{'role':'user','content':tool}]},config,'owner',{'chat_id':tool})
            headers['Authorization'] = 'Bearer offline-chat-fixture-key'
            async with client.stream('POST','/v1/responses',json=request,headers=headers) as upstream:
                assert upstream.status_code == 200
                raw = b''.join([c async for c in stream_response(upstream.aiter_bytes())]).decode()
            events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith('data: {')]
            final = next(e['response'] for e in events if e['type']=='response.completed')
            saved = json.loads(json.dumps(final['output']))
            calls = [i for i in saved if i['type']=='hermes:tool_call']
            results = [i for i in saved if i['type']=='hermes:tool_result']
            assert len(calls) == len(results) == 1, raw
            assert json.loads(results[0]['output'][0]['text']) == expected
            assert not any(i['type'] in {'function_call','function_call_output'} for i in saved)
            # Same full-history branch through the nonstreaming path.
            request['stream'] = False
            reply = await client.post('/v1/responses',json=request,headers=headers)
            reply.raise_for_status()
            converted = nonstream_response(reply.json())
            assert converted['choices'][0]['finish_reason'] == 'stop'
            assert len([i for i in converted['output'] if i['type']=='hermes:tool_result']) == 1
            assert 'tool_calls' not in converted['choices'][0]['message']
            print('PASS native stream/nonstream/persisted full result:', tool)


async def check_webui(url, native_port, model_port):
    assert url.startswith('http://127.0.0.1:'), 'isolated local WebUI only'
    async with httpx.AsyncClient(base_url=url,timeout=90) as client:
        credentials = {'email':'hermes-fixture@example.com','password':'isolated-fixture-password-123'}
        signup = await client.post('/api/v1/auths/signup',json={**credentials,'name':'Fixture owner'})
        if signup.status_code != 200:
            signup = await client.post('/api/v1/auths/signin',json=credentials)
        signup.raise_for_status()
        owner = signup.json()['id']
        client.headers['Authorization'] = 'Bearer '+signup.json()['token']
        settings = {'ENABLE_OPENAI_API':True,'OPENAI_API_BASE_URLS':[f'http://host.docker.internal:{native_port}/v1',f'http://host.docker.internal:{model_port}/v1'],
                    'OPENAI_API_KEYS':['offline-chat-fixture-key','ordinary-fixture-key'],'OPENAI_API_CONFIGS':{
                        '0':{'enable':True,'model_ids':['mock'],'hermes_chat':True,'hermes_owner_id':owner},
                        '1':{'enable':True,'model_ids':['ordinary']}}}
        response = await client.post('/openai/config/update',json=settings); response.raise_for_status()
        (await client.get('/api/models')).raise_for_status()
        user_id, message_id = str(uuid.uuid4()), str(uuid.uuid4())
        messages = {user_id:{'id':user_id,'role':'user','content':'trading_price_history','parentId':None,'childrenIds':[message_id]},
                    message_id:{'id':message_id,'role':'assistant','content':'','parentId':user_id,'childrenIds':[],'model':'mock'}}
        chat = await client.post('/api/v1/chats/new',json={'chat':{'title':'Hermes financial fixture','models':['mock'],
                    'history':{'messages':messages,'currentId':message_id},'messages':list(messages.values())}})
        chat.raise_for_status(); chat_id = chat.json()['id']
        reply = await client.post('/api/chat/completions',json={'model':'mock','stream':True,'chat_id':chat_id,'id':message_id,
                    'messages':[{'role':'user','content':'trading_price_history'}]})
        reply.raise_for_status()
        saved = (await client.get('/api/v1/chats/'+chat_id)).json()['chat']['history']['messages'][message_id]
        output = saved.get('output', [])
        results = [i for i in output if i['type']=='hermes:tool_result']
        assert len(results) == 1, (reply.text, saved)
        assert json.loads(results[0]['output'][0]['text']) == fixtures()['trading_price_history']
        assert saved.get('done'), saved
        print('PASS actual WebUI HTTP chat + saved history: '+url+'/c/'+chat_id, flush=True)
        for tool in TOOLS:
            reply = await client.post('/api/chat/completions',json={'model':'mock','stream':False,
                       'messages':[{'role':'user','content':tool}]})
            reply.raise_for_status()
            assert len([i for i in reply.json()['output'] if i['type']=='hermes:tool_result']) == 1
        print('PASS actual WebUI nonstreaming financial tools', flush=True)
        plain = await client.post('/api/chat/completions',json={'model':'ordinary','stream':False,'messages':[{'role':'user','content':'hello'}]})
        plain.raise_for_status()
        assert 'hermes:tool' not in plain.text
        assert plain.json()['choices'][0]['message']['content'] == '已取得数据，中文回答。'
        raw = await client.post('/openai/responses',json={'model':'mock','input':'hello'})
        assert raw.status_code == 403
        print('PASS ordinary connection and blocked raw Hermes bypass',flush=True)


def verify(checkout, webui_url=None, hold=False):
    assert subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip() == REVISION
    model = ThreadingHTTPServer(('127.0.0.1',0),Model)
    threading.Thread(target=model.serve_forever,daemon=True).start()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='hc-', dir='/tmp') as tmp:
        home = Path(tmp)
        plugin = home/'plugins/chat-fixtures'; plugin.mkdir(parents=True)
        (plugin/'plugin.yaml').write_text('name: chat-fixtures\nversion: 1.0.0\ndescription: offline test tools\n')
        (plugin/'fixtures.json').write_text(json.dumps(fixtures()))
        (plugin/'__init__.py').write_text('''import json
from pathlib import Path
def register(ctx):
    data = json.loads(Path(__file__).with_name('fixtures.json').read_text())
    for name, result in data.items():
        ctx.register_tool(name=name, toolset='chat-fixtures', handler=lambda args, _result=result, **kw: json.dumps(_result),
            schema={'name':name,'description':'offline fixture','parameters':{'type':'object','properties':{}}})
''')
        config = {'model':{'default':'mock','provider':'custom','base_url':f'http://127.0.0.1:{model.server_port}/v1','api_key':'offline-model-key'},
                  'tools':{'tool_search':{'enabled':'off'}},'platform_toolsets':{'api_server':['chat-fixtures']},'plugins':{'enabled':['chat-fixtures']},
                  'memory':{'memory_enabled':False,'user_profile_enabled':False},
                  'auxiliary':{'background_review':{'enabled':False}},
                  'platforms':{'api_server':{'enabled':True,'host':'127.0.0.1','port':port}}}
        (home/'config.yaml').write_text(json.dumps(config))
        env = {k:v for k,v in os.environ.items() if k in {'PATH','LANG','TMPDIR'}}
        env.update(HOME=tmp,HERMES_HOME=tmp,API_SERVER_ENABLED='true',API_SERVER_KEY='offline-chat-fixture-key',
                   HERMES_DISABLE_LAZY_INSTALLS='1',HERMES_ENABLE_PROJECT_PLUGINS='false')
        env['PATH'] = str(checkout/'.venv/bin')+os.pathsep+env.get('PATH','')
        with (home/'gateway.log').open('w+') as log:
            process = subprocess.Popen([str(checkout/'.venv/bin/hermes'),'gateway','run'],cwd=tmp,env=env,stdout=log,stderr=log)
            try:
                for _ in range(160):
                    try:
                        if httpx.get(f'http://127.0.0.1:{port}/health').status_code == 200: break
                    except httpx.TransportError: pass
                    if process.poll() is not None: raise RuntimeError('gateway exited')
                    time.sleep(.25)
                else: raise RuntimeError('gateway timeout')
                asyncio.run(check(port))
                if webui_url:
                    asyncio.run(check_webui(webui_url, port, model.server_port))
                if hold:
                    print(f'Fixture gateway ready at http://127.0.0.1:{port}; interrupt to stop.',flush=True)
                    while True: time.sleep(1)
            except Exception:
                log.seek(0); print(log.read()[-4000:]); raise
            finally:
                process.terminate()
                try: process.wait(timeout=20)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
                model.shutdown(); model.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout',type=Path)
    parser.add_argument('--webui-url')
    parser.add_argument('--hold',action='store_true')
    args = parser.parse_args()
    verify(args.checkout.resolve(), args.webui_url, args.hold)
