from crc.crc_core import pack_lowbits, unpack_and_verify, is_bitstring, parse_bitstring

def build_frame_from_input(text: str, poly_bits: str) -> bytes:
    if is_bitstring(text):
        data = parse_bitstring(text)
    else:
        data = text.encode("utf-8", "ignore")
    frame, _ = pack_lowbits(data, poly_bits)
    return frame

def parse_frame(frame: bytes, poly_bits: str):
    return unpack_and_verify(frame, poly_bits)
