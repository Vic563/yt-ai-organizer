"""Database migration to add topics support"""
import os
import sqlite3
from pathlib import Path

def run_migration():
    """Run the database migration"""
    db_path = Path(os.path.dirname(os.path.dirname(__file__))) / 'data' / 'project_insight.db'
    backup_path = db_path.with_suffix('.db.backup')
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if migration is needed
        cursor.execute("PRAGMA table_info('videos')")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'topic_id' in columns:
            print("Migration already applied")
            return
            
        print("Starting database migration...")
        
        # Create a backup
        print("Creating backup...")
        backup_conn = sqlite3.connect(str(backup_path))
        with backup_conn:
            conn.backup(backup_conn)
        backup_conn.close()
        print(f"Backup created at: {backup_path}")
        
        # Create topics table
        print("Creating topics table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create new videos table with topic columns
        print("Creating new videos table...")
        cursor.execute("""
        CREATE TABLE videos_new (
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
        print("Migrating data...")
        cursor.execute("PRAGMA table_info(videos)")
        old_columns = [col[1] for col in cursor.fetchall()]
        
        # Build column list for SELECT and INSERT
        common_columns = [col for col in old_columns 
                         if col not in ['topic_id']]
        
        # Copy data to new table
        cursor.execute(f"""
        INSERT INTO videos_new ({', '.join(common_columns)})
        SELECT {', '.join(common_columns)} FROM videos
        """)
        
        # Drop old table and rename new one
        print("Finalizing migration...")
        cursor.execute("DROP TABLE videos")
        cursor.execute("ALTER TABLE videos_new RENAME TO videos")
        
        # Create indexes
        print("Creating indexes...")
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_channel 
        ON videos(channel_id)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_published 
        ON videos(published_at)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_transcript 
        ON videos(has_transcript)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_topic 
        ON videos(topic_id)
        """)
        
        conn.commit()
        print("Migration completed successfully!")

if __name__ == "__main__":
    run_migration()
