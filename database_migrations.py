"""Database migration system"""

import os
import sqlite3
import importlib.util
import logging
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

def get_migrations_dir() -> Path:
    """Get the migrations directory path"""
    return Path(os.path.dirname(__file__)) / "migrations"

def get_applied_migrations(conn: sqlite3.Connection) -> List[str]:
    """Get list of already applied migrations"""
    cursor = conn.cursor()
    
    # Create migrations table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    
    # Get applied migrations
    cursor.execute("SELECT name FROM migrations ORDER BY name")
    return [row[0] for row in cursor.fetchall()]

def get_migration_files() -> List[Tuple[str, Path]]:
    """Get all migration files in order"""
    migrations_dir = get_migrations_dir()
    if not migrations_dir.exists():
        return []
    
    migration_files = []
    for file_path in sorted(migrations_dir.glob("*.py")):
        if file_path.name.startswith("__"):
            continue
        migration_files.append((file_path.stem, file_path))
    
    return migration_files

def load_migration_module(file_path: Path):
    """Dynamically load a migration module"""
    spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def run_migrations():
    """Run all pending database migrations"""
    from config import get_settings
    settings = get_settings()
    
    try:
        conn = sqlite3.connect(settings.database_path)
        applied_migrations = get_applied_migrations(conn)
        migration_files = get_migration_files()
        
        pending_migrations = [
            (name, path) for name, path in migration_files 
            if name not in applied_migrations
        ]
        
        if not pending_migrations:
            logger.info("No pending migrations")
            return
        
        logger.info(f"Found {len(pending_migrations)} pending migrations")
        
        for migration_name, migration_path in pending_migrations:
            logger.info(f"Running migration: {migration_name}")
            
            try:
                # Create backup before migration
                backup_path = Path(settings.database_path).with_suffix(f'.backup.{migration_name}')
                backup_conn = sqlite3.connect(str(backup_path))
                with backup_conn:
                    conn.backup(backup_conn)
                backup_conn.close()
                logger.info(f"Created backup at: {backup_path}")
                
                # Load and run migration
                module = load_migration_module(migration_path)
                
                if hasattr(module, 'up'):
                    module.up(conn)
                else:
                    logger.warning(f"Migration {migration_name} has no 'up' function")
                    continue
                
                # Record migration as applied
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO migrations (name) VALUES (?)",
                    (migration_name,)
                )
                conn.commit()
                
                logger.info(f"Successfully applied migration: {migration_name}")
                
            except Exception as e:
                logger.error(f"Error applying migration {migration_name}: {e}")
                conn.rollback()
                raise
        
        conn.close()
        logger.info("All migrations completed successfully")
        
    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise

def rollback_migration(migration_name: str):
    """Rollback a specific migration"""
    from config import get_settings
    settings = get_settings()
    
    try:
        conn = sqlite3.connect(settings.database_path)
        
        # Find the migration file
        migration_files = dict(get_migration_files())
        if migration_name not in migration_files:
            raise ValueError(f"Migration {migration_name} not found")
        
        # Load and run rollback
        module = load_migration_module(migration_files[migration_name])
        
        if hasattr(module, 'down'):
            module.down(conn)
        else:
            logger.warning(f"Migration {migration_name} has no 'down' function")
            return
        
        # Remove from migrations table
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM migrations WHERE name = ?",
            (migration_name,)
        )
        conn.commit()
        
        conn.close()
        logger.info(f"Successfully rolled back migration: {migration_name}")
        
    except Exception as e:
        logger.error(f"Rollback error: {e}")
        raise