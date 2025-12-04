import os
import logging

logger = logging.getLogger(__name__)

# Check if OpenAI API key is set (assumes it's loaded by db.embedding or environment)
USE_OPENAI = os.getenv("OPENAI_API_KEY") is not None


def _ensure_openai_key():
    """Ensure OPENAI_API_KEY is available; try reading from .openai_key in CWD if missing."""
    if os.getenv("OPENAI_API_KEY"):
        return True
    try:
        key_path = os.path.join(os.getcwd(), ".openai_key")
        if os.path.exists(key_path):
            with open(key_path, "r", encoding="utf-8") as f:
                key = f.read().strip()
            if key:
                os.environ["OPENAI_API_KEY"] = key
                logger.info("OPENAI_API_KEY loaded from .openai_key (llm.utils)")
                return True
    except Exception as e:
        logger.warning("Could not load .openai_key: %s", e)
    return False


def get_llm_and_trimmer():
    """Lazily import langchain modules to avoid heavy deps during import time.

    Returns:
        tuple: (llm, trimmer, error_reason)
    """
    llm = None
    trimmer = None
    error_reason = None

    # Load API key dynamically (supports .openai_key) to avoid stale USE_OPENAI
    if not _ensure_openai_key():
        error_reason = "OPENAI_API_KEY 미설정 또는 .openai_key 비어있음"
        return llm, trimmer, error_reason

    try:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(temperature=0, model=os.getenv("CHAT_MODEL", "gpt-4o-mini"))
        trimmer = None
        # Update exported flag for downstream checks
        global USE_OPENAI
        USE_OPENAI = True
    except Exception as e:
        error_reason = f"LLM 초기화 실패: {e}"
        logger.warning("Failed to initialize LLM/trimmer: %s", e)
        llm = None
        trimmer = None
    return llm, trimmer, error_reason


def log_openai_key_status():
    """Log whether OPENAI_API_KEY is available (attempts .openai_key load)."""
    if _ensure_openai_key():
        logger.info("OPENAI_API_KEY loaded and available")
    else:
        logger.warning("OPENAI_API_KEY not found; set env or .openai_key for LLM answers")


def get_base_prompt():
    """Lazily build the base prompt to avoid importing langchain at module import time."""
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    return ChatPromptTemplate.from_messages([
        ("system",
         "당신은 전산/전력 장비 운영을 도와주는 AIOps 어시스턴트입니다. "
         "질문을 분석해서 구성정보(Postgres), 시계열(Timescale), 연결성(Neo4j), 매뉴얼(pgvector), 작업 이력(Postgres) "
         "이전 대화 이력 중 어디를 봐야 할지 결정하고, "
         "결과를 11px UI에 맞춰 핵심만 짚게 한국어로 답변하세요. "
         "항상 가능한 한 근거 링크를 함께 제시하세요."
         ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])
