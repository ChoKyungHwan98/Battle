"""Read-only NPC -> camera association from the user's installed DS3 regulation."""
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from ReadDS3Camera import binder, utf16, SOURCE


def layout(definition):
    sizes = {'s8': 1, 'u8': 1, 's16': 2, 'u16': 2, 's32': 4, 'u32': 4,
             'f32': 4, 'dummy8': 1}
    at, bits = 0, 0
    fields = {}
    for field in ET.parse(definition).getroot().find('Fields'):
        kind, name = field.attrib['Def'].split()[:2]
        if ':' in name:
            count = int(name.split(':')[1])
            assert kind == 'u8'
            bits += count
            assert bits <= 8
            if bits == 8:
                at += 1
                bits = 0
            continue
        if bits:
            at += 1
            bits = 0
        array = re.search(r'\[(\d+)\]', name)
        count = int(array.group(1)) if array else 1
        name = name.split('[')[0]
        fields[name] = (at, kind)
        at += sizes[kind] * count
    return fields, at


if __name__ == '__main__':
    reference = Path('Saved/VibeUE/ReferenceReader')
    fields, width = layout(reference / 'NPC_PARAM_ST.xml')
    files, sha = binder()
    p = files[next(n for n in files if n.endswith('NpcParam.param'))]
    count = struct.unpack_from('<H', p, 10)[0]
    rows = [struct.unpack_from('<iiQQ', p, 64 + i * 24) for i in range(count)]
    names = dict(line.strip().split(' ', 1) for line in
                 (reference / 'NpcParam.txt').read_text(encoding='utf-8-sig').splitlines()
                 if line.strip() and ' ' in line.strip())
    cameras = {r['id']: r for r in json.loads(Path('Saved/VibeUE/ds3-camera-rows.json').read_text(encoding='utf-8'))['rows']}
    result = {'source': str(SOURCE), 'source_sha256': sha, 'npc_definition_size': width,
              'camera_id_offset': fields['lockCamParamId'][0], 'rows': []}
    for ident, zero, offset, label in rows:
        name = names.get(str(ident), '')
        if 'Gundyr' not in name:
            continue
        values = {}
        for key in ['behaviorVariationId', 'AiThinkId', 'NameId', 'lockCamParamId', 'lockCorrection',
                    'lockDist', 'pushOutCamRegionRadius', 'hitHeight', 'hitRadius']:
            at, kind = fields[key]
            fmt = {'s32': 'i', 'u8': 'B', 'f32': 'f'}[kind]
            values[key] = struct.unpack_from('<' + fmt, p, offset + at)[0]
        camera_id = values['lockCamParamId']
        result['rows'].append({'npc_id': ident, 'reference_name': name, 'values': values,
                               'camera': cameras.get(camera_id)})
    out = Path('Saved/VibeUE/ds3-gundyr-camera.json')
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
