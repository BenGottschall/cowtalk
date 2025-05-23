import socket
import threading
import json

HOST = '0.0.0.0'     # Listens on all interfaces
PORT = 9999          # Match client's default port

clients = {}         # Maps client socket -> username
lock = threading.Lock()

def broadcast(message_dict, sender_socket=None):
    """Send a message to all clients except the sender"""
    message_json = json.dumps(message_dict) + "\n"  # Add newline as message delimiter
    with lock:
        for client_sock in clients:
            if client_sock != sender_socket:
                try:
                    client_sock.send(message_json.encode('utf-8'))
                except:
                    client_sock.close()

def handle_client(client_sock, addr):
    try:
        # Receive the first message containing username
        data = client_sock.recv(4096)
        if not data:
            return
            
        message = json.loads(data.decode('utf-8'))
        username = message.get("username", "Anonymous")
        
        with lock:
            clients[client_sock] = username
        print(f"[+] {username} connected from {addr}")

        # Notify everyone about the new user
        broadcast({
            "type": "message",
            "username": "System",
            "content": f"{username} has joined the chat"
        })

        buffer = ""
        while True:
            data = client_sock.recv(4096)
            if not data:
                break
                
            buffer += data.decode('utf-8')
            
            # Split buffer into messages by newline
            while '\n' in buffer:
                message_json, buffer = buffer.split('\n', 1)
                try:
                    message = json.loads(message_json)
                    if message.get("type") == "message":
                        username = message.get("username", "Anonymous")
                        content = message.get("content", "")
                        print(f"{username}: {content}")
                        # Forward to other clients
                        broadcast(message, sender_socket=client_sock)
                    elif message.get("type") == "typing_status":
                        # Forward typing status to other clients
                        broadcast(message, sender_socket=client_sock)
                except json.JSONDecodeError as e:
                    print(f"Error decoding message: {e}")
                except Exception as e:
                    print(f"Error processing message: {e}")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        with lock:
            left_user = clients.get(client_sock, "Someone")
            if client_sock in clients:
                del clients[client_sock]
                
        print(f"[-] {left_user} disconnected.")
        broadcast({
            "type": "message", 
            "username": "System", 
            "content": f"{left_user} has left the chat"
        })
        client_sock.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()

    print(f"[💬 Server started] Listening on port {PORT}...")

    while True:
        client_sock, addr = server.accept()
        threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True).start()

if __name__ == "__main__":
    main()
