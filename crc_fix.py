# crc_fix.py — CRC binario MSB-first con división módulo-2 exacta
# Uso rápido:
#   python crc_fix.py --msg 11010011101100 --gen 1011
#   python crc_fix.py --hex 012345 --gen 10011  # si prefieres datos hex
import argparse

def _sanitize_bits(s:str)->str:
    s = s.strip().replace(" ", "")
    if not s or any(c not in "01" for c in s):
        raise ValueError("Solo 0/1 en cadenas de bits.")
    return s

def _bits_from_hex(h:str)->str:
    h = h.strip().replace(" ", "").lower()
    if h.startswith("0x"): h = h[2:]
    return "".join(f"{int(ch,16):04b}" for ch in h)

def crc_remainder(msg_bits:str, gen_bits:str)->str:
    """Devuelve residuo de long. len(gen)-1, con padding y recorte correctos."""
    m = _sanitize_bits(msg_bits)
    g = _sanitize_bits(gen_bits)
    if g[0] != "1": raise ValueError("El polinomio debe iniciar en 1 (coeficiente grado máximo).")
    n = len(g)
    work = [int(b) for b in m] + [0]*(n-1)     # se agregan n-1 ceros antes de dividir
    poly = [int(b) for b in g]
    # división módulo-2 MSB-first
    for i in range(len(m)):
        if work[i] == 1:
            for j in range(n):
                work[i+j] ^= poly[j]
    rem = work[-(n-1):]                        # recorte exacto
    return "".join(str(b) for b in rem).rjust(n-1, "0")

def crc_append(msg_bits:str, gen_bits:str)->str:
    """Devuelve codeword = mensaje + CRC correcto."""
    return _sanitize_bits(msg_bits) + crc_remainder(msg_bits, gen_bits)

def crc_verify(codeword_bits:str, gen_bits:str):
    """Devuelve (residuo, ok). Al ser codeword correcto, residuo es 000..0."""
    c = _sanitize_bits(codeword_bits)
    g = _sanitize_bits(gen_bits)
    if g[0] != "1": raise ValueError("El polinomio debe iniciar en 1.")
    n = len(g)
    work = [int(b) for b in c]
    poly = [int(b) for b in g]
    for i in range(len(work)-n+1):
        if work[i] == 1:
            for j in range(n):
                work[i+j] ^= poly[j]
    rem = work[-(n-1):]
    rem_str = "".join(str(b) for b in rem).rjust(n-1, "0")
    return rem_str, all(b == 0 for b in rem)

def _main():
    p = argparse.ArgumentParser()
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--msg", help="Mensaje en bits, p. ej. 11010011101100")
    src.add_argument("--hex", help="Mensaje en hex, p. ej. 012345 o 0x012345")
    p.add_argument("--gen", required=True, help="Polinomio en bits, p. ej. 1011")
    args = p.parse_args()

    msg_bits = args.msg if args.msg else _bits_from_hex(args.hex)
    gen_bits = args.gen

    crc = crc_remainder(msg_bits, gen_bits)
    codeword = crc_append(msg_bits, gen_bits)
    residuo_verif, ok = crc_verify(codeword, gen_bits)

    print(f"Mensaje           = {msg_bits}")
    print(f"Polinomio (G)     = {gen_bits}  (grado={len(gen_bits)-1})")
    print(f"CRC (a anexar)    = {crc}")
    print(f"Codeword          = {codeword}")
    print(f"Residuo verificación = {residuo_verif}  {'✔' if ok else '✗'}")

if __name__ == "__main__":
    _main()
