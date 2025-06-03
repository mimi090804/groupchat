import socket
import threading
import struct
import queue

# message id's
ID_ANMELDUNG = 0
ID_ABMELDUNG = 1
ID_BROADCAST = 2
ID_PEERLISTE = 3
ID_PEER_PEER_NACHR = 4
ID_ABLEHNUNG = 5
ID_BAD_FORMAT = 6

'''IP ADDRESSES
'100.111.188.229' #phillipe
'100.114.47.151' #janis
'''

# Configuration - change these as needed
SERVER_IP = '100.114.47.151'  # Change to your server IP
SERVER_PORT = 22222

MESHNET_IP = '100.114.49.113'  # own meshnet ip

pending_chat_requests = {}
peers = {}  # Format: {nickname: (ip, udp_port)}


def get_free_tcp_port():
    """Get a free TCP port dynamically assigned by the OS from 49152 to 65535."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


tcp_chat_port = get_free_tcp_port()
print(f"Freier TCP-Port: {tcp_chat_port}")

UDP_PORT = get_free_tcp_port()

# Queue for chat requests
chat_request_queue = queue.Queue()

nickname = input("Nickname: ")


def send_tcp_msg(sock, msg_id, payload):
    """Send a TCP message with header"""
    try:
        payload_bytes = payload.encode('utf-8')
        header = struct.pack('!IB', len(payload_bytes), msg_id) #len(...): how many bytes follow
        sock.sendall(header + payload_bytes)
    except Exception as e:
        print(f"Error sending TCP message: {e}")


def tcp_listener(sock):
    """Listen for messages from the server"""
    try:
        while True:
            header = sock.recv(5)
            if len(header) < 5:
                print("[TCP] Connection lost to server")
                return

            length, msg_id = struct.unpack("!IB", header)
            payload = ""
            if length > 0:
                payload = sock.recv(length).decode("utf-8")

            if msg_id == ID_ANMELDUNG:
                parts = payload.split('|')
                if len(parts) >= 1:
                    print(f"[Join] {parts[0]} joined the chat")
            elif msg_id == ID_ABMELDUNG:
                print(f"[Leave] {payload} left the chat")
            elif msg_id == ID_PEERLISTE:
                print("\n[Peer List]")
                if payload:
                    for peer in payload.strip().split('\n'):
                        if peer:
                            print(f"  - {peer}")
                else:
                    print("  No other peers online")
            elif msg_id == ID_BROADCAST:
                if '|' in payload:
                    nick, msg = payload.split('|', 1)
                    print(f"[Broadcast from {nick}] {msg}")
                else:
                    print(f"[Broadcast] {payload}")
            elif msg_id == ID_ABLEHNUNG:
                print("[Error] Request rejected by server")
            elif msg_id == ID_BAD_FORMAT:
                print("[Error] Bad message format")
            else:
                print(f"[Server] Unknown message: ID {msg_id} - {payload}")
    except Exception as e:
        print(f"[TCP Listener] Error: {e}")


def udp_listener():
    """Listen for UDP chat requests"""
    try:
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(('', UDP_PORT))
        print(f"[UDP] Listening on port {UDP_PORT}")

        while True:
            data, addr = udp_sock.recvfrom(1024)
            msg = data.decode('utf-8')
            parts = msg.split('|')
            if len(parts) != 3:
                continue
            peer_nick, peer_ip, peer_tcp_port = parts
            # Deduplizieren:
            if peer_nick in pending_chat_requests:
                continue  # Anfrage ist schon da!
            pending_chat_requests[peer_nick] = (peer_ip, int(peer_tcp_port))
            print(f"[Chat Request] from {peer_nick} ({peer_ip}:{peer_tcp_port})")
            print("Type '/accept' to accept the chat request or '/decline' to decline it.")

    except Exception as e:
        print(f"[UDP Listener] Error: {e}")


def chat_session(sock, peer_name):
    print(f"=== Chat started with {peer_name} ===")
    stop_event = threading.Event()

    def listener():
        try:
            while not stop_event.is_set():
                header = sock.recv(5)
                if not header:
                    break
                length, msg_id = struct.unpack("!IB", header)
                msg = sock.recv(length).decode("utf-8")
                print(f"[{peer_name}] {msg}")
        except Exception as e:
            print(f"Chat listener error: {e}")
        finally:
            stop_event.set()
            sock.close()
            print(f"=== Chat with {peer_name} ended ===")

    threading.Thread(target=listener, daemon=True).start()

    try:
        while not stop_event.is_set():
            msg = input(f"[You -> {peer_name}]: ")
            if msg.lower() == '/exit':
                stop_event.set()
                sock.close()
                break
            try:
                payload = msg.encode('utf-8')
                header = struct.pack('!IB', len(payload), 4)
                sock.sendall(header + payload)
            except Exception as e:
                print(f"Error sending TCP message: {e}")
                stop_event.set()
                break
    except Exception as e:
        print(f"Chat session aborted: {e}")
    finally:
        stop_event.set()
        sock.close()
        print(f"=== Chat with {peer_name} ended ===")


'''
def handle_chat_request():
    """Handle a pending chat request"""
    try:
        peer_nick, peer_ip, peer_tcp_port = chat_request_queue.get_nowait()
        print(f"Connecting to {peer_nick} at {peer_ip}:{peer_tcp_port}...")

        chat_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        chat_sock.settimeout(5)
        chat_sock.connect((peer_ip, int(peer_tcp_port)))
        threading.Thread(target=chat_session, args=(chat_sock, peer_nick), daemon=True).start()
        return True
    except queue.Empty:
        print("No pending chat requests.")
        return False
    except Exception as e:
        print(f"Error connecting to peer: {e}")
        return False
'''


def decline_chat_request():
    """Decline a pending chat request"""
    try:
        peer_nick, _, _ = chat_request_queue.get_nowait()
        print(f"Chat request from {peer_nick} declined.")
        return True
    except queue.Empty:
        print("No pending chat requests.")
        return False


def start_peer_chat(target_nick, target_ip, target_udp, my_tcp_port):
    # 1. TCP-Listener auf eigenem Port starten
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_sock.bind(('', my_tcp_port))
    tcp_sock.listen(1)
    tcp_sock.settimeout(10)

    udp_msg = f"{nickname}|{MESHNET_IP}|{my_tcp_port}"
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target_addr = (target_ip, int(target_udp))

    for i in range(3):
        udp_sock.sendto(udp_msg.encode('utf-8'), target_addr)
        print(f"[UDP] Request sent ({i + 1}/3)...")
        try:
            conn, addr = tcp_sock.accept()
            print(f"[TCP] Connection established with {addr}")
            chat_session(conn, target_nick)
            return
        except socket.timeout:
            print("[UDP] No response, retrying...")
    print(f"[Error] Chat with {target_nick} failed.")
    tcp_sock.close()


def accept_chat():
    if not pending_chat_requests:
        print("No pending chat requests.")
        return
    peer_nick, (peer_ip, peer_tcp_port) = pending_chat_requests.popitem()
    print(f"Connecting to {peer_nick} at {peer_ip}:{peer_tcp_port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((peer_ip, peer_tcp_port))
        chat_session(sock, peer_nick)
    except Exception as e:
        print(f"Error connecting: {e}")


def main():
    """Main client function"""
    try:
        # Connect to server
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.connect((SERVER_IP, SERVER_PORT))
        print(f"Connected to server at {SERVER_IP}:{SERVER_PORT}")

        # Register with server
        anmeldung_payload = f"{nickname}|{MESHNET_IP}|{UDP_PORT}"
        send_tcp_msg(tcp_sock, ID_ANMELDUNG, anmeldung_payload)

        # Wait for server response
        header = tcp_sock.recv(5)
        if len(header) < 5:
            print("Connection lost.")
            return

        length, msg_id = struct.unpack("!IB", header)
        if msg_id == ID_ABLEHNUNG:
            print("Nickname already taken!")
            return
        elif msg_id == ID_PEERLISTE:
            payload = tcp_sock.recv(length).decode('utf-8') if length > 0 else ""
            print("\n[Initial Peer List]")
            if payload:
                for peer in payload.strip().split('\n'):
                    if peer:
                        print(f"  - {peer}")
            else:
                print("No other peers online")

        # Start listener threads
        threading.Thread(target=tcp_listener, args=(tcp_sock,), daemon=True).start()
        threading.Thread(target=udp_listener, daemon=True).start()

        # Main command loop
        print("\nCommands:")
        print("  /broadcast <message> - Send message to all users")
        print("  /chat <nick> <ip> <udp_port> - Start private chat")
        print("  /accept - Accept pending chat request")
        print("  /decline - Decline pending chat request")
        print("  /exit - Quit")
        print()

        while True:
            try:
                cmd = input("> ")
                if cmd.startswith("/broadcast "):
                    msg = cmd[len("/broadcast "):]
                    if msg:
                        send_tcp_msg(tcp_sock, ID_BROADCAST, msg)
                    else:
                        print("Please provide a message to broadcast")

                elif cmd.startswith("/chat "):
                    parts = cmd.split()
                    if len(parts) == 4:
                        _, nick, ip, udp = parts
                        try:
                            udp_port_int = int(udp)
                            start_peer_chat(nick, ip, udp, tcp_chat_port)
                        except ValueError:
                            print("Invalid UDP port number")
                    else:
                        print("Usage: /chat <nickname> <ip> <udp_port>")

                elif cmd == "/accept":
                    # handle_chat_request()
                    accept_chat()
                elif cmd == "/decline":
                    decline_chat_request()

                elif cmd == "/exit":
                    send_tcp_msg(tcp_sock, ID_ABMELDUNG, '')
                    break
                elif cmd == "/help":
                    print("\nCommands:")
                    print("  /broadcast <message> - Send message to all users")
                    print("  /chat <nick> <ip> <udp_port> - Start private chat")
                    print("  /accept - Accept pending chat request")
                    print("  /decline - Decline pending chat request")
                    print("  /exit - Quit")
                elif cmd.strip():
                    print("Unknown command. Type /help for available commands.")

            except KeyboardInterrupt:
                print("\nExiting...")
                send_tcp_msg(tcp_sock, ID_ABMELDUNG, '')
                break

    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            tcp_sock.close()
        except:
            pass


if __name__ == '__main__':
    main()
