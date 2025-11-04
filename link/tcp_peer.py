import socket
import threading

class TcpPeer:
    def __init__(self, host="0.0.0.0", port=5000, on_data=None):
        self.host = host
        self.port = int(port)
        self.on_data = on_data
        self._srv = None
        self._stop = threading.Event()

    def start(self):
        t = threading.Thread(target=self._serve, daemon=True)
        t.start()
        return t

    def _serve(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.host, self.port))
        self._srv.listen(5)
        while not self._stop.is_set():
            try:
                self._srv.settimeout(1.0)
                conn, addr = self._srv.accept()
            except socket.timeout:
                continue
            threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()

    def _handle(self, conn, addr):
        with conn:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            if data and self.on_data:
                try:
                    self.on_data(data, addr)
                except Exception:
                    pass

    def send(self, host, port, data: bytes):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with s:
            s.connect((host, int(port)))
            s.sendall(data)

    def stop(self):
        self._stop.set()
        if self._srv:
            try:
                self._srv.close()
            except Exception:
                pass
