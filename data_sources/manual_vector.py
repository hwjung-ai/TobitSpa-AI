import logging
from typing import List, Optional, Dict, Any

try:
    from psycopg2.extras import RealDictCursor
except Exception:
    RealDictCursor = None  # Allow import without psycopg2 installed during tests

from db.connections import get_pg_conn
from db.embedding import compute_embedding

logger = logging.getLogger(__name__)

class ManualVectorSource:
    """매뉴얼/문서 pgvector 검색."""

    def search_manuals(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        emb = compute_embedding(query)
        if not emb:
            return []
        try:
            with get_pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT d.title,
                           d.converted_pdf,
                           dc.page_num,
                           dc.source_path,
                           dc.content,
                           1 - (dc.embedding <=> %s::vector) AS score
                FROM doc_chunks dc
                JOIN documents d ON d.id = dc.document_id
                ORDER BY dc.embedding <=> %s::vector
                LIMIT %s
                """,
                    (emb, emb, top_k),
                )
                rows = cur.fetchall()
        except Exception as e:
            logger.warning("ManualVectorSource search 실패, 빈 결과 반환: %s", e)
            return []

        results = []
        for r in rows:
            results.append({
                "title": r.get("title"),
                "link": r.get("converted_pdf") or r.get("source_path") or "",
                "page": r.get("page_num"),
                "snippet": (r.get("content") or "")[:400],
                "score": float(r.get("score", 0)),
            })
        return results
