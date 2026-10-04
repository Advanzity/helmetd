from helmetd_voice.game_reports import GameReports,GameRoadReport

def test_reports_persist_and_deduplicate(tmp_path):
    path=tmp_path/'reports.sqlite3'
    store=GameReports(path)
    key=store.add(GameRoadReport(x=10,z=20))
    assert store.add(GameRoadReport(x=11,z=21))==key
    other=GameReports(path)
    assert len(other.list())==1
    assert other.list()[0]['source']=='rider'
