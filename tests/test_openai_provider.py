import importlib.util
import json
import unittest
from types import SimpleNamespace

from study.claude_provider import ClaudeCodeProvider
from study.openai_provider import OPENAI_MODEL, OPENAI_RATES, OpenAIProvider, openai_usage, parse_openai_reply
from study.prompts import PROMPTS, user_message
from tests.test_api_provider import Recorder


def usage(total=1000, output=200, cached=0, written=0):
    details = SimpleNamespace(cached_tokens=cached, cache_write_tokens=written)
    return SimpleNamespace(input_tokens=total, output_tokens=output, input_tokens_details=details)


def response(payload, model=OPENAI_MODEL, status='completed', tokens=None):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(model=model, status=status, incomplete_details=None, output_text=text, usage=tokens or usage())


def provider(*replies):
    recorder = Recorder(*replies)
    return OpenAIProvider('v3', client_factory=lambda: object(), caller=recorder), recorder


class Usage(unittest.TestCase):
    def test_cost_uses_gpt_6_astra_standard_rates(self):
        record = openai_usage(usage(total=1_000_000, output=1_000_000))
        self.assertEqual(record['cost_usd'], OPENAI_RATES['input'] + OPENAI_RATES['output'])

    def test_matches_xu_ans_recorded_smoke_test_cost(self):
        self.assertAlmostEqual(openai_usage(usage(total=6870, output=2018))['cost_usd'], 0.16960)

    def test_cached_tokens_are_part_of_input_and_cheaper(self):
        record = openai_usage(usage(total=1000, output=0, cached=600))
        self.assertEqual(record['input_tokens'], 1000)
        self.assertAlmostEqual(record['cost_usd'], (400 * 10 + 600 * 1) / 1_000_000)

    def test_missing_or_inconsistent_usage_stays_unknown(self):
        self.assertIsNone(openai_usage(None)['cost_usd'])
        self.assertIsNone(openai_usage(usage(total=10, cached=20))['cost_usd'])


class SamePromptAsClaude(unittest.TestCase):
    def test_sends_the_frozen_system_prompt_and_user_message_at_high_effort(self):
        gpt, recorder = provider(response({'type': 'final', 'output': {'status': 'UNKNOWN'}}))
        gpt.next('case text', [], [])
        sent = recorder.requests[0]
        self.assertEqual(sent['system'], PROMPTS['v3']['system'])
        self.assertEqual(sent['message'], user_message('v3', 'case text', [], []))
        self.assertEqual((sent['model'], sent['effort']), (OPENAI_MODEL, ClaudeCodeProvider('v3').effort))

    def test_revision_names_the_model_and_transport(self):
        gpt, _ = provider()
        self.assertTrue(gpt.model_revision.startswith('gpt-6-astra|effort=high|prompt=v3|'))
        self.assertTrue(gpt.model_revision.endswith('|transport=openai-api'))


class Replies(unittest.TestCase):
    def test_reads_a_reply_from_a_dated_snapshot_of_the_model(self):
        gpt, _ = provider(response({'type': 'tool_call', 'name': 'csp', 'arguments': {}}, model='gpt-6-astra-2026-10-01'))
        self.assertEqual(gpt.next('case', [], [])['type'], 'tool_call')

    def test_another_model_or_an_incomplete_reply_is_an_error_with_usage_kept(self):
        for bad in (response({'type': 'final'}, model='gpt-5'), response({'type': 'final'}, status='incomplete')):
            with self.assertRaises(RuntimeError) as caught:
                parse_openai_reply(bad, OPENAI_MODEL)
            self.assertEqual(caught.exception.observed_usage['input_tokens'], 1000)


@unittest.skipIf(importlib.util.find_spec('openai') is None, 'openai SDK not installed')
class RealSdk(unittest.TestCase):
    """The installed SDK, a synthetic key and a local fake server: no network and no spend."""

    def client(self, handler):
        import httpx2
        import openai
        return openai.OpenAI(api_key='sk-test-synthetic-key-0000', max_retries=0,
                             http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))

    def test_request_body_and_reply_parsing(self):
        import httpx2
        from study.openai_provider import call_openai
        seen = {}
        body = {'id': 'resp_1', 'object': 'response', 'created_at': 0, 'model': OPENAI_MODEL, 'status': 'completed',
                'output': [{'type': 'message', 'id': 'msg_1', 'role': 'assistant', 'status': 'completed',
                            'content': [{'type': 'output_text', 'text': '{"type": "final", "output": {"status": "UNKNOWN"}}', 'annotations': []}]}],
                'usage': {'input_tokens': 900, 'output_tokens': 100, 'total_tokens': 1000,
                          'input_tokens_details': {'cached_tokens': 0}, 'output_tokens_details': {'reasoning_tokens': 60}},
                'parallel_tool_calls': False, 'tool_choice': 'auto', 'tools': []}

        def handler(request):
            seen.update(url=str(request.url), body=json.loads(request.content))
            return httpx2.Response(200, json=body)
        reply = parse_openai_reply(call_openai(self.client(handler), OPENAI_MODEL, 'high', 'SYSTEM', 'USER'), OPENAI_MODEL)
        self.assertEqual(seen['url'], 'https://api.openai.com/v1/responses')
        self.assertEqual({k: seen['body'][k] for k in ('model', 'instructions', 'reasoning', 'store', 'tools')},
                         {'model': OPENAI_MODEL, 'instructions': 'SYSTEM', 'reasoning': {'effort': 'high'}, 'store': False, 'tools': []})
        self.assertEqual((reply['type'], reply['usage']['input_tokens']), ('final', 900))

    def test_quota_and_rate_limit_errors_stop_the_runner(self):
        import httpx2
        from study.openai_provider import call_openai
        from study.run_hard import hit_usage_limit
        for code, kind in ((429, 'insufficient_quota'), (429, 'rate_limit_exceeded')):
            client = self.client(lambda request: httpx2.Response(code, json={'error': {'message': 'limit', 'type': kind, 'code': kind}}))
            with self.assertRaises(RuntimeError) as caught:
                call_openai(client, OPENAI_MODEL, 'high', 'S', 'U')
            self.assertTrue(hit_usage_limit({'errors': [{'error': f'RuntimeError: {caught.exception}'}]}))


if __name__ == '__main__':
    unittest.main()
