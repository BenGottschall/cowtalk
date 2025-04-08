import socket
import threading
import sys
import json
from getpass import getpass
from crypto_utils import MessageEncryption
from terminal_ui import ChatUI
import time

class CowtalkClient:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.username = None
        self.encryption = None
        self.ui = ChatUI()
        self.last_typing_update = 0
        self.typing_update_delay = 0.1  # Reduce to 100ms for more responsive updates
        
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
                # Then encrypt for sending if needed
                if self.encryption:
                    message_dict["content"] = self.encryption.encrypt_message(message_dict["content"])
            message_json = json.dumps(message_dict) + "\n"  # Add newline as message delimiter
            self.socket.send(message_json.encode('utf-8'))
        except Exception as e:
            print(f"Failed to send message: {e}")
            
    def receive_messages(self):
        """Continuously receive messages from the server"""
        buffer = ""
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
                    
                buffer += data.decode('utf-8')
                
                # Process complete messages
                while '\n' in buffer:
                    message_json, buffer = buffer.split('\n', 1)
                    try:
                        message = json.loads(message_json)
                        # Only process messages that aren't our own
                        if message.get("username") != self.username:
                            # Decrypt message content if it's a regular chat message (not a system message)
                            if (message.get("type") == "message" and 
                                message.get("username") != "System" and 
                                self.encryption):
                                encrypted_content = message.get("content")
                                if encrypted_content:
                                    try:
                                        decrypted_content = self.encryption.decrypt_message(encrypted_content)
                                        if decrypted_content:
                                            message["content"] = decrypted_content
                                        else:
                                            message["content"] = "[Encrypted message - cannot decrypt]"
                                    except Exception as e:
                                        message["content"] = "[Encrypted message - cannot decrypt]"
                            
                            self.ui.add_message(message)
                    except json.JSONDecodeError as e:
                        # Only show decode errors for non-typing messages (to reduce noise)
                        if "typing_status" not in message_json:
                            self.ui.add_message({
                                "type": "message",
                                "username": "System",
                                "content": f"Error decoding message: {e}"
                            })
                    except Exception as e:
                        self.ui.add_message({
                            "type": "message",
                            "username": "System",
                            "content": f"Error processing message: {e}"
                        })
            except Exception as e:
                self.ui.add_message({
                    "type": "message",
                    "username": "System",
                    "content": f"Connection error: {e}"
                })
                break
                
    def send_typing_status(self, is_typing=True):
        """Send typing status to server"""
        try:
            current_time = time.time()
            # Always send if state changes to false, otherwise respect rate limit
            if not is_typing or current_time - self.last_typing_update >= self.typing_update_delay:
                self.last_typing_update = current_time
                self.send_message({
                    "type": "typing_status",
                    "username": self.username,
                    "is_typing": is_typing
                })
        except Exception as e:
            pass  # Ignore typing status errors
            
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
            last_typing_state = False
            while True:
                message = self.ui.get_input()
                current_typing_state = self.ui.is_typing()
                
                # Send typing status only when state changes
                if current_typing_state != last_typing_state:
                    self.send_typing_status(current_typing_state)
                    last_typing_state = current_typing_state
                
                if message is not None:
                    if message.lower() == '/exit':
                        # Send not typing status before exit
                        self.send_typing_status(False)
                        break
                    self.send_message({
                        "type": "message",
                        "username": self.username,
                        "content": message
                    })
                    # Send not typing status after sending message
                    self.send_typing_status(False)
                    last_typing_state = False
                    
        except KeyboardInterrupt:
            pass
        finally:
            # Ensure we send not typing status on exit
            self.send_typing_status(False)
            self.ui.stop()
            self.socket.close()
            
if __name__ == "__main__":
    # Get server address from command line args if provided
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
    
    client = CowtalkClient(host, port)
    client.start()
