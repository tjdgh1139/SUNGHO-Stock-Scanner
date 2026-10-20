import tempfile
import unittest
from pathlib import Path
from atlas_server_preflight import preflight

class PreflightTests(unittest.TestCase):
    def test_missing_files_are_reported_without_side_effects(self):
        with tempfile.TemporaryDirectory() as folder:
            report=preflight(folder)
            self.assertFalse(report["ready"])
            self.assertFalse(report["checks"]["atlas_kis_readonly.py"])
    def test_static_function_presence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ("atlas_market_quote_store.py","atlas_kis_collector_cli.py"):
                (root/name).write_text("# stub\n")
            (root/"atlas_kis_readonly.py").write_text("def quote_request(*args): pass\n")
            (root/"atlas_kis_token_cache.py").write_text("def get_token(*args): pass\n")
            self.assertTrue(preflight(folder)["ready"])
            (root/"atlas_kis_token_cache.py").write_text("def wrong_name(): pass\n")
            self.assertFalse(preflight(folder)["ready"])

if __name__ == "__main__":
    unittest.main()
