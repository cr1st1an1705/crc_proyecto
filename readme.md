# CRC_PROYECTO2

Verificador CRC bidireccional. Adjunta CRC en los n bits bajos de un byte extra.

## Config (.env)
ROLE=servidor
HOST=0.0.0.0
PORT=5000
PEER_HOST=IP_de_la_otra_PC
PEER_PORT=5000
POLY_BITS=0011

## GUI
python -m app.gui

## CLI
python -m app.main --rol servidor --host 0.0.0.0 --puerto 5000 --peer_host 127.0.0.1 --peer_puerto 5001 --poly 0011
python -m app.main --rol cliente  --host 0.0.0.0 --puerto 5001 --peer_host 127.0.0.1 --peer_puerto 5000 --poly 0011
