import unittest
from atlas_ai_change_scope import review_paths

class ChangeScopeTests(unittest.TestCase):
    def test_unit_tests_and_selected_docs_allowed(self):
        self.assertTrue(review_paths(["test_atlas_quote_latency.py","ATLAS_AI_DRAFT_PR_ACTIVATION.md"])["approved"])
    def test_order_and_server_files_rejected(self):
        for path in ("app.py","atlas_kis_readonly.py",".github/workflows/deploy.yml",
                     "server/ssh_key","../test_atlas_safe.py","/tmp/test_atlas_safe.py",
                     "test_atlas_safe.py/../app.py","test_atlas_bad.py\\other"):
            self.assertFalse(review_paths([path])["approved"],path)
    def test_mixed_batch_fails_closed(self):
        self.assertFalse(review_paths(["test_atlas_ok.py","app.py"])["approved"])
    def test_empty_batch_fails_closed(self):
        self.assertFalse(review_paths([])["approved"])

if __name__=="__main__":
    unittest.main()
