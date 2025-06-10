"""Full-text search implementation using SQLite FTS5"""

import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """Search result with relevance score"""
    video_id: str
    title: str
    description: str
    channel_title: str
    published_at: str
    thumbnail_url: str
    score: float
    snippet: Optional[str] = None
    matched_fields: List[str] = None

class FullTextSearch:
    """Full-text search implementation using SQLite FTS"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self._check_fts_available()
    
    def _check_fts_available(self) -> bool:
        """Check if FTS is available and properly set up"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='videos_fts'
        """)
        return cursor.fetchone() is not None
    
    def _get_field_weights(self) -> Dict[str, float]:
        """Get field weights for relevance scoring"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM fts_config WHERE key LIKE '%_weight'")
        weights = {}
        for row in cursor.fetchall():
            field = row['key'].replace('_weight', '')
            weights[field] = float(row['value'])
        return weights
    
    def search(
        self, 
        query: str, 
        limit: int = 10,
        fields: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Perform full-text search across video content
        
        Args:
            query: Search query (supports FTS5 syntax)
            limit: Maximum number of results
            fields: List of fields to search in (default: all)
        
        Returns:
            List of SearchResult objects ordered by relevance
        """
        if not self._check_fts_available():
            logger.warning("FTS table not available, falling back to basic search")
            return self._fallback_search(query, limit)
        
        cursor = self.conn.cursor()
        weights = self._get_field_weights()
        
        # Prepare the query for FTS
        fts_query = self._prepare_fts_query(query)
        
        # Build field-specific search if requested
        if fields:
            field_conditions = []
            for field in fields:
                if field in ['title', 'description', 'channel_title', 'transcript']:
                    field_conditions.append(f"{field}:{fts_query}")
            search_expr = " OR ".join(field_conditions) if field_conditions else fts_query
        else:
            search_expr = fts_query
        
        # Perform the search with relevance scoring
        sql = """
            SELECT 
                v.*,
                fts.rank as fts_rank,
                snippet(videos_fts, 1, '<mark>', '</mark>', '...', 20) as snippet,
                bm25(videos_fts, ?, ?, ?, ?) as bm25_score
            FROM videos_fts fts
            JOIN videos v ON fts.video_id = v.video_id
            WHERE videos_fts MATCH ?
            ORDER BY bm25_score
            LIMIT ?
        """
        
        params = (
            weights.get('title', 10.0),
            weights.get('description', 5.0),
            weights.get('channel', 3.0),
            weights.get('transcript', 1.0),
            search_expr,
            limit
        )
        
        try:
            cursor.execute(sql, params)
            results = []
            
            for row in cursor.fetchall():
                # Determine which fields matched
                matched_fields = self._get_matched_fields(row['video_id'], fts_query)
                
                result = SearchResult(
                    video_id=row['video_id'],
                    title=row['title'],
                    description=row['description'],
                    channel_title=row['channel_title'],
                    published_at=row['published_at'],
                    thumbnail_url=row['thumbnail_url'],
                    score=abs(row['bm25_score']),  # BM25 returns negative scores
                    snippet=row['snippet'],
                    matched_fields=matched_fields
                )
                results.append(result)
            
            return results
            
        except sqlite3.OperationalError as e:
            logger.error(f"FTS search error: {e}")
            return self._fallback_search(query, limit)
    
    def _prepare_fts_query(self, query: str) -> str:
        """Prepare query for FTS5 syntax"""
        # Remove special characters that might break FTS
        special_chars = ['(', ')', '"', "'", '-', '*']
        cleaned_query = query
        for char in special_chars:
            cleaned_query = cleaned_query.replace(char, ' ')
        
        # Split into words and quote each one
        words = cleaned_query.strip().split()
        if not words:
            return '""'
        
        # For multi-word queries, search for the phrase and individual words
        if len(words) > 1:
            phrase = f'"{" ".join(words)}"'
            individual = ' OR '.join(f'"{word}"' for word in words)
            return f'({phrase} OR {individual})'
        else:
            return f'"{words[0]}"'
    
    def _get_matched_fields(self, video_id: str, query: str) -> List[str]:
        """Determine which fields matched the search query"""
        cursor = self.conn.cursor()
        matched = []
        
        # Check each field individually
        fields = ['title', 'description', 'channel_title', 'transcript']
        for field in fields:
            sql = f"""
                SELECT 1 FROM videos_fts 
                WHERE video_id = ? AND {field} MATCH ?
                LIMIT 1
            """
            cursor.execute(sql, (video_id, query))
            if cursor.fetchone():
                matched.append(field)
        
        return matched
    
    def _fallback_search(self, query: str, limit: int) -> List[SearchResult]:
        """Fallback to LIKE-based search if FTS is not available"""
        from database_search import search_videos_safe
        
        results = search_videos_safe(self.conn, query, limit)
        search_results = []
        
        for video in results:
            search_results.append(SearchResult(
                video_id=video['video_id'],
                title=video['title'],
                description=video['description'],
                channel_title=video['channel_title'],
                published_at=video['published_at'],
                thumbnail_url=video['thumbnail_url'],
                score=video.get('relevance_score', 1.0),
                snippet=None,
                matched_fields=['title', 'description']  # Approximate
            ))
        
        return search_results
    
    def suggest_queries(self, partial_query: str, limit: int = 5) -> List[str]:
        """
        Suggest search queries based on partial input
        
        Args:
            partial_query: Partial search query
            limit: Maximum number of suggestions
        
        Returns:
            List of suggested queries
        """
        if not partial_query or len(partial_query) < 2:
            return []
        
        cursor = self.conn.cursor()
        
        # Get unique words from titles that start with the partial query
        sql = """
            SELECT DISTINCT 
                LOWER(SUBSTR(
                    title, 
                    INSTR(LOWER(title), LOWER(?)), 
                    LENGTH(?)
                )) as suggestion
            FROM videos
            WHERE LOWER(title) LIKE LOWER(?)
            LIMIT ?
        """
        
        pattern = f"%{partial_query}%"
        cursor.execute(sql, (partial_query, partial_query, pattern, limit))
        
        suggestions = []
        for row in cursor.fetchall():
            if row['suggestion']:
                suggestions.append(row['suggestion'])
        
        return suggestions[:limit]
    
    def get_related_videos(self, video_id: str, limit: int = 5) -> List[SearchResult]:
        """
        Find videos related to a given video using FTS
        
        Args:
            video_id: ID of the video to find related content for
            limit: Maximum number of related videos
        
        Returns:
            List of related videos
        """
        cursor = self.conn.cursor()
        
        # Get the video's content
        cursor.execute("""
            SELECT title, description FROM videos WHERE video_id = ?
        """, (video_id,))
        
        video = cursor.fetchone()
        if not video:
            return []
        
        # Extract key terms from title and description
        combined_text = f"{video['title']} {video['description']}"
        
        # Use the title as the main search query
        results = self.search(video['title'], limit + 1)  # +1 to exclude self
        
        # Filter out the original video
        related = [r for r in results if r.video_id != video_id]
        
        return related[:limit]

def create_fts_index(conn: sqlite3.Connection) -> None:
    """Create or rebuild the FTS index"""
    cursor = conn.cursor()
    
    # Clear existing FTS data
    cursor.execute("DELETE FROM videos_fts")
    
    # Rebuild from videos and transcripts tables
    cursor.execute("""
        INSERT INTO videos_fts (video_id, title, description, channel_title, transcript)
        SELECT 
            v.video_id,
            v.title,
            v.description,
            v.channel_title,
            t.transcript_text
        FROM videos v
        LEFT JOIN transcripts t ON v.video_id = t.video_id
    """)
    
    conn.commit()
    logger.info("FTS index rebuilt successfully")