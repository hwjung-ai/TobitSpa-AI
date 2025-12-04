import logging
from typing import List, Optional, Dict, Any

from psycopg2.extras import RealDictCursor

from db.connections import get_pg_conn
from db.embedding import compute_embedding

logger = logging.getLogger(__name__)


def perform_rag_search(query: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """
    쿼리 임베딩 → pgvector Top-K 검색 → 스니펫/링크 반환
    LLM 본문 생성은 생략하고 검색 결과를 요약한 문자열만 반환
    """
    embedding = compute_embedding(query)
    if not embedding:
        return {"answer": "임베딩을 생성할 수 없습니다. OPENAI_API_KEY를 설정하세요.", "sources": []}

    try:
        with get_pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
                SELECT d.title,
                       d.converted_pdf,
                       dc.page_num,
                       dc.source_path,
                       dc.content,
                       1 - (dc.embedding <=> %s::vector) AS score
                FROM doc_chunks dc
                JOIN documents d ON d.id = dc.document_id
            """
            params = [embedding]
            if tenant_id:
                sql += " WHERE (dc.tenant_id = %s AND d.tenant_id = %s)"
                params.extend([tenant_id, tenant_id])
            sql += " ORDER BY dc.embedding <=> %s::vector LIMIT 5"
            params.append(embedding)
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
    except Exception as e:
        return {"answer": f"검색 중 오류: {e}", "sources": []}

    sources: List[Dict[str, Any]] = []
    snippets: List[str] = []
    for r in rows:
        src = {
            "title": r.get("title"),
            "link": (r.get("converted_pdf") or r.get("source_path") or ""),
            "page": r.get("page_num"),
            "score": float(r.get("score", 0)),
            "snippet": (r.get("content") or "")[:300],
        }
        sources.append(src)
        snippets.append(f"- {src['title']} (score={src['score']:.3f})")

    answer_text = "검색 결과 상위 문서:\n" + "\n".join(snippets) if snippets else "검색 결과가 없습니다."
    return {"answer": answer_text, "sources": sources}
