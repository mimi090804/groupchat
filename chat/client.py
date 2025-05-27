import socket
import threading
import struct
import time

# message id's
id_anmeldung = 0
id_abmeldung = 1
id_broadcast = 2
id_peerliste = 3
id_peer_peer_nachr = 4
id_ablehnung = 5
id_bad_format = 6

server_ip = '127.0.0.1'
# question: wie auf die Zahlen gekommen
server_port = 22222
udp_port = 33333
tcp_chat_port = 44444
clients = {}

nickname = input("Nickname: ")


def send_tcp_msg(sock, msg_id, payload):
    payload_bytes = payload.encode('utf-8')
    header = struct.pack('!IB', len(payload_bytes), msg_id)
    sock.sendall(header + payload_bytes)


def tcp_listener(sock):
    while True:
        header = sock.recv(5)
        if len(header) < 5:
            return
        length, msg_id = struct.unpack("!IB", header)
        payload = sock.recv(length).decode("utf-8")

        if msg_id == id_anmeldung:
            print(f"[Anmeldung] {payload} ist jetzt online.")
        elif msg_id == id_abmeldung:
            print(f"[Abmeldung] {payload} ist offline.")
        elif msg_id == id_peerliste:
            print("[Peerliste]")
            for peer in payload.strip().split('\n'):
                print(f"- {peer}")
        elif msg_id == id_broadcast:
            nick, msg = payload.split('|', 1)
            print(f"[Broadcast] von {nick}] {msg}")
        else:
            print(f"[Server] Unbekannte Nachricht: ID {msg_id} - {payload}")


def udp_listener():
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind(('', udp_port))
    while True:
        data, addr = udp_sock.recvfrom(1024)
        msg = data.decode('utf-8')
        parts = msg.split('|')
        if len(parts) != 3:
            continue # bad format
        peer_nick, peer_ip, peer_tcp_port = parts
        print(f"[Chat-Anfrage] von {peer_nick} ({peer_ip}:{peer_tcp_port})")

        try:
            chat_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            chat_sock.connect((peer_ip, int(peer_tcp_port)))
            threading.Thread(target=chat_session, args=(chat_sock, peer_nick), daemon=True).start()
        except Exception as e:
            print(f"Fehler beim Chat-Aufbau: {e}")


def chat_session(sock, peer_name):
    print(f"Chat gestartet mit {peer_name}")
    def listener():
        try:
            while True:
                header = sock.recv(5)
                if len(header) < 5:
                    return
                length, msg_id = struct.unpack("!IB", header)
                msg = sock.recv(length).decode("utf-8")
                print(f"[{peer_name}] {msg}")
        finally:
            sock.close()
    threading.Thread(target=listener, daemon=True).start()

    while True:
        msg = input(f"[Du -> {peer_name}]: ")
        if msg.lower() == '/exit':
            sock.close()
            break
        send_tcp_msg(sock, id_peer_peer_nachr, msg)


def start_peer_chat(target_nick, target_ip, target_udp, my_tcp_port):
    udp_msg = f"{nickname}|{socket.gethostbyname(socket.gethostname())}|{my_tcp_port}"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target_addr = (target_ip, int(target_udp))

    for i in range(3):
        sock.sendto(udp_msg.encode('utf-8'), target_addr)
        print(f"[UDP] Anfrage an {target_nick} gesendet ({i + 1}/3)...")
        try:
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.bind(('', my_tcp_port))
            tcp_sock.listen(1)
            tcp_sock.settimeout(3)
            conn, addr = tcp_sock.accept()
            chat_session(conn, target_nick)
            return
        except socket.timeout:
            print("[UDP] Keine Antwort, neuer Versuch...")
    print(f"[Fehler] Chat mit {target_nick} fehlgeschlagen.")


def main():
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.connect((server_ip, server_port))

    ip_addr = socket.gethostbyname(socket.gethostname())
    anmeldung_payload = f"{nickname}|{ip_addr}|{udp_port}"
    send_tcp_msg(tcp_sock, id_anmeldung, anmeldung_payload)

    header = tcp_sock.recv(5)
    if len(header) < 5:
        print("Verbindung getrennt.")
        return

    length, msg_id = struct.unpack("!IB", header)
    if msg_id == id_ablehnung:
        print("Nickname ist schon vergeben!")
        return
    elif msg_id == id_peerliste:
        payload = tcp_sock.recv(length).decode('utf-8')
        print("[Peerliste]")
        print(payload)

    threading.Thread(target=tcp_listener, args=(tcp_sock,), daemon=True).start()
    threading.Thread(target=udp_listener, daemon=True).start()

    print("Eingabeoptionen: /broadcast <msg>, /chat <nick> <ip> <udp>, /exit")
    while True:
        cmd = input("> ")
        if cmd.startswith("/broadcast "):
            msg = cmd[len("/broadcast "):]
            send_tcp_msg(tcp_sock, id_broadcast, msg)
        elif cmd.startswith("/chat "):
            _, nick, ip, udp = cmd.split()
            start_peer_chat(nick, ip, udp, tcp_chat_port)
        elif cmd == "/exit":
            send_tcp_msg(tcp_sock, id_abmeldung, '')
            tcp_sock.close()
            break

if __name__ == '__main__':
    main()