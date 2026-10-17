import streamlit as st
from atlas_paper_live_panel import render_paper_live_panel
class FakeTape:
    market=None
    def snapshots(self):
        return {},False,None
render_paper_live_panel(lambda:FakeTape())
