import json
import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

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

load_settings = _load_settings # Public alias
