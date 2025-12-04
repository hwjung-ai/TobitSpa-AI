import logging
from typing import List, Dict, Any, Optional

from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

from config.settings import load_settings
from db.embedding import compute_embedding

logger = logging.getLogger(__name__)

class LlamaIndexManualRetriever:
    """Wraps doc_chunks (pgvector) with LlamaIndex for semantic search."""

    def __init__(self):
        cfg = load_settings()
        pg_cfg = cfg["postgres"]
        try:
            # 일부 버전은 컬럼명을 받지 않고 기본 스키마(embedding, id, content)를 가정한다.
            self.pgvector = PGVectorStore.from_params(
                database=pg_cfg["dbname"],
                host=pg_cfg["host"],
                port=pg_cfg["port"],
                user=pg_cfg["user"],
                password=pg_cfg["password"],
                table_name="doc_chunks",
            )
        except Exception as e:
            logger.warning("PGVectorStore 초기화 실패, fallback 사용: %s", e)
            self.pgvector = None
        Settings.embed_model = OpenAIEmbedding(model=cfg.get("embed_model", "text-embedding-3-small"))

    def build_index(self):
        if not self.pgvector:
            raise RuntimeError("PGVectorStore가 초기화되지 않았습니다.")
        storage_context = StorageContext.from_defaults(vector_store=self.pgvector)
        return VectorStoreIndex.from_vector_store(self.pgvector, storage_context=storage_context)

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        try:
            index = self.build_index()
            retriever = index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
            if not nodes:
                raise ValueError("빈 검색 결과")
        except Exception as e:
            logger.warning("LlamaIndex search failed, falling back to manual embedding: %s", e)
            return self._fallback_search(query, top_k)

        results = []
        for n in nodes:
            meta = n.metadata or {}
            results.append({
                "title": meta.get("title") or meta.get("document_id") or "문서",
                "link": meta.get("converted_pdf") or meta.get("source_path") or "",
                "page": meta.get("page_num"),
                "snippet": (n.get_content() or "")[:400],
                "score": float(n.score or 0),
            })
        return self._boost_and_sort(query, results, top_k)

    def _fallback_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Fallback to manual embedding + SQL if LlamaIndex fails."""
        from data_sources.manual_vector import ManualVectorSource
        hits = ManualVectorSource().search_manuals(query, top_k=top_k)
        return self._boost_and_sort(query, hits, top_k)

    def _boost_and_sort(self, query: str, items: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """Apply simple metadata/token boost to favor title/snippet matches."""
        tokens = [t.lower() for t in query.split() if len(t) > 1]
        for it in items:
            score = it.get("score", 0.0) or 0.0
            title = (it.get("title") or "").lower()
            snippet = (it.get("snippet") or "").lower()
            boost = 0.0
            for tok in tokens:
                if tok in title:
                    boost += 0.05
                if tok in snippet:
                    boost += 0.02
            it["score"] = score + boost
        return sorted(items, key=lambda x: x.get("score", 0), reverse=True)[:top_k]
