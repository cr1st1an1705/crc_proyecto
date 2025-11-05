import os
import threading
import time
import tkinter as tk
from tkinter import scrolledtext
from tkinter import font as tkfont

from link.tcp_peer import TcpPeer
from link.proto import (
    build_data_frame_from_input,
    build_data_frame,
    build_ack_frame,
    parse_frame,
    TYPE_DATA, TYPE_ACK, TYPE_NACK
)

# acá intentamos importar una explicación "bonita" de CRC si existe.
# si no está, dejamos una función dummy que devuelve string vacío.
try:
    from crc.crc_core import explain_crc_long_division as explain_crc
except Exception:
    try:
        from crc.crc_core import explain_crc_math as explain_crc
    except Exception:
        def explain_crc(data, poly_bits): return ""

def load_env(path=".env"):
    """
    acá leemos variables sencillas desde un .env local.
    Formato: CLAVE=valor por línea. Ignoramos comentarios y líneas vacías.
    """
    env = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

class App:
    def __init__(self, master):
        # cargamos config de entorno: rol, ip/puerto local y del peer, y polinomio CRC
        self.env = load_env()
        self.role = self.env.get("ROLE", "servidor")
        self.host = self.env.get("HOST", "0.0.0.0")
        self.port = int(self.env.get("PORT", "5000"))
        self.peer_host = self.env.get("PEER_HOST", "127.0.0.1")
        self.peer_port = int(self.env.get("PEER_PORT", "5000"))
        self.poly_bits = self.env.get("POLY_BITS", "11011")

        # Estado interno del protocolo con ARQ simple
        self.next_seq = 0                 # próximo número de secuencia (0-255)
        self.timeout = 2.0               # tiempo de espera de ACK
        self.max_retries = 3             # reintentos antes de rendirse
        self.inject_fail = False         # bandera para forzar error de bit al enviar
        self.status = tk.StringVar(value="modo: NORMAL • listo")
        self._ack_wait = {}              # por-seq: event + resultado True/False/None
        self._ack_lock = threading.Lock()# lock para tocar _ack_wait
        self._delivered = set()          # SEQs ya entregados para filtrar duplicados

        master.title("crc wifi gui")

        # ======= Panel izquierdo: entrada y controles =======
        left = tk.Frame(master, bg="#2b579a", width=420)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

        tk.Label(left, text="mensajes para enviar", bg="#e67e22").pack(fill=tk.X)

        tk.Label(left, text="mensaje o crc:", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,0))
        self.entry = tk.Entry(left, bg="#66bb6a")
        self.entry.pack(fill=tk.X, padx=6, pady=4)

        # barra de botones: enviar, forzar fallo, volver a normal
        bar = tk.Frame(left, bg="#2b579a")
        bar.pack(anchor="w", padx=6, pady=2)
        tk.Button(bar, text="enviar", command=self.on_send, width=10).pack(side=tk.LEFT)
        tk.Button(bar, text="fallar", command=self.set_fail, width=8).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="arreglar", command=self.set_ok, width=8).pack(side=tk.LEFT)

        # lista de "palabras" o mensajes que ya mandamos
        tk.Label(left, text="palabras enviadas:", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(8,0))
        sent_wrap = tk.Frame(left, bg="#2b579a")
        sent_wrap.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.sent_list = tk.Listbox(sent_wrap, height=10)
        self.sent_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(sent_wrap, command=self.sent_list.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.sent_list.configure(yscrollcommand=sb.set)

        tk.Label(left, textvariable=self.status, bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,8))

        # ======= Panel derecho: salida/recibidos y proceso del CRC =======
        right = tk.Frame(master, bg="#2b579a")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(right, text="apartado para recibir", bg="#e67e22").pack(fill=tk.X)

        # texto plano recibido ya "decodificado" si es UTF-8
        tk.Label(right, text="mensaje de texto recibido es:", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,0))
        self.txt_msg = scrolledtext.ScrolledText(right, height=7, bg="#66bb6a")
        self.txt_msg.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # detalles del CRC recibido y calculado
        tk.Label(right, text="mensaje de crc recibido es:", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,0))
        self.txt_crc = scrolledtext.ScrolledText(right, height=7, bg="#66bb6a")
        self.txt_crc.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # pasos de la división larga del CRC, si la función explain_crc lo soporta
        tk.Label(right, text="operación CRC (división binaria):", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,0))
        self.txt_proc = scrolledtext.ScrolledText(right, height=16, bg="#66bb6a")
        try:
            self.txt_proc.configure(font=tkfont.Font(family="Consolas", size=10))
        except Exception:
            pass
        self.txt_proc.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # armamos el peer TCP: escucha y nos llama on_rx cuando llegan bytes
        self.peer = TcpPeer(host=self.host, port=self.port, on_data=self.on_rx)
        self.peer.start()

    def set_fail(self):
        """acá activamos el modo que mete un error de 1 bit para probar NACK/Retry."""
        self.inject_fail = True
        self.status.set("modo: FALLAR • listo")

    def set_ok(self):
        """acá volvemos al modo normal sin inyectar fallos."""
        self.inject_fail = False
        self.status.set("modo: NORMAL • listo")

    # --- envío con retry/ACK ---
    def on_send(self):
        """
        acá tomamos el texto de la caja, armamos un frame DATA con CRC y un SEQ,
        y lo mandamos. Si metimos fallo o no llega ACK, reintentamos hasta max_retries.
        """
        text = self.entry.get().strip()
        if not text:
            return

        # elegimos el SEQ y lo incrementamos con wrap a 0-255
        seq = self.next_seq
        self.next_seq = (self.next_seq + 1) & 0xFF

        # build_data_frame_from_input decide si 'text' es cadena normal o bits de CRC a pelo
        frame, payload = build_data_frame_from_input(text, self.poly_bits, seq)

        note = ""
        if self.inject_fail and len(payload) > 0:
            # forzamos flip de 1 bit en el primer byte del payload para simular error
            arr = bytearray(frame)
            # header de 5 bytes → tocamos el byte 5 que ya es payload
            arr[5] ^= 0x01
            frame = bytes(arr)
            note = "  (simulado FALLO: flip 1 bit)"

        # preparamos la espera de ACK/NACK con un Event asociado al seq
        evt = threading.Event()
        with self._ack_lock:
            self._ack_wait[seq] = {"event": evt, "result": None}

        ok = False
        for i in range(self.max_retries):
            try:
                self.status.set(f"enviando seq={seq} intento {i+1}/{self.max_retries}{note}")
                # acá se manda por socket al peer indicado
                self.peer.send(self.peer_host, self.peer_port, frame, timeout=2.0)
            except Exception as e:
                self.status.set(f"error de envío: {e}")
                break

            # esperamos el ACK/NACK o timeout
            if evt.wait(self.timeout):
                with self._ack_lock:
                    result = self._ack_wait.get(seq, {}).get("result", None)
                if result is True:
                    self.status.set(f"ACK seq={seq}")
                    ok = True
                    break
                else:
                    # recibimos NACK o algo no-True → reintentamos
                    self.status.set(f"NACK seq={seq} → reintento")
                    evt.clear()
                    time.sleep(0.2)
            else:
                # no llegó nada a tiempo → reintento
                self.status.set(f"timeout seq={seq} → reintento")
                time.sleep(0.2)

        # limpiamos la estructura de espera porque ya terminamos con ese seq
        with self._ack_lock:
            self._ack_wait.pop(seq, None)

        if not ok:
            self.status.set(f"falló después de {self.max_retries} intentos{note}")

        # registramos lo enviado en la lista y vaciamos la entrada
        self.sent_list.insert(tk.END, text + note)
        self.entry.delete(0, tk.END)

    # --- util GUI ---
    def _append(self, widget, s):
        """pequeña ayuda: habilita, escribe, scrollea al final, y vuelve a deshabilitar."""
        widget.configure(state="normal")
        widget.insert(tk.END, s)
        widget.see(tk.END)
        widget.configure(state="disabled")

    # --- recepción ---
    def on_rx(self, data: bytes, addr):
        """
        acá cae cualquier paquete recibido. Lo parseamos, vemos el tipo,
        validamos CRC si es DATA, y contestamos ACK/NACK. También mostramos detalles.
        """
        try:
            res = parse_frame(data, self.poly_bits)
            t = res["type"]
            seq = res["seq"]

            if t == TYPE_DATA:
                # verificamos CRC y preparamos la respuesta
                ok_crc = res["crc_ok"]
                try:
                    decoded = res["payload"].decode("utf-8")
                except Exception:
                    decoded = None

                if ok_crc:
                    # si no lo habíamos entregado antes, lo mostramos y marcamos el SEQ
                    if seq not in self._delivered:
                        if decoded is not None:
                            self._append(self.txt_msg, f"MENSAJE DESCIFRADO: {decoded}\n")
                        else:
                            self._append(self.txt_msg, f"MENSAJE DESCIFRADO: <bytes no-texto> {res['payload']!r}\n")
                        self._delivered.add(seq)
                    # siempre respondemos ACK cuando el CRC está ok, duplicado o no
                    ack = build_ack_frame(seq, True, self.poly_bits)
                    try:
                        self.peer.send(self.peer_host, self.peer_port, ack, timeout=2.0)
                    except Exception:
                        pass
                else:
                    # si el CRC falla, mandamos NACK y no entregamos el payload
                    nack = build_ack_frame(seq, False, self.poly_bits)
                    try:
                        self.peer.send(self.peer_host, self.peer_port, nack, timeout=2.0)
                    except Exception:
                        pass
                    self._append(self.txt_msg, "CRC FALLO. mensaje descartado\n")

                # mostramos info de bits y polinomio para el panel de CRC
                detalles = (
                    f"crc recibido: {res['crc_recv_bits']}\n"
                    f"crc calculado: {res['crc_calc_bits']}\n"
                    f"bits header: {res['header_bits']}\n"
                    f"bits payload: {res['payload_bits']}\n"
                    f"polinomio generador: {res['poly_bits']}\n"
                )
                self._append(self.txt_crc, detalles)

                # si la lib de CRC soporta pasos de división larga, los pintamos
                steps = explain_crc(res["hp_bytes"], self.poly_bits)
                if steps:
                    self._append(self.txt_proc, steps + "\n")

            elif t in (TYPE_ACK, TYPE_NACK):
                # acá llega el acuse del peer: despertamos al que esté esperando ese seq
                with self._ack_lock:
                    w = self._ack_wait.get(seq)
                    if w:
                        w["result"] = (t == TYPE_ACK)
                        w["event"].set()

        except Exception as e:
            # si algo raro pasa, lo mostramos en el panel de mensajes
            self._append(self.txt_msg, f"error al procesar: {e}\n")

def main():
    # lanzamos la ventana principal de Tk y arrancamos la App
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
