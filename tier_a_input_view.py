"""Draft v2 input view: remove fixed-ID example, preserve frozen source text."""
import hashlib
import json
from tier_a_inputs import prepare as raw_prepare, VERSION as RAW_VERSION, ARM

VERSION = 'tier-a-shared-input-view-draft-v2'
RAW_FRAGMENT = ('For an infeasible decision, a supported certificate is '
                '{"kind":"pair_order_impossible","patients":["A","E"]}: two mandatory surgeries')
VIEW_FRAGMENT = ('For an infeasible decision, use a certificate object with exactly '
                 'keys "kind" and "patients". The kind must be "pair_order_impossible" '
                 'and patients must be a list of two distinct actual mandatory surgery '
                 'IDs from this instance. The two mandatory surgeries')
SHARED = ('Solve the following controlled instance under its hard constraints and JSON '
          'answer shapes. Optional surgeries may be omitted; there is no optimization '
          'objective. FEASIBLE requires a valid schedule. INFEASIBLE requires a supported '
          'pair_order_impossible certificate; otherwise return UNKNOWN. Use actual '
          'instance surgery IDs in evidence. Priority and emergency are metadata only.')


def derive(text):
    """Exactly one literal instruction-span replacement; never edit instances."""
    if type(text) is not str or text.count(RAW_FRAGMENT) != 1:
        raise ValueError('expected exactly one frozen certificate instruction span')
    return text.replace(RAW_FRAGMENT, VIEW_FRAGMENT, 1)


def prepare(directory, arm, wrapper_version):
    if type(wrapper_version) is not str or wrapper_version != VERSION:
        raise ValueError('explicit supported v2 wrapper version required')
    raw = raw_prepare(directory, arm, RAW_VERSION)
    return tuple(dict(shared_instruction=SHARED, arm_instruction=ARM[arm],
                      instance_text=derive(p['instance_text'])) for p in raw)


def bindings(directory, arm, wrapper_version):
    """Separate evaluator receipts, never append to model-facing content."""
    view = prepare(directory, arm, wrapper_version)
    raw = raw_prepare(directory, arm, RAW_VERSION)
    def sha(text):
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    return tuple(dict(wrapper_version=VERSION,
                      transformation_sha256=sha(json.dumps([RAW_FRAGMENT, VIEW_FRAGMENT], separators=(',', ':'))),
                      raw_text_sha256=sha(a['instance_text']),
                      derived_text_sha256=sha(b['instance_text']),
                      shared_instruction_sha256=sha(SHARED),
                      arm_instruction_sha256=sha(b['arm_instruction']),
                      common_sha256=sha(json.dumps([SHARED, b['instance_text']], ensure_ascii=False, separators=(',', ':'))))
                 for a, b in zip(raw, view))
