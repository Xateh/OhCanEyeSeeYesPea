"""Review-ledger consistency, not provenance authenticity or independence proof."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_tier_a_semantics as anchors

ROOT = Path(__file__).resolve().parents[1]


def load_rows(relative):
    return [json.loads(s) for s in (ROOT / relative).read_text().splitlines()]


def normalized(instance):
    """Limited normalization: metadata removal and common absolute-time shift only.

    IDs, units, ordering, durations, gaps and budgets remain significant.
    No claim of full isomorphism or absence of other structural relationships.
    """
    result = deepcopy(instance)
    offset = min(p['release'] for p in result['patients'])
    for p in result['patients']:
        p.pop('priority', None)
        p.pop('emergency', None)
        p['release'] -= offset
        p['due'] -= offset
    for kind in ('rooms', 'surgeons'):
        for resource in result[kind]:
            active = [day for day, windows in enumerate(resource['calendar']) if windows]
            resource['calendar'] = [[[a + day * 1440 - offset, b + day * 1440 - offset]
                                     for a, b in windows]
                                    for day, windows in enumerate(resource['calendar']) if windows]
            resource['budgets'] = [resource['budgets'][day] for day in active]
    result['days'] = 1
    return result


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads((ROOT / 'docs/tier-a-relative-ledger.json').read_text())
        self.gold = load_rows('fixtures/tier-a-original-synthetic-v1/tier-a-gold.jsonl')
        self.pilot = load_rows('fixtures/arrival-deadline-v1/gold.jsonl')

    def test_every_case_and_pilot_parent_reference(self):
        families = self.ledger['families']
        listed = [i for f in families for i in f['case_ids']]
        self.assertEqual(len(listed), len(set(listed)))
        self.assertEqual(set(listed), {r['case_id'] for r in self.gold})
        self.assertEqual(len(families), 10)
        self.assertEqual(self.ledger['pilot_index'], [dict(
            case_id=r['id'], family=r['family'], theme=r['theme'],
            variant=r['lineage']['variant'],
            parent_instance_sha256=r['lineage']['parent_instance_sha256']) for r in self.pilot])
        self.assertEqual(len({r['family'] for r in self.pilot}), 24)
        for family in {r['family'] for r in self.pilot}:
            relatives = [r for r in self.pilot if r['family'] == family]
            self.assertEqual(len(relatives), 2)
            self.assertEqual(len({r['lineage']['parent_instance_sha256'] for r in relatives}), 1)
            original = next(r for r in relatives if r['lineage']['variant'] == 'feasible')
            negative = next(r for r in relatives if r['lineage']['variant'] == 'deadline_minus_one')
            expected = deepcopy(original['instance'])
            expected['patients'][1]['due'] -= 1
            self.assertEqual(expected, negative['instance'])
        self.assertIn('all 48', self.ledger['conservative_split_group'])

    def test_source_symbols_exist(self):
        refs = list(self.ledger['pilot_source_refs'])
        for family in self.ledger['families']:
            refs += [family['source_ref']] + family['analytical_refs']
        for ref in refs:
            tree = ast.parse((ROOT / ref['file']).read_text())
            nodes = tree.body
            for name in ref['symbol'].split('.'):
                found = [n for n in nodes if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name]
                self.assertEqual(len(found), 1, ref)
                nodes = found[0].body
        self.assertTrue((ROOT / self.ledger['documented_reuse_ref']).is_file())

    def test_exact_analytical_instances_without_solver_or_generation(self):
        count = 0
        for family in self.ledger['families']:
            if family['analytical_relationship'] != 'exact_instance_match':
                continue
            captured = []
            def capture(test, instance, *args, **kwargs):
                captured.append(deepcopy(instance))
            with patch.object(anchors.TierASemanticsTests, 'compare', capture):
                for ref in family['analytical_refs']:
                    method = ref['symbol'].split('.')[-1]
                    test = anchors.TierASemanticsTests(method)
                    getattr(test, method)()
            for row in self.gold:
                if row['case_id'] in family['case_ids']:
                    self.assertIn(row['instance'], captured, row['case_id'])
                    count += 1
        self.assertEqual(count, 11)

    def test_no_exact_or_limited_normalized_pilot_matches(self):
        for row in self.gold:
            for pilot in self.pilot:
                self.assertNotEqual(row['instance'], pilot['instance'])
                self.assertNotEqual(normalized(row['instance']), normalized(pilot['instance']))
