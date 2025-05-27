# peer_chat.py

import socket
import threading
import struct
import time

RETRY_INTERVAL = 3
MAX_RETRIES = 3

def send_udp_request(target_ip, target_udp_port, nickname, own_ip, own_tcp_port):
    msg = f"{nickname}|{own_ip}|{own_tcp_port}"
    msg_bytes = msg.encode('utf-8')
    length = struct.pack('!I', len(msg_bytes))
    udp_msg = length + msg_bytes

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.sendto(udp_msg, (target_ip, int(target_udp_port)))
    udp_sock.close()

def listen_udp(udp_port, on_request_callback):
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind(('0.0.0.0', udp_port))
    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            if len(data) < 4:
                continue
            length = struct.unpack('!I', data[:4])[0]
            payload = data[4:4+length].decode('utf-8')
            parts = payload.split('|')
            if len(parts) != 3:
                continue  # bad format, ignore
            nickname, ip, tcp_port = parts
            on_request_callback(nickname, ip, int(tcp_port))
        except:
            continue

def peer_accept(listen_port, on_message_callback):
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.bind(('0.0.0.0', listen_port))
    tcp_sock.listen(1)
    conn, _ = tcp_sock.accept()
    handle_peer_connection(conn, on_message_callback)

def peer_connect(target_ip, target_tcp_port, on_message_callback):
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.settimeout(RETRY_INTERVAL)
    for attempt in range(MAX_RETRIES):
        try:
            tcp_sock.connect((target_ip, target_tcp_port))
            handle_peer_connection(tcp_sock, on_message_callback)
            return
        except socket.timeout:
            continue
        except Exception:
            break
    print("Verbindung fehlgeschlagen.")

def send_peer_message(conn, message):
    msg_bytes = message.encode('utf-8')
    header = struct.pack('!IB', len(msg_bytes), 4)
    conn.sendall(header + msg_bytes)

def handle_peer_connection(conn, on_message_callback):
    try:
        while True:
            header = conn.recv(5)
            if not header:
                break
            length, msg_id = struct.unpack('!IB', header)
            data = conn.recv(length).decode('utf-8')
            if msg_id != 4:
                send_peer_message(conn, "bad format")
                continue
            on_message_callback(data)
    except:
        pass
    finally:
        conn.close()


if __name__ == '__main__':
    UDP_PORT = 30000  # Beispiel UDP-Port
    TCP_PORT = 40000  # Beispiel TCP-Port

    def on_peer_request(nickname, ip, tcp_port):
        print(f"Empfange Chat-Anfrage von {nickname}@{ip}:{tcp_port}")
        threading.Thread(target=peer_connect, args=(ip, tcp_port, print_message), daemon=True).start()

    def print_message(msg):
        print(f"[Peer] {msg}")

    # Starte UDP Listener (bereit für eingehende Peer-Chat-Anfragen)
    threading.Thread(target=listen_udp, args=(UDP_PORT, on_peer_request), daemon=True).start()

    # Starte TCP Listener (bereit für eingehende Verbindungen)
    threading.Thread(target=peer_accept, args=(TCP_PORT, print_message), daemon=True).start()

    print(f"Peer bereit – wartet auf eingehende Nachrichten (UDP:{UDP_PORT}, TCP:{TCP_PORT})")

    # Einfacher Loop für Benutzereingaben zum Test
    while True:
        cmd = input("Nachricht senden oder 'exit': ")
        if cmd == 'exit':
            break
