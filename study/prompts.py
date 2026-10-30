"""Versioned prompts. Add a new version; never edit one that has produced results."""
import hashlib
import json

SYSTEM_V1 = 'You answer with exactly one JSON object and nothing else: no prose and no code fence.'

FINAL_SHAPE = ('When you have your answer, reply {"type":"final","output":OUTPUT}, where OUTPUT is one of '
               '{"status":"FEASIBLE","schedule":[{"patient":ID,"day":D,"start":S,"room":R}]}, '
               '{"status":"INFEASIBLE","certificate":{"kind":"pair_order_impossible","patients":[ID,ID]}} '
               'or {"status":"UNKNOWN"}.')

TOOL_SHAPE = ('You have one tool. To call it reply {"type":"tool_call","name":"csp","arguments":{"instance":INSTANCE}}. '
              'Tool definition: ')

REQUIRE_TOOL = ('You must call csp before giving a final answer. Translate every fact in the problem into a '
                'complete instance, then base your final answer only on the result: copy its schedule or '
                'certificate exactly. If the tool reports an error, fix your instance and call it again.')

FORMAT_EXAMPLE = {
    'schema_version': '1.1', 'days': 1, 'day_minutes': 1440,
    'surgeons': [{'id': 'sx', 'gap': 0, 'budgets': [50], 'calendar': [[[100, 150], [200, 250]]]}],
    'rooms': [{'id': 'rx', 'gap': 0, 'budgets': [50], 'calendar': [[[100, 250]]]}],
    'patients': [{'id': 'X', 'mandatory': True, 'surgeon': 'sx', 'duration': 10, 'release': 100, 'due': 150,
                  'eligible_rooms': ['rx'], 'priority': 1, 'emergency': False}]}

REQUIRE_TOOL_WITH_FORMAT = (REQUIRE_TOOL + ' Follow this format exactly. It is an unrelated example, not your problem. '
                            'schema_version is required. calendar holds one list per day, and each day is a list of '
                            '[start,end] windows, so one window on one day is [[[start,end]]]: '
                            + json.dumps(FORMAT_EXAMPLE, sort_keys=True))

PROMPTS = {'v1': {'system': SYSTEM_V1, 'tool_guidance': ''},
           'v2': {'system': SYSTEM_V1, 'tool_guidance': REQUIRE_TOOL},
           'v3': {'system': SYSTEM_V1, 'tool_guidance': REQUIRE_TOOL_WITH_FORMAT}}


def prompt_sha256(version):
    text = json.dumps(PROMPTS[version], sort_keys=True) + FINAL_SHAPE + TOOL_SHAPE
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def format_history(history):
    calls = [{'submitted_instance': h['arguments'], 'result': h['result']} for h in history]
    return 'Your earlier tool calls and their results:\n' + json.dumps(calls, sort_keys=True)


def user_message(version, text, history, tools):
    parts = [text, FINAL_SHAPE]
    if tools:
        guidance = PROMPTS[version]['tool_guidance']
        parts += [TOOL_SHAPE + json.dumps(tools[0], sort_keys=True)] + ([guidance] if guidance else [])
    if history:
        parts.append(format_history(history))
    return '\n\n'.join(parts)
