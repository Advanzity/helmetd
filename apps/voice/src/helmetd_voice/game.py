"""Local game telemetry; isolated from camera detections and physical measurements."""
import threading
import time
from typing import Literal, Annotated
from pydantic import BaseModel, Field, ConfigDict


Coordinate = Annotated[int, Field(ge=0, le=1000)]


class GameNavigation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    state: Literal['idle', 'navigating', 'paused', 'off_route', 'arrived']
    maneuver: Literal['none', 'straight', 'left', 'right', 'uturn', 'arrive']
    distance_m: int = Field(ge=0, le=10000000)
    remaining_m: int = Field(ge=0, le=10000000)
    destination: str = Field(max_length=160)
    points: list[tuple[Coordinate, Coordinate]] = Field(max_length=32)
    position: tuple[Coordinate, Coordinate]


class GamePacket(BaseModel):
    model_config = ConfigDict(extra='forbid')
    session: str = Field(pattern=r'^[a-zA-Z0-9-]{1,64}$')
    sequence: int = Field(ge=1, le=2**53)
    navigation: GameNavigation | None = None
    paused: bool
    speed_mps: float = Field(ge=0, le=150, allow_inf_nan=False)
    gear: int = Field(ge=-1, le=6)
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
        self.nav_sent = -float("inf")

    def owns_navigation(self):
        return self.clock() - self.seen < 1.5

    def publish(self, packet):
        with self.lock:
            now = self.clock()
            if packet.session in self.retired:
                raise ValueError('Expired game session')
            if packet.session != self.session:
                if self.session and now-self.seen < 1.5 and packet.paused:
                    raise ValueError('Another game session is active')
                if self.session:
                    self.retired.add(self.session)
                self.session, self.sequence = packet.session, 0
                self.nav_sent = -float("inf")
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
            if now-self.nav_sent >= .4:
                self.nav_sent = now
                nav = packet.navigation
                label = (nav.destination if nav else 'Game').encode('ascii', 'replace')[:24].hex() or '47616d65'
                state = ('paused' if packet.paused and nav and nav.state != 'idle' else nav.state) if nav else 'idle'
                response = self.hud.request(f'game_nav {state} {nav.maneuver if nav else "none"} '
                    f'{nav.distance_m if nav else 0} {nav.remaining_m if nav else 0} '
                    f'{round(nav.remaining_m/8) if nav else 0} {label}')
                points = nav.points if nav else []
                if len(points) >= 2:
                    x,y = nav.position
                    mode = 'active' if state == 'navigating' else 'preview'
                    self.hud.request(f'nav_map {mode} {x} {y} {len(points)} ' +
                                     ' '.join(f'{a} {b}' for a,b in points))
                else:
                    self.hud.request('nav_map none -1 -1 0')
                if response.get('status') != 'ok': result = response
            return {'status':result.get('status','unavailable'), 'source':'game',
                    'sequence':self.sequence}
