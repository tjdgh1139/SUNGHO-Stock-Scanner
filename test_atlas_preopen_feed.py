from datetime import datetime,timezone,timedelta
import json
from atlas_preopen_feed import read_snapshot

NOW=datetime(2026,10,18,22,0,tzinfo=timezone.utc)

def sample(stage="first_0700",now=NOW):
    return {"schema_version":1,"market":"KR","session_date":"20261019",
            "stage":stage,"generated_at_utc":now.isoformat(),
            "candidates":[{"symbol":"000660","name":"SK hynix","sector":"memory",
                           "score":80,"source_urls":["https://example.org/filing"]}]}

def write(tmp_path,p):
    path=tmp_path/"snapshot.json"
    path.write_text(json.dumps(p),encoding="utf-8")
    return path

def test_first_premarket_snapshot(tmp_path):
    assert read_snapshot(write(tmp_path,sample()),now=NOW)["candidates"][0]["symbol"]=="000660"

def test_refresh_snapshot(tmp_path):
    t=NOW+timedelta(minutes=55)
    assert read_snapshot(write(tmp_path,sample("refresh_0755",t)),now=t)

def test_wrong_date_and_stage_rejected(tmp_path):
    p=sample();p["session_date"]="20261020"
    assert read_snapshot(write(tmp_path,p),now=NOW) is None
    p=sample("refresh_0755")
    assert read_snapshot(write(tmp_path,p),now=NOW) is None

def test_old_snapshot_not_live(tmp_path):
    assert read_snapshot(write(tmp_path,sample()),now=NOW+timedelta(hours=4)) is None

def test_unverified_source_rejected(tmp_path):
    p=sample();p["candidates"][0]["source_urls"]=[]
    assert read_snapshot(write(tmp_path,p),now=NOW) is None

def test_missing_file_is_not_fake_candidates(tmp_path):
    assert read_snapshot(tmp_path/"missing.json",now=NOW) is None
