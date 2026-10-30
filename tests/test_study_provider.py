"""Claude Code provider contract, exercised with a fake CLI runner (no model calls)."""
import json
import tempfile
import unittest
from pathlib import Path

from study.claude_provider import ClaudeCodeProvider, extract_json, isolated_argv, parse_cli_reply
from study.prompts import PROMPTS, prompt_sha256, user_message

MODEL = 'claude-opus-5-5'


def reply(result, model=MODEL, is_error=False):
    return json.dumps({'is_error': is_error, 'result': result, 'total_cost_usd': 0.25,
                       'usage': {'input_tokens': 3, 'cache_creation_input_tokens': 5,
                                 'cache_read_input_tokens': 7, 'output_tokens': 11},
                       'modelUsage': {model: {}}})


class Fake:
    def __init__(self, stdout):
        self.stdout, self.calls = stdout, []

    def __call__(self, argv, stdin, cwd):
        self.calls.append({'argv': argv, 'stdin': stdin, 'cwd': cwd,
                           'cwd_files': list(Path(cwd).iterdir())})
        return self.stdout


class IsolationTests(unittest.TestCase):
    def test_argv_disables_every_tool_and_outside_configuration(self):
        argv = isolated_argv('m', 'high', 'sys')
        for flag in ('--strict-mcp-config', '--no-session-persistence', '--disable-slash-commands'):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index('--tools') + 1], '')
        self.assertEqual(argv[argv.index('--setting-sources') + 1], '')

    def test_each_call_runs_in_a_new_empty_directory(self):
        fake = Fake(reply('{"type":"final","output":{"status":"UNKNOWN"}}'))
        provider = ClaudeCodeProvider('v1', runner=fake)
        provider.next('text', [], [])
        provider.next('text', [], [])
        self.assertNotEqual(fake.calls[0]['cwd'], fake.calls[1]['cwd'])
        self.assertEqual(fake.calls[0]['cwd_files'], [])
        self.assertFalse(Path(fake.calls[0]['cwd']).exists())


class ParseTests(unittest.TestCase):
    def test_extract_json_accepts_plain_object_and_single_fence(self):
        self.assertEqual(extract_json('{"a":1}'), {'a': 1})
        self.assertEqual(extract_json('```json\n{"a":1}\n```'), {'a': 1})

    def test_extract_json_rejects_prose_around_the_object(self):
        with self.assertRaises(ValueError):
            extract_json('Here you go: {"a":1}')

    def test_extract_json_rejects_non_objects(self):
        with self.assertRaises(ValueError):
            extract_json('[1]')

    def test_token_usage_includes_cache_tokens_and_keeps_cost(self):
        message = parse_cli_reply(reply('{"type":"final","output":{"status":"UNKNOWN"}}'), MODEL)
        self.assertEqual(message['usage'], {'input_tokens': 15, 'output_tokens': 11, 'cost_usd': 0.25})

    def test_raw_text_is_retained_for_failure_analysis(self):
        text = '{"type":"final","output":{"status":"UNKNOWN"}}'
        self.assertEqual(parse_cli_reply(reply(text), MODEL)['raw_text'], text)

    def test_cli_error_raises_instead_of_counting_as_an_answer(self):
        with self.assertRaises(RuntimeError):
            parse_cli_reply(reply('rate limited', is_error=True), MODEL)

    def test_a_different_model_than_requested_raises(self):
        with self.assertRaises(RuntimeError):
            parse_cli_reply(reply('{"type":"final"}', model='other'), MODEL)

    def test_unknown_message_type_raises(self):
        with self.assertRaises(ValueError):
            parse_cli_reply(reply('{"status":"UNKNOWN"}'), MODEL)


class PromptTests(unittest.TestCase):
    def test_revision_pins_model_effort_and_prompt_text(self):
        provider = ClaudeCodeProvider('v1', runner=Fake(''))
        for part in (MODEL, 'high', 'v1', prompt_sha256('v1')):
            self.assertIn(part, provider.model_revision)

    def test_unknown_prompt_version_is_rejected(self):
        with self.assertRaises(ValueError):
            ClaudeCodeProvider('nope', runner=Fake(''))

    def test_problem_text_is_identical_and_verbatim_in_both_arms(self):
        tool = {'name': 'csp', 'description': 'd', 'parameters': {}}
        for version in PROMPTS:
            self.assertIn('PROBLEM-TEXT', user_message(version, 'PROBLEM-TEXT', [], []))
            self.assertIn('PROBLEM-TEXT', user_message(version, 'PROBLEM-TEXT', [], [tool]))

    def test_no_tools_message_never_mentions_the_solver(self):
        for version in PROMPTS:
            self.assertNotIn('csp', user_message(version, 'x', [], []))

    def test_tool_history_is_replayed_to_the_model(self):
        tool = {'name': 'csp', 'description': 'd', 'parameters': {}}
        history = [{'name': 'csp', 'arguments': {'instance': {}}, 'result': {'status': 'MARKER'}, 'latency_seconds': 1}]
        self.assertIn('MARKER', user_message('v1', 'x', history, [tool]))


if __name__ == '__main__':
    unittest.main()
