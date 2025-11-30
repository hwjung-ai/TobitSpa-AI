"""
LlamaIndex Router / QueryEngine scaffolding that routes user queries across
- Manuals (pgvector-backed)
- Config (assets table)
- Work history (work_history table)
- Graph topology/path (Neo4j/GraphDataSource)

Note: This is a light-weight wrapper; heavy failures are caught and routed to
the existing ManualVectorSource fallback.
"""
import logging
from typing import List, Dict, Any

from llama_index.core import Document, get_response_synthesizer
from llama_index.core.query_engine.router_query_engine import RouterQueryEngine
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.response.schema import Response

from data_sources import AssetDataSource, WorkHistoryDataSource, GraphDataSource, ManualVectorSource
from llama_index_integration import LlamaIndexManualRetriever

logger = logging.getLogger(__name__)


class _SimpleEngine:
    """Minimal engine that returns a LlamaIndex Response from a callable."""

    def __init__(self, fn):
        self._fn = fn

    def query(self, q: str) -> Response:
        txt, meta = self._fn(q)
        return Response(response=txt, source_nodes=[], extra_info=meta)


class _GraphEngine:
    """Wrap GraphDataSource for Router."""

    def __init__(self, graph_ds: GraphDataSource):
        self.graph_ds = graph_ds

    def query(self, q: str) -> Response:
        # naive: if "경로" in q -> path; else neighbors on token
        tokens = q.replace(",", " ").split()
        if "경로" in q or "path" in q:
            start = tokens[0] if tokens else "a812dpt"
            end = tokens[-1] if len(tokens) > 1 else "db-master"
            graph = self.graph_ds.find_path_between_assets(start, end) or {}
            txt = f"Path {start} -> {end}: {graph}" if graph else "경로를 찾지 못했습니다."
        else:
            asset = tokens[0] if tokens else "a812dpt"
            topo = self.graph_ds.get_topology_for_asset(asset) or {}
            txt = f"{asset} 인접 토폴로지: {topo}" if topo else "토폴로지를 찾지 못했습니다."
        return Response(response=txt, source_nodes=[], extra_info={"graph": True})


class MultiSourceRouter:
    """RouterQueryEngine wrapper across manuals/config/work history/graph."""

    def __init__(self):
        self.asset_ds = AssetDataSource()
        self.work_ds = WorkHistoryDataSource()
        self.manual_retriever = LlamaIndexManualRetriever()
        self.manual_ds_fallback = ManualVectorSource()
        self.graph_ds = GraphDataSource()

    def _manual_tool(self) -> QueryEngineTool:
        try:
            index = self.manual_retriever.build_index()
            engine = index.as_query_engine(similarity_top_k=3, response_synthesizer=get_response_synthesizer())
            return QueryEngineTool(
                query_engine=engine,
                metadata=ToolMetadata(
                    name="manuals",
                    description="매뉴얼/문서 벡터 검색 (pgvector 기반)"
                ),
            )
        except Exception as e:
            logger.warning("Manual tool fallback: %s", e)

            class _FallbackEngine:
                def query(_, q: str) -> Response:
                    hits = self.manual_ds_fallback.search_manuals(q, top_k=3)
                    txt = "\n".join([f"- {h['title']} (score={h['score']:.3f})" for h in hits]) or "검색 결과 없음"
                    return Response(response=txt, source_nodes=[])

            return QueryEngineTool(
                query_engine=_FallbackEngine(),
                metadata=ToolMetadata(name="manuals_fallback", description="수동 매뉴얼 검색")
            )

    def _config_tool(self) -> QueryEngineTool:
        def _run(q: str):
            asset = None
            for t in q.replace(",", " ").split():
                if "." in t or "-" in t:
                    asset = t
                    break
            info = self.asset_ds.get_asset_by_name(asset) if asset else None
            txt = f"구성 정보: {info}" if info else "구성 정보를 찾지 못했습니다."
            return txt, {"asset": asset}

        return QueryEngineTool(
            query_engine=_SimpleEngine(_run),
            metadata=ToolMetadata(name="config", description="자산 구성정보 검색 (Postgres assets)")
        )

    def _work_tool(self) -> QueryEngineTool:
        def _run(q: str):
            asset = None
            for t in q.replace(",", " ").split():
                if "." in t or "-" in t:
                    asset = t
                    break
            asset = asset or "a812dpt"
            hist = self.work_ds.get_history_by_asset_name(asset)
            txt = "\n".join([f"- {h.get('work_date')}: {h.get('description')}" for h in hist]) or "작업 이력 없음"
            return txt, {"asset": asset}

        return QueryEngineTool(
            query_engine=_SimpleEngine(_run),
            metadata=ToolMetadata(name="work_history", description="작업/유지보수 이력 조회")
        )

    def _graph_tool(self) -> QueryEngineTool:
        return QueryEngineTool(
            query_engine=_GraphEngine(self.graph_ds),
            metadata=ToolMetadata(name="graph", description="Neo4j 연결성/경로 조회")
        )

    def query(self, user_query: str) -> Dict[str, Any]:
        tools = [
            self._manual_tool(),
            self._config_tool(),
            self._work_tool(),
            self._graph_tool(),
        ]
        try:
            router = RouterQueryEngine.from_defaults(tools)
            resp = router.query(user_query)
            text = resp.response if hasattr(resp, "response") else str(resp)
            sources = []
            for sn in getattr(resp, "source_nodes", []) or []:
                md = sn.metadata or {}
                sources.append({
                    "title": md.get("title") or md.get("document_id") or "source",
                    "snippet": (sn.get_content() or "")[:400],
                    "link": md.get("converted_pdf") or md.get("source_path") or "",
                    "page": md.get("page_num"),
                    "score": float(getattr(sn, "score", 0) or 0),
                })
            sources = self._boost_sources(user_query, sources)
            return {"text": text, "sources": sources}
        except Exception as e:
            logger.warning("RouterQueryEngine failed, fallback summary: %s", e)
            # minimal fallback: manual + config
            manual_hits = self.manual_ds_fallback.search_manuals(user_query, top_k=3)
            cfg = None
            for t in user_query.replace(",", " ").split():
                if "." in t or "-" in t:
                    cfg = self.asset_ds.get_asset_by_name(t)
                    break
            parts = []
            if manual_hits:
                parts.append("매뉴얼:\n" + "\n".join([f"- {h['title']} (score={h['score']:.3f})" for h in manual_hits]))
            if cfg:
                parts.append(f"구성: {cfg}")
            manual_hits = self._boost_sources(user_query, manual_hits)
            return {"text": "\n\n".join(parts) or "관련 데이터를 찾지 못했습니다.", "sources": manual_hits}

    def _boost_sources(self, query: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Light rerank: boost when title/snippet contains query tokens."""
        tokens = [t.lower() for t in query.split() if len(t) > 1]
        for s in sources:
            score = s.get("score", 0.0) or 0.0
            title = (s.get("title") or "").lower()
            snippet = (s.get("snippet") or "").lower()
            boost = 0.0
            for tok in tokens:
                if tok in title:
                    boost += 0.05
                if tok in snippet:
                    boost += 0.02
            s["score"] = score + boost
        return sorted(sources, key=lambda x: x.get("score", 0), reverse=True)
