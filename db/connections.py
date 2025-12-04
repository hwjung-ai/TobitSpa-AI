try:
    import psycopg2
except Exception:
    psycopg2 = None  # Allow import without psycopg2 installed (tests can use fallbacks)

from neo4j import GraphDatabase

from config.settings import load_settings

def _pg_conn():
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed; database operations are unavailable in this environment.")
    cfg = load_settings()["postgres"]
    return psycopg2.connect(**cfg, connect_timeout=5)

get_pg_conn = _pg_conn # Public alias

_neo4j_driver = None

def _get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        neo_cfg = load_settings()["neo4j"]
        _neo4j_driver = GraphDatabase.driver(
            neo_cfg["uri"], auth=(neo_cfg["user"], neo_cfg["password"]), connection_timeout=5
        )
    return _neo4j_driver

get_neo4j_driver = _get_neo4j_driver # Public alias
