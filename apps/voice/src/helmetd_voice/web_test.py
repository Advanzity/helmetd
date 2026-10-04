"""Loopback-only Mac voice test. API keys and native actions stay in Python."""

import asyncio
import json
import secrets
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .game import GameBridge, GamePacket
from .game_reports import GameReports, GameRoadReport
from .agent import configure_agent
from .copilot import Copilot, HudClient
from .navigation import NODES, PLACES, ROADS, Navigation
from .nearby import NearbyNavigation
from .road_hazards import RoadHazards
from .tool_specs import TOOLS
from .recordings import save_recent
from .pi_audio import PiAudio
from .directional_alerts import DirectionalAlerts
from .ride_restore import RideRestore
from .voice import elevenlabs_client, required

WEB = Path(__file__).resolve().parents[2] / "web"


def conversation_token():
    # A new conversation must know the current local actions. Retry on the next
    # explicit connection attempt if the provider was unreachable during setup.
    configure_agent()
    with elevenlabs_client() as client:
        return client.conversational_ai.conversations.get_webrtc_token(
            agent_id=required("ELEVENLABS_AGENT_ID")
        ).token


class Pulse(BaseModel):
    phase: Literal["listening", "speaking", "thinking", "offline"]
    volume: float = Field(ge=0, le=1, allow_inf_nan=False)


class Action(BaseModel):
    name: str = Field(max_length=64)
    parameters: dict = Field(default_factory=dict)


class HudAction(BaseModel):
    action: Literal["status", "signal", "camera", "mode", "preview", "notification"]
    value: str = Field(default="", max_length=16)


def create_web_app(
    token_factory=conversation_token, pilot_factory=Copilot, navigation=None, hud=None, hazards=None
):
    speaker = PiAudio()
    detection_alerts = DirectionalAlerts()
    guard = secrets.token_urlsafe(32)
    lock = threading.RLock()
    current = None
    restore_navigation = navigation is None
    navigation = navigation or NearbyNavigation()
    owns_hazards = hazards is None and isinstance(navigation, NearbyNavigation)
    hazards = hazards or (
        RoadHazards(navigation) if isinstance(navigation, NearbyNavigation) else None
    )
    hud = hud or HudClient()
    game = GameBridge(hud)
    checkpoint = RideRestore(hud.path.parent / 'ride-checkpoint.json') if isinstance(navigation, NearbyNavigation) else None
    if checkpoint and restore_navigation:
        checkpoint.restore(navigation)
    nav_hud = {"status": "unavailable"}

    def end():
        nonlocal current
        if current:
            previous, current = current, None
            previous.pilot.stop()

    @asynccontextmanager
    async def lifespan(_):
        async def navigate():
            nonlocal nav_hud
            while True:
                if game.owns_navigation():
                    await asyncio.sleep(.25)
                    continue
                navigation.tick()
                if checkpoint:
                    await asyncio.to_thread(checkpoint.save, navigation)
                nav_hud = await asyncio.to_thread(navigation.publish, hud)
                await asyncio.sleep(0.5)

        async def expire():
            while True:
                await asyncio.sleep(2)

                def check():
                    with lock:
                        if current and time.monotonic() - current.seen > 12:
                            end()

                await asyncio.to_thread(check)

        async def sync_hazards():
            while hazards:
                await asyncio.to_thread(hazards.refresh)
                await asyncio.sleep(30)

        async def announce_detections():
            speech = None
            speaking_cue = None
            game_spoken = None
            game_speech = None
            game_spoken_at = 0
            try:
                while True:
                    try:
                        if speech and speech.done():
                            if speech.result():
                                detection_alerts.mark_spoken(speaking_cue, time.monotonic())
                            speech = None
                        status = await asyncio.to_thread(hud.request, 'status')
                        cue = detection_alerts.update(status, time.monotonic())
                        game_cue = None
                        if status.get('game_fresh'):
                            mask = status.get('game_warning_mask', 0)
                            game_cue = ('Crash detected. Reset the ride when ready.' if status.get('game_crashed') else
                                        'Vehicle ahead.' if mask & 8 else
                                        'Vehicle on your left.' if mask & 1 else
                                        'Vehicle on your right.' if mask & 2 else
                                        'Vehicle behind.' if mask & 4 else None)
                        if game_speech and game_speech.done():
                            try:
                                if not game_speech.result(): game_spoken = None
                            except Exception:
                                game_spoken = None
                            game_speech = None
                        if not game_cue:
                            game_spoken = None
                            if game_speech:
                                speaker.cancel()
                                game_speech.cancel()
                                game_speech = None
                        if game_cue and game_cue != game_spoken and not speech and not game_speech and speaker.target() and time.monotonic()-game_spoken_at > 4:
                            volume = current.audio.volume if current else .65
                            if volume > 0:
                                game_speech = asyncio.create_task(asyncio.to_thread(speaker.speak, game_cue, volume, 3))
                                game_spoken, game_spoken_at = game_cue, time.monotonic()

                        if speech and speaking_cue:
                            source_live = status.get('status') == 'ok' and any(
                                c.get('label', '').lower() == speaking_cue[0] and c.get('fresh') is True
                                and not c.get('detection_failed', False)
                                for c in status.get('cameras', []))
                            if not source_live:
                                speaker.cancel()
                                speech.cancel()
                                speech = None
                        if cue and not speech and not game_speech and speaker.target():
                            volume = current.audio.volume if current else .65
                            if volume > 0:
                                speaking_cue = cue
                                speech = asyncio.create_task(asyncio.to_thread(
                                    speaker.speak, detection_alerts.phrase(cue), volume, 3))
                    except Exception:
                        speech = None
                    await asyncio.sleep(.25)
            finally:
                speaker.cancel()
                if speech:
                    speech.cancel()
                if game_speech:
                    game_speech.cancel()

        announcer = asyncio.create_task(announce_detections())
        watcher = asyncio.create_task(expire())
        navigator = asyncio.create_task(navigate())
        hazard_sync = asyncio.create_task(sync_hazards())
        try:
            yield
        finally:
            announcer.cancel()
            speaker.cancel()
            try:
                await announcer
            except asyncio.CancelledError:
                pass
            watcher.cancel()
            navigator.cancel()
            hazard_sync.cancel()
            try:
                await watcher
            except asyncio.CancelledError:
                pass
            try:
                await hazard_sync
            except asyncio.CancelledError:
                pass
            try:
                await navigator
            except asyncio.CancelledError:
                pass
            with lock:
                end()
            if owns_hazards:
                hazards.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def private_response(request, call_next):
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
            }
        )
        return response

    def authorize(request: Request):
        if request.headers.get(
            "origin"
        ) != f"http://{request.headers.get('host')}" or not secrets.compare_digest(
            request.headers.get("x-helmetd", ""), guard
        ):
            raise HTTPException(403, "Open the local Helmetd test page first")

    def session(request):
        if not current or not secrets.compare_digest(
            request.headers.get("x-helmetd-session", ""), current.id
        ):
            raise HTTPException(409, "This voice session has ended. Start a new conversation.")
        current.seen = time.monotonic()
        return current

    @app.get("/", response_class=HTMLResponse)
    def page():
        source = WEB / "nearby.html"
        if not source.exists():
            source = WEB / "index.html"
        return source.read_text().replace("__HELMETD_TOKEN__", guard)

    @app.get("/hud-map", response_class=HTMLResponse)
    def hud_map_page():
        return (WEB / "hud-map.html").read_text().replace("__HELMETD_TOKEN__", guard)

    game_reports = GameReports(hud.path.parent / 'game-road-reports.sqlite3')

    @app.get("/api/game/reports")
    def game_report_list():
        return {'reports': game_reports.list()}

    @app.post("/api/game/reports", dependencies=[Depends(authorize)])
    def game_report_add(body: GameRoadReport):
        return {'status':'ok', 'id':game_reports.add(body)}

    @app.get("/api/game/session")
    def game_session():
        return {"token": guard}

    @app.post("/api/game/telemetry", dependencies=[Depends(authorize)])
    def game_telemetry(packet: GamePacket):
        try:
            return game.publish(packet)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @app.post("/api/game/camera/{view}", dependencies=[Depends(authorize)])
    async def game_camera(view: Literal['front', 'left', 'right', 'rear'], request: Request):
        if request.headers.get('x-game-session') != game.session or not game.owns_navigation():
            raise HTTPException(409, "Inactive game session")
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > 640*360*4:
                raise HTTPException(413, "Camera frame too large")
        if len(payload) != 640*360*4:
            raise HTTPException(400, "Expected a 640x360 BGRA frame")
        if request.headers.get('x-game-session') != game.session or not game.owns_navigation():
            raise HTTPException(409, "Inactive game session")
        target = hud.path.parent / f"game-camera-{view}.bgra"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.tmp')
        temporary.write_bytes(payload)
        temporary.replace(target)
        return {'status': 'ok'}

    @app.post("/api/start", dependencies=[Depends(authorize)])
    def start():
        nonlocal current
        with lock:
            if current and time.monotonic() - current.seen <= 12:
                raise HTTPException(409, "A test session is already open. Stop it first.")
            end()
            try:
                token = token_factory()
            except Exception:
                raise HTTPException(502, "ElevenLabs could not connect. Try again.") from None
            audio = SimpleNamespace(active=False, speaking=False, volume=1.0, cancel_alert=speaker.cancel)
            pilot = pilot_factory(audio=audio, listener=detection_alerts, navigation=navigation, hazards=hazards)
            created = SimpleNamespace(
                id=secrets.token_urlsafe(24),
                pilot=pilot,
                audio=audio,
                seen=time.monotonic(),
                ending=False,
            )
            pilot.on_end = lambda: setattr(created, "ending", True)
            pilot.start()
            current = created
            return {"token": token, "session": created.id, "tools": [t["name"] for t in TOOLS]}

    @app.post("/api/pulse", dependencies=[Depends(authorize)])
    def pulse(body: Pulse, request: Request):
        with lock:
            live = session(request)
            live.audio.active = body.phase != "offline"
            live.audio.speaking = body.phase == "speaking"
            live.audio.volume = body.volume
            live.pilot.thinking_until = time.monotonic() + 2 if body.phase == "thinking" else 0
            updates = []
            live.pilot.awareness.publish(updates.append)
            return {"ending": live.ending, "context": updates[-1] if updates else None}

    @app.post("/api/action", dependencies=[Depends(authorize)])
    def action(body: Action, request: Request):
        with lock:
            live = session(request)
            pilot = live.pilot
        # Hazard RPCs can take seconds; don't block the browser heartbeat behind them.
        result = json.loads(pilot.call(body.name, body.parameters))
        return {"result": result, "volume": live.audio.volume}

    @app.post("/api/stop", dependencies=[Depends(authorize)])
    def stop(request: Request):
        with lock:
            session(request)
            end()
        return {"status": "ok"}

    @app.post("/api/hud/map-frame", dependencies=[Depends(authorize)])
    async def map_frame(request: Request):
        # Fixed-size BGRA frames; never accept arbitrary paths or image codecs.
        size = 640 * 360 * 4
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > size:
                raise HTTPException(413, "Map frame too large")
        if len(payload) != size:
            raise HTTPException(400, "Expected a 640x360 BGRA frame")
        target = hud.path.parent / "hud-map.bgra"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(target)
        return {"status": "ok"}

    @app.post("/api/audio/status", dependencies=[Depends(authorize)])
    def audio_status():
        return {"configured": speaker.target() is not None, "receipt_verified": False}

    @app.post("/api/audio/cancel", dependencies=[Depends(authorize)])
    def audio_cancel(request: Request):
        source = request.headers.get('x-helmetd-audio-source', 'conversation')
        speaker.cancel(2 if source == 'navigation' else 1)
        return {"status": "ok"}

    @app.post("/api/audio/pcm", dependencies=[Depends(authorize)])
    async def audio_pcm(request: Request):
        session(request)
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > 48000:
                raise HTTPException(413, "Audio chunk too large")
        if not payload or len(payload) % 2:
            raise HTTPException(400, "Expected 48 kHz mono S16LE")
        played = await asyncio.to_thread(speaker.play, bytes(payload))
        return {"status": "sent" if played else "suppressed", "receipt_verified": False}

    class SpeechCue(BaseModel):
        text: str = Field(min_length=1, max_length=500)
        volume: float = Field(default=1, ge=0, le=1, allow_inf_nan=False)

    @app.post("/api/audio/speak", dependencies=[Depends(authorize)])
    def audio_speak(body: SpeechCue):
        played = speaker.speak(body.text, body.volume)
        return {"status": "sent" if played else "cancelled", "receipt_verified": False}

    @app.post("/api/recordings/save", dependencies=[Depends(authorize)])
    def save_recording():
        result = save_recent(hud.path.parent / "recordings")
        hud.request('notice saved' if result.get('saved') else 'notice save_failed')
        return result

    @app.post("/api/hud", dependencies=[Depends(authorize)])
    def control_hud(body: HudAction):
        allowed = {
            "status": ("",),
            "notification": ("messages", "whatsapp", "phone", "music"),
            "preview": ("left", "right", "rear", "person", "turn", "message", "pothole", "debris", "roadworks", "slippery", "off"),
            "mode": ("full", "quiet"),
            "signal": ("left", "right", "off"),
            "camera": ("front", "left", "right", "rear", "auto"),
        }
        if body.value not in allowed[body.action]:
            raise HTTPException(400, "Unsupported HUD control")
        if body.action == 'notification':
            presets={'messages':'Messages Alex','whatsapp':'WhatsApp Jordan','phone':'Phone Sam','music':'Music Now_playing'}
            return hud.request('notification '+presets[body.value])
        return hud.request(f"{body.action} {body.value}".strip())

    @app.post("/api/ready", dependencies=[Depends(authorize)])
    def readiness():
        state = hud.request('status')
        frame = hud.path.parent / 'hud-map.bgra'
        target = speaker.target()
        return {'hud': state.get('status') == 'ok',
                'cameras': [{'label': c['label'], 'live': c.get('fresh', False)} for c in state.get('cameras', [])],
                'map': frame.exists() and time.time()-frame.stat().st_mtime < 3,
                'audio_configured': target is not None,
                'glasses': 'Unverified: requires Pi connection check'}

    recovery_lock = threading.Lock()
    @app.post("/api/recover", dependencies=[Depends(authorize)])
    def recover():
        if not recovery_lock.acquire(blocking=False):
            raise HTTPException(409, 'Recovery already running')
        try:
            config = json.loads((hud.path.parent/'pi-audio.json').read_text())
            host = config['host']
            import ipaddress
            ipaddress.ip_address(host)
            root = WEB.parents[2]
            with (hud.path.parent/'recovery.log').open('a') as log:
                subprocess.Popen([sys.executable, str(root/'tools/start_helmet.py'), '--pi', host],
                    cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            try:
                pi = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=3',
                    f'vyzrhalo@{host}',
                    'systemctl --user restart helmetd-display helmetd-audio; cat /sys/class/drm/card*-HDMI-A-*/status'],
                    capture_output=True, text=True, timeout=8)
                connected = 'connected' in pi.stdout.splitlines()
                return {'local': 'Startup requested', 'pi': 'Connected' if pi.returncode == 0 else 'SSH unavailable; reconnect Pi or authenticate',
                        'glasses': 'HDMI connected' if connected else 'HDMI unverified'}
            except subprocess.TimeoutExpired:
                return {'local': 'Startup requested', 'pi': 'Connection timed out', 'glasses': 'Unverified'}
        except (OSError, ValueError, KeyError):
            raise HTTPException(503, 'Pi address is not configured')
        finally:
            recovery_lock.release()

    @app.post("/api/navigation", dependencies=[Depends(authorize)])
    def navigate(body: Action):
        navigation.touch()
        try:
            if body.name == "demo":
                if not isinstance(navigation, Navigation):
                    raise ValueError("Simulation controls are disabled for real navigation")
                navigation.demo(body.parameters)
            elif body.name == "location" and isinstance(navigation, NearbyNavigation):
                navigation.location(body.parameters)
            elif body.name == "clear_location" and isinstance(navigation, NearbyNavigation):
                navigation.clear_location()
            elif body.name in ("plan", "control", "stop", "search"):
                navigation.action(body.name, body.parameters, hud)
            elif body.name != "status":
                raise ValueError("Unknown navigation command")
        except (ValueError, TypeError) as error:
            raise HTTPException(400, str(error)) from None
        data = {
            **navigation.snapshot(),
            "hud_connected": nav_hud.get("status") == "ok",
        }
        if hazards:
            data["hazards"] = hazards.snapshot(data)
        if not isinstance(navigation, Navigation):
            return data
        return {
            **data,
            "places": PLACES,
            "nodes": NODES,
            "roads": [
                {"a": a, "b": b, "name": name, "highway": highway}
                for a, b, name, _, highway in ROADS
            ],
        }

    @app.post("/api/hazards", dependencies=[Depends(authorize)])
    def hazard_action(body: Action):
        if not hazards:
            raise HTTPException(400, "Hazard reports require real navigation")
        try:
            if body.name == "report":
                return hazards.save(body.parameters)
            if body.name == "share":
                return hazards.share(body.parameters)
            if body.name == "status":
                return hazards.snapshot()
            raise ValueError("Unknown hazard action")
        except (ValueError, TypeError) as error:
            raise HTTPException(400, str(error)) from None

    app.mount("/assets", StaticFiles(directory=WEB / "dist"), name="assets")
    return app
