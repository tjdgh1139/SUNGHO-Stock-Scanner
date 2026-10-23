import unittest
from types import SimpleNamespace
from atlas_engine_health import evaluate_cycle

class EngineHealthTests(unittest.TestCase):
    def test_invalid_counters_fail_closed(self):
        bad=SimpleNamespace(attempted="2",stored=2,duplicates=0,failed={})
        self.assertEqual(evaluate_cycle(bad,expected=2).reason,"INVALID_COUNTERS")
        bad2=SimpleNamespace(attempted=True,stored=1,duplicates=0,failed={})
        self.assertEqual(evaluate_cycle(bad2,expected=1).state,"HALTED")

    def test_good_and_failure_states(self):
        def cycle(a,s,d,f):
            return SimpleNamespace(attempted=a,stored=s,duplicates=d,failed={str(i):"Error" for i in range(f)})
        self.assertEqual(evaluate_cycle(cycle(2,2,0,0),expected=2).state,"HEALTHY")
        self.assertEqual(evaluate_cycle(cycle(2,1,0,1),expected=2).state,"DEGRADED")
        self.assertEqual(evaluate_cycle(cycle(2,0,2,0),expected=2).reason,"NO_NEW_OBSERVATIONS")
        self.assertEqual(evaluate_cycle(cycle(2,1,0,0),expected=2).state,"HALTED")
        self.assertEqual(evaluate_cycle(cycle(2,2,0,0),expected=3).state,"DEGRADED")

if __name__=="__main__":
    unittest.main()
