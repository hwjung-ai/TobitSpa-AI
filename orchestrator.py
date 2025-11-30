import os
import uuid
import logging
import json
import re

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import trim_messages, HumanMessage, AIMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory

from data_sources import AssetDataSource, MetricDataSource, GraphDataSource, ManualVectorSource, ChatHistoryDataSource, WorkHistoryDataSource
from llama_index_integration import LlamaIndexManualRetriever
from llama_query_routing import MultiSourceRouter

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

# Langchain의 인-메모리 세션 기록 (휘발성)
store = {}
chat_history_ds_global = ChatHistoryDataSource()

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        # 세션이 메모리에 없으면 DB에서 지난 대화 기록을 로드
        db_history = chat_history_ds_global.get_history(session_id)
        chat_memory = ChatMessageHistory()
        logger.info("session_id '%s'에 대한 %d개의 대화기록을 DB에서 로드합니다.", session_id, len(db_history))
        for msg in db_history:
            if msg['role'] == 'user':
                chat_memory.add_message(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                chat_memory.add_message(AIMessage(content=msg['content']))
        store[session_id] = chat_memory
    return store[session_id]


class AIOpsOrchestrator:
    """여러 데이터소스를 LLM 기반으로 오케스트레이션하는 역할"""

    def __init__(self):
        self.asset_ds = AssetDataSource()
        self.metric_ds = MetricDataSource()
        self.graph_ds = GraphDataSource()
        self.manual_ds = ManualVectorSource()
        self.work_history_ds = WorkHistoryDataSource()
        self.chat_history_ds = chat_history_ds_global # DB 기반 영구 히스토리
        self.llama_retriever = LlamaIndexManualRetriever()
        self.router = MultiSourceRouter()
        self.session_id = str(uuid.uuid4())

        if USE_OPENAI:
            self.llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")
            self.trimmer = trim_messages(
                max_tokens=500, strategy="last", token_counter=self.llm, include_system=True
            )
        else:
            self.llm = None
            self.trimmer = None

        self.base_prompt = ChatPromptTemplate.from_messages([
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

    def reset_session(self):
        self.session_id = str(uuid.uuid4())

    def _decide_modes(self, query: str):
        q = query.lower()
        # 대화 이력 검색은 다른 모드와 독립적으로 작동
        if any(k in q for k in ["이력에서", "이전에", "지난 대화", "기록에서", "찾아줘"]):
            return ["history_search"]
        
        modes = []
        if any(k in q for k in ["구성", "config", "ip", "os", "서버", "장비", "목록", "리스트"]):
            modes.append("config")
        if any(k in q for k in ["추세", "trend", "시계열", "그래프", "cpu", "latency", "사용률"]):
            modes.append("metric")
        if any(k in q for k in ["연결", "구성도", "topology", "토폴로지", "path"]):
            modes.append("graph")
        if any(k in q for k in ["매뉴얼", "manual", "설명서", "가이드"]):
            modes.append("manual")
        if any(k in q for k in ["작업", "유지보수", "maintenance", "작업 이력", "history"]):
            modes.append("work_history")

        # 아무 모드도 감지되지 않으면 기본 모드 설정
        if not modes:
            modes = ["config", "manual"]
        return modes

    def _extract_search_term(self, query: str) -> str:
        """'이력에서 OOO 찾아줘' 같은 문장에서 검색어(OOO)를 추출합니다."""
        keywords = ["이력에서", "이전에", "지난 대화", "기록에서", "찾아줘", "검색"]
        q = query.lower()
        for kw in keywords:
            q = q.replace(kw, "")
        
        match = re.search(r"['"]([^'"]+)['"]", q)
        if match:
            return match.group(1)
        return q.strip()

    def _extract_asset_filters(self, query: str) -> dict:
        """LLM을 사용하여 사용자 질문에서 자산 검색 필터를 추출합니다."""
        if not self.llm: return {}
        # ... (implementation unchanged)
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a master of Natural Language Understanding. Your task is to extract asset filtering criteria from a user's query. "
             "The available filter keys are `asset_type`, `name`, and attributes like `os`, `ram`. "
             "Analyze the user's query and return a JSON object with the appropriate key-value pairs for filtering. "
             "For example, for the query 'Ubuntu 22.04를 사용하는 서버 목록 보여줘', you should return `{{\"os\": \"Ubuntu 22.04\", \"asset_type\": \"IT_DEVICE\"}}`. "
             "If no specific filters are found, return an empty JSON object `{{}}`."),
            ("human", "{input}")
        ])
        try:
            chain = prompt | self.llm
            result = chain.invoke({"input": query})
            content = result.content if hasattr(result, 'content') else str(result)
            json_str_match = re.search(r'```json\n(\{.*?\})\n```', content, re.DOTALL)
            if json_str_match: content = json_str_match.group(1)
            filters = json.loads(content)
            logger.info("추출된 자산 필터: %s", filters)
            return filters if isinstance(filters, dict) else {}
        except Exception as e:
            logger.warning("자산 필터 추출 실패: %s", e)
            return {}

    def _extract_metric_query(self, query: str) -> dict:
        """LLM을 사용하여 사용자 질문에서 시계열 쿼리 파라미터를 추출합니다."""
        if not self.llm: return {}
        # ... (implementation unchanged)
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a master of Natural Language Understanding. Your task is to extract parameters for a time-series query from a user's request. "
             "You need to identify three parameters: `asset_name` (the name of the device), `metric` (the name of the metric, e.g., 'cpu_usage', 'memory_utilization', 'network_traffic'), and `period` (a PostgreSQL-compatible interval string, e.g., '1 day', '3 hours', '60 minutes'). "
             "For the query '지난 3시간 동안 was-01의 CPU 사용률 추세 보여줘', you should return `{{\"asset_name\": \"was-01\", \"metric\": \"cpu_usage\", \"period\": \"3 hours\"}}`. "
             "If a parameter is not specified, omit it from the JSON. If no parameters can be found, return an empty JSON object `{{}}`."),
            ("human", "{input}")
        ])
        try:
            chain = prompt | self.llm
            result = chain.invoke({"input": query})
            content = result.content if hasattr(result, 'content') else str(result)
            json_str_match = re.search(r'```json\n(\{.*?\})\n```', content, re.DOTALL)
            if json_str_match: content = json_str_match.group(1)
            params = json.loads(content)
            logger.info("추출된 시계열 쿼리 파라미터: %s", params)
            return params if isinstance(params, dict) else {}
        except Exception as e:
            logger.warning("시계열 쿼리 파라미터 추출 실패: %s", e)
            return {}

    def _extract_graph_query(self, query: str) -> dict:
        """LLM을 사용하여 사용자 질문에서 그래프 쿼리 파라미터를 추출합니다."""
        if not self.llm: return {}
        # ... (implementation unchanged)
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a master of Natural Language Understanding. Your task is to extract parameters for a graph query from a user's request. "
             "You need to identify the `query_type`, which can be 'path' or 'neighbors'. "
             "If the type is 'path', you must extract `start_asset` and `end_asset`. "
             "If the type is 'neighbors', you must extract the `asset_name`. "
             "For 'was-01부터 db-main까지 경로 보여줘', return `{{\"query_type\": \"path\", \"start_asset\": \"was-01\", \"end_asset\": \"db-main\"}}`. "
             "For 'a812dpt에 연결된 장비는?', return `{{\"query_type\": \"neighbors\", \"asset_name\": \"a812dpt\"}}`. "
             "If no specific graph query is found, return an empty JSON object `{{}}`."),
            ("human", "{input}")
        ])
        try:
            chain = prompt | self.llm
            result = chain.invoke({"input": query})
            content = result.content if hasattr(result, 'content') else str(result)
            json_str_match = re.search(r'```json\n(\{.*?\})\n```', content, re.DOTALL)
            if json_str_match: content = json_str_match.group(1)
            params = json.loads(content)
            logger.info("추출된 그래프 쿼리 파라미터: %s", params)
            return params if isinstance(params, dict) else {}
        except Exception as e:
            logger.warning("그래프 쿼리 파라미터 추출 실패: %s", e)
            return {}

    def route_and_answer(self, user_query: str):
        modes = self._decide_modes(user_query)
        logger.info("Orchestrator query: '%s' modes=%s session=%s", user_query, modes, self.session_id)

        self.chat_history_ds.add_message(self.session_id, 'user', user_query)

        if "history_search" in modes:
            search_term = self._extract_search_term(user_query)
            hits = self.chat_history_ds.search_history(self.session_id, search_term)
            if not hits:
                answer_text = f"'{search_term}'(을)를 포함한 대화 이력이 없습니다."
            else:
                lines = []
                for h in hits:
                    ts = h.get("timestamp")
                    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else ""
                    lines.append(f"[{ts_str}] {h.get('role')}: {h.get('content')}")
                answer_text = "최근 대화 이력 검색 결과:\n" + "\n".join(lines)
            final_response = {
                "answer_text": answer_text, "config": None, "metric": None,
                "graph": None, "manuals": [], "work_history": None
            }
            self.chat_history_ds.add_message(self.session_id, 'assistant', answer_text, final_response)
            return final_response
            
        config_info, metric_info, graph_info, manuals, work_history_info = None, None, None, [], None
        
        if "config" in modes:
            filters = self._extract_asset_filters(user_query)
            if filters:
                config_info = self.asset_ds.find_assets_by_attributes(filters)
            else:
                asset_name = None
                for token in user_query.replace(",", " ").split():
                    if "." in token or "-" in token or token.lower().startswith("a"):
                        asset_name = token.strip()
                        break
                if asset_name:
                    config_info = self.asset_ds.get_asset_by_name(asset_name)

        asset_name_for_other_modes = "a812dpt"
        if isinstance(config_info, dict) and config_info.get('name'):
            asset_name_for_other_modes = config_info['name']
        elif isinstance(config_info, list) and len(config_info) == 1 and config_info[0].get('name'):
             asset_name_for_other_modes = config_info[0]['name']
        elif not config_info:
            for token in user_query.replace(",", " ").split():
                if "." in token or "-" in token or token.lower().startswith("a"):
                    asset_name_for_other_modes = token.strip()
                    break

        if "metric" in modes:
            metric_params = self._extract_metric_query(user_query)
            asset_name = metric_params.get("asset_name", asset_name_for_other_modes)
            metric = metric_params.get("metric", "cpu_usage")
            period = metric_params.get("period", "1h")
            metric_info = self.metric_ds.get_metric_timeseries(asset_name, metric, period)

        if "graph" in modes:
            graph_params = self._extract_graph_query(user_query)
            query_type = graph_params.get("query_type")
            if query_type == 'path':
                start = graph_params.get("start_asset")
                end = graph_params.get("end_asset")
                if start and end:
                    graph_info = self.graph_ds.find_path_between_assets(start, end)
            else:
                asset_name = graph_params.get("asset_name", asset_name_for_other_modes)
                graph_info = self.graph_ds.get_topology_for_asset(asset_name)

        if "work_history" in modes:
            work_history_info = self.work_history_ds.get_history_by_asset_name(asset_name_for_other_modes)

        if "manual" in modes:
            # Prefer LlamaIndex if possible; fallback is inside retriever
            manuals = self.llama_retriever.search(user_query, top_k=3)

        router_result = None
        if self.llm and self.router:
            try:
                router_result = self.router.query(user_query)
            except Exception as e:
                logger.warning("Router query failed: %s", e)

        if not self.llm:
            answer_text = f"[MOCK] 질의: {user_query}\n\n- 구성정보: {config_info}\n- 시계열: {metric_info}\n- 작업이력: {work_history_info}\n- 매뉴얼 hits: {len(manuals)}건"
        else:
            chain = self.base_prompt | self.trimmer | self.llm
            chain_with_history = RunnableWithMessageHistory(
                chain, get_session_history, input_messages_key="input", history_messages_key="history"
            )

            context_parts = []
            if config_info:
                if isinstance(config_info, list):
                    cfg_text = "\n".join([f"- {d.get('name', 'N/A')}: {d.get('attributes', '{}')}" for d in config_info])
                    context_parts.append(f"[구성정보 목록]\n{cfg_text}")
                else:
                    context_parts.append(f"[구성정보]\n{config_info}")
            if metric_info: context_parts.append(f"[시계열 정보]\n{metric_info}")
            if graph_info: context_parts.append(f"[연결성 정보]\n{graph_info}")
            if work_history_info:
                hist_text = "\n".join([f"- {h.get('work_date').strftime('%Y-%m-%d')}: {h.get('description')} (담당자: {h.get('worker_name')})" for h in work_history_info])
                context_parts.append(f"[작업 이력]\n{hist_text}")
            if manuals:
                mtext = "\n".join([f"- {m['title']}: {m['snippet']}" for m in manuals])
                context_parts.append(f"[매뉴얼 검색 결과]\n{mtext}")
            if router_result:
                context_parts.append(f"[Router 결과]\n{router_result.get('text')}")
            
            context_text = "\n\n".join(context_parts) if context_parts else "관련 데이터 없음"
            prompt_input = f"사용자 질문: {user_query}\n\n아래는 검색된 데이터입니다. 이 데이터를 참고해서 답변을 작성하세요.\n\n[Context]\n{context_text}"
            
            logger.info("LLM prompt (truncated): %s", prompt_input[:300])
            result = chain_with_history.invoke({"input": prompt_input}, config={"configurable": {"session_id": self.session_id}})
            answer_text = result.content if hasattr(result, "content") else str(result)
            logger.info("LLM answer (truncated): %s", str(answer_text)[:300])

        final_response = {
            "answer_text": answer_text, "config": config_info, "metric": metric_info,
            "graph": graph_info, "manuals": manuals, "work_history": work_history_info,
            "router": router_result
        }
        
        self.chat_history_ds.add_message(self.session_id, 'assistant', answer_text, final_response)

        return final_response
