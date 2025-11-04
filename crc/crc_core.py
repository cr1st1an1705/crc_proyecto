from typing import List, Tuple

def bits_from_bytes(data: bytes) -> List[int]:
    bits: List[int] = []
    for b in data:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits

def bytes_from_bits(bits: List[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i:i+8]
        v = 0
        for bit in chunk:
            v = (v << 1) | (bit & 1)
        pad = (8 - len(chunk)) % 8
        v = v << pad
        out.append(v)
    return bytes(out)

def is_bitstring(s: str) -> bool:
    s2 = s.replace(" ", "")
    return len(s2) > 0 and set(s2) <= {"0", "1"}

def parse_bitstring(s: str) -> bytes:
    s2 = s.replace(" ", "")
    bits = [(1 if c == "1" else 0) for c in s2]
    return bytes_from_bits(bits)

def crc_calc(data: bytes, poly_bits: str, init: int = 0) -> int:
    n = len(poly_bits)
    if n < 1 or n > 8:
        raise ValueError("POLY_BITS debe tener entre 1 y 8 bits")
    mask = (1 << n) - 1
    poly = int(poly_bits, 2) & mask
    reg = init & mask
    for bit in bits_from_bytes(data):
        msb = (reg >> (n - 1)) & 1
        reg = ((reg << 1) & mask) | (bit & 1)
        if msb:
            reg ^= poly
    return reg & mask

def pack_lowbits(msg: bytes, poly_bits: str) -> Tuple[bytes, int]:
    n = len(poly_bits)
    crc = crc_calc(msg, poly_bits)
    last = crc & ((1 << n) - 1)
    return msg + bytes([last]), crc

def unpack_and_verify(frame: bytes, poly_bits: str):
    n = len(poly_bits)
    if not frame:
        raise ValueError("frame vacío")
    crc_recv = frame[-1] & ((1 << n) - 1)
    payload = frame[:-1]
    calc = crc_calc(payload, poly_bits)
    ok = (calc == crc_recv)
    return {
        "ok": ok,
        "payload": payload,
        "crc_recv": crc_recv,
        "crc_calc": calc,
        "n": n,
        "poly_bits": poly_bits,
        "payload_bits": "".join(str(b) for b in bits_from_bytes(payload)),
        "crc_recv_bits": format(crc_recv, f"0{n}b"),
        "crc_calc_bits": format(calc, f"0{n}b"),
    }
