import json
import tempfile
import unittest
from pathlib import Path

from study.run_api import evaluator_for, folder_for
from study.run_ortools import execute, load, record_session
from tests.test_api_provider import provider, reply


def final(status):
    return reply({'type': 'final', 'output': {'status': status}})


class Evaluation(unittest.TestCase):
    def setUp(self):
        slots, self.gold = load('pilot-validation')
        self.case, _ = slots[0]

    def test_alone_arm_scores_the_reply_and_keeps_api_accounting(self):
        api, recorder = provider(final('UNKNOWN'))
        row = evaluator_for('alone', lambda: api)(self.case, self.gold[self.case['id']], 0)
        self.assertEqual((row['arm'], row['transport'], row['repetition']), ('no_tools', 'anthropic-api', 0))
        self.assertEqual(row['token_usage'], {'input_tokens': 1000, 'output_tokens': 200})
        self.assertIn('call_accounting', row)
        self.assertEqual(len(recorder.requests), 1)

    def test_unknown_arm_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluator_for('simple', lambda: None)

    def test_results_go_to_separate_api_folders(self):
        self.assertEqual(folder_for('openai', 'ortools', 'hard-n80').name, 'api-openai-ortools-hard-n80')


class Sessions(unittest.TestCase):
    def test_session_metadata_records_the_api_transport(self):
        folder = Path(tempfile.mkdtemp())
        record_session(folder, 'pilot-validation', 1.0, 0, 0.5, 'finished', {'arm': 'no_tools', 'solver': None, 'transport': 'anthropic-api'})
        meta = json.loads((folder / 'meta.json').read_text())
        self.assertEqual((meta['arm'], meta['transport'], len(meta['sessions'])), ('no_tools', 'anthropic-api', 1))

    def test_whole_cohort_runs_and_resumes_with_a_mocked_api(self):
        folder = Path(tempfile.mkdtemp()) / 'out'
        evaluate = evaluator_for('alone', lambda: provider(final('UNKNOWN'))[0])
        execute('pilot-validation', folder, budget_usd=1, workers=2, evaluator=evaluate, limit=3)
        remaining, _, reason = execute('pilot-validation', folder, budget_usd=1, workers=2, evaluator=evaluate)
        self.assertEqual((remaining, reason, len((folder / 'runs.jsonl').read_text().splitlines())), (0, 'finished', 8))


if __name__ == '__main__':
    unittest.main()
