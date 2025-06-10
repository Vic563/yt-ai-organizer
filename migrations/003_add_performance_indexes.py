"""Add performance indexes for better query performance"""

def up(conn):
    """Apply migration - add performance indexes"""
    cursor = conn.cursor()
    
    # Add indexes for videos table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_updated_at ON videos(updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_has_transcript ON videos(has_transcript)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at)")
    
    # Composite indexes for common query patterns
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_topic_published ON videos(topic_id, published_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_channel_published ON videos(channel_id, published_at DESC)")
    
    # Add indexes for api_usage table if it exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='api_usage'
    """)
    if cursor.fetchone():
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_query_type ON api_usage(query_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_user_query ON api_usage(user_query)")
    
    # Add indexes for messages table
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='messages'
    """)
    if cursor.fetchone():
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)")
    
    # Add indexes for encrypted_keys table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_encrypted_keys_key_name ON encrypted_keys(key_name)")
    
    # Add indexes for sessions table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)")
    
    conn.commit()

def down(conn):
    """Rollback migration - remove indexes"""
    cursor = conn.cursor()
    
    # Remove videos indexes
    cursor.execute("DROP INDEX IF EXISTS idx_videos_created_at")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_updated_at")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_has_transcript")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_channel_id")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_published_at")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_topic_published")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_channel_published")
    
    # Remove api_usage indexes
    cursor.execute("DROP INDEX IF EXISTS idx_api_usage_query_type")
    cursor.execute("DROP INDEX IF EXISTS idx_api_usage_created_at")
    cursor.execute("DROP INDEX IF EXISTS idx_api_usage_user_query")
    
    # Remove messages indexes
    cursor.execute("DROP INDEX IF EXISTS idx_messages_conversation_id")
    cursor.execute("DROP INDEX IF EXISTS idx_messages_created_at")
    
    # Remove encrypted_keys indexes
    cursor.execute("DROP INDEX IF EXISTS idx_encrypted_keys_key_name")
    
    # Remove sessions indexes
    cursor.execute("DROP INDEX IF EXISTS idx_sessions_expires_at")
    
    conn.commit()