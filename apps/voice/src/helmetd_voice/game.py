"""Local game telemetry; isolated from camera detections and physical measurements."""
import threading
import time
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class GamePacket(BaseModel):
    model_config = ConfigDict(extra='forbid')
    session: str = Field(pattern=r'^[a-zA-Z0-9-]{1,64}$')
    sequence: int = Field(ge=1, le=2**53)
    paused: bool
    speed_mps: float = Field(ge=0, le=150, allow_inf_nan=False)
    gear: int = Field(ge=0, le=6)
    rpm: float = Field(ge=0, le=20000, allow_inf_nan=False)
    signal: Literal['off', 'left', 'right']
    crashed: bool
    warnings: list[Literal['left', 'right', 'rear', 'front']] = Field(max_length=4)


class GameBridge:
    def __init__(self, hud, clock=time.monotonic):
        self.hud, self.clock = hud, clock
        self.session = None
        self.sequence = 0
        self.seen = -float('inf')
        self.lock = threading.Lock()
        self.retired = set()

    def publish(self, packet):
        with self.lock:
            now = self.clock()
            if packet.session in self.retired:
                raise ValueError('Expired game session')
            if packet.session != self.session:
                if self.session and now-self.seen < 1.5 and packet.sequence != 1:
                    raise ValueError('Another game session is active')
                if self.session:
                    self.retired.add(self.session)
                self.session, self.sequence = packet.session, 0
            if packet.sequence <= self.sequence:
                raise ValueError('Out-of-order game frame')
            self.sequence, self.seen = packet.sequence, now
            mask = sum(bit for zone, bit in [('left',1),('right',2),('rear',4),('front',8)]
                       if zone in packet.warnings) if not packet.paused else 0
            command = (f'game {int(not packet.paused)} {round(packet.speed_mps*2.23694)} '
                       f'{packet.gear} {round(packet.rpm)} '
                       f'{packet.signal if not packet.paused else "off"} '
                       f'{int(packet.crashed and not packet.paused)} {mask}')
            result = self.hud.request(command)
            return {'status':result.get('status','unavailable'), 'source':'game',
                    'sequence':self.sequence}
