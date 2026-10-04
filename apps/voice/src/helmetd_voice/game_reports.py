"""Anonymous local game-world reports. Virtual coordinates never represent GPS."""
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field

class GameRoadReport(BaseModel):
    x: float = Field(ge=-100000, le=100000, allow_inf_nan=False)
    z: float = Field(ge=-100000, le=100000, allow_inf_nan=False)
    kind: Literal['pothole','debris','roadworks','slippery','blocked_lane','stopped_vehicle','dangerous_intersection','near_miss','impact'] = 'pothole'
    reporter: str = Field(default='local', pattern=r'^[a-zA-Z0-9-]{1,64}$')

class GameReports:
    def __init__(self, path, clock=time.time):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.clock=clock
        self.db=sqlite3.connect(path, check_same_thread=False)
        self.lock=threading.Lock()
        self.db.execute('CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, x REAL, z REAL, created REAL)')
        columns={r[1] for r in self.db.execute('PRAGMA table_info(reports)')}
        if 'kind' not in columns:self.db.execute("ALTER TABLE reports ADD COLUMN kind TEXT NOT NULL DEFAULT 'pothole'")
        self.db.execute('CREATE TABLE IF NOT EXISTS confirmations (report TEXT, reporter TEXT, PRIMARY KEY(report,reporter))')
        self.db.commit()
    def list(self):
        with self.lock:
            self.db.execute('DELETE FROM reports WHERE created < ?', (self.clock()-86400,))
            self.db.execute('DELETE FROM confirmations WHERE report NOT IN (SELECT id FROM reports)')
            self.db.commit()
            rows=self.db.execute('SELECT id,x,z,created,kind,(SELECT count(*) FROM confirmations WHERE report=reports.id) FROM reports ORDER BY created DESC LIMIT 200')
            return [dict(id=r[0],x=r[1],z=r[2],created=r[3],kind=r[4],source='rider',confirmations=r[5],confidence=round(min(.9,.3+.15*max(0,r[5]-1))*max(0,1-(self.clock()-r[3])/86400),2),expires=r[3]+86400) for r in rows]
    def add(self, report):
        with self.lock:
            existing=self.db.execute('SELECT id FROM reports WHERE (x-?)*(x-?)+(z-?)*(z-?)<64 AND kind=? AND created>?',(report.x,report.x,report.z,report.z,report.kind,self.clock()-86400)).fetchone()
            key=existing[0] if existing else str(uuid.uuid4())
            if not existing:self.db.execute('INSERT INTO reports (id,x,z,created,kind) VALUES (?,?,?,?,?)',(key,report.x,report.z,self.clock(),report.kind))
            self.db.execute('INSERT OR IGNORE INTO confirmations VALUES (?,?)',(key,report.reporter))
            self.db.commit()
            return key
