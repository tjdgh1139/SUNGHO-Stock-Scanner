import io
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

    def test_reject_invalid_symbol(self):
        with self.assertRaises(SystemExit):
            main(["--db","/tmp/atlas_test.db","--symbols","BAD","--dry-run"])

if __name__=="__main__":
    unittest.main()
