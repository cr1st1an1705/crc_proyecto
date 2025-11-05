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

# explicación matemática si está disponible
try:
    from crc.crc_core import explain_crc_long_division as explain_crc
except Exception:
    try:
        from crc.crc_core import explain_crc_math as explain_crc
    except Exception:
        def explain_crc(data, poly_bits): return ""

def load_env(path=".env"):
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
        self.env = load_env()
        self.role = self.env.get("ROLE", "servidor")
        self.host = self.env.get("HOST", "0.0.0.0")
        self.port = int(self.env.get("PORT", "5000"))
        self.peer_host = self.env.get("PEER_HOST", "127.0.0.1")
        self.peer_port = int(self.env.get("PEER_PORT", "5000"))
        self.poly_bits = self.env.get("POLY_BITS", "11011")

        # Estado de protocolo
        self.next_seq = 0
        self.timeout = 2.0
        self.max_retries = 3
        self.inject_fail = False
        self.status = tk.StringVar(value="modo: NORMAL • listo")
        self._ack_wait = {}   # seq -> {"event": Event, "result": True/False/None}
        self._ack_lock = threading.Lock()
        self._delivered = set()  # SEQs ya entregados

        master.title("crc wifi gui")

        # izquierda: entrada + controles
        left = tk.Frame(master, bg="#2b579a", width=420)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        tk.Label(left, text="mensajes para enviar", bg="#e67e22").pack(fill=tk.X)
        tk.Label(left, text="mensaje o crc:", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,0))
        self.entry = tk.Entry(left, bg="#66bb6a")
        self.entry.pack(fill=tk.X, padx=6, pady=4)

        bar = tk.Frame(left, bg="#2b579a")
        bar.pack(anchor="w", padx=6, pady=2)
        tk.Button(bar, text="enviar", command=self.on_send, width=10).pack(side=tk.LEFT)
        tk.Button(bar, text="fallar", command=self.set_fail, width=8).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="arreglar", command=self.set_ok, width=8).pack(side=tk.LEFT)

        tk.Label(left, text="palabras enviadas:", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(8,0))
        sent_wrap = tk.Frame(left, bg="#2b579a")
        sent_wrap.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.sent_list = tk.Listbox(sent_wrap, height=10)
        self.sent_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(sent_wrap, command=self.sent_list.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.sent_list.configure(yscrollcommand=sb.set)

        tk.Label(left, textvariable=self.status, bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,8))

        # derecha: salida
        right = tk.Frame(master, bg="#2b579a")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        tk.Label(right, text="apartado para recibir", bg="#e67e22").pack(fill=tk.X)

        tk.Label(right, text="mensaje de texto recibido es:", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,0))
        self.txt_msg = scrolledtext.ScrolledText(right, height=7, bg="#66bb6a")
        self.txt_msg.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        tk.Label(right, text="mensaje de crc recibido es:", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,0))
        self.txt_crc = scrolledtext.ScrolledText(right, height=7, bg="#66bb6a")
        self.txt_crc.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        tk.Label(right, text="operación CRC (división binaria):", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,0))
        self.txt_proc = scrolledtext.ScrolledText(right, height=16, bg="#66bb6a")
        try:
            self.txt_proc.configure(font=tkfont.Font(family="Consolas", size=10))
        except Exception:
            pass
        self.txt_proc.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        self.peer = TcpPeer(host=self.host, port=self.port, on_data=self.on_rx)
        self.peer.start()

    def set_fail(self):
        self.inject_fail = True
        self.status.set("modo: FALLAR • listo")

    def set_ok(self):
        self.inject_fail = False
        self.status.set("modo: NORMAL • listo")

    # --- envío con retry/ACK ---
    def on_send(self):
        text = self.entry.get().strip()
        if not text:
            return

        seq = self.next_seq
        self.next_seq = (self.next_seq + 1) & 0xFF

        frame, payload = build_data_frame_from_input(text, self.poly_bits, seq)

        note = ""
        if self.inject_fail and len(payload) > 0:
            arr = bytearray(frame)
            # flip 1 bit del primer byte de payload (después de cabecera de 5 bytes)
            arr[5] ^= 0x01
            frame = bytes(arr)
            note = "  (simulado FALLO: flip 1 bit)"

        evt = threading.Event()
        with self._ack_lock:
            self._ack_wait[seq] = {"event": evt, "result": None}

        ok = False
        for i in range(self.max_retries):
            try:
                self.status.set(f"enviando seq={seq} intento {i+1}/{self.max_retries}{note}")
                self.peer.send(self.peer_host, self.peer_port, frame, timeout=2.0)
            except Exception as e:
                self.status.set(f"error de envío: {e}")
                break

            if evt.wait(self.timeout):
                with self._ack_lock:
                    result = self._ack_wait.get(seq, {}).get("result", None)
                if result is True:
                    self.status.set(f"ACK seq={seq}")
                    ok = True
                    break
                else:
                    self.status.set(f"NACK seq={seq} → reintento")
                    evt.clear()
                    time.sleep(0.2)
            else:
                self.status.set(f"timeout seq={seq} → reintento")
                time.sleep(0.2)

        with self._ack_lock:
            self._ack_wait.pop(seq, None)

        if not ok:
            self.status.set(f"falló después de {self.max_retries} intentos{note}")

        self.sent_list.insert(tk.END, text + note)
        self.entry.delete(0, tk.END)

    # --- util GUI ---
    def _append(self, widget, s):
        widget.configure(state="normal")
        widget.insert(tk.END, s)
        widget.see(tk.END)
        widget.configure(state="disabled")

    # --- recepción ---
    def on_rx(self, data: bytes, addr):
        try:
            res = parse_frame(data, self.poly_bits)
            t = res["type"]
            seq = res["seq"]

            if t == TYPE_DATA:
                # verificar CRC y responder ACK/NACK
                ok_crc = res["crc_ok"]
                try:
                    decoded = res["payload"].decode("utf-8")
                except Exception:
                    decoded = None

                if ok_crc:
                    # duplicado?
                    if seq not in self._delivered:
                        if decoded is not None:
                            self._append(self.txt_msg, f"MENSAJE DESCIFRADO: {decoded}\n")
                        else:
                            self._append(self.txt_msg, f"MENSAJE DESCIFRADO: <bytes no-texto> {res['payload']!r}\n")
                        self._delivered.add(seq)
                    # responder ACK siempre
                    ack = build_ack_frame(seq, True, self.poly_bits)
                    try:
                        self.peer.send(self.peer_host, self.peer_port, ack, timeout=2.0)
                    except Exception:
                        pass
                else:
                    nack = build_ack_frame(seq, False, self.poly_bits)
                    try:
                        self.peer.send(self.peer_host, self.peer_port, nack, timeout=2.0)
                    except Exception:
                        pass
                    self._append(self.txt_msg, "CRC FALLO. mensaje descartado\n")

                # Detalles y operación matemática usando cabecera+payload
                detalles = (
                    f"crc recibido: {res['crc_recv_bits']}\n"
                    f"crc calculado: {res['crc_calc_bits']}\n"
                    f"bits header: {res['header_bits']}\n"
                    f"bits payload: {res['payload_bits']}\n"
                    f"polinomio generador: {res['poly_bits']}\n"
                )
                self._append(self.txt_crc, detalles)

                steps = explain_crc(res["hp_bytes"], self.poly_bits)
                if steps:
                    self._append(self.txt_proc, steps + "\n")

            elif t in (TYPE_ACK, TYPE_NACK):
                with self._ack_lock:
                    w = self._ack_wait.get(seq)
                    if w:
                        w["result"] = (t == TYPE_ACK)
                        w["event"].set()

        except Exception as e:
            self._append(self.txt_msg, f"error al procesar: {e}\n")

def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()