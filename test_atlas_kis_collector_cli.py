import io
import tempfile
from pathlib import Path
import os
import sys
import types
from unittest.mock import patch
import unittest
from contextlib import redirect_stdout
from atlas_kis_collector_cli import main

class CollectorCliTests(unittest.TestCase):
    def test_dry_run_no_api_calls(self):
        output=io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--db","/tmp/atlas_test.db","--symbols","000660","005930","000660","--dry-run"]),0)
        self.assertIn('"mode": "DRY_RUN"',output.getvalue())
        self.assertIn('"000660"',output.getvalue())

    def test_auth_error_is_redacted(self):
        fake_token=types.ModuleType("atlas_kis_token_cache")
        def bad_token(*args):
            raise RuntimeError("SECRET_SHOULD_NOT_APPEAR")
        fake_token.get_token=bad_token
        fake_quote=types.ModuleType("atlas_kis_readonly")
        fake_quote.quote_request=lambda *args,**kwargs: {"price":100}
        output=io.StringIO()
        with patch.dict(os.environ,{"KIS_APP_KEY":"test","KIS_APP_SECRET":"test"}), patch.dict(sys.modules,{"atlas_kis_token_cache":fake_token,"atlas_kis_readonly":fake_quote}), redirect_stdout(output):
            self.assertEqual(main(["--db","/tmp/unused.db","--symbols","000660"]),3)
        self.assertIn("AUTH_FAILED",output.getvalue())
        self.assertNotIn("SECRET_SHOULD_NOT_APPEAR",output.getvalue())


    def test_fake_broker_end_to_end_sqlite(self):
        fake_token=types.ModuleType("atlas_kis_token_cache")
        fake_token.get_token=lambda *args, **kwargs: "FAKE_TOKEN"
        fake_quote=types.ModuleType("atlas_kis_readonly")
        calls=[]
        def quote(symbol,key,secret,token):
            calls.append(symbol)
            return {"rt_cd":"0","output":{"stck_prpr":"1292000","acml_vol":"3678841","prdy_ctrt":"-1.57"}}
        fake_quote.quote_request=quote
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"market.sqlite")
            output=io.StringIO()
            with patch.dict(os.environ,{"KIS_APP_KEY":"test","KIS_APP_SECRET":"test"}), patch.dict(sys.modules,{"atlas_kis_token_cache":fake_token,"atlas_kis_readonly":fake_quote}), redirect_stdout(output):
                self.assertEqual(main(["--db",db,"--symbols","000660","005930"]),0)
            from atlas_market_quote_store import latest_quote
            self.assertEqual(latest_quote(db,"KRX","000660")["price"],1292000)
            self.assertEqual(latest_quote(db,"KRX","005930")["volume"],3678841)
            self.assertEqual(calls,["000660","005930"])
            self.assertIn('"stored": 2',output.getvalue())

    def test_reject_invalid_symbol(self):
        with self.assertRaises(SystemExit):
            main(["--db","/tmp/atlas_test.db","--symbols","BAD","--dry-run"])

if __name__=="__main__":
    unittest.main()
