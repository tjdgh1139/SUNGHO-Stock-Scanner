from atlas_paper_no_feed_integration import verify_no_feed_paper_safety

def test_no_feed_never_creates_paper_trades():
    assert verify_no_feed_paper_safety()=="ATLAS PAPER NO-FEED SAFETY OK"
