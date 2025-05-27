import socket
import struct

SERVER_IP = '127.0.0.1'
SERVER_PORT = 22222

nickname = 'Peer1'
ip = '127.0.0.1'
udp_port = '30000'

payload = f"{nickname}|{ip}|{udp_port}".encode('utf-8')
length = struct.pack('!I', len(payload))
msg_id = struct.pack('!B', 0)  # ID 0 = Anmeldung

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((SERVER_IP, SERVER_PORT))
    s.sendall(length + msg_id + payload)

    while True:
        header = s.recv(5)
        if not header:
            break
        l, msg_id = struct.unpack('!IB', header)
        data = s.recv(l).decode('utf-8')
        print(f"Empfangen (ID={msg_id}): {data}")
