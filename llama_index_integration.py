import logging
from typing import List, Dict, Any, Optional

from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.psycopg import PGVectorStore

from data_sources import _load_settings, _compute_embedding

logger = logging.getLogger(__name__)

class LlamaIndexManualRetriever:
    """Wraps doc_chunks (pgvector) with LlamaIndex for semantic search."""

    def __init__(self):
        cfg = _load_settings()
        pg_cfg = cfg["postgres"]
        self.pgvector = PGVectorStore.from_params(
            database=pg_cfg["dbname"],
            host=pg_cfg["host"],
            port=pg_cfg["port"],
            user=pg_cfg["user"],
            password=pg_cfg["password"],
            table_name="doc_chunks",
            vector_column="embedding",
            text_column="content",
            id_column="id",
            embed_dim=None,  # infer from table
        )
        Settings.embed_model = OpenAIEmbedding(model=cfg.get("embed_model", "text-embedding-3-small"))

    def build_index(self):
        storage_context = StorageContext.from_defaults(vector_store=self.pgvector)
        return VectorStoreIndex.from_vector_store(self.pgvector, storage_context=storage_context)

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        try:
            index = self.build_index()
            retriever = index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
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
        from data_sources import ManualVectorSource
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
