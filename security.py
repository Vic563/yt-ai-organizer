"""Security utilities for encryption and password handling"""

import os
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Encryption key management
_encryption_key = None

def get_or_create_encryption_key() -> bytes:
    """Get or create encryption key for API keys"""
    global _encryption_key
    
    if _encryption_key:
        return _encryption_key
    
    # Try to load from environment
    key_str = os.environ.get("ENCRYPTION_KEY")
    if key_str:
        _encryption_key = base64.urlsafe_b64decode(key_str)
        return _encryption_key
    
    # Generate new key if not exists
    key = Fernet.generate_key()
    _encryption_key = key
    
    # Save to .env file for persistence
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    with open(env_path, 'a') as f:
        f.write(f"\nENCRYPTION_KEY={base64.urlsafe_b64encode(key).decode()}\n")
    
    return key

def derive_key_from_password(password: str, salt: bytes) -> bytes:
    """Derive encryption key from password"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def encrypt_value(value: str) -> str:
    """Encrypt a string value"""
    key = get_or_create_encryption_key()
    f = Fernet(key)
    return f.encrypt(value.encode()).decode()

def decrypt_value(encrypted_value: str) -> str:
    """Decrypt an encrypted string value"""
    key = get_or_create_encryption_key()
    f = Fernet(key)
    return f.decrypt(encrypted_value.encode()).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def hash_token(token: str) -> str:
    """Create a hash of a token for storage"""
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()

def generate_api_key() -> str:
    """Generate a new API key"""
    return secrets.token_urlsafe(32)

def rotate_encryption_key(old_key: bytes, new_key: bytes, encrypted_values: list) -> list:
    """Rotate encryption key for all encrypted values"""
    old_fernet = Fernet(old_key)
    new_fernet = Fernet(new_key)
    
    rotated_values = []
    for encrypted_value in encrypted_values:
        # Decrypt with old key
        decrypted = old_fernet.decrypt(encrypted_value.encode())
        # Encrypt with new key
        new_encrypted = new_fernet.encrypt(decrypted)
        rotated_values.append(new_encrypted.decode())
    
    return rotated_values