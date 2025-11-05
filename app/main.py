import argparse
from link.tcp_peer import TcpPeer
from link.frame import build_frame_from_input, parse_frame
#hola
def run(role, host, port, peer_host, peer_port, poly_bits):
    def on_rx(data, addr):
        res = parse_frame(data, poly_bits)
        print("OK" if res["ok"] else "FAIL")
        if res["ok"]:
            try:
                print("MENSAJE DESCIFRADO:", res["payload"].decode("utf-8"))
            except Exception:
                print("MENSAJE DESCIFRADO: <bytes>", res["payload"])
        print("crc recibido:", res["crc_recv_bits"])
        print("crc calculado:", res["crc_calc_bits"])
        print("bits enviados:", res["payload_bits"])
        print("polinomio generador:", res["poly_bits"])

    peer = TcpPeer(host=host, port=port, on_data=on_rx)
    peer.start()
    print(f"{role} escuchando en {host}:{port}")
    try:
        while True:
            s = input("> ")
            if not s:
                continue
            frame = build_frame_from_input(s, poly_bits)
            peer.send(peer_host, peer_port, frame)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rol", default="servidor", choices=["servidor", "cliente"])
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--puerto", type=int, default=5000)
    p.add_argument("--peer_host", default="127.0.0.1")
    p.add_argument("--peer_puerto", type=int, default=5000)
    p.add_argument("--poly", default="0011")
    a = p.parse_args()
    run(a.rol, a.host, a.puerto, a.peer_host, a.peer_puerto, a.poly)
