"""Add full-text search capability using SQLite FTS5"""

def up(conn):
    """Apply migration - create FTS5 virtual table for video search"""
    cursor = conn.cursor()
    
    # Check if FTS5 is available
    cursor.execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')")
    fts5_available = cursor.fetchone()
    
    if not fts5_available or not fts5_available[0]:
        # Fall back to FTS4 if FTS5 is not available
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts USING fts4(
                video_id,
                title,
                description,
                channel_title,
                transcript,
                tokenize=porter
            )
        """)
    else:
        # Create FTS5 virtual table
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts USING fts5(
                video_id UNINDEXED,
                title,
                description,
                channel_title,
                transcript,
                tokenize='porter unicode61'
            )
        """)
    
    # Create triggers to keep FTS table in sync with videos table
    
    # Insert trigger
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS videos_fts_insert 
        AFTER INSERT ON videos
        BEGIN
            INSERT INTO videos_fts (video_id, title, description, channel_title, transcript)
            SELECT 
                NEW.video_id,
                NEW.title,
                NEW.description,
                NEW.channel_title,
                (SELECT transcript_text FROM transcripts WHERE video_id = NEW.video_id)
            FROM videos WHERE video_id = NEW.video_id;
        END
    """)
    
    # Update trigger
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS videos_fts_update
        AFTER UPDATE ON videos
        BEGIN
            UPDATE videos_fts 
            SET 
                title = NEW.title,
                description = NEW.description,
                channel_title = NEW.channel_title
            WHERE video_id = NEW.video_id;
        END
    """)
    
    # Delete trigger
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS videos_fts_delete
        AFTER DELETE ON videos
        BEGIN
            DELETE FROM videos_fts WHERE video_id = OLD.video_id;
        END
    """)
    
    # Create transcripts table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            video_id TEXT PRIMARY KEY,
            transcript_text TEXT,
            language TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
        )
    """)
    
    # Create trigger for transcript updates
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS transcripts_fts_update
        AFTER INSERT OR UPDATE ON transcripts
        BEGIN
            UPDATE videos_fts 
            SET transcript = NEW.transcript_text
            WHERE video_id = NEW.video_id;
        END
    """)
    
    # Populate FTS table with existing data
    cursor.execute("""
        INSERT OR REPLACE INTO videos_fts (video_id, title, description, channel_title, transcript)
        SELECT 
            v.video_id,
            v.title,
            v.description,
            v.channel_title,
            t.transcript_text
        FROM videos v
        LEFT JOIN transcripts t ON v.video_id = t.video_id
    """)
    
    # Create a rank configuration table for search relevance tuning
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fts_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Insert default weights for different fields
    cursor.execute("""
        INSERT OR REPLACE INTO fts_config (key, value) VALUES
        ('title_weight', '10.0'),
        ('description_weight', '5.0'),
        ('channel_weight', '3.0'),
        ('transcript_weight', '1.0')
    """)
    
    conn.commit()

def down(conn):
    """Rollback migration - remove FTS tables and triggers"""
    cursor = conn.cursor()
    
    # Drop triggers
    cursor.execute("DROP TRIGGER IF EXISTS videos_fts_insert")
    cursor.execute("DROP TRIGGER IF EXISTS videos_fts_update")
    cursor.execute("DROP TRIGGER IF EXISTS videos_fts_delete")
    cursor.execute("DROP TRIGGER IF EXISTS transcripts_fts_update")
    
    # Drop FTS table
    cursor.execute("DROP TABLE IF EXISTS videos_fts")
    
    # Drop config table
    cursor.execute("DROP TABLE IF EXISTS fts_config")
    
    # Note: We don't drop the transcripts table as it contains data
    
    conn.commit()