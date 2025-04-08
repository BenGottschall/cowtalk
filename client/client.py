import socket
import threading
import sys
import json
from getpass import getpass
from crypto_utils import MessageEncryption
from terminal_ui import ChatUI

class CowtalkClient:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.username = None
        self.encryption = None
        self.ui = ChatUI()
        
    def connect(self):
        """Connect to the server"""
        try:
            self.socket.connect((self.host, self.port))
            self.username = input("Enter your username: ")
            # Initialize encryption with a password
            password = getpass("Enter encryption password: ")
            self.encryption = MessageEncryption(password)
            # Send username to server
            self.send_message({"type": "connect", "username": self.username})
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False
            
    def send_message(self, message_dict):
        """Send a message to the server"""
        try:
            # Add message to UI immediately if it's a chat message
            if message_dict.get("type") == "message":
                # Add an unencrypted copy to the UI
                self.ui.add_message({
                    "type": "message",
                    "username": message_dict["username"],
                    "content": message_dict["content"]
                })
                # Then encrypt for sending
                if self.encryption:
                    message_dict["content"] = self.encryption.encrypt_message(message_dict["content"])
            self.socket.send(json.dumps(message_dict).encode('utf-8'))
        except Exception as e:
            print(f"Failed to send message: {e}")
            
    def receive_messages(self):
        """Continuously receive messages from the server"""
        while True:
            try:
                data = self.socket.recv(4096)
                if not data:
                    self.ui.add_message({
                        "type": "message",
                        "username": "System",
                        "content": "Disconnected from server"
                    })
                    break
                    
                message = json.loads(data.decode('utf-8'))
                # Only process messages that aren't our own (since we already displayed those)
                if message.get("username") != self.username:
                    # Decrypt message content if it's a regular chat message (not a system message)
                    if (message.get("type") == "message" and 
                        message.get("username") != "System" and 
                        self.encryption):
                        encrypted_content = message.get("content")
                        if encrypted_content:
                            decrypted_content = self.encryption.decrypt_message(encrypted_content)
                            if decrypted_content:
                                message["content"] = decrypted_content
                            else:
                                message["content"] = "[Encrypted message - cannot decrypt]"
                    
                    self.ui.add_message(message)
            except Exception as e:
                self.ui.add_message({
                    "type": "message",
                    "username": "System",
                    "content": f"Error receiving message: {e}"
                })
                break
                
    def start(self):
        """Start the client application"""
        if not self.connect():
            return
            
        try:
            # Start UI
            self.ui.start()
            
            # Start receive thread
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            # Main input loop
            while True:
                message = self.ui.get_input()
                if message is not None:
                    if message.lower() == '/exit':
                        break
                    self.send_message({
                        "type": "message",
                        "username": self.username,
                        "content": message
                    })
                    
        except KeyboardInterrupt:
            pass
        finally:
            self.ui.stop()
            self.socket.close()
            
if __name__ == "__main__":
    # Get server address from command line args if provided
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
    
    client = CowtalkClient(host, port)
    client.start()
