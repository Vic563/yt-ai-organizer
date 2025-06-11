"""Add performance indexes for better query performance"""
import logging

logger = logging.getLogger(__name__)

def up(conn):
    """Apply migration - add performance indexes"""
    cursor = conn.cursor()
    logger.info("Applying migration 003_add_performance_indexes...")

    # Add indexes for videos table
    logger.debug("Creating indexes for 'videos' table...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_updated_at ON videos(updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_has_transcript ON videos(has_transcript)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_topic_published ON videos(topic_id, published_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_channel_published ON videos(channel_id, published_at DESC)")

    # Add indexes for api_usage table
    logger.debug("Checking for 'api_usage' table to create indexes...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_usage'")
    if cursor.fetchone():
        logger.info("'api_usage' table found. Checking columns for index creation...")
        cursor.execute("PRAGMA table_info(api_usage)")
        api_usage_columns = [column[1] for column in cursor.fetchall()]

        if 'query_type' in api_usage_columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_query_type ON api_usage(query_type)")
            logger.debug("Created index idx_api_usage_query_type.")
        else:
            logger.warning("Column 'query_type' not found in 'api_usage' table. Skipping index creation for it.")

        if 'created_at' in api_usage_columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at)")
            logger.debug("Created index idx_api_usage_created_at.")
        else:
            logger.warning("Column 'created_at' not found in 'api_usage' table. Skipping index creation for it.")

        if 'user_query' in api_usage_columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_user_query ON api_usage(user_query)")
            logger.debug("Created index idx_api_usage_user_query.")
        else:
            logger.warning("Column 'user_query' not found in 'api_usage' table. Skipping index creation for idx_api_usage_user_query.")
    else:
        logger.info("'api_usage' table not found. Skipping index creation for it.")

    # Add indexes for messages table
    logger.debug("Checking for 'messages' table to create indexes...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
    if cursor.fetchone():
        logger.info("'messages' table found. Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)")
        logger.debug("Created indexes for 'messages' table.")
    else:
        logger.info("'messages' table not found. Skipping index creation for it.")

    # Add indexes for encrypted_keys table
    logger.debug("Creating index for 'encrypted_keys' table...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_encrypted_keys_key_name ON encrypted_keys(key_name)")

    # Add indexes for sessions table
    logger.debug("Creating index for 'sessions' table...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)")
    
    logger.info("Migration 003_add_performance_indexes applied successfully.")
    # conn.commit() # Removed: Handled by migration runner

def down(conn):
    """Rollback migration - remove indexes"""
    cursor = conn.cursor()
    logger.info("Rolling back migration 003_add_performance_indexes...")

    # Remove videos indexes
    logger.debug("Dropping indexes for 'videos' table...")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_created_at")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_updated_at")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_has_transcript")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_channel_id")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_published_at")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_topic_published")
    cursor.execute("DROP INDEX IF EXISTS idx_videos_channel_published")

    # Remove api_usage indexes
    logger.debug("Dropping indexes for 'api_usage' table...")
    cursor.execute("DROP INDEX IF EXISTS idx_api_usage_query_type")
    cursor.execute("DROP INDEX IF EXISTS idx_api_usage_created_at")
    cursor.execute("DROP INDEX IF EXISTS idx_api_usage_user_query")

    # Remove messages indexes
    logger.debug("Dropping indexes for 'messages' table...")
    cursor.execute("DROP INDEX IF EXISTS idx_messages_conversation_id")
    cursor.execute("DROP INDEX IF EXISTS idx_messages_created_at")

    # Remove encrypted_keys indexes
    logger.debug("Dropping index for 'encrypted_keys' table...")
    cursor.execute("DROP INDEX IF EXISTS idx_encrypted_keys_key_name")

    # Remove sessions indexes
    logger.debug("Dropping index for 'sessions' table...")
    cursor.execute("DROP INDEX IF EXISTS idx_sessions_expires_at")
    
    logger.info("Migration 003_add_performance_indexes rolled back successfully.")
    # conn.commit() # Removed: Handled by migration runner
