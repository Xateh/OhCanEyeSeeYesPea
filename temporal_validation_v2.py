"""Versioned strict schema-1.1 boundary; historical modules remain byte-frozen.

Explicit opt-in for new registrations. No corpus/protocol membership is changed.
Uses independent intended-instance checks, never substitutes translated gold.
"""
from copy import deepcopy
from surgerybench import temporal_check as frozen_check
from surgerybench import temporal_text as frozen_text
from surgerybench import temporal_csp as frozen_csp
from surgerybench.temporal_benchmark import score as frozen_score

REVISION = 'temporal-strict-validation-v2'
SCHEMA_VERSION = '1.1'


def structural_errors(i):
    """Require the documented JSON object/array shape before semantic checks.

    Unknown fields fail closed: they may be misspelled or unsupported constraints.
    Empty arrays are permitted; resource references and mandatory work are checked
    by the independent semantic validator below.
    """
    root = {'schema_version', 'days', 'day_minutes', 'surgeons', 'rooms', 'patients'}
    resource = {'id', 'gap', 'budgets', 'calendar'}
    patient = {'id', 'mandatory', 'surgeon', 'duration', 'release', 'due',
               'eligible_rooms', 'priority'}
    if not isinstance(i, dict) or set(i) != root:
        return ['temporal instance requires exactly the documented top-level fields']
    for kind in ('surgeons', 'rooms', 'patients'):
        if not isinstance(i[kind], list):
            return [kind + ' must be an array']
    for kind in ('surgeons', 'rooms'):
        for r in i[kind]:
            if not isinstance(r, dict) or set(r) != resource:
                return ['resource requires exactly id, gap, budgets and calendar']
            if not isinstance(r['budgets'], list) or not isinstance(r['calendar'], list):
                return ['resource budgets and calendar must be arrays']
            for day in r['calendar']:
                if not isinstance(day, list):
                    return ['each calendar day must be an array']
                if any(not isinstance(w, list) or len(w) != 2 for w in day):
                    return ['calendar windows must be two-element arrays']
    for p in i['patients']:
        if not isinstance(p, dict) or not patient <= set(p) <= patient | {'emergency'}:
            return ['patient requires documented fields and optional emergency only']
        if not isinstance(p['eligible_rooms'], list):
            return ['room eligibility must be an array']
    return []


def schema_errors(i):
    errors = structural_errors(i)
    return errors if errors else frozen_check.schema_errors(i)


def normalize_instance(i):
    """Validated copy; only omitted emergency metadata defaults to false."""
    errors = schema_errors(i)
    if errors:
        raise ValueError(errors)
    result = deepcopy(i)
    for patient in result['patients']:
        patient.setdefault('emergency', False)
    return result


def render(i):
    """Same original text bytes for populated metadata; never mutates input."""
    return frozen_text.render(normalize_instance(i))


def parse(text):
    result = frozen_text.parse(text)
    errors = schema_errors(result)
    if errors:
        raise ValueError(errors)
    return result


def check_schedule(i, schedule):
    errors = schema_errors(i)
    return errors if errors else frozen_check.check_schedule(i, schedule)


def check_certificate(i, certificate):
    return not schema_errors(i) and frozen_check.check_certificate(i, certificate)


def solve(i, max_nodes=100000, seconds=2):
    errors = schema_errors(i)
    if errors:
        raise ValueError(errors)
    return frozen_csp.solve(i, max_nodes=max_nodes, seconds=seconds)


def score(gold, output):
    """Validate intended schema first; retain the original scoring contract."""
    errors = schema_errors(gold['instance'])
    if errors:
        raise ValueError(errors)
    return frozen_score(gold, output)


class CSPAdapter:
    revision = REVISION
    tool_definition = deepcopy(frozen_csp.TOOL)

    def invoke(self, arguments):
        if not isinstance(arguments, dict) or set(arguments) != {'instance'}:
            raise ValueError('only a model-translated instance is accepted')
        return solve(arguments['instance'])
