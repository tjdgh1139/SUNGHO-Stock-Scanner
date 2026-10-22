"""Conservative file-scope gate for future AI-generated draft PRs.

This is defense-in-depth, not a sandbox or authorization boundary.
"""
from pathlib import PurePosixPath

SAFE_PREFIXES=("test_atlas_",)
SAFE_DOCS=("ATLAS_AI_DRAFT_PR_ACTIVATION.md","ATLAS_UNATTENDED_DEVELOPMENT.md")

def review_paths(paths):
    rejected=[]
    for path in paths:
        if not isinstance(path,str) or not path or "\\" in path:
            rejected.append(path)
            continue
        p=PurePosixPath(path)
        if p.is_absolute() or ".." in p.parts or len(p.parts)!=1:
            rejected.append(path)
            continue
        name=p.name
        if name in SAFE_DOCS or (name.startswith(SAFE_PREFIXES) and name.endswith(".py")):
            continue
        rejected.append(path)
    return {"approved":not rejected and bool(paths),"rejected":rejected}

def main(argv=None):
    import argparse
    import json
    import sys
    p=argparse.ArgumentParser()
    p.add_argument("paths",nargs="+")
    args=p.parse_args(argv)
    result=review_paths(args.paths)
    print(json.dumps(result))
    return 0 if result["approved"] else 2

if __name__=="__main__":
    raise SystemExit(main())
