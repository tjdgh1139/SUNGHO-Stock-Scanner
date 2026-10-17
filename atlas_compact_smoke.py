import atlas_compact_dashboard as d

class FakeTape:
    def snapshots(self):
        return {},False,""

    def stop(self):
        return None

d._quick_macro=lambda:[{"지표":name,"상태":"미수신"} for name in d.QUICK]
d.render_compact_dashboard(lambda:FakeTape(),lambda:False,lambda:False,lambda k:"")
