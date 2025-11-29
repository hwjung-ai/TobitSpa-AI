import json
import logging
import os
from functools import lru_cache
from typing import List, Optional

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

# 우선 한 번 시도
_load_api_key_file()

DEFAULT_CONFIG_PATH = os.getenv("APP_CONFIG_PATH", os.path.join("config", "db_config.json"))


@lru_cache(maxsize=1)
def _load_settings():
    """설정 파일을 읽고, 없으면 기본값을 반환."""
    cfg = {
        "postgres": {
            "host": "115.21.12.151",
            "port": 5432,
            "dbname": "spadb",
            "user": "spa",
            "password": "spa1!",
        },
        "neo4j": {
            "uri": "bolt://115.21.12.151:7687",
            "user": "neo4j",
            "password": "wemb1!",
        },
        "embed_model": "text-embedding-3-small",
    }
    try:
        with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            file_cfg = json.load(f)
        # 얕은 병합
        cfg["postgres"].update(file_cfg.get("postgres", {}))
        cfg["neo4j"].update(file_cfg.get("neo4j", {}))
        if "embed_model" in file_cfg:
            cfg["embed_model"] = file_cfg["embed_model"]
    except Exception as e:
        logger.warning("설정 파일(%s) 로드 실패, 기본값 사용: %s", DEFAULT_CONFIG_PATH, e)
    # 환경변수로 최종 오버라이드
    pg_env = {
        "host": os.getenv("PG_HOST"),
        "port": os.getenv("PG_PORT"),
        "dbname": os.getenv("PG_DB"),
        "user": os.getenv("PG_USER"),
        "password": os.getenv("PG_PASSWORD"),
    }
    for k, v in pg_env.items():
        if v:
            cfg["postgres"][k] = int(v) if k == "port" else v
    neo_env = {
        "uri": os.getenv("NEO4J_URI"),
        "user": os.getenv("NEO4J_USER"),
        "password": os.getenv("NEO4J_PASSWORD"),
    }
    for k, v in neo_env.items():
        if v:
            cfg["neo4j"][k] = v
    embed_env = os.getenv("EMBED_MODEL")
    if embed_env:
        cfg["embed_model"] = embed_env
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
            neo_cfg["uri"],
            auth=(neo_cfg["user"], neo_cfg["password"]),
            connection_timeout=5,
        )
    return _neo4j_driver


def _compute_embedding(text: str) -> Optional[List[float]]:
    if not OpenAI:
        return None
    if not os.getenv("OPENAI_API_KEY"):
        _load_api_key_file()
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set. Embedding unavailable.")
        return None
    try:
        client = OpenAI()
        model_name = _load_settings().get("embed_model", "text-embedding-3-small")
        resp = client.embeddings.create(model=model_name, input=text)
        return resp.data[0].embedding
    except Exception as e:
        logger.warning("임베딩 생성 실패, 데모 fallback 사용: %s", e)
        return None


class ConfigDataSource:
    """구성정보 (Postgres) 조회. 실패 시 데모 반환."""

    def get_asset_config(self, asset_name: str):
        demo = {
            "a812dpt": {"name": "a812dpt", "ip": "10.1.2.3", "type": "server", "location": "IDC-1 Rack-12", "os": "Linux"},
            "db-master": {"name": "db-master", "ip": "10.2.0.10", "type": "db", "location": "IDC-1-Rack-05", "os": "Linux"},
        }
        try:
            with _pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT asset_name AS name, ip, type, location, os
                    FROM asset_configs
                    WHERE lower(asset_name) = lower(%s)
                    LIMIT 1
                    """,
                    (asset_name,),
                )
                row = cur.fetchone()
                if row:
                    return dict(row)
        except Exception as e:
            logger.warning("ConfigDataSource fallback 사용 (%s)", e)
        return demo.get(asset_name.lower())


class MetricDataSource:
    """메트릭(Timescale/Postgres) 조회. 실패 시 데모 반환."""

    def get_metric_timeseries(self, asset_name: str, metric: str, period: str = "1h"):
        try:
            with _pg_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ts, value
                    FROM metrics
                    WHERE asset_name = %s AND metric = %s AND ts >= now() - interval %s
                    ORDER BY ts
                    """,
                    (asset_name, metric, period),
                )
                rows = cur.fetchall()
                if rows:
                    times = [r[0].strftime("%H:%M") for r in rows]
                    values = [r[1] for r in rows]
                    return {"asset": asset_name, "metric": metric, "period": period, "times": times, "values": values}
        except Exception as e:
            logger.warning("MetricDataSource fallback 사용 (%s)", e)

        times = ["09:00", "10:00", "11:00", "12:00", "13:00"]
        values = [20, 35, 45, 30, 95]
        return {"asset": asset_name, "metric": metric, "period": period, "times": times, "values": values}


class GraphDataSource:
    """연결성(Neo4j) 조회. 실패 시 데모 반환."""

    def get_topology_for_asset(self, asset_name: str):
        try:
            driver = _get_neo4j_driver()
            with driver.session() as session:
                records = session.run(
                    """
                    MATCH p=(n {name:$asset})-[r*1..2]-(m)
                    RETURN nodes(p) AS ns, relationships(p) AS rs
                    LIMIT 5
                    """,
                    {"asset": asset_name},
                )
                nodes = {}
                edges = set()
                for rec in records:
                    for n in rec["ns"]:
                        name = n.get("name") or n.id
                        nodes[name] = {
                            "id": name,
                            "label": n.get("label", name),
                            "icon": "f233",
                            "color": "#3498db",
                        }
                    for rel in rec["rs"]:
                        edges.add((rel.start_node.get("name", rel.start_node.id), rel.end_node.get("name", rel.end_node.id)))
                if nodes:
                    return {"nodes": list(nodes.values()), "edges": list(edges)}
        except Exception as e:
            logger.warning("GraphDataSource fallback 사용 (%s)", e)

        nodes = [
            {"id": "FW-01", "label": "Firewall", "icon": "f132", "color": "#e74c3c"},
            {"id": "SW-Core-01", "label": "Switch A", "icon": "f233", "color": "#3498db"},
            {"id": "SW-Core-02", "label": "Switch B", "icon": "f233", "color": "#3498db"},
            {"id": "WEB-01", "label": "Web-01", "icon": "f108", "color": "#2ecc71"},
            {"id": "WAS-01", "label": "WAS-01", "icon": "f013", "color": "#9b59b6"},
            {"id": "DB-Master", "label": "DB Master", "icon": "f1c0", "color": "#e67e22"},
        ]
        edges = [
            ("FW-01", "SW-Core-01"),
            ("SW-Core-01", "SW-Core-02"),
            ("SW-Core-01", "WEB-01"),
            ("SW-Core-02", "WAS-01"),
            ("WAS-01", "DB-Master"),
        ]
        return {"nodes": nodes, "edges": edges}


class ManualVectorSource:
    """매뉴얼(pgvector) 검색. 실패 시 데모 반환."""

    def search_manuals(self, question: str, top_k: int = 3):
        embedding = _compute_embedding(question)
        if embedding:
            try:
                with _pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT d.id AS document_id,
                               d.title,
                               d.converted_pdf,
                               dc.page_num,
                               dc.content,
                               dc.source_path,
                               1 - (dc.embedding <=> %s::vector) AS score
                        FROM doc_chunks dc
                        JOIN documents d ON d.id = dc.document_id
                        ORDER BY dc.embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (embedding, embedding, top_k),
                    )
                    rows = cur.fetchall()
                    results = []
                    for r in rows:
                        results.append(
                            {
                                "title": r.get("title", "문서"),
                                "snippet": (r.get("content") or "")[:200],
                                "link": (r.get("converted_pdf") or r.get("source_path") or ""),
                                "page": r.get("page_num"),
                                "score": r.get("score"),
                            }
                        )
                    logger.info("ManualVectorSource hit %d rows for query '%s'", len(results), question[:80])
                    if results:
                        return results
            except Exception as e:
                logger.warning("ManualVectorSource fallback 사용 (%s)", e)
        else:
            logger.error("ManualVectorSource embedding unavailable for query '%s'", question[:80])

        return [
            {
                "title": "가이드: 서버 CPU 장애 대응",
                "snippet": "CPU 사용률이 90% 이상 지속되면 스레드 덤프를 채취하고...",
                "link": "/docs/manuals/cpu_trouble_guide.pdf#page=3&highlight=cpu",
            },
            {
                "title": "매뉴얼: WAS 성능 튜닝",
                "snippet": "WAS-01 인스턴스의 스레드 풀 사이즈를 늘리고...",
                "link": "/docs/manuals/was_tuning.pdf#page=5&highlight=latency",
            },
        ]
