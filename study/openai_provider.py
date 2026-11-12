"""GPT through the official OpenAI SDK (Responses API), with the same prompts and turn rules as the Claude runs.

The frozen system prompt goes in `instructions`, the user message is identical, effort stays high, and no native
tools are offered: like the CLI runs, the model asks for the solver in its JSON reply. Needs the openai SDK and an
owner-only `.env` holding one OPENAI_API_KEY line (Xu An's loader).
"""
from pathlib import Path

from .api_provider import BILLING_WORDS, MAX_RETRIES, MAX_TOKENS, UNKNOWN_USAGE, APIProvider, parse_json_reply, whole
from .claude_provider import CALL_TIMEOUT_SECONDS, EFFORT

OPENAI_MODEL = 'gpt-6-astra'
OPENAI_KEY_FILE = Path('.env')
# USD per million tokens, standard tier, short context. Input includes cached and cache-write tokens.
OPENAI_RATES = {'input': 10.00, 'output': 50.00, 'cache_read': 1.00, 'cache_write': 12.50}


def openai_usage(usage):
    """Tokens and estimated cost in the CLI receipt shape; anything unreported stays unknown, never zero."""
    total_in, output = getattr(usage, 'input_tokens', None), getattr(usage, 'output_tokens', None)
    details = getattr(usage, 'input_tokens_details', None)
    read = getattr(details, 'cached_tokens', None) or 0
    write = getattr(details, 'cache_write_tokens', None) or 0
    if not whole(total_in, output, read, write) or read + write > total_in:
        return dict(UNKNOWN_USAGE)
    rates = OPENAI_RATES
    cost = ((total_in - read - write) * rates['input'] + read * rates['cache_read'] + write * rates['cache_write']
            + output * rates['output']) / 1_000_000
    return dict(input_tokens=total_in, output_tokens=output, cost_usd=cost)


def openai_client():
    import openai
    from responses_credentials import load_key_file
    return openai.OpenAI(api_key=load_key_file(OPENAI_KEY_FILE), max_retries=MAX_RETRIES, timeout=CALL_TIMEOUT_SECONDS)


def call_openai(client, model, effort, system, message):
    import openai
    try:
        return client.responses.create(model=model, instructions=system, input=[{'role': 'user', 'content': message}],
                                       reasoning={'effort': effort}, max_output_tokens=MAX_TOKENS, tools=[],
                                       store=False, service_tier='default')
    except openai.APIStatusError as error:
        if any(word in str(error).lower() for word in BILLING_WORDS):
            raise RuntimeError(f'usage limit (billing): {str(error)[:200]}') from None
        if isinstance(error, openai.RateLimitError):
            raise RuntimeError(f'rate limit reached: {str(error)[:200]}') from None
        raise


def same_model(returned, requested):
    """The API may answer with a dated snapshot of the requested model, such as gpt-6-astra-2026-10-01."""
    return returned == requested or str(returned).startswith(requested + '-')


def parse_openai_reply(response, model):
    observed = openai_usage(getattr(response, 'usage', None))
    try:
        if not same_model(response.model, model):
            raise RuntimeError(f'requested {model} but the API used {response.model}')
        if response.status != 'completed':
            raise RuntimeError(f'reply stopped early: {response.status} {response.incomplete_details}')
        return parse_json_reply(response.output_text, observed)
    except Exception as error:
        error.observed_usage = observed
        raise


class OpenAIProvider(APIProvider):
    transport = 'openai-api'

    def __init__(self, prompt_version, model=OPENAI_MODEL, effort=EFFORT, client_factory=openai_client, caller=call_openai):
        super().__init__(prompt_version, model, effort, client_factory, caller, parse_openai_reply)
