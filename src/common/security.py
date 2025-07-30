"""Security utilities for encrypting sensitive data like API keys."""

import os
import base64
import secrets
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class SecureStorage:
    """Handles encryption/decryption of sensitive data using Fernet (AES 128)."""
    
    def __init__(self, password: Optional[str] = None):
        """Initialize with a master password or generate one."""
        self._fernet = None
        self._setup_encryption(password)
    
    def _setup_encryption(self, password: Optional[str] = None):
        """Setup encryption using either provided password or auto-generated key."""
        # Use provided password or generate a secure one
        if password is None:
            # Check for existing key file first
            key_file = self._get_key_file_path()
            if os.path.exists(key_file):
                try:
                    with open(key_file, 'rb') as f:
                        key = f.read()
                    self._fernet = Fernet(key)
                    return
                except Exception:
                    # If key file is corrupted, generate new one
                    pass
            
            # Generate new key and save it
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions (owner read/write only)
            os.chmod(key_file, 0o600)
            self._fernet = Fernet(key)
        else:
            # Derive key from password using PBKDF2
            salt = self._get_or_create_salt()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            self._fernet = Fernet(key)
    
    def _get_key_file_path(self) -> str:
        """Get the path for the encryption key file."""
        # Support Docker data directory structure
        if os.path.exists("/app/data"):
            return "/app/data/.security/encryption.key"
        else:
            return ".security/encryption.key"
    
    def _get_salt_file_path(self) -> str:
        """Get the path for the salt file."""
        # Support Docker data directory structure
        if os.path.exists("/app/data"):
            return "/app/data/.security/salt.bin"
        else:
            return ".security/salt.bin"
    
    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create a new one."""
        salt_file = self._get_salt_file_path()
        if os.path.exists(salt_file):
            with open(salt_file, 'rb') as f:
                return f.read()
        else:
            salt = secrets.token_bytes(16)
            os.makedirs(os.path.dirname(salt_file), exist_ok=True)
            with open(salt_file, 'wb') as f:
                f.write(salt)
            # Set restrictive permissions
            os.chmod(salt_file, 0o600)
            return salt
    
    def encrypt(self, data: str) -> str:
        """Encrypt a string and return base64 encoded result."""
        if not data:
            return ""
        encrypted_data = self._fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt base64 encoded encrypted data."""
        if not encrypted_data:
            return ""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self._fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {e}")
    
    def is_encrypted(self, data: str) -> bool:
        """Check if data appears to be encrypted (base64 format)."""
        if not data:
            return False
        try:
            # Check if it's valid base64 and has reasonable length for encrypted data
            decoded = base64.urlsafe_b64decode(data.encode())
            return len(decoded) > 32  # Fernet adds overhead, so encrypted data is longer
        except Exception:
            return False
    
    @staticmethod
    def secure_compare(a: str, b: str) -> bool:
        """Constant-time string comparison to prevent timing attacks."""
        return secrets.compare_digest(a.encode(), b.encode())
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token."""
        return secrets.token_urlsafe(length)


class APIKeyManager:
    """Manages encrypted storage and retrieval of API keys."""
    
    def __init__(self):
        self.storage = SecureStorage()
    
    def store_api_key(self, key_id: str, api_key: str) -> str:
        """Store an API key securely and return the encrypted version."""
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")
        
        # Validate API key format
        api_key = api_key.strip()
        if not self._validate_api_key_format(api_key):
            raise ValueError("Invalid API key format")
        
        return self.storage.encrypt(api_key)
    
    def retrieve_api_key(self, encrypted_key: str) -> str:
        """Retrieve and decrypt an API key."""
        if not encrypted_key:
            return ""
        
        try:
            return self.storage.decrypt(encrypted_key)
        except Exception as e:
            # Log error but don't expose details
            print(f"⚠️ Warning: Failed to decrypt API key: corrupted data")
            return ""
    
    def _validate_api_key_format(self, api_key: str) -> bool:
        """Validate API key format for security."""
        if not api_key:
            return False
        
        # Check for common API key patterns
        if api_key.startswith(('sk-', 'sk-ant-api', 'pk_')) or \
           (len(api_key) >= 20 and '_' in api_key):  # DO AI keys have underscores
            # Basic length checks
            if len(api_key) < 20:  # Too short to be valid
                return False
            if len(api_key) > 200:  # Suspiciously long
                return False
            # Check for obvious test/placeholder values
            test_patterns = ['test', 'example', 'placeholder', 'your_key_here', 'xxx', '000']
            if any(pattern in api_key.lower() for pattern in test_patterns):
                return False
            return True
        
        return False
    
    def mask_api_key(self, api_key: str) -> str:
        """Create a safe display version of an API key."""
        if not api_key or len(api_key) < 8:
            return ""
        
        # Show first 8 and last 4 characters with dots in between
        if len(api_key) <= 12:
            return api_key[:4] + "..." + api_key[-2:]
        else:
            return api_key[:8] + "..." + api_key[-4:]