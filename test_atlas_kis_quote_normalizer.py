import unittest
from atlas_kis_quote_normalizer import normalize_kis_quote

class KISNormalizerTests(unittest.TestCase):
    def test_full_rest_response(self):
        q=normalize_kis_quote({"rt_cd":"0","output":{
            "stck_prpr":"1,292,000","acml_vol":"3678841",
            "acml_tr_pbmn":"4500000000","prdy_ctrt":"-1.57"}})
        self.assertEqual(q["price"],1292000)
        self.assertEqual(q["volume"],3678841)
        self.assertEqual(q["change_pct"],-1.57)
    def test_missing_optional_is_not_zero(self):
        q=normalize_kis_quote({"stck_prpr":"1000"})
        self.assertIsNone(q["volume"])
    def test_reject_failure_and_invalid(self):
        for q in ({"rt_cd":"1","output":{"stck_prpr":"1000"}},
                  {"output":{"stck_prpr":"NaN"}},{"output":{}}):
            with self.assertRaises(ValueError):
                normalize_kis_quote(q)

if __name__=="__main__":
    unittest.main()
