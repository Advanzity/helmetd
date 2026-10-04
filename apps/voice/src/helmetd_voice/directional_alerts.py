"""Short, directional cues from fresh local detections, with no speech backlog."""
from .awareness import camera_observations


class DirectionalAlerts:
    def __init__(self):
        self.enabled = True
        self.seen = {}
        self.announced = set()
        self.last_play = -float('inf')

    def update(self, status, now):
        active = set()
        cameras = camera_observations(status) if status.get('status') == 'ok' else []
        live = {c['camera'] for c in cameras if c['video_fresh']}
        for key in list(self.seen):
            if key[0] not in live:
                del self.seen[key]
                self.announced.discard(key)
        for camera in cameras:
            if not camera['detection_fresh']:
                continue
            side = camera['camera']
            for item in camera['objects']:
                label = item['label']
                if label == 'PERSON' or (side in ('left', 'right', 'rear') and label in ('CAR', 'TRUCK', 'BUS', 'MOTORCYCLE', 'BICYCLE')):
                    active.add((side, "PERSON" if label == "PERSON" else "VEHICLE"))
        for key in list(self.seen):
            if key not in active and now-self.seen[key][1] >= 2:
                del self.seen[key]
                self.announced.discard(key)
        for key in active:
            first, last = self.seen.get(key, (now, now))
            if now-last > 2:
                first = now
            self.seen[key] = (first, now)
        if not self.enabled or now-self.last_play < 4:
            return None
        for key in sorted(active, key=lambda k: (k[1] != 'PERSON', k)):
            if key in self.announced or now-self.seen[key][0] < .5:
                continue
            return key
        return None

    def phrase(self, key):
        side, label = key
        suffix = {'front': '', 'rear': ' behind you', 'left': ' on the left', 'right': ' on the right'}[side]
        return f'{label.capitalize()} detected{suffix}.'

    def mark_spoken(self, key, now):
        self.announced.add(key)
        self.last_play = now
