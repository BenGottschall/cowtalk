import socket
import threading

HOST = '0.0.0.0'     # Listens on all interfaces (good for local or public)
PORT = 12345         # Same port clients must connect to

clients = {}         # Maps client socket -> username
lock = threading.Lock()

def broadcast(message, sender_socket=None):
    with lock:
        for client_sock in clients:
            if client_sock != sender_socket:
                try:
                    client_sock.send(message.encode())
                except:
                    client_sock.close()

def handle_client(client_sock, addr):
    try:
        username = client_sock.recv(1024).decode().strip()
        with lock:
            clients[client_sock] = username
        print(f"[+] {username} connected from {addr}")

        broadcast(f"📢 {username} has joined the chat.")

        while True:
            msg = client_sock.recv(1024)
            if not msg:
                break
            text = msg.decode()
            full_msg = f"{username}: {text}"
            print(full_msg)
            broadcast(full_msg, sender_socket=client_sock)
    except:
        pass
    finally:
        with lock:
            left_user = clients.get(client_sock, "Someone")
            print(f"[-] {left_user} disconnected.")
            del clients[client_sock]
        broadcast(f"❌ {left_user} has left the chat.")
        client_sock.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()

    print(f"[💬 Server started] Listening on port {PORT}...")

    while True:
        client_sock, addr = server.accept()
        threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True).start()

if __name__ == "__main__":
    main()
