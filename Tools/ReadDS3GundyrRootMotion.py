"""Read installed Gundyr's extracted reference-frame motion; never modify DS3.

This reads only the observed 64-bit little-endian Havok 2014 packfile layout.
It does not decode foot bones or emulate DS3's Type 760 movement correction.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import struct
from urllib.request import Request, urlopen

import ReadDS3Archives as archives
from ReadDS3BossFlow import binder_files

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Saved/VibeUE/DS3GundyrMotion_20261005'
SHA = lambda b: hashlib.sha256(b).hexdigest()
REPO = 'Meowmaritus/SoulsAssetPipeline'
SOURCES = ['SoulsAssetPipeline/Animation/HKX/HKX.cs',
           'SoulsAssetPipeline/Animation/HKX/RootMotionData.cs',
           'SoulsAssetPipeline/Animation/HKX2/Autogen/hkaDefaultAnimatedReferenceFrame.cs',
           'SoulsAssetPipeline/Animation/HKX2/Autogen/hkaAnimatedReferenceFrame.cs',
           'SoulsAssetPipeline/Animation/HKX2/Autogen/hkaAnimation.cs',
           'SoulsAssetPipeline/Animation/HKX2/Autogen/hkReferencedObject.cs']


def fetch(url):
    return urlopen(Request(url, headers={'User-Agent': 'Battle-reference-research'}), timeout=25).read()


def reference_frame(blob):
    assert blob[:8] == bytes.fromhex('57e0e05710c0c010')
    assert struct.unpack_from('<I', blob, 12)[0] == 11
    assert blob[16:20] == bytes([8, 1, 0, 1])
    assert blob[40:55] == b'hk_2014.1.0-r1\0'
    assert struct.unpack_from('<I', blob, 20)[0] == 3
    start = 64 + struct.unpack_from('<h', blob, 62)[0]
    sections = [struct.unpack_from('<7I', blob, start+i*64+20) for i in range(3)]
    base, local, global_, virtual, exports, imports, end = sections[2]
    assert 0 <= local <= global_ <= virtual <= exports <= imports <= end
    assert base+end <= len(blob)
    fixups = {src: dst for src, dst in
              (struct.unpack_from('<2I', blob, at) for at in range(base+local, base+global_-7, 8))
              if src != 0xffffffff}
    objects = {}
    for at in range(base+virtual, base+exports-11, 12):
        src, section, name = struct.unpack_from('<3I', blob, at)
        if src == 0xffffffff:
            continue
        assert section < len(sections)
        off = sections[section][0]+name
        classname = blob[off:blob.index(b'\0', off)].decode('ascii')
        objects[classname] = src
    src = objects['hkaDefaultAnimatedReferenceFrame']
    at = base+src
    up = struct.unpack_from('<4f', blob, at+32)
    forward = struct.unpack_from('<4f', blob, at+48)
    duration, = struct.unpack_from('<f', blob, at+64)
    animation_at = base+objects['hkaSplineCompressedAnimation']
    animation_type, animation_duration = struct.unpack_from('<if', blob, animation_at+16)
    assert animation_type == 3 and abs(animation_duration-duration) < .00001
    count, capacity = struct.unpack_from('<2I', blob, at+80)
    sample_start = base+fixups[src+72]
    assert duration > 0 and 1 < count < 10000 and count <= (capacity & 0x3fffffff)
    assert sample_start+count*16 <= base+local
    frames = [list(struct.unpack_from('<4f', blob, sample_start+i*16)) for i in range(count)]
    assert all(math.isfinite(v) for frame in frames for v in frame)
    assert all(abs(v) < .00001 for v in frames[0])
    return {'up': up, 'forward': forward, 'duration': duration, 'count': count,
            'animation_header_duration': animation_duration,
            'sample_rate_observed': (count-1)/duration, 'frames': frames,
            'object_offset': src, 'sample_offset': sample_start-base}


def sample(r, time):
    x = min(max(time/r['duration']*(r['count']-1), 0), r['count']-1)
    i = int(x); j = min(i+1, r['count']-1)
    return [a+(b-a)*(x-i) for a, b in zip(r['frames'][i], r['frames'][j])]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    commit = json.loads(fetch(f'https://api.github.com/repos/{REPO}/commits/master'))['sha']
    sources = []
    for source in SOURCES:
        url = f'https://raw.githubusercontent.com/{REPO}/{commit}/{source}'
        data = fetch(url); name = source.rsplit('/', 1)[-1]
        (OUT/name).write_bytes(data)
        sources.append({'url': url, 'sha256': SHA(data), 'file': name})
    packed = archives.member('Data3', '/chr/c5110.anibnd.dcx', archives.header('Data3'))
    files = binder_files(packed)
    tae = next(data for name, data in files.items() if name.endswith('c5110.tae'))
    prior = json.loads((ROOT/'Saved/VibeUE/DS3BossFlow_20261005/manifest.json').read_text(encoding='utf-8'))
    assert SHA(tae) == next(x['sha256'] for x in prior['files'] if x.get('file') == 'c5110.tae')
    events = json.loads((ROOT/'Saved/VibeUE/DS3BossFlow_20261005/gundyr_flow_evidence.json').read_text())
    events = {a['id']: a['events'] for a in events['animations']}
    selected = [2000, 2001, 2002, 2003, 3000, 3001, 3002, 3003, 3004, 3005, 3008, 3012]
    report = {'read_only_installation': str(archives.GAME), 'decoded_binder_sha256': SHA(packed),
              'tae_sha256': SHA(tae), 'source_commit': commit, 'sources': sources, 'animations': [],
              'limits': ['Reference-frame translations, not foot bone poses or live character movement.',
                         'TAE/HKX numeric name correspondence; unreferenced base animations only.',
                         'No DS3 Type760 formula, live rate multiplier, collision or model transform simulated.',
                         'Motion times are source animation time; translation units not converted to Battle cm.']}
    for ident in selected:
        filename = f'a000_{ident:06d}.hkx'
        matches = [(name, data) for name, data in files.items() if name.replace('\\', '/').rsplit('/', 1)[-1] == filename]
        assert len(matches) == 1, filename
        name, data = matches[0]; ref = reference_frame(data)
        # Verify the matched base TAE entry is not a reference to a different animation.
        _, count, table = struct.unpack_from('<iiq', tae, 80)
        entries = {i: at for i, at in (struct.unpack_from('<qq', tae, table+j*16) for j in range(count))}
        meta, = struct.unpack_from('<q', tae, entries[ident]+24)
        assert struct.unpack_from('<q', tae, meta)[0] == 0
        record = {'animation': ident, 'archive_name': name, 'sha256': SHA(data), **ref,
                  'events': events.get(ident, [])}
        strike = [e for e in record['events'] if e['type'] == 1]
        checkpoints = sorted(set([0, .3, .6, .9, 1.2, ref['duration']] +
                                 [e[k] for e in record['events'] if e['type'] in [1, 760] for k in ['start', 'end']]))
        record['checkpoints'] = [{'time': t, 'reference_sample': sample(ref, t)} for t in checkpoints if t <= ref['duration']]
        if strike:
            record['first_hit_start'] = min(e['start'] for e in strike)
            record['root_at_first_hit'] = sample(ref, record['first_hit_start'])
        report['animations'].append(record)
        with (OUT/(filename+'.csv')).open('w', encoding='utf-8', newline='') as f:
            w = csv.writer(f);w.writerow(['source_time_s', 'x', 'y', 'z', 'yaw_component', 'translation_speed_raw_units_per_s'])
            dt = ref['duration']/(ref['count']-1)
            for i, frame in enumerate(ref['frames']):
                speed = 0 if i == 0 else math.dist(frame[:3], ref['frames'][i-1][:3])/dt
                w.writerow([i*dt, *frame, speed])
        print(filename, 'duration',round(ref['duration'],3), 'Hz',round(ref['sample_rate_observed'],3),
              'root_end', [round(x,3) for x in ref['frames'][-1]], 'hit_start',record.get('first_hit_start'))
    (OUT/'root_motion_evidence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('REPORT', OUT/'root_motion_evidence.json')


if __name__ == '__main__':
    main()
