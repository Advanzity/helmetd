"""Shared game-world reports. Never mixes virtual positions with GPS reports."""
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from pydantic import BaseModel, Field

class GameRoadReport(BaseModel):
    x: float = Field(ge=-100000, le=100000, allow_inf_nan=False)
    z: float = Field(ge=-100000, le=100000, allow_inf_nan=False)

class GameReports:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db=sqlite3.connect(path, check_same_thread=False)
        self.lock=threading.Lock()
        self.db.execute('CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, x REAL, z REAL, created REAL)')
    def list(self):
        with self.lock:
            self.db.execute('DELETE FROM reports WHERE created < ?', (time.time()-86400,))
            self.db.commit()
            return [dict(id=r[0],x=r[1],z=r[2],created=r[3],source='rider') for r in self.db.execute('SELECT * FROM reports ORDER BY created DESC LIMIT 200')]
    def add(self, report):
        with self.lock:
            existing=self.db.execute('SELECT id FROM reports WHERE abs(x-?)<8 AND abs(z-?)<8 AND created>?',(report.x,report.z,time.time()-86400)).fetchone()
            if existing:return existing[0]
            key=str(uuid.uuid4())
            self.db.execute('INSERT INTO reports VALUES (?,?,?,?)',(key,report.x,report.z,time.time()));self.db.commit();return key
