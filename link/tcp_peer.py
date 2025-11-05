import socket
import threading

class TcpPeer:
    def __init__(self, host="0.0.0.0", port=5000, on_data=None):
        # guardamos parámetros básicos del peer
        self.host = host
        self.port = int(port)
        # callback que se llama cuando llega *todo* el contenido de una conexión
        self.on_data = on_data
        # socket del servidor y señal de parada
        self._srv = None
        self._stop = threading.Event()

    def start(self):
        """
        Levanta el servidor en un hilo daemon.
        Devuelve el Thread por si querés esperarlo o inspeccionarlo.
        """
        t = threading.Thread(target=self._serve, daemon=True)
        t.start()
        return t

    def _serve(self):
        """
        Hilo servidor:
        - crea socket TCP,
        - bind y listen,
        - hace accept en bucle con timeout para poder chequear _stop,
        - por cada conexión entrante lanza _handle en otro hilo.
        """
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # reutilizar puerto rápido
        self._srv.bind((self.host, self.port))
        self._srv.listen(5)  # backlog chico, alcanza para pruebas

        while not self._stop.is_set():
            try:
                # ponemos timeout al accept para no quedarnos bloqueados al apagar
                self._srv.settimeout(1.0)
                conn, addr = self._srv.accept()
            except socket.timeout:
                continue
            # cada cliente se maneja en su propio hilo
            threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()

    def _handle(self, conn, addr):
        """
        Atiende una conexión:
        - lee hasta EOF (cuando el cliente cierra),
        - acumula todo en memoria,
        - si hay datos, llama on_data(data, addr).
        Nota: no hay framing ni mensajes múltiples por conexión. Es “una conexión = un mensaje”.
        """
        with conn:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    # EOF: el cliente cerró su lado → salimos del loop
                    break
                data += chunk
            if data and self.on_data:
                try:
                    self.on_data(data, addr)
                except Exception:
                    # silenciamos errores del callback para no matar el hilo
                    pass

    def send(self, host, port, data: bytes, timeout=2.0):
        """
        Cliente simple de uso puntual:
        - abre conexión al peer,
        - manda todo el buffer,
        - cierra.
        Ideal para “fire-and-forget”. No espera respuesta en la misma conexión.
        """
        with socket.create_connection((host, int(port)), timeout=timeout) as s:
            s.sendall(data)

    def stop(self):
        """
        Señal de parada para el hilo servidor y cierre del socket de escucha.
        Llama esto para apagar prolijo.
        """
        self._stop.set()
        if self._srv:
            try:
                self._srv.close()
            except Exception:
                pass
