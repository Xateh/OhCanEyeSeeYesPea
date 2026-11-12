"""Run a frontier model through its SDK on exactly the slots the Claude CLI runs used.

Providers: 'claude' (Anthropic API) and 'openai' (GPT through the OpenAI API). Arms: 'alone' (no tools) and
'ortools' (model + OR-Tools solver). Same prompt, effort, cases and repetitions as the CLI runs. Rows are saved as
they finish, calling again runs only slots never attempted, and new work stops at the spend limit, a rate or
billing limit, or an unknown cost. Needs the provider's SDK and key file, and ortools for the 'ortools' arm.
"""
import argparse

from surgerybench.temporal_benchmark import run_arm, score
from surgerybench.temporal_csp import CSPAdapter

from .accounting import attach
from .run_hard import RESULTS
from .run_ortools import COHORTS, PROMPT, execute, record_session

ARMS = {'alone': 'no_tools', 'ortools': 'csp'}
PROVIDERS = ('claude', 'openai')


def provider_class(name):
    if name == 'claude':
        from .api_provider import ClaudeAPIProvider
        return ClaudeAPIProvider
    if name == 'openai':
        from .openai_provider import OpenAIProvider
        return OpenAIProvider
    raise ValueError(f'unknown provider: {name}')


def folder_for(provider, arm, cohort):
    return RESULTS / f'api-{provider}-{arm}-{cohort}'


def adapter_for(arm):
    """A model alone is offered no tools; the unused adapter only satisfies the harness signature, as in run_hard."""
    if arm == 'ortools':
        from .ortools_solver import REVISION, ORToolsAdapter
        return ORToolsAdapter(), REVISION
    return CSPAdapter(), None


def evaluator_for(arm, provider_factory):
    if arm not in ARMS:
        raise ValueError(f'unknown arm: {arm}')

    def evaluate(case, gold, repetition):
        provider = provider_factory()
        adapter, revision = adapter_for(arm)
        row = attach(run_arm(provider, case['text'], ARMS[arm], adapter), provider)
        return {**row, 'case_id': case['id'], 'repetition': repetition, 'arm': ARMS[arm], 'family': gold['family'],
                'label': gold['label'], 'split': gold.get('split'), 'size': gold.get('size'), 'transport': provider.transport,
                'model_revision': provider.model_revision, 'tool_revision': revision, 'score': score(gold, row['output'])}
    return evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=PROVIDERS, required=True)
    parser.add_argument('--arm', choices=sorted(ARMS), required=True)
    parser.add_argument('--cohort', choices=sorted(COHORTS), required=True)
    parser.add_argument('--budget', type=float, required=True, help='stop new work past this estimated USD')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--limit', type=int, default=None, help='attempt at most this many new slots (smoke test)')
    args = parser.parse_args()
    make = provider_class(args.provider)
    folder = folder_for(args.provider, args.arm, args.cohort)
    remaining, spent, reason = execute(args.cohort, folder, args.budget, args.workers,
                                       evaluator_for(args.arm, lambda: make(PROMPT)), args.limit)
    if args.limit is not None and reason == 'finished' and remaining:
        reason = 'smoke_limit'
    sample, (_, revision) = make(PROMPT), adapter_for(args.arm)
    record_session(folder, args.cohort, args.budget, remaining, spent, reason,
                   {'arm': ARMS[args.arm], 'solver': revision, 'transport': sample.transport, 'model': sample.model})
    print(f'{folder}: stopped because {reason}; {remaining} slots left; ~${spent:.2f}')


if __name__ == '__main__':
    main()
