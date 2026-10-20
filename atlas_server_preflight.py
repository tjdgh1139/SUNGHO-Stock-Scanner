"""ATLAS read-only server compatibility preflight.

Run before deploying collector code. Never prints credentials or tokens,
never calls KIS, never changes production files.
"""
from __future__ import annotations
import json
from pathlib import Path

def preflight(project_dir: str = "/opt/atlas") -> dict:
    path = Path(project_dir)
    result = {"project_exists": path.is_dir(), "checks": {}, "ready": False}
    required = ("atlas_kis_readonly.py", "atlas_kis_token_cache.py",
                "atlas_market_quote_store.py", "atlas_kis_collector_cli.py")
    for filename in required:
        result["checks"][filename] = (path / filename).is_file()
    if not all(result["checks"].values()):
        return result
    # Inspection only; do not import arbitrary deployed modules or invoke APIs.
    import ast
    expected = {"atlas_kis_readonly.py": {"quote_request"},
                "atlas_kis_token_cache.py": {"get_token"}}
    for filename, functions in expected.items():
        try:
            tree = ast.parse((path / filename).read_text(encoding="utf-8"))
            defined = {n.name for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            result["checks"][filename + ":functions"] = functions <= defined
        except (OSError, SyntaxError, UnicodeError):
            result["checks"][filename + ":functions"] = False
    # Ensure the deployed read-only quote adapter accepts four positional args:
    # (symbol, app_key, app_secret, token). Never invoke it here.
    try:
        tree = ast.parse((path / "atlas_kis_readonly.py").read_text(encoding="utf-8"))
        quote_defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "quote_request"]
        args = quote_defs[0].args if quote_defs else None
        positional = len(args.posonlyargs) + len(args.args) if args else 0
        defaults = len(args.defaults) if args else 0
        required = positional - defaults
        result["checks"]["quote_request:four_positional_args"] = bool(args and (args.vararg or (required <= 4 <= positional)))
    except (OSError, SyntaxError, UnicodeError):
        result["checks"]["quote_request:four_positional_args"] = False
    result["ready"] = all(result["checks"].values())
    return result

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", default="/opt/atlas")
    args = parser.parse_args()
    print(json.dumps(preflight(args.project_dir), sort_keys=True))
