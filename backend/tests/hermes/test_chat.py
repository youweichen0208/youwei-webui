import asyncio
import json

import pytest

from open_webui.utils.hermes_chat import HermesResponse, prepare_request, stream_response


def test_completed_summary_keeps_full_results_and_never_exposes_executable_calls():
    adapter = HermesResponse()
    call = {'type': 'function_call', 'call_id': 'c1', 'name': 'trading_price_history', 'arguments': '{}'}
    result = {'type': 'function_call_output', 'call_id': 'c1', 'output': [{'type': 'input_text', 'text': 'x' * 2000}]}
    adapter.event({'type': 'response.output_item.added', 'item': call, 'output_index': 0})
    adapter.event({'type': 'response.output_item.done', 'item': result, 'output_index': 1})
    final = adapter.event({'type': 'response.completed', 'response': {'id': 'r1', 'output': [
        call, {**result, 'output': [{'type': 'input_text', 'text': 'truncated'}]}
    ]}})
    output = final['response']['output']
    assert output[1]['output'][0]['text'] == 'x' * 2000
    assert [i['type'] for i in output] == ['hermes:tool_call', 'hermes:tool_result']
    assert output[1]['name'] == 'trading_price_history'


def test_request_keeps_branch_history_but_removes_tool_overrides_and_continuation():
    payload = {'model': 'Hermes', 'stream': True, 'previous_response_id': 'other', 'tools': [{}],
               'messages': [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'first'},
                            {'role': 'assistant', 'content': 'answer', 'tool_calls': [{}]},
                            {'role': 'tool', 'content': 'old result'}, {'role': 'user', 'content': 'next'}]}
    config = {'hermes_chat': True, 'hermes_owner_id': 'owner'}
    body, headers = prepare_request(payload, config, 'owner', {'chat_id': 'chat'})
    assert body['instructions'] == 'system'
    assert [i['content'] for i in body['input']] == ['first', 'answer', 'next']
    assert 'tools' not in body and 'previous_response_id' not in body
    assert headers['X-Hermes-Session-Key'].startswith('webui:')
    assert prepare_request(payload, config, 'owner', {'chat_id': 'another'})[1] != headers
    with pytest.raises(Exception) as exc:
        prepare_request(payload, config, 'other', {'chat_id': 'chat'})
    assert exc.value.status_code == 403


def test_stream_handles_split_utf8_crlf_duplicates_and_partial_disconnect():
    async def run():
        frames = [
            {'type': 'response.output_item.added', 'output_index': 0, 'item': {
                'type': 'function_call', 'call_id': 'c', 'name': 'memory', 'arguments': '{}'}},
            {'type': 'response.output_text.delta', 'delta': '中文'},
        ]
        raw = ''.join('data: ' + json.dumps(f, ensure_ascii=False) + '\r\n\r\n' for f in frames).encode()
        async def chunks():
            for byte in raw:
                yield bytes([byte])
        emitted = b''.join([chunk async for chunk in stream_response(chunks())]).decode()
        assert '中文' in emitted
        assert 'interrupted' in emitted
        assert '"error"' in emitted
        assert '"type": "function_call"' not in emitted
    asyncio.run(run())


def test_oversized_result_and_separate_generations_do_not_leak_cached_data():
    from open_webui.utils.hermes_chat import MAX_RESULT, nonstream_response
    def response(text):
        return {'id': 'r', 'output': [
            {'type':'function_call','call_id':'same','name':'trading_indicators'},
            {'type':'function_call_output','call_id':'same','output':text},
            {'type':'message','content':[{'type':'output_text','text':'answer'}]},
        ]}
    assert nonstream_response(response('first'))['output'][1]['output'] == 'first'
    assert nonstream_response(response('second'))['output'][1]['output'] == 'second'
    large = nonstream_response(response('x' * (MAX_RESULT + 1)))
    assert '过大' in large['output'][1]['output'][0]['text']
    assert 'tool_calls' not in large['choices'][0]['message']


def test_out_of_order_results_keep_tool_identity_and_terminal_status():
    adapter = HermesResponse()
    result = {'type':'function_call_output','call_id':'c','output':'{"error":"provider_failed"}'}
    adapter.event({'type':'response.output_item.done','item':result})
    call = {'type':'function_call','call_id':'c','name':'trading_financials','status':'in_progress'}
    adapter.event({'type':'response.output_item.added','item':call})
    final = adapter.event({'type':'response.completed','response':{'output':[call,result,result]}})['response']['output']
    assert len(final) == 2
    assert final[0]['status'] == 'completed'
    assert final[1]['name'] == 'trading_financials'


def test_final_answer_is_not_dropped_after_interim_commentary_without_ids():
    from open_webui.utils.hermes_chat import nonstream_response
    reply = nonstream_response({'output': [
        {'type':'message','phase':'commentary','content':[{'type':'output_text','text':'working'}]},
        {'type':'message','content':[{'type':'output_text','text':'answer'}]},
    ]})
    assert len(reply['output']) == 2
    assert 'answer' in reply['choices'][0]['message']['content']
