import os
import tkinter as tk
from tkinter import scrolledtext
from tkinter import font as tkfont

from link.tcp_peer import TcpPeer
from link.frame import build_frame_from_input, parse_frame
from crc.crc_core import explain_crc_long_division

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

        master.title("crc wifi gui")

        # izquierda: entrada
        left = tk.Frame(master, bg="#2b579a", width=420)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        tk.Label(left, text="mensajes para enviar", bg="#e67e22").pack(fill=tk.X)
        tk.Label(left, text="mensaje o crc:", bg="#2b579a", fg="white").pack(anchor="w", padx=6, pady=(6,0))
        self.entry = tk.Entry(left, bg="#66bb6a")
        self.entry.pack(fill=tk.X, padx=6, pady=4)
        tk.Button(left, text="enviar", command=self.on_send).pack(padx=6, pady=6, anchor="w")

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

    def on_send(self):
        text = self.entry.get().strip()
        if not text:
            return
        frame = build_frame_from_input(text, self.poly_bits)
        try:
            self.peer.send(self.peer_host, self.peer_port, frame)
            self.entry.delete(0, tk.END)
        except Exception as e:
            self._append(self.txt_msg, f"error de envío: {e}\n")

    def _append(self, widget, s):
        widget.configure(state="normal")
        widget.insert(tk.END, s)
        widget.see(tk.END)
        widget.configure(state="disabled")

    def on_rx(self, data: bytes, addr):
        try:
            res = parse_frame(data, self.poly_bits)
            ok = res["ok"]
            payload = res["payload"]
            try:
                decoded = payload.decode("utf-8")
            except Exception:
                decoded = None

            if ok and decoded is not None:
                self._append(self.txt_msg, f"MENSAJE DESCIFRADO: {decoded}\n")
            elif ok:
                self._append(self.txt_msg, f"MENSAJE DESCIFRADO: <bytes no-texto> {payload!r}\n")
            else:
                self._append(self.txt_msg, "CRC FALLO. mensaje descartado\n")

            detalles = (
                f"crc recibido: {res['crc_recv_bits']}\n"
                f"crc calculado: {res['crc_calc_bits']}\n"
                f"bits enviados: {res['payload_bits']}\n"
                f"polinomio generador: {res['poly_bits']}\n"
            )
            self._append(self.txt_crc, detalles)

            # División binaria visual
            steps = explain_crc_long_division(payload, self.poly_bits)
            self._append(self.txt_proc, steps + "\n")

        except Exception as e:
            self._append(self.txt_msg, f"error al procesar: {e}\n")

def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()