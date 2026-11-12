"""Send each turn to a frontier model through its official SDK instead of the Claude Code CLI.

The system prompt, user message and effort level are exactly those of ClaudeCodeProvider. APIProvider holds the
shared turn logic; ClaudeAPIProvider (here) and OpenAIProvider (openai_provider.py) only differ in the SDK call.
"""
from pathlib import Path

from .claude_provider import CALL_TIMEOUT_SECONDS, EFFORT, MODEL, extract_json
from .prompts import PROMPTS, prompt_sha256, user_message

MAX_TOKENS = 64000
MAX_RETRIES = 2
UNKNOWN_USAGE = dict(input_tokens=None, output_tokens=None, cost_usd=None)


def whole(*values):
    return all(type(v) is int and v >= 0 for v in values)


def parse_json_reply(text, observed):
    """The CLI's reply rules: one JSON object, optionally fenced, of type final or tool_call."""
    reply = extract_json(text)
    if reply.get('type') not in ('final', 'tool_call'):
        raise ValueError('model reply needs type final or tool_call')
    return {**reply, 'raw_text': text, 'usage': observed}


class APIProvider:
    """One SDK request per turn. Failed attempts stay in attempt_accounting with whatever usage was observed."""
    transport = None

    def __init__(self, prompt_version, model, effort, client_factory, caller, parser):
        if prompt_version not in PROMPTS:
            raise ValueError(f'unknown prompt version: {prompt_version}')
        self.prompt_version, self.model, self.effort = prompt_version, model, effort
        self.client_factory, self.caller, self.parser, self.client = client_factory, caller, parser, None
        self.attempt_accounting = []

    @property
    def model_revision(self):
        return (f'{self.model}|effort={self.effort}|prompt={self.prompt_version}|sha={prompt_sha256(self.prompt_version)}'
                f'|transport={self.transport}')

    def next(self, text, history, tools):
        message = user_message(self.prompt_version, text, history, tools)
        try:
            self.client = self.client or self.client_factory()
            received = self.caller(self.client, self.model, self.effort, PROMPTS[self.prompt_version]['system'], message)
            reply = self.parser(received, self.model)
        except Exception as error:
            self.attempt_accounting.append(dict(usage=getattr(error, 'observed_usage', None), reason=type(error).__name__))
            raise
        self.attempt_accounting.append(dict(usage=reply['usage'], reason='API usage observed'))
        return reply


# ---- Claude through the Anthropic SDK ----

CLAUDE_KEY_FILE = Path('.env.anthropic')
# USD per million tokens for claude-opus-5-5 on the standard tier; cache writes are the 5-minute rate.
CLAUDE_RATES = {'input': 4.00, 'output': 20.00, 'cache_read': 0.20, 'cache_write': 5.00}
# Messages that must stop the run, worded so run_hard.hit_usage_limit recognises them.
BILLING_WORDS = ('credit balance', 'billing', 'quota')


def claude_usage(usage):
    """Tokens and estimated cost in the CLI receipt shape; anything unreported stays unknown, never zero."""
    fresh, output = getattr(usage, 'input_tokens', None), getattr(usage, 'output_tokens', None)
    write = getattr(usage, 'cache_creation_input_tokens', None) or 0
    read = getattr(usage, 'cache_read_input_tokens', None) or 0
    if not whole(fresh, output, write, read):
        return dict(UNKNOWN_USAGE)
    rates = CLAUDE_RATES
    cost = (fresh * rates['input'] + output * rates['output'] + read * rates['cache_read'] + write * rates['cache_write']) / 1_000_000
    return dict(input_tokens=fresh + write + read, output_tokens=output, cost_usd=cost)


def claude_client():
    import anthropic
    from anthropic_sdk_client import load_key_file
    return anthropic.Anthropic(api_key=load_key_file(CLAUDE_KEY_FILE), max_retries=MAX_RETRIES, timeout=CALL_TIMEOUT_SECONDS)


def call_claude(client, model, effort, system, message):
    """One streamed request; streaming keeps long replies clear of HTTP timeouts."""
    import anthropic
    try:
        with client.messages.stream(model=model, max_tokens=MAX_TOKENS, system=system,
                                    messages=[{'role': 'user', 'content': message}],
                                    thinking={'type': 'adaptive'}, output_config={'effort': effort}) as stream:
            return stream.get_final_message()
    except anthropic.RateLimitError as error:
        raise RuntimeError(f'rate limit reached: {str(error)[:200]}') from None
    except anthropic.APIStatusError as error:
        if any(word in str(error).lower() for word in BILLING_WORDS):
            raise RuntimeError(f'usage limit (billing): {str(error)[:200]}') from None
        raise


def parse_claude_reply(message, model):
    observed = claude_usage(getattr(message, 'usage', None))
    try:
        if message.model != model:
            raise RuntimeError(f'requested {model} but the API used {message.model}')
        if message.stop_reason != 'end_turn':
            raise RuntimeError(f'reply stopped early: {message.stop_reason}')
        return parse_json_reply(''.join(block.text for block in message.content if block.type == 'text'), observed)
    except Exception as error:
        error.observed_usage = observed
        raise


class ClaudeAPIProvider(APIProvider):
    transport = 'anthropic-api'

    def __init__(self, prompt_version, model=MODEL, effort=EFFORT, client_factory=claude_client, caller=call_claude):
        super().__init__(prompt_version, model, effort, client_factory, caller, parse_claude_reply)
