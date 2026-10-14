"""Pre-native startup clock negatives. No original failed observer is upgraded."""
import unittest
import improvement_question_watch_v10 as watch

class Probes(unittest.TestCase):
    def test_preparation_time_does_not_reset_original_deadline(self):
        row=watch.startup_sample(100,124,139,140,141,140)
        self.assertEqual(row['product_deadline'],1300)
        self.assertEqual(row['allocation_started_at'],100)
        self.assertFalse(row['native_qualified'])
        self.assertFalse(row['cleanup_authorized'])

    def test_pending_source_is_observed_without_phantom_completion(self):
        row=watch.startup_sample(100,124,124,125,126)
        self.assertFalse(row['native_source_observed'])
        self.assertIsNone(row['first_native_timestamp'])

    def test_continuous_pending_wait_does_not_extend_clock(self):
        row=watch.startup_sample(100,124,1200,1201,1202,1201)
        self.assertEqual(row['product_deadline'],1300)
        with self.assertRaises(ValueError):watch.startup_sample(100,124,1299,1300,1301,1300)

    def test_late_start_or_capture_rejected(self):
        for first in (123,90,100):
            with self.subTest(first=first),self.assertRaises(ValueError):watch.startup_sample(100,124,124,125,126,first)
        with self.assertRaises(ValueError):watch.startup_sample(100,124,160,161,162,125)

    def test_pending_cadence_gap_rejected(self):
        with self.assertRaises(ValueError):watch.startup_sample(100,124,124,155,156)

    def test_bool_nonfinite_and_reversed_clocks_rejected(self):
        for args in ((100,True,124,125,126),(100,124,124,125,float('nan')),(100,124,125,124,126),(100,99,124,125,126)):
            with self.subTest(args=args),self.assertRaises(ValueError):watch.startup_sample(*args)
        with self.assertRaises(ValueError):watch.startup_sample(100,124,124,125,126,True)

if __name__=='__main__':unittest.main()
