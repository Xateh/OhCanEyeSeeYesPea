import importlib.util
import inspect
import json
import unittest
from types import SimpleNamespace

from study.api_provider import CLAUDE_RATES as RATES, ClaudeAPIProvider, claude_usage as usage_record, parse_claude_reply as parse_api_reply
from study.claude_provider import MODEL, ClaudeCodeProvider, isolated_argv
from study.prompts import PROMPTS, user_message
from study.run_hard import hit_usage_limit


def usage(fresh=1000, output=200, write=0, read=0):
    return SimpleNamespace(input_tokens=fresh, output_tokens=output, cache_creation_input_tokens=write, cache_read_input_tokens=read)


def reply(payload, model=MODEL, stop='end_turn', tokens=None):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    blocks = [SimpleNamespace(type='thinking', thinking=''), SimpleNamespace(type='text', text=text)]
    return SimpleNamespace(model=model, stop_reason=stop, content=blocks, usage=tokens or usage())


class Recorder:
    """Stands in for the API call and keeps every request it receives."""
    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def __call__(self, client, model, effort, system, message):
        self.requests.append(dict(model=model, effort=effort, system=system, message=message))
        answer = self.replies.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def provider(*replies):
    recorder = Recorder(*replies)
    return ClaudeAPIProvider('v3', client_factory=lambda: object(), caller=recorder), recorder


class Usage(unittest.TestCase):
    def test_cost_uses_opus_5_5_standard_rates(self):
        record = usage_record(usage(fresh=1_000_000, output=1_000_000))
        self.assertEqual(record, {'input_tokens': 1_000_000, 'output_tokens': 1_000_000, 'cost_usd': RATES['input'] + RATES['output']})

    def test_cached_tokens_count_as_input_like_the_cli_receipts(self):
        record = usage_record(usage(fresh=100, output=10, write=1000, read=2000))
        self.assertEqual(record['input_tokens'], 3100)
        self.assertAlmostEqual(record['cost_usd'], (100 * 4 + 10 * 20 + 1000 * 5 + 2000 * 0.2) / 1_000_000)

    def test_missing_usage_stays_unknown_not_zero(self):
        self.assertEqual(usage_record(None), {'input_tokens': None, 'output_tokens': None, 'cost_usd': None})


class SameRequestAsTheCli(unittest.TestCase):
    def test_sends_the_cli_system_prompt_user_message_model_and_effort(self):
        api, recorder = provider(reply({'type': 'final', 'output': {'status': 'UNKNOWN'}}))
        api.next('case text', [], [])
        cli_argv = isolated_argv(MODEL, 'high', PROMPTS['v3']['system'])
        sent = recorder.requests[0]
        self.assertEqual(sent['system'], cli_argv[cli_argv.index('--system-prompt') + 1])
        self.assertEqual(sent['message'], user_message('v3', 'case text', [], []))
        self.assertEqual((sent['model'], sent['effort']), (MODEL, cli_argv[cli_argv.index('--effort') + 1]))

    def test_revision_matches_the_cli_apart_from_the_transport(self):
        api, _ = provider()
        self.assertEqual(api.model_revision, ClaudeCodeProvider('v3').model_revision + '|transport=anthropic-api')

    def test_the_sdk_stream_call_accepts_the_request_fields(self):
        if importlib.util.find_spec('anthropic') is None:
            self.skipTest('anthropic SDK not installed')
        from anthropic.resources.messages import Messages
        accepted = inspect.signature(Messages.stream).parameters
        for name in ('model', 'max_tokens', 'system', 'messages', 'thinking', 'output_config'):
            self.assertIn(name, accepted)


class Replies(unittest.TestCase):
    def test_reads_a_fenced_json_reply_and_records_usage(self):
        api, _ = provider(reply('```json\n{"type": "final", "output": {"status": "UNKNOWN"}}\n```'))
        message = api.next('case', [], [])
        self.assertEqual(message['type'], 'final')
        self.assertEqual(api.attempt_accounting[0]['usage']['output_tokens'], 200)

    def test_a_different_model_is_an_error_but_its_usage_is_kept(self):
        api, _ = provider(reply({'type': 'final', 'output': {}}, model='claude-sonnet-5-5'))
        with self.assertRaises(RuntimeError):
            api.next('case', [], [])
        self.assertEqual(api.attempt_accounting[0]['usage']['input_tokens'], 1000)

    def test_a_cut_off_or_refused_reply_is_an_error(self):
        for stop in ('max_tokens', 'refusal'):
            with self.assertRaises(RuntimeError):
                parse_api_reply(reply({'type': 'final', 'output': {}}, stop=stop), MODEL)

    def test_a_failed_call_is_recorded_with_unknown_usage(self):
        api, _ = provider(RuntimeError('rate limit reached: 429'))
        with self.assertRaises(RuntimeError):
            api.next('case', [], [])
        self.assertEqual(api.attempt_accounting, [{'usage': None, 'reason': 'RuntimeError'}])

    def test_rate_and_billing_errors_stop_the_runner(self):
        for text in ('RuntimeError: rate limit reached: 429', 'RuntimeError: usage limit (billing): credit balance too low'):
            self.assertTrue(hit_usage_limit({'errors': [{'error': text}]}))


if __name__ == '__main__':
    unittest.main()
