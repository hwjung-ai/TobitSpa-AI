import logging
import os
from typing import List, Optional

from config.settings import load_settings

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

logger = logging.getLogger(__name__)

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


def _compute_embedding(text: str) -> Optional[List[float]]:
    """OpenAI 임베딩을 생성하고, 실패 시 None 반환."""
    _load_api_key_file()
    if not OpenAI or not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY가 설정되지 않아 임베딩을 건너뜁니다.")
        return None
    try:
        client = OpenAI()
        model = load_settings().get("embed_model", "text-embedding-3-small")
        resp = client.embeddings.create(model=model, input=text)
        return resp.data[0].embedding
    except Exception as e:
        logger.error("임베딩 생성 실패: %s", e)
        return None

compute_embedding = _compute_embedding # Public alias
