import unittest
from atlas_strategy_promotion import StrategyEvidence,evaluate_candidate

class PromotionTests(unittest.TestCase):
    def test_only_verified_improvement_eligible(self):
        base=StrategyEvidence(150,5,8,99,True,True)
        good=StrategyEvidence(160,7,7,99,True,True)
        self.assertTrue(evaluate_candidate(good,base)["eligible"])
        self.assertEqual(evaluate_candidate(StrategyEvidence(160,7,9,99,True,True),base)["reason"],"DRAWDOWN_WORSE")
        self.assertEqual(evaluate_candidate(StrategyEvidence(160,7,7,99,True,False),base)["reason"],"CANDIDATE_UNVERIFIED")
        self.assertEqual(evaluate_candidate(StrategyEvidence(20,7,7,99,True,True),base)["reason"],"CANDIDATE_INSUFFICIENT_SAMPLE")

if __name__=="__main__":
    unittest.main()
