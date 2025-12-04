import logging
from typing import Dict, Any

from data_sources.chat_history import ChatHistoryDataSource

logger = logging.getLogger(__name__)

_store: Dict[str, Any] = {}
_chat_history_ds_global = ChatHistoryDataSource()


def _make_memory():
    """
    Lazily create a chat memory object. If LangChain is available, return ChatMessageHistory.
    Otherwise, return a lightweight placeholder with a compatible interface.
    """
    try:
        from langchain_community.chat_message_histories import ChatMessageHistory
        return ChatMessageHistory()
    except Exception as e:
        logger.warning("LangChain ChatMessageHistory unavailable (%s); using lightweight memory.", e)

        class _LightMemory:
            def __init__(self):
                self.messages = []

            def add_message(self, message):
                # Accept any object; store as-is
                self.messages.append(message)

        return _LightMemory()


def get_session_history(session_id: str):
    """
    Return a per-session chat memory. If LangChain is available, it will be a ChatMessageHistory;
    otherwise it will be a lightweight in-memory history. This avoids heavy deps during test collection.
    """
    if session_id not in _store:
        db_history = _chat_history_ds_global.get_history(session_id)
        mem = _make_memory()
        # Try to import HumanMessage/AIMessage if available; otherwise store plain dicts
        try:
            from langchain_core.messages import HumanMessage, AIMessage
            for msg in db_history:
                if msg.get('role') == 'user':
                    mem.add_message(HumanMessage(content=msg.get('content', '')))
                elif msg.get('role') == 'assistant':
                    mem.add_message(AIMessage(content=msg.get('content', '')))
        except Exception:
            for msg in db_history:
                mem.add_message({"role": msg.get("role"), "content": msg.get("content")})
        _store[session_id] = mem
    return _store[session_id]


def get_global_chat_history_data_source() -> ChatHistoryDataSource:
    return _chat_history_ds_global
