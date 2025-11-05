from crc.crc_core import pack_lowbits, unpack_and_verify, is_bitstring, parse_bitstring

def build_frame_from_input(text: str, poly_bits: str) -> bytes:
    """
    Arma un frame listo para mandar:
    - Si 'text' parece una tira de bits ("1010 011"), lo convierte a bytes.
    - Si no, lo toma como texto y lo codifica en UTF-8.
    - Le calcula el CRC con 'poly_bits' y pega esos n bits en el último byte.
    """
    if is_bitstring(text):
        # acá interpretamos la entrada como bits crudos
        data = parse_bitstring(text)
    else:
        # acá lo tratamos como texto normal
        data = text.encode("utf-8", "ignore")

    # pack_lowbits mete el CRC (n bits bajos) al final y devuelve (frame, crc_int)
    frame, _ = pack_lowbits(data, poly_bits)
    return frame

def parse_frame(frame: bytes, poly_bits: str):
    """
    Desempaqueta y valida:
    - Separa payload y CRC embebido.
    - Recalcula con 'poly_bits' y dice si matchea.
    Devuelve un dict con ok/payload/bits útiles para debug.
    """
    return unpack_and_verify(frame, poly_bits)
