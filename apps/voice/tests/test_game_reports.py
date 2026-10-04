from helmetd_voice.game_reports import GameReports,GameRoadReport

def test_reports_persist_and_deduplicate(tmp_path):
    path=tmp_path/'reports.sqlite3'
    store=GameReports(path)
    key=store.add(GameRoadReport(x=10,z=20))
    assert store.add(GameRoadReport(x=11,z=21))==key
    other=GameReports(path)
    assert len(other.list())==1
    assert other.list()[0]['source']=='rider'

def test_types_confidence_and_expiry(tmp_path):
    now=[100000.]
    store=GameReports(tmp_path/'hazards.db',clock=lambda:now[0])
    a=store.add(GameRoadReport(x=0,z=0,kind='debris',reporter='one'))
    assert store.add(GameRoadReport(x=1,z=1,kind='debris',reporter='one'))==a
    assert store.list()[0]['confirmations']==1
    store.add(GameRoadReport(x=1,z=1,kind='debris',reporter='two'))
    assert store.list()[0]['confidence']==.45
    assert store.add(GameRoadReport(x=0,z=0,kind='pothole'))!=a
    now[0]+=86401
    assert store.list()==[]
