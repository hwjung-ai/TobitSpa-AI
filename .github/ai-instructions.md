# Repo-specific AI Assistant instructions for AIOps SPA

This project is a single-file Panel-based AIOps prototype. Below are concise, actionable notes an AI coding agent should use to be productive in this codebase.

**Big Picture:**
- **Entry point:** `main.py` — creates a `Panel` app via `create_app()` and starts it with `pn.serve(..., port=5006)` when run as a script.
- **Architecture:** UI (`AIOpsChatbot`, Panel templates/widgets) -> Orchestrator (`AIOpsOrchestrator`) -> Data sources (stub classes) -> optional LLM (`ChatOpenAI`). Data flows from UI to orchestrator to data sources and (if available) to the LLM; results are then rendered as markdown, charts, topology, or tables.

**Key files / symbols:**
- `main.py` — full application; search here for implementations and patterns.
- `AIOpsOrchestrator` — routing logic, base LLM prompt, and public method `route_and_answer(user_query)` which returns the composite result structure.
- `AIOpsChatbot.answer(contents)` — UI-facing wrapper that converts orchestrator results into Panel components.
- Stub data sources: `ConfigDataSource.get_asset_config`, `MetricDataSource.get_metric_timeseries`, `GraphDataSource.get_topology_for_asset`, `ManualVectorSource.search_manuals`, and `HistoryStore`.

**Replaceable integrations (how to implement real connectors):**
- Postgres config: replace `ConfigDataSource.get_asset_config` with a class that queries Postgres (use connection pooling, param queries).
- TimescaleDB: replace `MetricDataSource.get_metric_timeseries` to return timestamps and numeric series (same dict keys: `asset`, `metric`, `period`, `times`, `values`).
- Neo4j: replace `GraphDataSource.get_topology_for_asset` and return a dict with `nodes` and `edges` (nodes list of dicts with `id`, `label`, `icon`, `color`).
- Vector store / RAG: replace `ManualVectorSource.search_manuals` to call pgvector / LlamaIndex and return list of dicts with `title`, `snippet`, `link`.
- History storage: `HistoryStore` is currently in-memory; persist to Redis/Postgres and expose `add_qa` and `search_history` preserving returned list format.

**LLM & credentials:**
- `load_api_key()` attempts to read `.openai_key` and set `OPENAI_API_KEY` or you can set `OPENAI_API_KEY` in the environment. The code expects keys that start with `sk-`.
- When `OPENAI_API_KEY` is present, `AIOpsOrchestrator` instantiates `ChatOpenAI(temperature=0, model="gpt-4o-mini")` and composes `base_prompt` with `trim_messages`/history. Changing model or client should be done in the orchestrator initializer.

**Run / dev workflow:**
- Install dependencies (example):
```powershell
python -m pip install -r requirements.txt
# or minimal: panel matplotlib networkx pandas reportlab pyvis langchain-openai
```
- Start dev server:
```powershell
python main.py
# Panel will serve on http://localhost:5006 by default (port 5006 in code)
```
- API key setup (PowerShell):
```powershell
# Option A: write key into repo file (used by repo helper)
"sk-..." | Out-File -Encoding utf8 .openai_key
# Option B: set environment variable for current shell
$env:OPENAI_API_KEY = 'sk-...'
```

**Project-specific conventions & patterns**
- UI / language: messages and prompt templates assume Korean localized responses and an 11px compact UI (fonts set to `Malgun Gothic`). Keep text size and Korean phrasing when generating UI strings.
- Simple heuristic routing: `_decide_modes(query)` implements keyword-based routing (`config`, `metric`, `graph`, `manual`, `history`). When adding functionality, update both `_decide_modes` and downstream handling in `route_and_answer`.
- Composite return format from `route_and_answer`: contains keys `answer_text`, `config`, `metric`, `graph`, `manuals`, `history_hits`. Code assumes these keys when assembling UI.
- Admin mode: the app includes a code editor (`pn.widgets.CodeEditor`) that reads/writes repo files via `load_file`/`save_file`. Be cautious: edits are written directly to disk — treat as privileged.

**Debugging tips / gotchas**
- Matplotlib backend is forced to `Agg` (headless images) to avoid GUI errors — keep this for server runs.
- Temporary HTML topology files are written then removed in `build_topology_panel`; ensure the server user has write access to CWD.
- LLM chain uses `RunnableWithMessageHistory` and `trim_messages`. If LLM calls fail, the code falls back to a mock summary (see `route_and_answer`).
- If new data-source classes are added, they must return the same shape used by UI builder helpers (`build_line_chart_panel`, `build_topology_panel`).

**Examples (search patterns to edit behavior)**
- To change the LLM model: edit `ChatOpenAI(temperature=0, model="gpt-4o-mini")` in `AIOpsOrchestrator.__init__`.
- To persist chat history: replace `HistoryStore` class with a store exposing `add_qa(question, answer)` and `search_history(query)`.

If anything is missing or you want the instructions to include a `requirements.txt` or CI/test run steps, let me know which you'd like added and I'll update this file.

---
Requested-by: AI agent assistance — please review and let me know if any areas are unclear and need expansion.
