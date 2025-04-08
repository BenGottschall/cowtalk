from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

class MessageEncryption:
    def __init__(self, password):
        """Initialize encryption with a password"""
        # Generate a key from the password using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'cowtalk_static_salt',  # In production, use a unique salt per user
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.fernet = Fernet(key)

    def encrypt_message(self, message):
        """Encrypt a message"""
        return self.fernet.encrypt(message.encode()).decode()

    def decrypt_message(self, encrypted_message):
        """Decrypt a message"""
        try:
            return self.fernet.decrypt(encrypted_message.encode()).decode()
        except Exception as e:
            # print(f"Failed to decrypt message: {e}")
            return None 