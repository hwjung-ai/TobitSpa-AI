import json
import logging
import os
from functools import lru_cache
from typing import List, Optional, Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor
from neo4j import GraphDatabase

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

# OpenAI 키 로더 (.openai_key 파일 지원)
_api_key_loaded = False


def _load_api_key_file():
    """현재 작업 디렉터리에 있는 .openai_key 파일을 읽어 환경변수에 설정."""
    global _api_key_loaded
    if _api_key_loaded:
        return
    key_path = os.path.join(os.getcwd(), ".openai_key")
    if os.path.exists(key_path):
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                key = f.read().strip()
            if key and key.lower().startswith(("sk-", "sess-")):
                os.environ["OPENAI_API_KEY"] = key
                _api_key_loaded = True
                logger.info("OPENAI_API_KEY loaded from .openai_key")
        except Exception as e:
            logger.warning(".openai_key 로드 실패: %s", e)

_load_api_key_file()

DEFAULT_CONFIG_PATH = os.getenv("APP_CONFIG_PATH", os.path.join("config", "db_config.json"))


@lru_cache(maxsize=1)
def _load_settings():
    """설정 파일을 읽고, 없으면 기본값을 반환."""
    cfg = {
        "postgres": {
            "host": "localhost", "port": 5432, "dbname": "spadb", "user": "spa", "password": "password"
        },
        "neo4j": {
            "uri": "bolt://localhost:7687", "user": "neo4j", "password": "password"
        },
        "embed_model": "text-embedding-3-small",
    }
    try:
        with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            file_cfg = json.load(f)
        cfg["postgres"].update(file_cfg.get("postgres", {}))
        cfg["neo4j"].update(file_cfg.get("neo4j", {}))
        if "embed_model" in file_cfg:
            cfg["embed_model"] = file_cfg["embed_model"]
    except Exception as e:
        logger.warning("설정 파일(%s) 로드 실패, 기본값 사용: %s", DEFAULT_CONFIG_PATH, e)
    
    # 환경변수로 최종 오버라이드
    # ... (기존 환경변수 로직 유지) ...
    return cfg


def _pg_conn():
    cfg = _load_settings()["postgres"]
    return psycopg2.connect(**cfg, connect_timeout=5)


_neo4j_driver = None


def _get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        neo_cfg = _load_settings()["neo4j"]
        _neo4j_driver = GraphDatabase.driver(
            neo_cfg["uri"], auth=(neo_cfg["user"], neo_cfg["password"]), connection_timeout=5
        )
    return _neo4j_driver


def _compute_embedding(text: str) -> Optional[List[float]]:
    """OpenAI 임베딩을 생성하고, 실패 시 None 반환."""
    _load_api_key_file()
    if not OpenAI or not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY가 설정되지 않아 임베딩을 건너뜁니다.")
        return None
    try:
        client = OpenAI()
        model = _load_settings().get("embed_model", "text-embedding-3-small")
        resp = client.embeddings.create(model=model, input=text)
        return resp.data[0].embedding
    except Exception as e:
        logger.error("임베딩 생성 실패: %s", e)
        return None


class AssetDataSource:
    """자산 구성정보 (Postgres 'assets' table) 조회. 실패 시 데모 반환."""

    def get_asset_by_name(self, asset_name: str) -> Optional[Dict[str, Any]]:
        """특정 이름의 자산 정보를 조회합니다."""
        demo = {
            "a812dpt": {"id": 1, "asset_type": "IT_DEVICE", "name": "a812dpt", "attributes": {"ip": "10.1.2.3", "os": "Linux", "ram": "16GB"}},
            "db-master": {"id": 2, "asset_type": "IT_DEVICE", "name": "db-master", "attributes": {"ip": "10.2.0.10", "os": "Linux", "ram": "64GB"}},
        }
        try:
            with _pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, asset_type, name, attributes FROM assets WHERE lower(name) = lower(%s) LIMIT 1",
                    (asset_name,),
                )
                row = cur.fetchone()
                if row:
                    return dict(row)
        except Exception as e:
            logger.warning("get_asset_by_name fallback 사용 (%s)", e)
        return demo.get(asset_name.lower())

    def find_assets_by_attributes(self, attrs: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        """JSONB 속성을 기준으로 자산을 검색합니다."""
        if not attrs:
            return []
        
        demo_assets = [
            {"id": 1, "asset_type": "IT_DEVICE", "name": "a812dpt", "attributes": {"ip": "10.1.2.3", "os": "Linux", "ram": "16GB"}},
            {"id": 2, "asset_type": "IT_DEVICE", "name": "db-master", "attributes": {"ip": "10.2.0.10", "os": "Linux", "ram": "64GB"}},
            {"id": 3, "asset_type": "IT_DEVICE", "name": "web-01", "attributes": {"ip": "192.168.1.100", "os": "Ubuntu 22.04", "ram": "32GB"}},
        ]

        try:
            with _pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                # JSONB containment operator @> 를 사용하여 쿼리
                cur.execute(
                    "SELECT id, asset_type, name, attributes FROM assets WHERE attributes @> %s::jsonb LIMIT %s",
                    (json.dumps(attrs), limit),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("find_assets_by_attributes fallback 사용 (%s)", e)
            
            # Fallback 로직: 데모 데이터에서 필터링
            results = []
            for asset in demo_assets:
                match = True
                for key, value in attrs.items():
                    if asset.get("attributes", {}).get(key) != value:
                        match = False
                        break
                if match:
                    results.append(asset)
            return results[:limit]

    def get_asset_id_by_name(self, asset_name: str) -> Optional[int]:
        asset = self.get_asset_by_name(asset_name)
        return asset.get("id") if asset else None

# AssetDataSource 인스턴스 공유
asset_ds = AssetDataSource()

class MetricDataSource:
    """메트릭(Timescale/Postgres) 조회. 실패 시 데모 반환."""

    def get_metric_timeseries(self, asset_name: str, metric: str, period: str = "1h"):
        asset_id = asset_ds.get_asset_id_by_name(asset_name)
        if not asset_id:
            logger.warning("'%s' 자산 ID를 찾을 수 없어 MetricDataSource fallback 사용", asset_name)
        else:
            try:
                with _pg_conn() as conn, conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT ts, value
                        FROM metrics
                        WHERE asset_id = %s AND metric = %s AND ts >= now() - interval %s
                        ORDER BY ts
                        """,
                        (asset_id, metric, period),
                    )
                    rows = cur.fetchall()
                    if rows:
                        times = [r[0].strftime("%H:%M") for r in rows]
                        values = [r[1] for r in rows]
                        return {"asset": asset_name, "metric": metric, "period": period, "times": times, "values": values}
            except Exception as e:
                logger.warning("MetricDataSource fallback 사용 (%s)", e)

        # Fallback 로직: 동적 파라미터를 사용하여 데모 데이터 생성
        import random
        from datetime import datetime, timedelta

        try:
            # '1h', '3 days' 같은 문자열에서 숫자와 단위를 분리
            num, unit = period.split()
            num = int(num)
            if 'hour' in unit:
                delta = timedelta(hours=num)
            elif 'day' in unit:
                delta = timedelta(days=num)
            elif 'minute' in unit:
                delta = timedelta(minutes=num)
            else:
                delta = timedelta(hours=1)
        except Exception:
            delta = timedelta(hours=1)

        now = datetime.now()
        times = [(now - delta + timedelta(minutes=i*10)).strftime("%H:%M") for i in range(6)]
        values = [random.randint(20, 100) for _ in range(6)]
        
        logger.info(f"Fallback metric data generated for {asset_name}, {metric}, {period}")
        return {"asset": asset_name, "metric": metric, "period": period, "times": times, "values": values}

class WorkHistoryDataSource:
    """작업 이력(Postgres 'work_history' table) 조회. 실패 시 데모 반환."""

    def get_history_by_asset_name(self, asset_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        asset_id = asset_ds.get_asset_id_by_name(asset_name)
        if not asset_id:
            logger.warning("'%s' 자산 ID를 찾을 수 없어 WorkHistoryDataSource fallback 사용", asset_name)
        else:
            try:
                with _pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT work_date, worker_name, work_type, description
                        FROM work_history
                        WHERE asset_id = %s
                        ORDER BY work_date DESC
                        LIMIT %s
                        """,
                        (asset_id, limit),
                    )
                    rows = cur.fetchall()
                    if rows:
                        return [dict(row) for row in rows]
            except Exception as e:
                logger.warning("WorkHistoryDataSource fallback 사용 (%s)", e)

        return [
            {"work_date": "2024-05-20 10:00:00", "worker_name": "Admin", "work_type": "maintenance", "description": "정기 보안 패치 적용"},
            {"work_date": "2024-05-18 15:30:00", "worker_name": "Dev", "work_type": "update", "description": "애플리케이션 v1.2 배포"},
        ]

class ChatHistoryDataSource:
    """대화 이력(Postgres 'chat_history' table) 저장 및 조회."""

    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        try:
            with _pg_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_history (session_id, role, content, metadata)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (session_id, role, content, json.dumps(metadata) if metadata else None),
                )
                conn.commit()
        except Exception as e:
            logger.error("대화 저장 실패: %s", e)

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            with _pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
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
            with _pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
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


class GraphDataSource:
    """그래프 기반 연결성(Neo4j) 조회. 실패 시 데모 반환."""

    def _graph_to_dict(self, records):
        nodes = []
        edges = []
        node_ids = set()

        for record in records:
            for node in record.get('nodes', []):
                node_id = node.element_id
                if node_id not in node_ids:
                    node_ids.add(node_id)
                    nodes.append({
                        "id": node.get('name'),
                        "label": node.get('name'),
                        "group": list(node.labels)[0],
                        "icon": node.get('icon', 'f1c0'), # fa-database
                        "color": node.get('color', '#6ca6fd')
                    })
            for rel in record.get('relationships', []):
                start_node_name = rel.start_node.get('name')
                end_node_name = rel.end_node.get('name')
                edges.append((start_node_name, end_node_name))
        
        return {"nodes": nodes, "edges": edges}

    def get_topology_for_asset(self, asset_name: str) -> Optional[Dict[str, Any]]:
        """특정 자산과 직접 연결된 이웃 노드들의 토폴로지 조회."""
        query = """
        MATCH (a:Asset {name: $asset_name})
        OPTIONAL MATCH (a)-[r]-(neighbor)
        RETURN nodes(collect(a) + collect(neighbor)) as nodes, relationships(collect(r)) as relationships
        """
        try:
            driver = _get_neo4j_driver()
            with driver.session() as session:
                result = session.run(query, asset_name=asset_name)
                records = list(result)
                if records:
                    return self._graph_to_dict(records)
        except Exception as e:
            logger.warning("get_topology_for_asset fallback 사용 (%s)", e)
        
        # Fallback 데모 데이터
        return {
            "nodes": [
                {"id": "a812dpt", "label": "a812dpt", "icon": "f233", "color": "#f0ad4e"},
                {"id": "sw-core-01", "label": "sw-core-01", "icon": "f6ff", "color": "#5bc0de"},
                {"id": "nas-01", "label": "nas-01", "icon": "f0a0", "color": "#6ca6fd"}
            ],
            "edges": [("a812dpt", "sw-core-01"), ("a812dpt", "nas-01")]
        }

    def find_path_between_assets(self, start_asset: str, end_asset: str) -> Optional[Dict[str, Any]]:
        """두 자산 간의 최단 경로를 찾습니다."""
        query = """
        MATCH (start:Asset {name: $start_asset}), (end:Asset {name: $end_asset})
        MATCH p = allShortestPaths((start)-[*..5]-(end))
        RETURN nodes(p) as nodes, relationships(p) as relationships
        """
        try:
            driver = _get_neo4j_driver()
            with driver.session() as session:
                result = session.run(query, start_asset=start_asset, end_asset=end_asset)
                records = list(result) # A single path becomes a single record
                if records:
                    return self._graph_to_dict(records)
        except Exception as e:
            logger.warning("find_path_between_assets fallback 사용 (%s)", e)

        # Fallback 데모 데이터
        if "a812dpt" in [start_asset, end_asset] and "db-master" in [start_asset, end_asset]:
             return {
                "nodes": [
                    {"id": "a812dpt", "label": "a812dpt", "icon": "f233", "color": "#f0ad4e"},
                    {"id": "sw-core-01", "label": "sw-core-01", "icon": "f6ff", "color": "#5bc0de"},
                    {"id": "db-master", "label": "db-master", "icon": "f1c0", "color": "#5cb85c"}
                ],
                "edges": [("a812dpt", "sw-core-01"), ("sw-core-01", "db-master")]
            }
        return None


class ManualVectorSource:
    """매뉴얼/문서 pgvector 검색."""

    def search_manuals(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        emb = _compute_embedding(query)
        if not emb:
            return []
        try:
            with _pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT d.title,
                           d.converted_pdf,
                           dc.page_num,
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
