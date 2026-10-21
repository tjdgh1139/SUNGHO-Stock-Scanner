import unittest
from atlas_request_pacer import RequestPacer

class PacerTests(unittest.TestCase):
    def test_spacing(self):
        state={"now":0.0}
        waits=[]
        def clock(): return state["now"]
        def sleep(seconds):
            waits.append(seconds)
            state["now"]+=seconds
        p=RequestPacer(0.5,clock=clock,sleep=sleep)
        p.before_request()
        p.before_request()
        self.assertEqual(waits,[0.5])
    def test_reject_invalid(self):
        with self.assertRaises(ValueError):
            RequestPacer(0)

if __name__=="__main__":
    unittest.main()
