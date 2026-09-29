"""Numerical TAE3 event extraction based on SoulsFormats TAE3 reader."""
import hashlib
import json
import pathlib
import struct

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'Saved/VibeUE/ReferenceReader'


def read(path):
    b = path.read_bytes()
    assert b[:4] == b'TAE ' and struct.unpack_from('<I', b, 8)[0] == 0x1000c
    tae_id, count, table = struct.unpack_from('<iiq', b, 80)
    animations = []
    for i in range(count):
        anim_id, offset = struct.unpack_from('<qq', b, table + 16*i)
        events, groups, times, anim_file, n = struct.unpack_from('<qqqqi', b, offset)
        ref, _, name, unk18, unk1c = struct.unpack_from('<qqqii', b, anim_file)
        rows = []
        for j in range(n):
            start, end, event = struct.unpack_from('<qqq', b, events + 24*j)
            kind, params = struct.unpack_from('<qq', b, event)
            rows.append({'type': kind,
                         'start': struct.unpack_from('<f', b, start)[0],
                         'end': struct.unpack_from('<f', b, end)[0],
                         'first_int': struct.unpack_from('<i', b, params)[0],
                         'raw16': b[params:params+16].hex()})
        animations.append({'id': anim_id, 'reference': bool(ref), 'ref_id': unk1c,
                           'ref_unk18': unk18, 'events': rows})
    return {'file': path.name, 'sha256': hashlib.sha256(b).hexdigest(),
            'tae_id': tae_id, 'animations': animations}


def main():
    for name in ['c0000-a00.tae', 'c0000-a23.tae', 'c5110-c5110.tae']:
        report = read(ROOT/name)
        (ROOT/(name+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(name, len(report['animations']), 'first', [a['id'] for a in report['animations'][:8]])
        for a in report['animations']:
            if name.endswith('a23.tae') and 3000 <= a['id'] < 3100 or name.endswith('a00.tae') and 600 <= a['id'] < 650:
                print(a)


if __name__ == '__main__': main()
