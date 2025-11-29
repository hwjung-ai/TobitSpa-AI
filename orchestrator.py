import os
import uuid
import logging

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import trim_messages
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory

from data_sources import ConfigDataSource, MetricDataSource, GraphDataSource, ManualVectorSource

API_KEY_FILE = ".openai_key"


def load_api_key():
    if os.path.exists(API_KEY_FILE):
        try:
            with open(API_KEY_FILE, 'r') as f:
                key = f.read().strip()
            if key.startswith('sk-'):
                os.environ["OPENAI_API_KEY"] = key
                return True
        except Exception:
            pass
    return False


load_api_key()
USE_OPENAI = os.getenv("OPENAI_API_KEY") is not None

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

class HistoryStore:
    """챗봇 히스토리 기반 검색 Stub"""

    def __init__(self):
        # 실제로는 Redis/PG 등에 저장된 벡터 RAG를 권장
        self._history_texts = []

    def add_qa(self, question: str, answer: str):
        self._history_texts.append(f"Q: {question}\nA: {answer}")

    def search_history(self, query: str):
        # TODO: 실제로는 벡터 검색으로 교체
        hits = [h for h in self._history_texts if query.lower() in h.lower()]
        return hits[:3]


store = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]


class AIOpsOrchestrator:
    """여러 데이터소스를 LLM 기반으로 오케스트레이션하는 역할"""

    def __init__(self):
        self.config_ds = ConfigDataSource()
        self.metric_ds = MetricDataSource()
        self.graph_ds = GraphDataSource()
        self.manual_ds = ManualVectorSource()
        self.history_store = HistoryStore()
        self.session_id = str(uuid.uuid4())

        if USE_OPENAI:
            # 여기선 작은 모델 사용, 나중에 solar/로컬 LLM 교체 가능
            self.llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")
            self.trimmer = trim_messages(
                max_tokens=500,
                strategy="last",
                token_counter=self.llm,
                include_system=True
            )
        else:
            self.llm = None
            self.trimmer = None

        # 기본 프롬프트 템플릿(페르소나 설명 + 히스토리)
        self.base_prompt = ChatPromptTemplate.from_messages([
            ("system",
             "당신은 전산/전력 장비 운영을 도와주는 AIOps 어시스턴트입니다. "
             "질문을 분석해서 구성정보(Postgres), 시계열(Timescale), 연결성(Neo4j), 매뉴얼(pgvector), "
             "이전 대화 이력 중 어디를 봐야 할지 결정하고, "
             "결과를 11px UI에 맞춰 핵심만 짚게 한국어로 답변하세요. "
             "항상 가능한 한 근거 링크를 함께 제시하세요."
             ),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

    def reset_session(self):
        self.session_id = str(uuid.uuid4())

    # --- 간단한 라우팅 heuristic: 실제로는 LLM/Router 로 교체 가능---
    def _decide_modes(self, query: str):
        q = query.lower()
        modes = []
        if any(k in q for k in ["구성", "config", "ip", "os", "서버", "장비"]):
            modes.append("config")
        if any(k in q for k in ["추세", "trend", "시계열", "그래프", "cpu", "latency", "사용률"]):
            modes.append("metric")
        if any(k in q for k in ["연결", "구성도", "topology", "토폴로지", "path"]):
            modes.append("graph")
        if any(k in q for k in ["매뉴얼", "manual", "설명서", "가이드"]):
            modes.append("manual")
        if any(k in q for k in ["이력에서", "이전에", "지난 대화", "지난 질의"]):
            modes.append("history")

        if not modes:
            # 기본값 config + manual 정도
            modes = ["config", "manual"]
        return modes

    def route_and_answer(self, user_query: str):
        modes = self._decide_modes(user_query)
        logger.info("Orchestrator query: '%s' modes=%s session=%s", user_query, modes, self.session_id)

        config_info = None
        metric_info = None
        graph_info = None
        manuals = []
        history_hits = []

        asset_name = None
        for token in user_query.replace(",", " ").split():
            if "." in token or "-" in token or token.lower().startswith("a"):
                asset_name = token.strip()
                break
        if not asset_name:
            asset_name = "a812dpt"

        if "config" in modes:
            config_info = self.config_ds.get_asset_config(asset_name)
        if "metric" in modes:
            metric_info = self.metric_ds.get_metric_timeseries(asset_name, metric="cpu_usage", period="1h")
        if "graph" in modes:
            graph_info = self.graph_ds.get_topology_for_asset(asset_name)
        if "manual" in modes:
            manuals = self.manual_ds.search_manuals(user_query, top_k=3)
        if "history" in modes:
            history_hits = self.history_store.search_history(user_query)

        if not self.llm:
            answer_text = f"[MOCK] 질의: {user_query}\n\n- 구성정보: {config_info}\n- 시계열: {metric_info}\n- 매뉴얼 hits: {len(manuals)}건\n- 이력 hits: {len(history_hits)}건"
        else:
            chain = self.base_prompt | self.trimmer | self.llm
            chain_with_history = RunnableWithMessageHistory(
                chain, get_session_history, input_messages_key="input", history_messages_key="history"
            )

            context_parts = []
            if config_info: context_parts.append(f"[구성정보]\n{config_info}")
            if metric_info: context_parts.append(f"[시계열]\n{metric_info}")
            if manuals:
                mtext = "\n".join(f"- {m['title']}: {m['snippet']} (link: {m['link']})" for m in manuals)
                context_parts.append(f"[매뉴얼 검색 결과]\n{mtext}")
            if history_hits:
                htext = "\n".join(history_hits)
                context_parts.append(f"[이전 대화 히스토리]\n{htext}")
            context_text = "\n\n".join(context_parts) if context_parts else "관련 데이터 없음"

            prompt_input = f"사용자 질문: {user_query}\n\n아래는 구성/시계열/매뉴얼/히스토리에서 가져온 예시 데이터입니다. 이 데이터를 참고해서 답변을 작성하세요.\n\n[Context]\n{context_text}"
            logger.info("LLM prompt (truncated): %s", prompt_input[:300])
            result = chain_with_history.invoke({"input": prompt_input}, config={"configurable": {"session_id": self.session_id}})
            answer_text = result.content if hasattr(result, "content") else str(result)
            logger.info("LLM answer (truncated): %s", str(answer_text)[:300])

        if isinstance(answer_text, str):
            self.history_store.add_qa(user_query, answer_text)

        return {
            "answer_text": answer_text, "config": config_info, "metric": metric_info,
            "graph": graph_info, "manuals": manuals, "history_hits": history_hits,
        }
