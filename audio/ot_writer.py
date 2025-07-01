 # Octatrack .ot バイナリ生成
import struct, numpy as np
from pathlib import Path
from model.sample_item import SampleItem

def write(item: SampleItem, bpm: int, slices=None):
    OT_SIZE = 0x340
    buf = bytearray(OT_SIZE)
    mv = memoryview(buf)
    mv[:4]=b'FORM'; mv[8:12]=b'DPS1'; mv[12:16]=b'SMPA'
    struct.pack_into('>I', mv, 0x17, bpm*24)
    struct.pack_into('>H', mv, 0x2B, 0x30)
    slices = slices or []; struct.pack_into('>I', mv, 0x33A, len(slices))
    for i,(st,en,lp) in enumerate(slices):
        struct.pack_into('>III', mv, 0x3A+i*12, st,en,lp)
    checksum = (0xFFFF - sum(mv[:-2]) & 0xFFFF); struct.pack_into('>H', mv, -2, checksum)
    ot_path = item.path.with_suffix('.ot')
    with open(ot_path,'wb') as f: f.write(buf)
    return ot_path
