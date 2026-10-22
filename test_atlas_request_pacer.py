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


    def test_ten_sequential_requests_offline(self):
        state={"now":0.0}
        starts=[]
        def clock(): return state["now"]
        def sleep(seconds): state["now"]+=seconds
        pacer=RequestPacer(0.5,clock=clock,sleep=sleep)
        for _ in range(10):
            pacer.before_request()
            starts.append(clock())
        self.assertEqual(len(starts),10)
        self.assertTrue(all(b-a>=0.5-1e-9 for a,b in zip(starts,starts[1:])))
        self.assertAlmostEqual(starts[-1],4.5)

    def test_slow_requests_need_no_extra_wait(self):
        state={"now":0.0}
        waits=[]
        def sleep(seconds):
            waits.append(seconds)
            state["now"]+=seconds
        pacer=RequestPacer(0.5,clock=lambda:state["now"],sleep=sleep)
        pacer.before_request()
        state["now"]=1.0
        pacer.before_request()
        self.assertEqual(waits,[])

if __name__=="__main__":
    unittest.main()
