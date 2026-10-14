"""Actor-free amendment scope and pre-effect refusal checks."""
import unittest
from unittest import mock
import improvement_optional_comparison_observer_amendment_v1 as a

class Amendment(unittest.TestCase):
    def test_existing_rows_cannot_use_amendment(self):
        for row in a.original.inputs.sequence()[:2]:
            with self.assertRaises(ValueError): a.admission(row)

    def test_missing_freeze_denies(self):
        with mock.patch.object(a, 'FREEZE', a.original.ROOT / 'never-created-amendment-probe.json'):
            with self.assertRaises(ValueError): a.admission(a.ROWS[0])

    def test_admission_refusal_precedes_effects(self):
        row = a.ROWS[0]
        with mock.patch.object(a, 'admission', side_effect=ValueError('denied')), \
             mock.patch.object(a.original, 'close') as close, \
             mock.patch.object(a.original, 'close_failure') as failure, \
             mock.patch.object(a.original.control, 'atomic_json') as write:
            for call in (lambda: a.select_observer(row), lambda: a.close(row, 'source', 'id'),
                         lambda: a.close_failure(row, 'source', 'id', {'type':'x','message':'x'})):
                with self.assertRaises(ValueError): call()
            close.assert_not_called(); failure.assert_not_called(); write.assert_not_called()

    def test_scoped_decoder_restores_on_closure_error(self):
        module = a.observer.original.lifecycle; saved = module.lifecycle
        def fail(*args):
            self.assertIs(module.lifecycle, a.observer.replacement.lifecycle)
            raise RuntimeError('closure error')
        with mock.patch.object(a, 'admission'), mock.patch.object(a.original, 'close', side_effect=fail):
            with self.assertRaises(RuntimeError): a.close(a.ROWS[0], 'source', 'id')
        self.assertIs(module.lifecycle, saved)

if __name__ == '__main__': unittest.main()
