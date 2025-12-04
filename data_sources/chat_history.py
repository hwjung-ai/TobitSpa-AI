import logging
import math
import json
from typing import List, Optional, Dict, Any

try:
    from psycopg2.extras import RealDictCursor
except Exception:
    RealDictCursor = None  # Allow import without psycopg2 installed during tests

from db.connections import get_pg_conn

logger = logging.getLogger(__name__)

class ChatHistoryDataSource:
    """대화 이력(Postgres 'chat_history' table) 저장 및 조회."""

    def _sanitize_json_data(self, obj):
        """Postgres JSON이 거부하는 NaN/Inf 등을 None으로 치환."""
        if isinstance(obj, dict):
            return {k: self._sanitize_json_data(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize_json_data(v) for v in obj]
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj

    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        clean_meta = self._sanitize_json_data(metadata) if metadata else None
        try:
            with get_pg_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_history (session_id, role, content, metadata)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (session_id, role, content, json.dumps(clean_meta) if clean_meta else None),
                )
                conn.commit()
        except Exception as e:
            logger.error("대화 저장 실패: %s", e)

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            with get_pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT role, content, metadata, "timestamp"
                    FROM chat_history
                    WHERE session_id = %s
                    ORDER BY "timestamp" DESC
                    LIMIT %s
                    """,
                    (session_id, limit),
                )
                rows = cur.fetchall()
                # 시간 역순으로 가져왔으므로 다시 정순으로 변경
                return sorted([dict(row) for row in rows], key=lambda x: x['timestamp'])
        except Exception as e:
            logger.error("대화 이력 조회 실패: %s", e)
            return []

    def search_history(self, session_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Searches chat history for a given query."""
        try:
            with get_pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Use ILIKE for case-insensitive search and % for wildcard matching
                search_term = f"%{query}%"
                cur.execute(
                    """
                    SELECT role, content, "timestamp"
                    FROM chat_history
                    WHERE session_id = %s AND content ILIKE %s
                    ORDER BY "timestamp" DESC
                    LIMIT %s
                    """,
                    (session_id, search_term, limit),
                )
                rows = cur.fetchall()
                logger.info("Chat history search for '%s' found %d results.", query, len(rows))
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error("대화 이력 검색 실패: %s", e)
            return []

    def get_all_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Gets a summary of all recent chat sessions."""
        try:
            with get_pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    WITH ranked_messages AS (
                        SELECT
                            session_id,
                            content,
                            "timestamp",
                            ROW_NUMBER() OVER(PARTITION BY session_id ORDER BY "timestamp") as rn
                        FROM chat_history
                        WHERE role = 'user'
                    )
                    SELECT
                        session_id,
                        content AS first_message
                    FROM ranked_messages
                    WHERE rn = 1
                    ORDER BY "timestamp" DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error("모든 세션 요약 조회 실패: %s", e)
            return []

    def delete_session(self, session_id: str) -> int:
        """Deletes all messages for a session and returns the number of rows deleted."""
        try:
            with get_pg_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM chat_history WHERE session_id = %s",
                    (session_id,),
                )
                deleted = cur.rowcount or 0
                conn.commit()
                return deleted
        except Exception as e:
            logger.error("세션 삭제 실패: %s", e)
            return 0
