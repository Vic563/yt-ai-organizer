"""Database migration to add topics support"""
import logging

logger = logging.getLogger(__name__)

def up(conn):
    """Apply migration - add topics table and topic_id to videos"""
    cursor = conn.cursor()
    
    logger.info("Applying migration 001_add_topics: Creating topics table and adding topic_id to videos.")

    # Create topics table
    logger.info("Creating topics table (IF NOT EXISTS)...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create new videos table with topic columns
    logger.info("Creating new videos table (videos_temp_001)...")
    cursor.execute("""
    CREATE TABLE videos_temp_001 (
        video_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        channel_id TEXT NOT NULL,
        channel_title TEXT NOT NULL,
        published_at TEXT NOT NULL,
        duration TEXT,
        thumbnail_url TEXT,
        view_count INTEGER,
        like_count INTEGER,
        has_transcript BOOLEAN DEFAULT FALSE,
        transcript_language TEXT,
        topic_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """)
    
    # Copy data from old table to new table
    logger.info("Migrating data from 'videos' to 'videos_temp_001'...")
    
    cursor.execute("PRAGMA table_info(videos)")
    old_columns = [col[1] for col in cursor.fetchall()]
    
    columns_to_copy = [col for col in old_columns if col != 'topic_id']
    columns_to_copy_str = ', '.join(columns_to_copy)
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='videos'")
    if cursor.fetchone():
        cursor.execute(f"INSERT INTO videos_temp_001 ({columns_to_copy_str}) SELECT {columns_to_copy_str} FROM videos")
    else:
        logger.info("'videos' table does not exist or is empty, skipping data copy.")

    logger.info("Dropping old 'videos' table...")
    cursor.execute("DROP TABLE videos")
    
    logger.info("Renaming 'videos_temp_001' to 'videos'...")
    cursor.execute("ALTER TABLE videos_temp_001 RENAME TO videos")
    
    logger.info("Creating indexes for 'videos' table (related to 001_add_topics)...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_published ON videos(published_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_transcript ON videos(has_transcript)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_topic ON videos(topic_id)")
    
    logger.info("Migration 001_add_topics applied successfully by up().")

def down(conn):
    """Rollback migration - remove topics table and topic_id from videos"""
    cursor = conn.cursor()
    logger.info("Rolling back migration 001_add_topics.")

    logger.info("Creating temporary videos table (videos_temp_rollback_001) without topic_id...")
    cursor.execute("""
    CREATE TABLE videos_temp_rollback_001 (
        video_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        channel_id TEXT NOT NULL,
        channel_title TEXT NOT NULL,
        published_at TEXT NOT NULL,
        duration TEXT,
        thumbnail_url TEXT,
        view_count INTEGER,
        like_count INTEGER,
        has_transcript BOOLEAN DEFAULT FALSE,
        transcript_language TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("PRAGMA table_info(videos_temp_rollback_001)")
    rollback_columns = [col[1] for col in cursor.fetchall()]
    rollback_columns_str = ', '.join(rollback_columns)

    logger.info("Copying data from 'videos' to 'videos_temp_rollback_001'...")
    cursor.execute(f"INSERT INTO videos_temp_rollback_001 ({rollback_columns_str}) SELECT {rollback_columns_str} FROM videos")

    logger.info("Dropping current 'videos' table...")
    cursor.execute("DROP TABLE videos")

    logger.info("Renaming 'videos_temp_rollback_001' to 'videos'...")
    cursor.execute("ALTER TABLE videos_temp_rollback_001 RENAME TO videos")

    logger.info("Dropping 'topics' table...")
    cursor.execute("DROP TABLE IF EXISTS topics")
    
    logger.info("Recreating original indexes for 'videos' table (post-rollback)...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_published ON videos(published_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_transcript ON videos(has_transcript)")

    logger.info("Migration 001_add_topics rolled back successfully by down().")
