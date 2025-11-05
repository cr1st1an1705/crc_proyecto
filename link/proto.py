from typing import Dict, Any, Tuple
from crc.crc_core import bits_from_bytes, is_bitstring, parse_bitstring, crc_calc

# versión de protocolo y tipos de frame
VER = 1
TYPE_DATA = 0
TYPE_ACK  = 1
TYPE_NACK = 2

def _to_payload_bytes(text: str) -> bytes:
    """
    Convierte la entrada del usuario a bytes de payload.
    - Si parece una tira de bits ("1010 011"), la parsea como bits crudos.
    - Si no, la codifica como UTF-8.
    """
    if is_bitstring(text):
        return parse_bitstring(text)
    return text.encode("utf-8", "ignore")

def build_data_frame_from_input(text: str, poly_bits: str, seq: int) -> Tuple[bytes, bytes]:
    """
    Atajo cómodo: recibe texto, lo convierte a payload y arma el frame DATA.
    Devuelve (frame, payload_original) para que quien llama pueda, por ejemplo,
    simular errores sobre el frame pero conservar el payload a mano.
    """
    payload = _to_payload_bytes(text)
    return build_data_frame(payload, poly_bits, seq), payload

def build_data_frame(payload: bytes, poly_bits: str, seq: int) -> bytes:
    """
    Arma un frame de datos:
      header = [VER(1), TYPE_DATA(1), SEQ(1), LEN(2 big-endian)]
      body   = payload
      crc    = n bits bajos del CRC(header + payload)
    Donde n = len(poly_bits) y SEQ se recorta a 0..255.
    """
    seq = seq & 0xFF                  # limitamos a 8 bits por si mandan >255
    length = len(payload)             # longitud del payload
    header = bytes([VER, TYPE_DATA, seq]) + length.to_bytes(2, "big")
    n = len(poly_bits)                # ancho del CRC
    # CRC se calcula sobre header+payload para proteger ambas partes
    crc = crc_calc(header + payload, poly_bits) & ((1 << n) - 1)
    # Empaquetamos: header | payload | 1 byte con los n bits bajos del CRC
    return header + payload + bytes([crc])

def build_ack_frame(seq: int, ok: bool, poly_bits: str) -> bytes:
    """
    Arma un ACK/NACK:
      header = [VER, TYPE_ACK o TYPE_NACK, SEQ, LEN=0]
      crc    = n bits bajos de CRC(header)
    No lleva payload, solo confirmación de un SEQ.
    """
    t = TYPE_ACK if ok else TYPE_NACK
    header = bytes([VER, t, seq & 0xFF]) + (0).to_bytes(2, "big")
    n = len(poly_bits)
    crc = crc_calc(header, poly_bits) & ((1 << n) - 1)
    return header + bytes([crc])

def _bits_str(b: bytes) -> str:
    """
    Devuelve los bits de 'b' como string "0101..." para debug bonito.
    """
    return "".join(str(x) for x in bits_from_bytes(b))

def parse_frame(frame: bytes, poly_bits: str) -> Dict[str, Any]:
    """
    Parsea y valida un frame tanto DATA como ACK/NACK.
    Estructura esperada mínima: 5 bytes de header + 1 byte de CRC.
    - Extrae ver, type, seq, len y payload.
    - Recalcula el CRC y compara con lo recibido (n bits bajos del último byte).
    - Devuelve un dict con todo lo útil para capa superior y para debug.
    """
    if len(frame) < 5 + 1:
        raise ValueError("frame demasiado corto")

    # Partimos el frame
    header = frame[:5]
    ver, t, seq = header[0], header[1], header[2]
    length = int.from_bytes(header[3:5], "big")
    payload = frame[5:-1]  # todo menos CRC final

    # Chequeo de consistencia de longitud
    if len(payload) != length:
        raise ValueError(f"LEN={length} pero payload={len(payload)}")

    # Recalculo y verificación de CRC
    n = len(poly_bits)
    crc_recv = frame[-1] & ((1 << n) - 1)                         # n bits bajos recibidos
    crc_calc_val = crc_calc(header + payload, poly_bits) & ((1 << n) - 1)  # n bits bajos calculados
    ok_crc = (crc_recv == crc_calc_val)

    # Armamos el “reporte” del frame
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
        "hp_bytes": header + payload,   # útil para mostrar división larga u otros detalles
    }
