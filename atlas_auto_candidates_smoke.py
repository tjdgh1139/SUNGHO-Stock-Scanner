import streamlit as st
from atlas_auto_candidate_board import render_auto_candidate_board
render_auto_candidate_board(lambda:None,lambda *a,**k:None,
                            lambda *a,**k:(None,{}),lambda:False,
                            lambda:None,lambda:False,lambda k:"")
