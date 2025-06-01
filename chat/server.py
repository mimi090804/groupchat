import socket
import threading
import struct

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 22222

# message id's
id_anmeldung = 0
id_abmeldung = 1
id_broadcast = 2
id_peerliste = 3
id_peer_peer_nachr = 4
id_ablehnung = 5
id_bad_format = 6

clients = {}  # nickname -> {'ip': str, 'udp': str, 'conn': socket, 'lock': Lock}
lock = threading.Lock()


def send_message(sock, msg_id, payload):
    payload_bytes = payload.encode('utf-8')
    header = struct.pack('!IB', len(payload_bytes), msg_id) # !IB --> uint32 + uint8
    sock.sendall(header + payload_bytes)


def broadcast_peers():
    peerlist = '\n'.join(f"{n}|{c['ip']}|{c['udp']}" for n, c in clients.items())
    for c in clients.values():
        send_message(c['sock'], 3, peerlist)


def notify_peers_join(nickname, ip, udp):
    msg = f"{nickname}|{ip}|{udp}"
    for nick, client in clients.items():
        if nick != nickname:
            send_message(client['sock'], 4, msg)


def notify_peers_leave(nickname):
    for nick, client in clients.items():
        if nick != nickname:
            send_message(client['sock'], 4, nickname)


def forward_broadcast(sender_nick, message):
    payload = f"{sender_nick}|{message}"
    for client in clients.values():
        send_message(client['sock'], 2, payload)


def client_listener(nickname, conn):
    try:
        while True:
            header = conn.recv(5)
            if not header:
                break
            length, msg_id = struct.unpack('!IB', header)
            data = conn.recv(length).decode('utf-8')

            if msg_id == 1:
                break
            elif msg_id == 2:
                forward_broadcast(nickname, data)
            else:
                send_message(conn, id_bad_format, 'Unexpected message ID')
    except:
        pass
    finally:
        conn.close()
        if nickname in clients:
            del clients[nickname]
            notify_peers_leave(nickname)


def handle_client(sock):
    try:
        header = sock.recv(5)
        if len(header) < 5:
            sock.close()
            return
        length, msg_id = struct.unpack('!IB', header)
        data = sock.recv(length).decode('utf-8')

        if msg_id != id_anmeldung:
            send_message(sock, id_bad_format, '')
            sock.close()
            return

        parts = data.strip().split('|')
        if len(parts) != 3:
            send_message(sock, id_bad_format, '')
            sock.close()
            return

        nickname, ip, udp_port = parts
        udp_port = int(udp_port)

        with lock:
            if nickname in clients:
                send_message(sock, id_ablehnung, '')
                sock.close()
                return

            clients[nickname] = {'ip': ip, 'udp': udp_port, 'sock': sock, 'lock': threading.Lock()}
            print(f"{nickname} registered from {ip}:{udp_port}")

            #peer_list = '\n'.join([f"{nick}|{info[0]}|{info[1]}" for nick, info in clients.items() if nick != nickname])
            peer_list = '\n'.join([f"{nick}|{info['ip']}|{info['udp']}" for nick, info in clients.items() if nick != nickname])
            send_message(sock, id_peerliste, peer_list)

            forward_broadcast(id_anmeldung, f"{nickname}|{ip}|{udp_port}")
            notify_peers_join(nickname, ip, udp_port)
            threading.Thread(target=client_listener, args=(nickname, sock), daemon=True).start()

    except:
        sock.close()
#        while True:
 #           header = sock.recv(5)
  #          if len(header) < 5:
   ##             break
    #        length, msg_id = struct.unpack('!IB', header)
     #       payload = sock.recv(length).decode('utf-8')
#
 #           if msg_id == id_broadcast:
  #              broadcast(id_broadcast, f"{nickname}|{payload}")
   #         elif msg_id == id_abmeldung:
    #            break
     #       else:
      #          send_message(sock, id_ablehnung, '')
   # except Exception as e:
     #   print(f"Fehler mit {addr}: {e}")
   # finally:
    #    with lock:
     #       if nickname in clients:
      #          del clients[nickname]
       #     broadcast(id_abmeldung, f"{nickname}|{ip}|{udp_port}")
        #sock.close()
        #print(f"[Server] Verbindung mit {addr} geschlossen.")


def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((SERVER_HOST, SERVER_PORT))
    s.listen(5)
    print(f"[Server] Listening on port {SERVER_PORT}...")

    while True:
        sock, _ = s.accept()
        threading.Thread(target=handle_client, args=(sock,), daemon=True).start()


if __name__ == '__main__':
    start_server()
