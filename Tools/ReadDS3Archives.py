"""Read selected installed DS3 archive members; never modify the game installation.

Layout and public keys: SoulsFormats BHD5/SFUtil and UXM Selective Unpack.
Only numerical event reports are intended for the Battle implementation.
"""
import hashlib
import json
import pathlib
import re
import struct
import zlib
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

GAME = pathlib.Path('C:/Program Files (x86)/Steam/steamapps/common/DARK SOULS III/Game')
OUT = pathlib.Path(__file__).resolve().parents[1] / 'Saved/VibeUE/ReferenceReader'


def path_hash(path):
    value = 0
    for char in '/' + path.lower().replace('\\', '/').lstrip('/'):
        value = (value * 37 + ord(char)) & 0xffffffff
    return value


def header(archive):
    key_source = (OUT / 'ArchiveKeys.cs').read_text(encoding='utf-8').split('SekiroKeys')[0]
    key = re.search(r'\["' + archive + r'"\]\s*=\s*@"([^"]+)"', key_source).group(1)
    numbers = load_pem_public_key(key.encode()).public_numbers()
    encrypted = (GAME / (archive + '.bhd')).read_bytes()
    decoded = bytearray()
    for offset in range(0, len(encrypted), 256):
        block = pow(int.from_bytes(encrypted[offset:offset+256], 'big'), numbers.e, numbers.n)
        decoded.extend(block.to_bytes(255, 'big'))
    assert decoded[:4] == b'BHD5'
    endian = '>' if decoded[4] == 0 else '<'
    count, buckets = struct.unpack_from(endian + 'ii', decoded, 16)
    entries = {}
    for i in range(count):
        n, table = struct.unpack_from(endian + 'ii', decoded, buckets + i * 8)
        for j in range(n):
            fields = struct.unpack_from(endian + 'Iiqqqq', decoded, table + j * 40)
            entries[fields[0]] = fields
    return decoded, entries, endian


def member(archive, path, hdr):
    decoded, entries, endian = hdr
    fields = entries.get(path_hash(path))
    if not fields:
        return None
    _, size, offset, _, aes_offset, raw_size = fields
    with (GAME / (archive + '.bdt')).open('rb') as stream:
        stream.seek(offset)
        data = bytearray(stream.read(size))
    if aes_offset:
        key = bytes(decoded[aes_offset:aes_offset+16])
        count, = struct.unpack_from(endian + 'i', decoded, aes_offset + 16)
        for i in range(count):
            start, end = struct.unpack_from(endian + 'qq', decoded, aes_offset + 20 + i * 16)
            if start == -1 or end == -1 or start == end:
                continue
            decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
            data[start:end] = decryptor.update(bytes(data[start:end])) + decryptor.finalize()
    data = bytes(data[:raw_size if raw_size > 0 else size])
    if data[:4] == b'DCX\0':
        dca = data.index(b'DCA\0')
        data = zlib.decompress(data[dca+8:])
    return data


def main():
    paths = ['/action/script/c0000.hks', '/action/script/common_define.hks',
             '/chr/c0000.anibnd.dcx', '/chr/c5110.anibnd.dcx', '/chr/c0000.behbnd.dcx']
    found = []
    for archive in ['Data3', 'Data1']:
        hdr = header(archive)
        print('HEADER', archive, len(hdr[1]), flush=True)
        for path in paths:
            data = member(archive, path, hdr)
            if data is None:
                continue
            filename = OUT / pathlib.Path(path).name.replace('.dcx', '')
            filename.write_bytes(data)
            row = {'archive': archive, 'path': path, 'sha256': hashlib.sha256(data).hexdigest(),
                   'length': len(data), 'magic': data[:8].hex(), 'output': str(filename)}
            found.append(row)
            print(json.dumps(row), flush=True)
        if len(found) >= 4:
            break
    (OUT / 'selected-members.json').write_text(json.dumps(found, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
