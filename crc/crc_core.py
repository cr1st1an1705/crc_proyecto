from typing import List, Tuple

def bits_from_bytes(data: bytes) -> List[int]:
    """
    Convierte bytes a una lista de bits [0/1] en orden MSB→LSB.
    Básicamente recorre cada byte y va empujando sus 8 bits de mayor a menor.
    """
    bits: List[int] = []
    for b in data:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits

def bytes_from_bits(bits: List[int]) -> bytes:
    """
    Empaqueta una lista de bits [0/1] a bytes.
    Toma de a 8, arma el entero, y si el último grupo viene incompleto lo
    desplaza a la izquierda para “rellenar” con ceros al final.
    """
    out = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i:i+8]
        v = 0
        for bit in chunk:
            v = (v << 1) | (bit & 1)
        # si no son 8 bits, metemos ceros a la derecha para completar el byte
        pad = (8 - len(chunk)) % 8
        v = v << pad
        out.append(v)
    return bytes(out)

def is_bitstring(s: str) -> bool:
    """
    Chequeo rápido: ¿la cadena contiene solo 0/1 (ignorando espacios)?
    Sirve para decidir si lo que tipeaste es “bits crudos” o texto normal.
    """
    s2 = s.replace(" ", "")
    return len(s2) > 0 and set(s2) <= {"0", "1"}

def parse_bitstring(s: str) -> bytes:
    """
    Convierte una cadena tipo "1010 111" a bytes.
    Quita espacios, mapea a [0/1], y reutiliza bytes_from_bits().
    """
    s2 = s.replace(" ", "")
    bits = [(1 if c == "1" else 0) for c in s2]
    return bytes_from_bits(bits)

def crc_calc(data: bytes, poly_bits: str, init: int = 0) -> int:
    """
    Calcula el CRC con un LFSR de n bits (n = len(poly_bits) en [1..8]).
    Implementación estándar estilo “shift left + xor con poly si MSB era 1”.
    - mask: limita el registro y el polinomio a n bits
    - reg: registro del LFSR (arranca en 'init' pero acotado a n bits)
    - por cada bit de data: shift, inyectamos bit, y si MSB previo era 1 → XOR.
    Retorna el resto final en n bits.
    """
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
    """
    Empaqueta el CRC en el último byte, usando solo los n bits bajos.
    Devuelve (frame, crc_int). El frame = msg + [crc_lowbits].
    Ojo: el CRC queda truncado a n bits y guardado tal cual en un byte.
    """
    n = len(poly_bits)
    crc = crc_calc(msg, poly_bits)
    last = crc & ((1 << n) - 1)
    return msg + bytes([last]), crc

def unpack_and_verify(frame: bytes, poly_bits: str):
    """
    Saca el CRC del último byte (n bits bajos), separa payload y verifica.
    Prepara un dict con flags, números y strings útiles para debug/impresión.
    """
    n = len(poly_bits)
    if not frame:
        raise ValueError("frame vacío")
    crc_recv = frame[-1] & ((1 << n) - 1)  # lo que vino, recortado a n bits
    payload = frame[:-1]                    # todo menos el último byte
    calc = crc_calc(payload, poly_bits)     # lo que calculamos localmente
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

def explain_crc_steps(data: bytes, poly_bits: str) -> str:
    """
    Explica paso a paso el mismo LFSR que usa crc_calc(), para entender el proceso.
    Imprime el polinomio, los bits de entrada y el estado del registro en cada paso.
    """
    n = len(poly_bits)
    if n < 1 or n > 8:
        raise ValueError("POLY_BITS debe tener entre 1 y 8 bits")
    mask = (1 << n) - 1
    poly = int(poly_bits, 2) & mask
    reg = 0  # arranque en cero para la explicación textual

    def _bits(d: bytes):
        for b in d:
            for i in range(7, -1, -1):
                yield (b >> i) & 1

    bits_in = "".join(str(b) for b in _bits(data))
    lines = []
    lines.append(f"polinomio: {poly_bits}  (n={n})")
    lines.append(f"bits de entrada: {bits_in}")
    lines.append(f"reg inicial: {format(reg, f'0{n}b')}\n")

    step = 0
    for bit in _bits(data):
        msb = (reg >> (n - 1)) & 1
        shifted = ((reg << 1) & mask) | (bit & 1)
        if msb:
            reg = shifted ^ poly
            action = f"XOR poly ({poly_bits})"
        else:
            reg = shifted
            action = "sin XOR"
        step += 1
        lines.append(
            f"paso {step:02d}: in={bit} msb={msb}  shift={format(shifted, f'0{n}b')}  -> {action}  reg={format(reg, f'0{n}b')}"
        )

    lines.append(f"\nresto final (CRC): {format(reg, f'0{n}b')}")
    return "\n".join(lines)


def explain_crc_long_division(data: bytes, poly_bits: str) -> str:
    """
    Muestra la división binaria “larga” en GF(2) estilo papel y lápiz.
    Arma el dividendo como datos + n ceros al final, y va restando (XOR) el
    generador alineado cuando el bit líder es 1. Al final reporta el residuo.
    """
    n = len(poly_bits)
    if n < 1 or n > 8:
        raise ValueError("POLY_BITS debe tener entre 1 y 8 bits")
    divisor_bits = poly_bits
    divisor = int(divisor_bits, 2)  # acá no lo usamos directo, pero queda claro

    # generamos los bits del mensaje original
    def _bits(d: bytes):
        for b in d:
            for i in range(7, -1, -1):
                yield (b >> i) & 1

    # dividendo = data_bits + n ceros
    dividend_bits = "".join(str(b) for b in _bits(data)) + "0"*n

    # trabajamos como lista mutable de '0'/'1' para ir aplicando las “restas”
    work = list(dividend_bits)
    L = len(work)

    lines = []
    lines.append(f"generador: {divisor_bits}")
    lines.append(f"trama:     {dividend_bits}\n")

    i = 0
    while i <= L - n:
        if work[i] == "1":
            # segmento actual sobre el que “restamos” (XOR) el generador
            segment = "".join(work[i:i+n])

            # resultado de la resta bit a bit, solo para mostrarlo en pantalla
            res_bits = "".join("0" if segment[j] == divisor_bits[j] else "1" for j in range(n))

            # aplicamos la resta (XOR) en el buffer de trabajo
            for j in range(n):
                work[i+j] = "0" if work[i+j] == divisor_bits[j] else "1"

            # sangría visual para alinear la resta en el “papel”
            indent = " " * i
            lines.append(f"{indent}{segment}")
            lines.append(f"{indent}{divisor_bits}")
            lines.append(f"{indent}{'-'*n}")
            lines.append(f"{indent}{res_bits}\n")
        i += 1

    # los últimos n bits son el residuo
    resto = "".join(work[-n:])
    lines.append(f"residuo:   {resto}")
    return "\n".join(lines)
