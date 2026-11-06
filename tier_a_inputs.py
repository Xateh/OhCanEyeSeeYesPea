"""Draft offline input preparation only. No provider, tool schema or runner."""
import hashlib
import json
from pathlib import Path
from tier_a_contract import strict_json
from tier_a_handoff import inventory

VERSION = 'tier-a-shared-input-draft-v1'
SHARED = (
    'Solve the instance in the following controlled text. Follow its hard constraints '
    'and JSON answer shapes. Optional surgeries may be omitted; there is no optimization '
    'objective. A FEASIBLE answer needs a valid schedule; INFEASIBLE needs the supported '
    'pair_order_impossible certificate, otherwise return UNKNOWN. '
    'Certificate example clarification: the literal A/E pair in the frozen text is '
    'illustrative, not a supplied proof. Substitute two distinct actual mandatory '
    'surgery IDs from this instance only when both orders are impossible. '
    'Do not infer constraints from priority or emergency metadata.'
)
ARM = {
    'no_tools': 'Answer directly from the same instance text, without tools.',
    'csp': ('If a separately approved CSP tool is provided, translate only from the '
            'same instance text into its documented interface. Do not assume an '
            'interface or tool status proves infeasibility. Return evidence for '
            'the original text; unsupported proof remains UNKNOWN.')}


def prepare(directory, arm, wrapper_version):
    """Return fresh model-facing fields in frozen eligible order, never IDs/gold.

    Caller must keep inventory, routing and fingerprints outside model content.
    CSP interface and actual tool exposure are NOT implemented or agreed here.
    """
    if type(wrapper_version) is not str or wrapper_version != VERSION:
        raise ValueError('explicit supported draft wrapper version required')
    if type(arm) is not str or arm not in ARM:
        raise ValueError('unsupported arm')
    result = inventory(directory)  # full audit + exact frozen hashes first
    eligible = {c['case_id'] for c in result['cases']
                if c['use'] == 'evidence_eligible_development'}
    rows = [strict_json(line) for line in
            (Path(directory) / 'tier-a-model.jsonl').read_text().splitlines()]
    return tuple(dict(shared_instruction=SHARED, arm_instruction=ARM[arm],
                      instance_text=row['text']) for row in rows if row['case_id'] in eligible)


def fingerprint(payload):
    """Evaluator-only identity; do not append it to model-facing fields."""
    keys = {'shared_instruction', 'arm_instruction', 'instance_text'}
    if type(payload) is not dict or set(payload) != keys or any(
            type(value) is not str for value in payload.values()):
        raise ValueError('exact string-only input fields required')
    if payload['shared_instruction'] != SHARED or payload['arm_instruction'] not in ARM.values():
        raise ValueError('unsupported draft instruction')
    def sha(value):
        return hashlib.sha256(value.encode('utf-8')).hexdigest()
    common = json.dumps([payload['shared_instruction'], payload['instance_text']],
                        ensure_ascii=False, separators=(',', ':'))
    return dict(wrapper_version=VERSION, common_sha256=sha(common),
                shared_instruction_sha256=sha(SHARED),
                instance_text_sha256=sha(payload['instance_text']),
                arm_instruction_sha256=sha(payload['arm_instruction']))
