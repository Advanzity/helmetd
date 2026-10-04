"""Save finalized rolling camera segments without touching the active fragment."""
import json
import shutil
import time
import uuid
from pathlib import Path


def save_recent(root=Path('.local/recordings')):
    root = Path(root)
    selected = {}
    for port, role in ((5002, 'front'), (5004, 'left'), (5006, 'right'), (5008, 'rear')):
        files = []
        for path in (root/'rolling'/str(port)).glob('segment-*.mp4'):
            try:
                info = path.stat()
            except FileNotFoundError:
                continue  # The bounded recorder can retire a segment during enumeration.
            files.append((info.st_mtime, info.st_size, path))
        files.sort(key=lambda item: item[0])
        # The newest fragment may not have its MP4 index yet. Save only closed files.
        finished = [path for modified, size, path in files[:-1]
                    if time.time()-modified < 40 and size > 0][-6:]
        if finished:
            selected[role] = finished
    if not selected:
        return {'status': 'unavailable', 'reason': 'No finalized camera footage yet. Allow at least 10 seconds of live video.'}
    event = root/'saved'/uuid.uuid4().hex
    event.mkdir(parents=True)
    saved = {}
    for role, files in selected.items():
        target = event/role
        target.mkdir()
        copied = []
        for i, source in enumerate(files):
            destination = target/f'{i:02}.mp4'
            try:
                shutil.copyfile(source, destination)
                copied.append(destination.name)
            except FileNotFoundError:
                destination.unlink(missing_ok=True)
        if copied:
            saved[role] = copied
    if not saved:
        return {'status': 'unavailable', 'reason': 'Camera buffer changed during save; try again.'}
    manifest = {'status': 'ok', 'saved': True, 'directory': str(event.absolute()), 'cameras': saved,
                'note': 'Up to six finalized five-second clips per camera; the current partial clip is excluded. Streams may contain gaps.'}
    (event/'manifest.json').write_text(json.dumps(manifest, indent=2))
    return manifest
