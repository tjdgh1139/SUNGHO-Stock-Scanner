import io
import json
import tempfile
import types
import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
from atlas_kis_health_cli import main
from atlas_collector_heartbeat import latest_heartbeat

class KISHealthCliTests(unittest.TestCase):
    def test_dry_run_no_network(self):
        output=io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--db","unused","--health-db","unused","--symbols","000660","--dry-run"]),0)
        self.assertEqual(json.loads(output.getvalue())["status"],"DRY_RUN")
    def test_fake_kis_persists_health(self):
        token=types.ModuleType("atlas_kis_token_cache")
        token.get_token=lambda k,s:"FAKE"
        quote=types.ModuleType("atlas_kis_readonly")
        quote.QuoteRateLimited=type("QuoteRateLimited",(Exception,),{})
        quote.quote_request=lambda code,k,s,t: {"현재가":1000,"누적거래량":100,"누적거래대금":1000000,"등락%":-1}
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"quotes.sqlite")
            health=str(Path(folder)/"health.sqlite")
            with patch.dict(os.environ,{"KIS_APP_KEY":"TEST","KIS_APP_SECRET":"TEST"}),patch.dict(sys.modules,{"atlas_kis_token_cache":token,"atlas_kis_readonly":quote}),redirect_stdout(io.StringIO()):
                rc=main(["--db",db,"--health-db",health,"--symbols","000660","005930"])
            self.assertEqual(rc,0)
            self.assertEqual(latest_heartbeat(health,"KRX")["stored"],2)

    def test_http_429_stops_remaining_symbols(self):
        token=types.ModuleType("atlas_kis_token_cache")
        token.get_token=lambda k,s:"FAKE"
        quote=types.ModuleType("atlas_kis_readonly")
        quote.QuoteRateLimited=type("QuoteRateLimited",(Exception,),{})
        calls=[]
        def request(code,k,s,t):
            calls.append(code)
            raise quote.QuoteRateLimited("mock 429")
        quote.quote_request=request
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"quotes.sqlite")
            health=str(Path(folder)/"health.sqlite")
            with patch.dict(os.environ,{"KIS_APP_KEY":"TEST","KIS_APP_SECRET":"TEST"}),patch.dict(sys.modules,{"atlas_kis_token_cache":token,"atlas_kis_readonly":quote}),redirect_stdout(io.StringIO()):
                rc=main(["--db",db,"--health-db",health,"--symbols","000660","005930"])
            self.assertEqual(rc,2)
            self.assertEqual(calls,["000660"])
            self.assertEqual(latest_heartbeat(health,"KRX")["state"],"DEGRADED")

if __name__=="__main__":
    unittest.main()
