import os
import time
from helmetd_voice.recordings import save_recent


def test_save_excludes_open_and_expired_fragments(tmp_path):
    folder=tmp_path/'rolling'/'5002';folder.mkdir(parents=True)
    for i,age in enumerate((100,25,20,15,10,5,0)):
        p=folder/f'segment-{i:05}.mp4';p.write_bytes(bytes([i])*100)
        os.utime(p,(time.time()-age,time.time()-age))
    result=save_recent(tmp_path)
    assert result['saved'] and len(result['cameras']['front'])==5
    from pathlib import Path
    saved=Path(result['directory'])/'front'
    assert (saved/'00.mp4').read_bytes()==bytes([1])*100
    assert (saved/'04.mp4').read_bytes()==bytes([5])*100
    assert save_recent(tmp_path)['directory']!=result['directory']


def test_empty_buffer_never_claims_saved(tmp_path):
    assert save_recent(tmp_path)['status']=='unavailable'
