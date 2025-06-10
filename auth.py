"""Authentication system for the application"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, validator
import sqlite3
import os
from security import (
    verify_password, get_password_hash, create_access_token, 
    create_refresh_token, decode_token, hash_token
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    
    @validator('username')
    def username_alphanumeric(cls, v):
        assert v.isalnum(), 'must be alphanumeric'
        assert len(v) >= 3, 'must be at least 3 characters'
        return v
    
    @validator('password')
    def password_strength(cls, v):
        assert len(v) >= 8, 'must be at least 8 characters'
        return v

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None

# Database functions
def get_db_connection():
    """Get database connection"""
    db_path = os.path.join(os.path.dirname(__file__), "data", "project_insight.db")
    return sqlite3.connect(db_path)

def create_user(user_data: UserCreate) -> UserResponse:
    """Create a new user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if user already exists
        cursor.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (user_data.username, user_data.email)
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered"
            )
        
        # Create user
        hashed_password = get_password_hash(user_data.password)
        cursor.execute(
            """INSERT INTO users (username, email, hashed_password) 
               VALUES (?, ?, ?)""",
            (user_data.username, user_data.email, hashed_password)
        )
        conn.commit()
        user_id = cursor.lastrowid
        
        # Fetch created user
        cursor.execute(
            """SELECT id, username, email, is_active, is_admin, created_at 
               FROM users WHERE id = ?""",
            (user_id,)
        )
        user = cursor.fetchone()
        
        return UserResponse(
            id=user[0],
            username=user[1],
            email=user[2],
            is_active=bool(user[3]),
            is_admin=bool(user[4]),
            created_at=datetime.fromisoformat(user[5])
        )
    finally:
        conn.close()

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """SELECT id, username, email, hashed_password, is_active, is_admin 
               FROM users WHERE username = ? OR email = ?""",
            (username, username)  # Allow login with email or username
        )
        user = cursor.fetchone()
        
        if not user:
            return None
        
        if not verify_password(password, user[3]):
            return None
        
        if not user[4]:  # is_active
            return None
        
        return {
            "id": user[0],
            "username": user[1],
            "email": user[2],
            "is_active": bool(user[4]),
            "is_admin": bool(user[5])
        }
    finally:
        conn.close()

def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    # Check if token is revoked
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        token_hash = hash_token(token)
        cursor.execute(
            "SELECT is_revoked FROM sessions WHERE token_hash = ?",
            (token_hash,)
        )
        session = cursor.fetchone()
        
        if session and session[0]:  # is_revoked
            raise credentials_exception
        
        # Get user details
        cursor.execute(
            """SELECT id, username, email, is_active, is_admin 
               FROM users WHERE username = ?""",
            (username,)
        )
        user = cursor.fetchone()
        
        if not user or not user[3]:  # is_active
            raise credentials_exception
        
        return {
            "id": user[0],
            "username": user[1],
            "email": user[2],
            "is_active": bool(user[3]),
            "is_admin": bool(user[4])
        }
    finally:
        conn.close()

def get_current_active_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Ensure user is active"""
    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_admin_user(current_user: Dict[str, Any] = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Ensure user is admin"""
    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

def create_user_session(user_id: int, access_token: str) -> None:
    """Create a session record for token tracking"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        token_hash = hash_token(access_token)
        expires_at = datetime.utcnow() + timedelta(minutes=30)
        
        cursor.execute(
            """INSERT INTO sessions (user_id, token_hash, expires_at) 
               VALUES (?, ?, ?)""",
            (user_id, token_hash, expires_at)
        )
        conn.commit()
    finally:
        conn.close()

def revoke_token(token: str) -> None:
    """Revoke a token"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        token_hash = hash_token(token)
        cursor.execute(
            "UPDATE sessions SET is_revoked = TRUE WHERE token_hash = ?",
            (token_hash,)
        )
        conn.commit()
    finally:
        conn.close()

def cleanup_expired_sessions() -> None:
    """Clean up expired sessions"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "DELETE FROM sessions WHERE expires_at < ?",
            (datetime.utcnow(),)
        )
        conn.commit()
    finally:
        conn.close()

# API route handlers
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """Login endpoint"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user["username"]})
    refresh_token = create_refresh_token(data={"sub": user["username"]})
    
    # Create session
    create_user_session(user["id"], access_token)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )

async def register(user_data: UserCreate) -> UserResponse:
    """Register a new user"""
    return create_user(user_data)

async def logout(token: str = Depends(oauth2_scheme)) -> Dict[str, str]:
    """Logout endpoint"""
    revoke_token(token)
    return {"message": "Successfully logged out"}

async def refresh(refresh_token: str) -> Token:
    """Refresh access token"""
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    username = payload.get("sub")
    access_token = create_access_token(data={"sub": username})
    
    # Get user ID for session
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if user:
            create_user_session(user[0], access_token)
    finally:
        conn.close()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )