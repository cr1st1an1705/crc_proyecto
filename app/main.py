import argparse
from link.tcp_peer import TcpPeer
from link.frame import build_frame_from_input, parse_frame
# hola: dejo este comentario tal cual, no afecta nada

def run(role, host, port, peer_host, peer_port, poly_bits):
    """
    Arranca el peer TCP y se queda en un loop leyendo del teclado.
    Cada línea que escribís se arma en un frame con CRC y se envía al peer.
    Cuando llega algo del socket, lo parseamos y mostramos si el CRC dio ok.
    """

    def on_rx(data, addr):
        # acá nos cae un paquete del otro lado. Lo decodificamos.
        res = parse_frame(data, poly_bits)

        # imprimimos si el frame pasó la validación de CRC
        print("OK" if res["ok"] else "FAIL")

        if res["ok"]:
            # si el payload es texto UTF-8, lo mostramos como string
            try:
                print("MENSAJE DESCIFRADO:", res["payload"].decode("utf-8"))
            except Exception:
                # si no es texto, mostramos los bytes crudos
                print("MENSAJE DESCIFRADO: <bytes>", res["payload"])

        # datos útiles para entender el CRC y los bits
        print("crc recibido:", res["crc_recv_bits"])
        print("crc calculado:", res["crc_calc_bits"])
        print("bits enviados:", res["payload_bits"])
        print("polinomio generador:", res["poly_bits"])

    # armamos el peer TCP que escucha en host:port y llama on_rx al recibir algo
    peer = TcpPeer(host=host, port=port, on_data=on_rx)
    peer.start()
    print(f"{role} escuchando en {host}:{port}")

    try:
        # loop principal: leemos desde stdin y mandamos al peer
        while True:
            s = input("> ")  # escribís un mensaje o una cadena de bits, según soporte build_frame_from_input
            if not s:
                # si apretaste Enter vacío, no mandamos nada
                continue

            # transformamos lo que tipeaste en un frame con CRC usando el polinomio elegido
            frame = build_frame_from_input(s, poly_bits)

            # lo enviamos al peer en peer_host:peer_port
            peer.send(peer_host, peer_port, frame)

    except KeyboardInterrupt:
        # Ctrl+C para salir prolijo del loop
        pass


if __name__ == "__main__":
    # acá definimos los flags de CLI. Están en español para que sea directo.
    p = argparse.ArgumentParser(description="Peer TCP simple con CRC por línea de comandos")
    p.add_argument("--rol", default="servidor", choices=["servidor", "cliente"],
                   help="solo etiqueta informativa para imprimir en consola")
    p.add_argument("--host", default="0.0.0.0",
                   help="IP local donde escuchar")
    p.add_argument("--puerto", type=int, default=5000,
                   help="puerto local donde escuchar")
    p.add_argument("--peer_host", default="127.0.0.1",
                   help="IP del peer al que le vamos a mandar")
    p.add_argument("--peer_puerto", type=int, default=5000,
                   help="puerto del peer al que le vamos a mandar")
    p.add_argument("--poly", default="0011",
                   help="polinomio generador del CRC en bits, ej: 11011")

    # parseamos los argumentos
    a = p.parse_args()

    # lanzamos el run con los parámetros ya tipados
    run(a.rol, a.host, a.puerto, a.peer_host, a.peer_puerto, a.poly)
