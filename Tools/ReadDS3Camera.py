"""Read-only DS3 regulation camera export; never writes into the game directory.

Format references: Atvaark/DarkSoulsIII.FileFormats, JKAnderson/SoulsFormats,
and soulsmods/Paramdex DS3 LOCK_CAM_PARAM_ST.xml. No game asset export.
"""
from pathlib import Path
import struct, zlib, json, hashlib, xml.etree.ElementTree as ET
from urllib.request import urlopen
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

SOURCE=Path('C:/Program Files (x86)/Steam/steamapps/common/DARK SOULS III/Game/Data0.bdt')
OUT=Path('Saved/VibeUE')

def utf16(blob,offset):
    end=offset
    while blob[end:end+2]!=b'\0\0':end+=2
    return blob[offset:end].decode('utf-16le')

def binder():
    original=SOURCE.read_bytes()
    dec=Cipher(algorithms.AES(b'ds3#jn/8_7(rsY9pg55GFN7VFL#+3n/)'),modes.CBC(original[:16])).decryptor()
    dcx=dec.update(original[16:])+dec.finalize()
    assert dcx[:4]==b'DCX\0' and dcx[40:44]==b'DFLT'
    blob=zlib.decompress(dcx[0x4c:])
    assert blob[:4]==b'BND4' and blob[9]==0 and blob[10]==1
    count=struct.unpack_from('<I',blob,12)[0]
    width=struct.unpack_from('<Q',blob,32)[0]
    assert width==36 and blob[49]==0x74
    files={}
    for i in range(count):
        at=64+i*width
        size,rawsize,offset,ident,name=struct.unpack_from('<QQIiI',blob,at+8)
        data=blob[offset:offset+size]
        assert len(data)==size and size==rawsize and blob[at]==0x40
        files[utf16(blob,name)]=data
    return files,hashlib.sha256(original).hexdigest()

if __name__=='__main__':
    files,sha=binder()
    name=next(n for n in files if 'LockCamParam.param' in n)
    p=files[name]
    assert p[44:47]==bytes([0,0x85,7])
    count=struct.unpack_from('<H',p,10)[0]
    type_offset=struct.unpack_from('<Q',p,16)[0]
    param_type=p[type_offset:p.index(b'\0',type_offset)].decode('ascii')
    definition=OUT/'ReferenceReader'/'LOCK_CAM_PARAM_ST.xml'
    if not definition.exists():
        definition.parent.mkdir(parents=True,exist_ok=True)
        with urlopen('https://raw.githubusercontent.com/soulsmods/Paramdex/master/DS3/Defs/LOCK_CAM_PARAM_ST.xml',timeout=20) as response:
            definition.write_bytes(response.read())
    defs=ET.parse(definition).getroot().find('Fields')
    fields=[f.attrib['Def'].split()[1] for f in defs if f.attrib['Def'].startswith('f32 ')]
    rows=[]
    for i in range(count):
        ident,zero,offset,label=struct.unpack_from('<iiQQ',p,64+i*24)
        assert zero==0
        values=dict(zip(fields,struct.unpack_from('<'+'f'*len(fields),p,offset)))
        rows.append({'id':ident,'name':utf16(p,label) if label else '', 'values':values})
    result={'source':str(SOURCE),'source_sha256':sha,'binder_version':'01350000',
        'param_type':param_type,'field_definition':'soulsmods/Paramdex DS3/Defs/LOCK_CAM_PARAM_ST.xml','rows':rows}
    out=OUT/'ds3-camera-rows.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Exported',len(rows),'camera rows:',out,'SHA256',sha)
    for row in rows:
        print(row['id'],row['name'],{k:round(row['values'][k],4) for k in fields[:6]})
