"""Private restart checkpoint. Routes resume paused and never restore a live fix."""
import json
import os
import time
from pathlib import Path


class RideRestore:
    def __init__(self, path):
        self.path = Path(path)
        self.last = None

    def save(self, navigation):
        snapshot = navigation.snapshot()
        state = {key: snapshot.get(key) for key in ('route', 'preview', 'progress_m', 'route_generation')}
        text = json.dumps(state, sort_keys=True)
        if text == self.last:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as file:
            json.dump({'saved_at': time.time(), 'navigation': state}, file)
        temporary.replace(self.path)
        self.last = text

    def restore(self, navigation):
        try:
            data = json.loads(self.path.read_text())
            if not 0 <= time.time()-data['saved_at'] < 86400:
                return False
            state = data['navigation']
            for key in ('route', 'preview'):
                route = state.get(key)
                if route is not None and (not isinstance(route, dict) or not isinstance(route.get('geometry'), list)):
                    return False
            progress = float(state.get('progress_m') or 0)
            generation = int(state.get('route_generation') or 0)
        except (OSError, ValueError, TypeError, KeyError):
            return False
        navigation.route, navigation.preview = state.get('route'), state.get('preview')
        navigation.progress = max(0, progress)
        navigation.route_generation = generation
        navigation.state = 'paused' if navigation.route else 'idle'
        navigation.fix = None
        navigation.revision += 1
        navigation.notice = 'Route restored. Refresh location, then resume when ready.'
        return True
