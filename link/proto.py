from typing import Dict, Any, Tuple
from crc.crc_core import bits_from_bytes, is_bitstring, parse_bitstring, crc_calc

VER = 1
TYPE_DATA = 0
TYPE_ACK  = 1
TYPE_NACK = 2

def _to_payload_bytes(text: str) -> bytes:
    if is_bitstring(text):
        return parse_bitstring(text)
    return text.encode("utf-8", "ignore")

def build_data_frame_from_input(text: str, poly_bits: str, seq: int) -> Tuple[bytes, bytes]:
    payload = _to_payload_bytes(text)
    return build_data_frame(payload, poly_bits, seq), payload

def build_data_frame(payload: bytes, poly_bits: str, seq: int) -> bytes:
    seq = seq & 0xFF
    length = len(payload)
    header = bytes([VER, TYPE_DATA, seq]) + length.to_bytes(2, "big")
    n = len(poly_bits)
    crc = crc_calc(header + payload, poly_bits) & ((1 << n) - 1)
    return header + payload + bytes([crc])

def build_ack_frame(seq: int, ok: bool, poly_bits: str) -> bytes:
    t = TYPE_ACK if ok else TYPE_NACK
    header = bytes([VER, t, seq & 0xFF]) + (0).to_bytes(2, "big")
    n = len(poly_bits)
    crc = crc_calc(header, poly_bits) & ((1 << n) - 1)
    return header + bytes([crc])

def _bits_str(b: bytes) -> str:
    return "".join(str(x) for x in bits_from_bytes(b))

def parse_frame(frame: bytes, poly_bits: str) -> Dict[str, Any]:
    if len(frame) < 5 + 1:
        raise ValueError("frame demasiado corto")
    header = frame[:5]
    ver, t, seq = header[0], header[1], header[2]
    length = int.from_bytes(header[3:5], "big")
    payload = frame[5:-1]
    if len(payload) != length:
        raise ValueError(f"LEN={length} pero payload={len(payload)}")
    n = len(poly_bits)
    crc_recv = frame[-1] & ((1 << n) - 1)
    crc_calc_val = crc_calc(header + payload, poly_bits) & ((1 << n) - 1)
    ok_crc = (crc_recv == crc_calc_val)
    return {
        "ver": ver,
        "type": t,
        "seq": seq,
        "len": length,
        "payload": payload,
        "crc_ok": ok_crc,
        "crc_recv": crc_recv,
        "crc_calc": crc_calc_val,
        "crc_recv_bits": format(crc_recv, f"0{n}b"),
        "crc_calc_bits": format(crc_calc_val, f"0{n}b"),
        "poly_bits": poly_bits,
        "header_bits": _bits_str(header),
        "payload_bits": _bits_str(payload),
        "hp_bytes": header + payload,
    }