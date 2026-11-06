"""Harness provider that sends each turn to an isolated, tool-free Claude Code process."""
import json
import re
import subprocess
import tempfile

from .prompts import PROMPTS, prompt_sha256, user_message
from .accounting import envelope_usage

MODEL = 'claude-opus-5-5'
EFFORT = 'high'
CALL_TIMEOUT_SECONDS = 300
CALL_BUDGET_USD = 2
FENCE = re.compile(r'\A```(?:json)?\n(.*)\n```\Z', re.DOTALL)


def isolated_argv(model, effort, system_prompt):
    """Flags that leave the model with no tools, user settings, MCP servers or saved session."""
    return ['claude', '-p', '--tools', '', '--setting-sources', '', '--strict-mcp-config',
            '--no-session-persistence', '--disable-slash-commands', '--model', model,
            '--effort', effort, '--max-budget-usd', str(CALL_BUDGET_USD),
            '--output-format', 'json', '--system-prompt', system_prompt]


def run_cli(argv, stdin, cwd):
    done = subprocess.run(argv, input=stdin, cwd=cwd, capture_output=True, text=True,
                          timeout=CALL_TIMEOUT_SECONDS)
    if done.returncode != 0 and not done.stdout.strip():
        raise RuntimeError(f'claude exited {done.returncode}: {done.stderr[-300:]}')
    return done.stdout


def extract_json(text):
    """Accept one object, optionally inside one code fence. Anything else is a model error."""
    stripped = text.strip()
    fenced = FENCE.match(stripped)
    parsed = json.loads(fenced.group(1) if fenced else stripped)
    if not isinstance(parsed, dict):
        raise ValueError('model reply must be a JSON object')
    return parsed


def parse_cli_reply(stdout, model):
    observed = None
    try:
        envelope = json.loads(stdout)
        observed = envelope_usage(envelope)
        if envelope.get('is_error'):
            raise RuntimeError(f"claude reported an error: {str(envelope.get('result'))[:300]}")
        used = set(envelope.get('modelUsage', {}))
        if used != {model}:
            raise RuntimeError(f'requested {model} but claude used {sorted(used)}')
        message = extract_json(envelope['result'])
        if message.get('type') not in ('final', 'tool_call'):
            raise ValueError('model reply needs type final or tool_call')
        return {**message, 'raw_text': envelope['result'], 'usage': observed}
    except Exception as error:
        error.observed_usage = observed
        raise


class ClaudeCodeProvider:
    def __init__(self, prompt_version, model=MODEL, effort=EFFORT, runner=run_cli):
        if prompt_version not in PROMPTS:
            raise ValueError(f'unknown prompt version: {prompt_version}')
        self.prompt_version, self.model, self.effort, self.runner = prompt_version, model, effort, runner
        self.attempt_accounting = []

    @property
    def model_revision(self):
        return f'{self.model}|effort={self.effort}|prompt={self.prompt_version}|sha={prompt_sha256(self.prompt_version)}'

    def next(self, text, history, tools):
        argv = isolated_argv(self.model, self.effort, PROMPTS[self.prompt_version]['system'])
        message = user_message(self.prompt_version, text, history, tools)
        try:
            with tempfile.TemporaryDirectory(prefix='claude-study-') as empty:
                stdout = self.runner(argv, message, empty)
            reply = parse_cli_reply(stdout, self.model)
        except Exception as error:
            self.attempt_accounting.append(dict(usage=getattr(error, 'observed_usage', None), reason=type(error).__name__))
            raise
        self.attempt_accounting.append(dict(usage=reply['usage'], reason='CLI envelope observed'))
        return reply
