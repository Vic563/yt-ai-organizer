"""Database connection pooling with SQLAlchemy"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.engine import Engine

from config import get_settings

logger = logging.getLogger(__name__)

# Global engine instance
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None

def get_database_url() -> str:
    """Get database URL for SQLAlchemy"""
    settings = get_settings()
    return f"sqlite:///{settings.database_path}"

def init_db_engine(
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_timeout: int = 30,
    pool_recycle: int = 3600
) -> Engine:
    """Initialize SQLAlchemy engine with connection pooling"""
    global _engine, _SessionLocal
    
    if _engine is not None:
        return _engine
    
    # SQLite doesn't support true connection pooling, but we can still use SQLAlchemy
    # for better connection management and consistent API
    engine_args = {
        "connect_args": {
            "check_same_thread": False,  # SQLite specific
            "timeout": 30
        },
        "echo": False,  # Set to True for SQL query logging
    }
    
    # For SQLite, we use NullPool to avoid connection pooling issues
    # In production with PostgreSQL/MySQL, use QueuePool
    if get_database_url().startswith("sqlite"):
        engine_args["poolclass"] = NullPool
    else:
        engine_args.update({
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_timeout": pool_timeout,
            "pool_recycle": pool_recycle,
            "pool_pre_ping": True,  # Verify connections before using
        })
    
    _engine = create_engine(get_database_url(), **engine_args)
    
    # Configure SQLite for better performance
    if get_database_url().startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys=ON")
            # Optimize SQLite performance
            cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes
            cursor.execute("PRAGMA cache_size=10000")  # Larger cache
            cursor.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
            cursor.close()
    
    # Create session factory
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    
    logger.info("Database engine initialized with connection pooling")
    return _engine

def get_engine() -> Engine:
    """Get or create database engine"""
    if _engine is None:
        init_db_engine()
    return _engine

def get_session() -> Session:
    """Get a new database session"""
    if _SessionLocal is None:
        init_db_engine()
    return _SessionLocal()

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Database session context manager"""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def close_db_engine():
    """Close database engine and cleanup connections"""
    global _engine, _SessionLocal
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        logger.info("Database engine closed")

# Connection pool statistics
def get_pool_status() -> dict:
    """Get connection pool statistics"""
    if _engine is None:
        return {"status": "not initialized"}
    
    pool = _engine.pool
    return {
        "size": getattr(pool, "size", None),
        "checked_in_connections": getattr(pool, "checkedin", None),
        "overflow": getattr(pool, "overflow", None),
        "total": getattr(pool, "total", None),
        "status": "active"
    }

# Raw SQL execution helpers for migration compatibility
def execute_raw_sql(sql: str, params: Optional[tuple] = None) -> None:
    """Execute raw SQL statement"""
    with get_db() as session:
        result = session.execute(text(sql), params or {})
        session.commit()
        return result

def fetch_one_raw(sql: str, params: Optional[tuple] = None) -> Optional[tuple]:
    """Fetch one row with raw SQL"""
    with get_db() as session:
        result = session.execute(text(sql), params or {})
        return result.fetchone()

def fetch_all_raw(sql: str, params: Optional[tuple] = None) -> list:
    """Fetch all rows with raw SQL"""
    with get_db() as session:
        result = session.execute(text(sql), params or {})
        return result.fetchall()

# Backward compatibility wrapper
@contextmanager
def get_db_connection():
    """Get database connection (backward compatibility with sqlite3 API)"""
    # This provides a compatibility layer for existing code
    # Returns the raw SQLite connection from SQLAlchemy
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        yield conn
    finally:
        conn.close()