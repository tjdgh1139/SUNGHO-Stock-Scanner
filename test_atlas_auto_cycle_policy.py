import unittest
from atlas_auto_cycle_policy import SessionState,cycle_actions

class CyclePolicyTests(unittest.TestCase):
    def test_regular_market(self):
        result=cycle_actions(SessionState("KRX","REGULAR",True,True),outstanding_followups=2)
        self.assertIn("RESEARCH_CANDIDATES",result["actions"])
        self.assertIn("EVALUATE_PRIOR_SIGNALS",result["actions"])
    def test_closed_and_unverified(self):
        self.assertEqual(cycle_actions(SessionState("KRX","CLOSED",True,True),outstanding_followups=0)["actions"],[])
        self.assertEqual(cycle_actions(SessionState("NASDAQ","REGULAR",False,True),outstanding_followups=1)["reason"],"CALENDAR_UNVERIFIED")
    def test_feed_failure_blocks_new_scans(self):
        result=cycle_actions(SessionState("NYSE","REGULAR",True,False),outstanding_followups=1)
        self.assertEqual(result["actions"],["EVALUATE_PRIOR_SIGNALS"])

if __name__=="__main__":
    unittest.main()
