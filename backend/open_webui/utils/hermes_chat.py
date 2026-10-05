"""Presentation-only adapter for the pinned Hermes Responses API.

Tool execution stays in Hermes. Namespaced items cannot enter WebUI's client-side
tool dispatch, including incomplete calls on disconnect. State is per HTTP request.
"""
import codecs
import copy
import hashlib
import json
import uuid

from fastapi import HTTPException

MAX_RESULT = 512 * 1024
MAX_TOTAL = 4 * 1024 * 1024
MAX_ITEMS = 200


def prepare_request(payload, config, user_id, metadata):
    owner = config.get('hermes_owner_id')
    if not owner or user_id != owner:
        raise HTTPException(403, '仅所有者可以使用 Hermes 聊天')
    # Explicit branch history is authoritative. Never forward browser tool/model
    # runtime overrides, previous_response_id, or an arbitrary native session ID.
    messages = payload.get('messages', [])
    instructions = '\n'.join(m['content'] for m in messages
                             if m.get('role') in {'system', 'developer'} and isinstance(m.get('content'), str))
    inputs = [{'role': m['role'], 'content': m.get('content', '')} for m in messages
              if m.get('role') in {'user', 'assistant'} and m.get('content')]
    # Chat-completions text/image parts are also accepted by pinned Hermes.
    body = {'model': payload['model'], 'input': inputs, 'instructions': instructions,
            'stream': bool(payload.get('stream')), 'store': False}
    chat = (metadata or {}).get('chat_id') or str(uuid.uuid4())
    scope = hashlib.sha256(json.dumps([user_id, chat]).encode()).hexdigest()
    return body, {'X-Hermes-Session-Key': 'webui:' + scope}


class HermesResponse:
    def __init__(self):
        self.calls = {}
        self.results = {}
        self.indexes = {}
        self.total = 0
        self.terminal = False
        self.failed = False

    def item(self, raw, index=None):
        if not isinstance(raw, dict):
            raise ValueError('invalid Hermes output item')
        item = copy.deepcopy(raw)
        kind, call = item.get('type'), item.get('call_id')
        if kind not in {'function_call', 'function_call_output'}:
            return item
        if not isinstance(call, str) or not call or len(call) > 256:
            raise ValueError('invalid Hermes tool call identity')
        if call not in self.calls and call not in self.results and len(self.calls.keys() | self.results.keys()) >= MAX_ITEMS:
            raise ValueError('too many Hermes tool calls')
        if kind == 'function_call':
            item['type'] = 'hermes:tool_call'
            item['id'] = 'hermes-call-' + call
            item['status'] = item.get('status', 'in_progress')
            if call in self.results:
                item['status'] = self.calls.get(call, {}).get('status', 'completed')
                self.results[call]['name'] = item.get('name', '')
            self.calls[call] = item
            if index is not None:
                self.indexes[call] = index
        else:
            if call in self.results:
                return copy.deepcopy(self.results[call])
            item['type'] = 'hermes:tool_result'
            item['id'] = 'hermes-result-' + call
            item['name'] = self.calls.get(call, {}).get('name', '')
            size = len(json.dumps(item.get('output'), ensure_ascii=False).encode())
            if size > MAX_RESULT or self.total + size > MAX_TOTAL:
                item['output'] = [{'type': 'input_text', 'text': '{"error":"工具结果过大，无法展示完整数据"}'}]
            else:
                self.total += size
            self.results[call] = item
            if call in self.calls:
                self.calls[call]['status'] = 'completed'
        return copy.deepcopy(item)

    def event(self, raw):
        if not isinstance(raw, dict):
            raise ValueError('invalid Hermes event')
        data = copy.deepcopy(raw)
        if isinstance(data.get('item'), dict):
            data['item'] = self.item(data['item'], data.get('output_index'))
        if data.get('type') in {'response.completed', 'response.failed', 'response.incomplete'}:
            self.terminal = True
            self.failed = data['type'] != 'response.completed'
            response = data.setdefault('response', {})
            # Native final output is a compact summary. Full incremental results
            # win; stable call IDs also remove duplicate added/done events.
            output, seen = [], set()
            for raw_item in response.get('output', []):
                item = self.item(raw_item)
                identity = (item.get('type'), item.get('call_id') or item.get('id'))
                if not identity[1] or identity not in seen:
                    seen.add(identity)
                    output.append(item)
            for item in [*self.calls.values(), *self.results.values()]:
                identity = (item['type'], item['call_id'])
                if identity not in seen:
                    output.append(copy.deepcopy(item))
            for item in output:
                if item.get('type') == 'hermes:tool_call' and item.get('call_id') not in self.results:
                    item['status'] = 'interrupted'
            response['output'] = output
        return data

    def incomplete_events(self):
        for call, item in self.calls.items():
            if call not in self.results:
                yield {'type': 'response.output_item.done', 'output_index': self.indexes.get(call, 0),
                       'item': {**item, 'status': 'interrupted'}}


def encode_event(data):
    return ('data: ' + json.dumps(data, ensure_ascii=False) + '\n\n').encode()


async def stream_response(chunks):
    adapter = HermesResponse()
    decoder = codecs.getincrementaldecoder('utf-8')()
    buffer, lines = '', []

    def frame():
        raw = '\n'.join(line[5:].lstrip(' ') for line in lines if line.startswith('data:'))
        if not raw or raw == '[DONE]':
            return None
        return encode_event(adapter.event(json.loads(raw)))

    try:
        async for chunk in chunks:
            buffer += decoder.decode(chunk) if isinstance(chunk, bytes) else chunk
            if len(buffer) > MAX_TOTAL * 2:
                raise ValueError('Hermes stream frame too large')
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.removesuffix('\r')
                if line:
                    lines.append(line)
                    if sum(map(len, lines)) > MAX_TOTAL * 2:
                        raise ValueError('Hermes stream frame too large')
                else:
                    encoded = frame()
                    if encoded:
                        yield encoded
                    lines.clear()
        buffer += decoder.decode(b'', final=True)
        if buffer:
            lines.append(buffer)
        if lines:
            encoded = frame()
            if encoded:
                yield encoded
    except (ValueError, UnicodeError):
        adapter.failed = True
    finally:
        # Closing this generator closes the provider connection through stream_wrapper.
        close = getattr(chunks, 'aclose', None)
        if close:
            await close()
    for event in adapter.incomplete_events():
        yield encode_event(event)
    if not adapter.terminal or adapter.failed:
        yield encode_event({'error': {'message': 'Hermes 运行未完整结束；已收到的结果保留。'}})
    yield b'data: [DONE]\n\n'


def nonstream_response(response):
    output = HermesResponse().event({'type': 'response.completed', 'response': response})['response']['output']
    content = ''.join(p.get('text', '') for i in output if i.get('type') == 'message'
                      for p in i.get('content', []) if p.get('type') == 'output_text')
    return {'id': response.get('id'), 'object': 'chat.completion', 'model': response.get('model'),
            'output': output, 'usage': response.get('usage', {}),
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}]}
