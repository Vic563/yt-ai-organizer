"""Safe database search functions with proper parameterization"""

import sqlite3
import logging
from typing import List, Dict, Any, Set
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Common stop words to filter out
STOP_WORDS: Set[str] = {
    'i', 'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'to',
    'of', 'in', 'on', 'at', 'by', 'for', 'with', 'as', 'and', 'or', 'but', 'if', 'any',
    'some', 'all', 'no', 'not', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'this',
    'that', 'these', 'those', 'me', 'you', 'he', 'she', 'it', 'we', 'they', 'them', 'us',
    'about', 'videos', 'video', 'watch', 'see', 'get', 'go', 'come', 'take', 'make', 'know',
    'think', 'say', 'tell', 'ask', 'give', 'find', 'look', 'want', 'need', 'try', 'use',
    'work', 'call', 'first', 'last', 'long', 'great', 'little', 'own', 'other', 'old', 'right',
    'left', 'hand', 'part', 'child', 'eye', 'week', 'case', 'point', 'government', 'company',
    'number', 'group', 'problem', 'fact', 'show', 'like', 'just', 'should', 'well', 'also',
    'one', 'two', 'three', 'really', 'actually', 'even', 'still', 'much', 'very', 'just',
    'done', 'made', 'got', 'put', 'let', 'run', 'set', 'good', 'best', 'better', 'true'
}

def clean_query_words(query: str) -> List[str]:
    """Extract meaningful words from query, filtering out stop words"""
    words = query.lower().strip().split()
    query_words = []
    
    for word in words:
        # Only include words that are 3+ chars and not stop words
        if len(word) >= 3 and word not in STOP_WORDS:
            query_words.append(word)
    
    # If all words were filtered out, use original query as phrase
    if not query_words and query.strip():
        query_words = [query.lower().strip()]
    
    return query_words

def search_videos_exact_phrase(conn: sqlite3.Connection, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search for exact phrase match in titles and descriptions"""
    cursor = conn.cursor()
    exact_phrase = f"%{query.lower()}%"
    
    cursor.execute("""
        SELECT *,
               CASE
                   WHEN LOWER(title) LIKE ? THEN 3
                   WHEN LOWER(description) LIKE ? THEN 2
                   ELSE 1
               END as relevance_score
        FROM videos
        WHERE LOWER(title) LIKE ? OR LOWER(description) LIKE ?
        ORDER BY relevance_score DESC, published_at DESC
        LIMIT ?
    """, (exact_phrase, exact_phrase, exact_phrase, exact_phrase, limit))
    
    return [dict(row) for row in cursor.fetchall()]

def search_videos_by_words(conn: sqlite3.Connection, query_words: List[str], limit: int = 10) -> List[Dict[str, Any]]:
    """Search for videos matching individual words"""
    if not query_words:
        return []
    
    cursor = conn.cursor()
    
    # Build query with fixed structure - no dynamic SQL construction
    # We'll use a maximum of 10 search terms to prevent query explosion
    max_words = min(len(query_words), 10)
    query_words = query_words[:max_words]
    
    # Create a fixed query structure for up to 10 words
    # Each word gets a condition and a score
    base_query = """
        WITH search_params AS (
            SELECT ? as word1, ? as word2, ? as word3, ? as word4, ? as word5,
                   ? as word6, ? as word7, ? as word8, ? as word9, ? as word10
        ),
        scored_videos AS (
            SELECT v.*,
                   (CASE WHEN LOWER(v.title) LIKE '%' || sp.word1 || '%' OR 
                            LOWER(v.description) LIKE '%' || sp.word1 || '%' THEN 1 ELSE 0 END +
                    CASE WHEN sp.word2 IS NOT NULL AND 
                            (LOWER(v.title) LIKE '%' || sp.word2 || '%' OR 
                             LOWER(v.description) LIKE '%' || sp.word2 || '%') THEN 1 ELSE 0 END +
                    CASE WHEN sp.word3 IS NOT NULL AND 
                            (LOWER(v.title) LIKE '%' || sp.word3 || '%' OR 
                             LOWER(v.description) LIKE '%' || sp.word3 || '%') THEN 1 ELSE 0 END +
                    CASE WHEN sp.word4 IS NOT NULL AND 
                            (LOWER(v.title) LIKE '%' || sp.word4 || '%' OR 
                             LOWER(v.description) LIKE '%' || sp.word4 || '%') THEN 1 ELSE 0 END +
                    CASE WHEN sp.word5 IS NOT NULL AND 
                            (LOWER(v.title) LIKE '%' || sp.word5 || '%' OR 
                             LOWER(v.description) LIKE '%' || sp.word5 || '%') THEN 1 ELSE 0 END +
                    CASE WHEN sp.word6 IS NOT NULL AND 
                            (LOWER(v.title) LIKE '%' || sp.word6 || '%' OR 
                             LOWER(v.description) LIKE '%' || sp.word6 || '%') THEN 1 ELSE 0 END +
                    CASE WHEN sp.word7 IS NOT NULL AND 
                            (LOWER(v.title) LIKE '%' || sp.word7 || '%' OR 
                             LOWER(v.description) LIKE '%' || sp.word7 || '%') THEN 1 ELSE 0 END +
                    CASE WHEN sp.word8 IS NOT NULL AND 
                            (LOWER(v.title) LIKE '%' || sp.word8 || '%' OR 
                             LOWER(v.description) LIKE '%' || sp.word8 || '%') THEN 1 ELSE 0 END +
                    CASE WHEN sp.word9 IS NOT NULL AND 
                            (LOWER(v.title) LIKE '%' || sp.word9 || '%' OR 
                             LOWER(v.description) LIKE '%' || sp.word9 || '%') THEN 1 ELSE 0 END +
                    CASE WHEN sp.word10 IS NOT NULL AND 
                            (LOWER(v.title) LIKE '%' || sp.word10 || '%' OR 
                             LOWER(v.description) LIKE '%' || sp.word10 || '%') THEN 1 ELSE 0 END
                   ) as word_matches,
                   (CASE WHEN LOWER(v.title) LIKE '%' || sp.word1 || '%' THEN 2 
                         WHEN LOWER(v.description) LIKE '%' || sp.word1 || '%' THEN 1 
                         ELSE 0 END +
                    CASE WHEN sp.word2 IS NOT NULL AND LOWER(v.title) LIKE '%' || sp.word2 || '%' THEN 2 
                         WHEN sp.word2 IS NOT NULL AND LOWER(v.description) LIKE '%' || sp.word2 || '%' THEN 1 
                         ELSE 0 END +
                    CASE WHEN sp.word3 IS NOT NULL AND LOWER(v.title) LIKE '%' || sp.word3 || '%' THEN 2 
                         WHEN sp.word3 IS NOT NULL AND LOWER(v.description) LIKE '%' || sp.word3 || '%' THEN 1 
                         ELSE 0 END +
                    CASE WHEN sp.word4 IS NOT NULL AND LOWER(v.title) LIKE '%' || sp.word4 || '%' THEN 2 
                         WHEN sp.word4 IS NOT NULL AND LOWER(v.description) LIKE '%' || sp.word4 || '%' THEN 1 
                         ELSE 0 END +
                    CASE WHEN sp.word5 IS NOT NULL AND LOWER(v.title) LIKE '%' || sp.word5 || '%' THEN 2 
                         WHEN sp.word5 IS NOT NULL AND LOWER(v.description) LIKE '%' || sp.word5 || '%' THEN 1 
                         ELSE 0 END
                   ) as relevance_score
            FROM videos v, search_params sp
            WHERE sp.word1 IS NOT NULL AND 
                  (LOWER(v.title) LIKE '%' || sp.word1 || '%' OR 
                   LOWER(v.description) LIKE '%' || sp.word1 || '%' OR
                   (sp.word2 IS NOT NULL AND 
                    (LOWER(v.title) LIKE '%' || sp.word2 || '%' OR 
                     LOWER(v.description) LIKE '%' || sp.word2 || '%')) OR
                   (sp.word3 IS NOT NULL AND 
                    (LOWER(v.title) LIKE '%' || sp.word3 || '%' OR 
                     LOWER(v.description) LIKE '%' || sp.word3 || '%')) OR
                   (sp.word4 IS NOT NULL AND 
                    (LOWER(v.title) LIKE '%' || sp.word4 || '%' OR 
                     LOWER(v.description) LIKE '%' || sp.word4 || '%')) OR
                   (sp.word5 IS NOT NULL AND 
                    (LOWER(v.title) LIKE '%' || sp.word5 || '%' OR 
                     LOWER(v.description) LIKE '%' || sp.word5 || '%')))
        )
        SELECT * FROM scored_videos
        WHERE word_matches > 0
        ORDER BY relevance_score DESC, word_matches DESC, published_at DESC
        LIMIT ?
    """
    
    # Prepare parameters - pad with None for unused slots
    params = query_words + [None] * (10 - len(query_words))
    params.append(limit)
    
    cursor.execute(base_query, params)
    results = [dict(row) for row in cursor.fetchall()]
    
    # Filter by minimum match threshold
    min_matches = 1 if len(query_words) <= 2 else max(1, len(query_words) // 2)
    return [video for video in results if video.get('word_matches', 0) >= min_matches]

def search_videos_safe(conn: sqlite3.Connection, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Safe video search with SQL injection protection"""
    if not query or not query.strip():
        return []
    
    # First try exact phrase match
    exact_results = search_videos_exact_phrase(conn, query, limit)
    if exact_results:
        return exact_results
    
    # If no exact matches, try word-based search
    query_words = clean_query_words(query)
    if query_words:
        return search_videos_by_words(conn, query_words, limit)
    
    return []