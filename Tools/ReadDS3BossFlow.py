"""Read selected installed DS3 boss AI/TAE files; only write under Saved.

Archive and regulation readers are reused from earlier reference research.
This exports evidence, never edits DS3 or Battle gameplay assets.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from urllib.request import urlopen
import zlib
import csv
from datetime import datetime, timezone

import ReadDS3Archives as archives
from ReadDS3Camera import binder as regulation, utf16
from ReadDS3Events import read as read_tae
from ReadDS3GundyrCamera import layout

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Saved/VibeUE/DS3BossFlow_20261005'
REFERENCE = ROOT / 'Saved/VibeUE/ReferenceReader'
SHA = lambda data: hashlib.sha256(data).hexdigest()


def binder_files(blob):
    assert blob[:4] == b'BND4' and blob[9] == 0 and blob[10] == 1
    assert blob[49] == 0x74, 'Only the observed DS3 binder format is supported'
    count = struct.unpack_from('<I', blob, 12)[0]
    width = struct.unpack_from('<Q', blob, 32)[0]
    assert width == 36
    result = {}
    for i in range(count):
        at = 64 + i * width
        size, raw_size, offset, ident, name = struct.unpack_from('<QQIiI', blob, at + 8)
        filename = utf16(blob, name) if blob[48] else blob[name:blob.index(b'\0', name)].decode('shift_jis')
        data = blob[offset:offset + size]
        if blob[at] == 0xc0:
            data = zlib.decompress(data)
        else:
            assert blob[at] == 0x40
        assert len(data) == raw_size
        result[filename] = data
    return result


def download(url, name):
    with urlopen(url, timeout=30) as response:
        data = response.read()
    (OUT / name).write_bytes(data)
    return {'url': url, 'sha256': SHA(data), 'file': name}


def param_rows(blob):
    # The installed DS3 PARAM files use 64-bit row offsets and a 64-byte header.
    assert blob[44:47] == bytes([0, 0x85, 7])
    count = struct.unpack_from('<H', blob, 10)[0]
    return {ident: offset for ident, zero, offset, label in
            (struct.unpack_from('<iiQQ', blob, 64 + i * 24) for i in range(count))}


def selected_params(reg):
    def asset(suffix):
        return reg[next(n for n in reg if n.endswith(suffix))]
    npc = asset('NpcParam.param')
    definitions, _ = layout(REFERENCE / 'NPC_PARAM_ST.xml')
    rows = param_rows(npc)
    npcs = []
    for ident in [511000, 511100]:
        values = {}
        for key in ['behaviorVariationId', 'AiThinkId', 'turnVellocity', 'hitHeight', 'hitRadius']:
            at, kind = definitions[key]
            values[key] = struct.unpack_from('<' + {'s32': 'i', 'f32': 'f'}[kind], npc, rows[ident] + at)[0]
        npcs.append({'id': ident, 'values': values})
    variation = npcs[0]['values']['behaviorVariationId']
    behavior = asset('BehaviorParam.param')
    selected = []
    for ident, at in param_rows(behavior).items():
        var, judge = struct.unpack_from('<ii', behavior, at)
        if var == variation:
            selected.append({'id': ident, 'variationId': var, 'behaviorJudgeId': judge,
                             'refType': behavior[at + 9], 'refId': struct.unpack_from('<i', behavior, at + 12)[0]})
    attacks = asset('AtkParam_Npc.param')
    attack_offsets = param_rows(attacks)
    attack_rows = []
    for ident in sorted({r['refId'] for r in selected if r['refType'] == 0}):
        if ident not in attack_offsets:
            continue
        at = attack_offsets[ident]
        # Only the fixed prefix before bitfields is read.
        attack_rows.append({'id': ident, 'radius0_3': list(struct.unpack_from('<4f', attacks, at)),
                            'dummy1_0_3': list(struct.unpack_from('<4h', attacks, at + 44)),
                            'dummy2_0_3': list(struct.unpack_from('<4h', attacks, at + 52))})
    return {'npcs': npcs, 'behavior_rows': selected, 'attack_rows_first_four_shapes': attack_rows}


def decode_events(path):
    blob = path.read_bytes()
    _, count, table = struct.unpack_from('<iiq', blob, 80)
    animations = []
    for i in range(count):
        ident, at = struct.unpack_from('<qq', blob, table + i * 16)
        event_table, _, _, _, n = struct.unpack_from('<qqqqi', blob, at)
        events = []
        for j in range(n):
            st, en, data = struct.unpack_from('<qqq', blob, event_table + j * 24)
            kind, params = struct.unpack_from('<qq', blob, data)
            if kind not in [0, 1, 224, 760]:
                continue
            row = {'type': kind, 'start': struct.unpack_from('<f', blob, st)[0],
                   'end': struct.unpack_from('<f', blob, en)[0]}
            if kind == 1:
                row['attack_type'], row['attack_index'], row['behavior_judge_id'] = struct.unpack_from('<iii', blob, params)
            elif kind == 224:
                row['turn_value'] = struct.unpack_from('<f', blob, params)[0]
            elif kind == 760:
                row['enabled'] = bool(blob[params])
                row.update(zip(['reference_dist', 'range_min', 'range_max', 'arrive_angle', 'arrive_dist'],
                               struct.unpack_from('<5f', blob, params + 4)))
                row['raw32'] = blob[params:params + 32].hex()
            else:
                row['jump_table_id'] = struct.unpack_from('<i', blob, params)[0]
            events.append(row)
        animations.append({'id': ident, 'events': events})
    return animations


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {'game': str(archives.GAME), 'read_only_game': True,
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'archives': [], 'files': [], 'public_sources': [],
                'npc_definition_sha256': SHA((REFERENCE / 'NPC_PARAM_ST.xml').read_bytes())}
    manifest['decompiler_commit'] = subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=REFERENCE / 'DSLuaDecompiler',
        check=True, capture_output=True, text=True).stdout.strip()
    hdr = archives.header('Data1')
    targets = {
        '/script/aicommon.luabnd.dcx': {'Gunda_battle.lua', 'Gunda_HU_battle.lua', 'common_battle_func.lua',
                                      'common_func.lua', 'common_func2.lua', 'common_func_FDP.lua'},
        '/script/m40_00_00_00.luabnd.dcx': {'511000_battle.lua'},
    }
    exe = REFERENCE / 'DSLuaDecompiler/DSLuaDecompiler/bin/Debug/net9.0/DSLuaDecompiler.exe'
    assert exe.exists()
    for archive_path, names in targets.items():
        blob = archives.member('Data1', archive_path, hdr)
        assert blob is not None
        manifest['archives'].append({'archive': 'Data1', 'path': archive_path, 'decoded_sha256': SHA(blob)})
        files = binder_files(blob)
        found = set()
        for path, data in files.items():
            name = path.replace('\\', '/').rsplit('/', 1)[-1]
            if name not in names:
                continue
            found.add(name)
            raw = OUT / (name + '.bytecode')
            dec = OUT / (name + '.dec.lua')
            raw.write_bytes(data)
            process = subprocess.run([str(exe), str(raw), '-o', str(dec)], capture_output=True, text=True, timeout=60)
            row = {'path': path, 'file': raw.name, 'sha256': SHA(data), 'length': len(data),
                   'decompiled_file': dec.name, 'decompiler_exit': process.returncode}
            if process.returncode:
                row['error'] = (process.stdout + process.stderr)[-1600:]
            manifest['files'].append(row)
            print('AI', name, len(data), 'decompile', process.returncode, flush=True)
        assert names == found, (names - found)
    hdr3 = archives.header('Data3')
    anim = archives.member('Data3', '/chr/c5110.anibnd.dcx', hdr3)
    manifest['archives'].append({'archive': 'Data3', 'path': '/chr/c5110.anibnd.dcx', 'decoded_sha256': SHA(anim)})
    files = binder_files(anim)
    name = next(n for n in files if n.endswith('c5110.tae'))
    tae = OUT / 'c5110.tae'
    tae.write_bytes(files[name])
    events = read_tae(tae)
    (OUT / 'c5110_events.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
    manifest['files'].append({'file': tae.name, 'sha256': SHA(files[name]), 'animation_count': len(events['animations'])})
    # Re-read installed regulation and retain evidence rows, not a guessed web table.
    reg, sha = regulation()
    manifest['regulation_sha256'] = sha
    for suffix in ['NpcParam.param', 'NpcThinkParam.param', 'BehaviorParam.param', 'AtkParam_Npc.param']:
        matches = [n for n in reg if n.endswith(suffix)]
        print('REGULATION', suffix, matches, flush=True)
    for url, name in [
        ('https://raw.githubusercontent.com/soulsmods/Paramdex/master/DS3/Defs/ATK_PARAM_ST.xml', 'ATK_PARAM_ST.xml'),
        ('https://raw.githubusercontent.com/soulsmods/Paramdex/master/DS3/Defs/BEHAVIOR_PARAM_ST.xml', 'BEHAVIOR_PARAM_ST.xml'),
        ('https://raw.githubusercontent.com/katalash/DSLuaDecompiler/master/README.md', 'DSLuaDecompiler_README.md'),
        ('https://raw.githubusercontent.com/Meowmaritus/DSAnimStudio/master/DSAnimStudioNETCore/Res/TAE.Template.DS3.xml', 'TAE.Template.DS3.xml'),
    ]:
        manifest['public_sources'].append(download(url, name))
    report = {'parameters': selected_params(reg), 'animations': decode_events(tae),
              'limits': ['installed files, not authenticated vanilla', 'TAE times are animation time, not measured wall clock',
                         'Type760 semantics follow public reverse-engineered template; movement formula is not measured',
                         'HKX trajectory/footfall count and live gameplay not measured']}
    (OUT / 'gundyr_flow_evidence.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with (OUT / 'attack_windows.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, ['animation_id', 'start', 'end', 'behavior_judge_id'])
        writer.writeheader()
        for anim in report['animations']:
            for e in anim['events']:
                if e['type'] == 1:
                    writer.writerow({'animation_id': anim['id'], 'start': e['start'], 'end': e['end'],
                                     'behavior_judge_id': e['behavior_judge_id']})
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print('REPORT', OUT / 'manifest.json')


if __name__ == '__main__':
    main()
