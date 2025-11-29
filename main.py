import warnings
import html
import datetime
import os

import panel as pn
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

from chatbot import AIOpsChatbot, generate_pdf_report
from api import app as rest_app  # FastAPI 앱을 Panel 서버와 함께 구동
from api import upload_via_python, chat_search
from utils import get_real_file_list, load_file, save_file
from styles import CHAT_CSS, PLANNER_CSS
from project_planner import PlannerStore

# Matplotlib 백엔드 설정 (GUI 에러 방지)
matplotlib.use('Agg')

warnings.filterwarnings("ignore")
pn.extension('codeeditor', 'tabulator',
             design='material',
             sizing_mode='stretch_width',
             css_files=['assets/font-awesome.min.css'])


plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

UPLOAD_API_URL = os.getenv("UPLOAD_API_URL", "http://localhost:5006/upload")
USER_BUBBLE_STYLE = (
    "float:right; clear:both; background:#f3f4f6; color:#222; border-radius:18px;"
    " padding:10px 14px; margin:6px 12px 6px 40px; width:fit-content; max-width:80%;"
    " text-align:left; font-size:12px; box-shadow:0 1px 2px rgba(0,0,0,0.08);"
)
BOT_BUBBLE_STYLE = (
    "float:left; clear:both; background:#fff; color:#222; border:1px solid #e5e7eb;"
    " border-radius:14px; padding:10px 14px; margin:6px 40px 6px 12px;"
    " width:fit-content; max-width:90%; font-size:12px;"
    " box-shadow:0 1px 2px rgba(0,0,0,0.08);"
)


# ============================================================
# 4. Panel UI (기존 코드 기반)
# ============================================================

def create_app():
    bot = AIOpsChatbot()
    history_buttons = []
    planner_store = PlannerStore()

    def _normalize_id(value):
        """Tabulator selections can be nested list/tuple; flatten to first scalar value."""
        while isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value in ("", None):
            return None
        return value

    def _parse_date(value):
        """DatePicker expects date/datetime; convert ISO strings safely."""
        if not value:
            return None
        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, datetime.date):
            return value
        try:
            return datetime.date.fromisoformat(str(value))
        except Exception:
            return None

    # CSS
    chat_css = CHAT_CSS

    # Sidebar
    btn_new = pn.widgets.Button(
        name='✨ New Chat', button_type='primary',
        sizing_mode='stretch_width', height=28
    )
    inp_search = pn.widgets.TextInput(
        placeholder='Search...', sizing_mode='stretch_width', height=26
    )
    hist_col = pn.Column(sizing_mode='stretch_width')

    def update_history_view(event=None):
        query = (inp_search.value or "").strip().lower()
        if query:
            hist_col.objects = [b for b in history_buttons if query in b.name.lower()]
        else:
            hist_col.objects = history_buttons

    inp_search.param.watch(update_history_view, 'value')

    sidebar = pn.Column(
        btn_new,
        pn.pane.Markdown("---", margin=(5, 0)),
        inp_search,
        pn.pane.Markdown("**최근 대화**",
                         styles={'font-size': '11px', 'color': 'gray', 'margin': '8px 0'}),
        hist_col,
        sizing_mode='stretch_width',
        margin=0
    )

    # Editor (Admin 모드에서 보는 코드 편집기)
    files = get_real_file_list()
    init_file = files[0] if files else "No Files"
    sel_file = pn.widgets.Select(options=files, value=init_file,
                                 width=150, height=26)
    btn_save = pn.widgets.Button(name='Save', button_type='primary',
                                 width=60, height=26)
    editor = pn.widgets.CodeEditor(
        value=load_file(init_file),
        language='python',
        theme='monokai',
        sizing_mode='stretch_both',
        styles={'font-size': '11px'}
    )

    def on_file_change(e):
        editor.value = load_file(e.new)

    sel_file.param.watch(on_file_change, 'value')
    btn_save.on_click(lambda e: save_file(sel_file.value, editor.value))
    editor_box = pn.Column(
        pn.Row(sel_file, btn_save, align='center'),
        editor,
        sizing_mode='stretch_both',
        styles={'height': '100%'}
    )

    # PDF 버튼
    btn_pdf = pn.widgets.FileDownload(
        callback=pn.bind(lambda: generate_pdf_report(bot.last_topo_buffer, bot.last_chart_buffer), watch=False),
        filename="Report.pdf",
        label="PDF",
        button_type="success",
        width=50,
        height=26,
        styles={'font-size': '10px'}
    )

    # Chat Layout
    chat_log = pn.Column(
        sizing_mode='stretch_both',
        scroll=True,
        css_classes=['chat-log-container'],
        styles={'overflow-y': 'auto', 'padding': '10px', 'flex': '1'}
    )

    chat_input = pn.widgets.TextInput(
        placeholder="무엇이든 물어보세요", sizing_mode='stretch_width', height=42
    )
    chat_send = pn.widgets.Button(
        name="Send", button_type="primary", width=60, height=30
    )

    def make_user_bubble(text):
        safe = html.escape(text)
        return pn.pane.HTML(
            f'<div class="user-msg-box" style="{USER_BUBBLE_STYLE}">{safe}</div>',
            sizing_mode='stretch_width',
            margin=0,
            styles={'padding': '0'}
        )

    def send_message(event=None):
        text = chat_input.value.strip()
        if not text:
            return

        chat_log.append(make_user_bubble(text))
        chat_input.value = ""

        loading = pn.pane.HTML(
            f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE} color:gray;">생각 중...</div>',
            sizing_mode='stretch_width',
            margin=0,
            styles={'padding': '0'}
        )
        chat_log.append(loading)

        try:
            # LLM 기반 답변 (orchestrator 사용)
            llm_result = bot.orchestrator.route_and_answer(text)
            answer_text = llm_result.get("answer_text", "")

            # RAG 검색 결과 (pgvector)
            resp = chat_search(text)
            sources = resp.get("sources", []) or []

            chat_log[-1] = pn.pane.HTML(
                f'<div style="padding:6px 10px 0 10px;">{html.escape(answer_text)}</div>',
                sizing_mode='stretch_width',
                margin=0,
                styles={'padding': '0'}
            )

            # 근거를 답변 아래 링크로 표시 (새 창으로 열기)
            if sources:
                from urllib.parse import quote

                def _normalize_link(raw):
                    if not raw:
                        return "#"
                    path = str(raw).replace("\\", "/")
                    if "uploads/" in path:
                        path = path.split("uploads/", 1)[1]
                        path = "/uploads/" + path
                    elif not path.startswith("/"):
                        path = "/" + path.lstrip("/")
                    return quote(path, safe="/:-_.")

                def _highlight_snippet(snippet):
                    safe = html.escape(snippet or "")[:500]
                    for token in text.split():
                        if len(token) < 2:
                            continue
                        safe = safe.replace(html.escape(token), f"<mark>{html.escape(token)}</mark>")
                    return safe or "스니펫 없음"

                items = []
                for s in sources:
                    title = s.get("title", "문서")
                    page = s.get("page") or "?"
                    link = _normalize_link(s.get("link") or s.get("source_path"))
                    if page and str(page).isdigit():
                        link = f"{link}#page={page}"
                    snippet = _highlight_snippet(s.get("snippet", ""))
                    items.append(f'<li><a href="{link}" target="_blank">{html.escape(title)} (p.{page})</a><div style="font-size:11px;color:#555;">{snippet}</div></li>')
                html_list = "<ul>" + "".join(items) + "</ul>"
                chat_log.append(
                    pn.pane.HTML(
                        f'<div class="bot-msg-box">📚 근거{html_list}</div>',
                        sizing_mode='stretch_width',
                        margin=0,
                        styles={'padding': '0'}
                    )
                )
        except Exception as e:
            chat_log[-1] = pn.pane.HTML(
                f'<div class="bot-msg-box">Error: {html.escape(str(e))}</div>',
                sizing_mode='stretch_width',
                margin=0,
                styles={'padding': '0'}
            )

    chat_send.on_click(send_message)
    chat_input.param.watch(lambda e: send_message() if e.new else None, 'enter_pressed')

    chat_box = pn.Column(
        chat_log,
        pn.Row(chat_input, chat_send,
               sizing_mode='stretch_width',
               styles={'padding-top': '5px', 'flex': '0 0 auto'}),
        pn.pane.Markdown(
            "SPA AI는 실수를 할 수 있습니다. 중요한 내용을 포함한 답변은 반드시 재차 확인해 주세요.",
            styles={'font-size': '10px', 'color': '#777', 'margin': '4px 0 0 4px'}
        ),
        sizing_mode='stretch_both',
        styles={'display': 'flex', 'flex-direction': 'column', 'height': '100%'}
    )


    # --- Upload 탭 (파일 업로드 + 메타데이터) ---
    upload_file = pn.widgets.FileInput(
        accept='.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx',
        multiple=True,
        sizing_mode='stretch_width'
    )
    meta_title = pn.widgets.TextInput(name="제목*", width=200)
    meta_system = pn.widgets.TextInput(name="시스템*", width=160)
    meta_category = pn.widgets.TextInput(name="카테고리*", width=160)
    meta_owner = pn.widgets.TextInput(name="담당*", width=140)
    meta_tags = pn.widgets.TextInput(name="태그(쉼표)", width=220)
    btn_upload = pn.widgets.Button(name="업로드", button_type="primary", width=80)
    upload_status = pn.pane.Markdown("", sizing_mode='stretch_width')

    def _build_files_payload():
        names = upload_file.filename
        mime = upload_file.mime_type
        data = upload_file.value
        if not data:
            return []
        if isinstance(data, list):
            files = []
            for idx, raw in enumerate(data):
                fname = names[idx] if isinstance(names, list) else f"file_{idx}"
                mtype = mime[idx] if isinstance(mime, list) else "application/octet-stream"
                files.append((fname, raw, mtype))
            return files
        return [(names or "file.bin", data, mime or "application/octet-stream")]

    def do_upload(event=None):
        req_fields = [meta_title.value, meta_system.value, meta_category.value, meta_owner.value]
        if not all(req_fields):
            upload_status.object = "필수 항목(제목/시스템/카테고리/담당)을 입력하세요."
            return
        files = _build_files_payload()
        if not files:
            upload_status.object = "파일을 선택하세요."
            return
        try:
            result = upload_via_python(
                files,
                meta_title.value,
                meta_system.value,
                meta_category.value,
                meta_owner.value,
                meta_tags.value,
            )
            upload_status.object = f"업로드 완료: {result}"
        except Exception as e:
            upload_status.object = f"업로드 실패: {e}"

    btn_upload.on_click(do_upload)

    upload_tab = pn.Column(
        pn.Row(meta_title, meta_system, meta_category, meta_owner, meta_tags, sizing_mode='stretch_width'),
        upload_file,
        pn.Row(btn_upload, sizing_mode='stretch_width'),
        upload_status,
        sizing_mode='stretch_both',
        styles={'padding': '8px'}
    )

    # --- Planner (JSON CRUD + Tree) ---
    selected_ids = []

    def _children_map(items):
        cmap = {}
        for it in items:
            cmap.setdefault(it["parent_id"], []).append(it)
        for v in cmap.values():
            v.sort(key=lambda x: (x["type"], x["title"]))
        return cmap

    def _descendants(item_id, items):
        item_id = _normalize_id(item_id)
        if not item_id:
            return set()
        desc = set()
        changed = True
        while changed:
            changed = False
            for it in items:
                if it["parent_id"] in (desc | {item_id}) and it["id"] not in desc:
                    desc.add(it["id"])
                    changed = True
        return desc

    def build_parent_options(current_id=None):
        current_id = _normalize_id(current_id)
        items = planner_store.list_items()
        blocked = set()
        if current_id:
            blocked |= {current_id}
            blocked |= _descendants(current_id, items)
        opts = [("", None)]
        for it in items:
            if it["id"] in blocked:
                continue
            opts.append((f"{it['title']} ({it['type']})", it["id"]))
        return {label: value for label, value in opts}

    def build_flat_options():
        items = planner_store.list_items()
        cmap = _children_map(items)
        options = []

        def walk(parent_id, depth):
            for item in cmap.get(parent_id, []):
                prefix = "· " * depth
                options.append((f"{prefix}{item['title']} ({item['type']})", item["id"]))
                walk(item["id"], depth + 1)

        walk(None, 0)
        return {label: value for label, value in [("", None)] + options}

    
    def build_table_rows():
        items = planner_store.list_items()
        cmap = _children_map(items)
        parent_of = {it["id"]: it["parent_id"] for it in items}

        def path_of(item_id):
            parts = []
            cur = item_id
            while cur:
                itm = next((i for i in items if i["id"] == cur), None)
                if not itm:
                    break
                parts.append(itm["title"])
                cur = parent_of.get(cur)
            return "/".join(reversed(parts))

        rows = []
        def walk(parent_id, prefix_stack):
            children = cmap.get(parent_id, [])
            # sort children by existing order (numeric first), fallback idx
            def _order_key(item):
                val = item.get("order", "")
                try:
                    return (0, int(val))
                except Exception:
                    return (1, str(val))
            children = sorted(children, key=lambda x: (_order_key(x), x["title"]))
            total = len(children)
            for idx, child in enumerate(children):
                is_last = idx == total - 1
                branch = "└─ " if is_last else "├─ "
                # keep a visible indent even when ancestors are last siblings
                indent = "".join("│  " for _ in prefix_stack)
                rows.append({
                    "id": child["id"],
                    "title": indent + branch + child["title"],
                    "order": child.get("order", "") or idx + 1,
                    "type": child["type"],
                    "status": child["status"],
                    "owner": child["owner"],
                    "due": child["due"],
                    "path": path_of(child["id"]),
                })
                walk(child["id"], prefix_stack + [is_last])

        walk(None, [])
        return rows


    def build_tabulator(value, config=None):
        # Prefer row-click selection; fall back to checkbox if needed
        for selectable_opt in (True, 'checkbox', 1):
            try:
                kwargs = dict(show_index=False, selectable=selectable_opt, sizing_mode='stretch_both')
                if config:
                    kwargs["configuration"] = config
                return pn.widgets.Tabulator(value, **kwargs)
            except Exception:
                continue
        kwargs = dict(show_index=False, sizing_mode='stretch_both')
        if config:
            kwargs["configuration"] = config
        return pn.widgets.Tabulator(value, **kwargs)

    def build_tree_grid(value, config=None):
        """Use Tabulator dataTree mode with _children."""
        kwargs = dict(
            show_index=False,
            selectable=True,
            sizing_mode='stretch_both',
        )
        if config:
            kwargs["configuration"] = config
        return pn.widgets.Tabulator(value, **kwargs)

    # Tabulator: dataTree 우선, 실패 시 평면 DF
    tree_supported = True

    def _strip_path(nodes):
        """Remove path to avoid auto-generated columns."""
        for n in nodes:
            n.pop("path", None)
            if "_children" in n:
                _strip_path(n["_children"])
    def _annotate_order(nodes):
        """Annotate sibling order (1-based); keep existing order if provided."""
        if not nodes:
            return
        for idx, n in enumerate(nodes, start=1):
            if not n.get("order"):
                n["order"] = idx
            if "_children" in n:
                _annotate_order(n["_children"])

    planner_columns_tree = [
        {"title": "제목", "field": "title", "formatter": "tree", "editor": False},
        {"title": "정렬", "field": "order", "hozAlign": "center", "width": 70, "editor": False},
        {"title": "구분", "field": "type", "editor": False},
        {"title": "상태", "field": "status", "editor": False},
        {"title": "담당", "field": "owner", "editor": False},
        {"title": "Due Date", "field": "due", "editor": False},
    ]
    planner_columns_plain = [
        {k: v for k, v in col.items() if k != "formatter"}
        for col in planner_columns_tree
    ]

    try:
        tree_rows = planner_store.to_tree_rows()
        _strip_path(tree_rows)
        _annotate_order(tree_rows)
        planner_table = build_tree_grid(
            tree_rows,
            config={
                "layout": "fitColumns",
                "dataTree": True,
                "dataTreeChildField": "_children",
                "dataTreeColumn": "title",
                "dataTreeStartExpanded": True,
                "dataTreeSort": False,
                "index": "id",
                "dataTreeChildIndent": 26,
                "columnDefaults": {"headerSort": False, "editor": False},
            },
        )
    except Exception:
        tree_supported = False
        planner_table = build_tabulator(
            pd.DataFrame(build_table_rows(), columns=["title", "order", "type", "status", "owner", "due", "path", "id"]),
            config={
                "layout": "fitColumns",
                "columnDefaults": {"headerSort": False, "editor": False},
                "columns": planner_columns_plain,
            },
        )

    try:
        planner_table.hidden_columns = ["id", "parent_id", "_children", "path"]
    except Exception:
        pass
    sel_target = pn.widgets.Select(name="선택/수정 대상", options=build_flat_options(), value=None, sizing_mode='stretch_width')
    sel_target_display = pn.widgets.TextInput(name="선택 항목 (표에서 선택)", value="", sizing_mode='stretch_width')
    sel_parent = pn.widgets.Select(
        name="부모 노드",
        options=build_parent_options(),
        value=None,
        sizing_mode='stretch_width'
    )
    inp_title = pn.widgets.TextInput(name="제목", placeholder="예) API Gateway", value="", sizing_mode='stretch_width')
    sel_type = pn.widgets.Select(
        name="구분",
        options={"": None, "Architecture": "Architecture", "Data": "Data", "Feature": "Feature", "UI": "UI", "Schedule": "Schedule"},
        value=None,
        sizing_mode='stretch_width'
    )
    sel_status = pn.widgets.Select(
        name="상태",
        options={"": None, "Planned": "Planned", "In Progress": "In Progress", "Done": "Done", "Hold": "Hold"},
        value=None,
        sizing_mode='stretch_width'
    )
    inp_owner = pn.widgets.TextInput(name="담당", placeholder="예) Infra", value="", sizing_mode='stretch_width')
    inp_due = pn.widgets.DatePicker(name="Due Date", value=None, sizing_mode='stretch_width')
    inp_notes = pn.widgets.TextAreaInput(name="메모", rows=3, value="", sizing_mode='stretch_width')
    inp_notes.css_classes = ["planner-notes"]
    inp_order = pn.widgets.TextInput(name="정렬", placeholder="예) 1", value="", sizing_mode='stretch_width')
    planner_msg = pn.pane.Markdown("", sizing_mode='stretch_width', styles={'font-size': '12px', 'color': '#444'})

    def _label_for_id(item_id):
        item_id = _normalize_id(item_id)
        opts = build_flat_options()
        for label, val in opts.items():
            if val == item_id:
                return label
        return ""

    def refresh_planner(message=""):
        current = [_normalize_id(v) for v in selected_ids]
        if tree_supported:
            planner_table.value = planner_store.to_tree_rows()
        else:
            planner_table.value = pd.DataFrame(build_table_rows(),
                                               columns=["title", "order", "type", "status", "owner", "due", "path", "id"])

        flat_options = build_flat_options()
        sel_target.options = flat_options
        sel_target_display.value = _label_for_id(sel_target.value or (selected_ids[0] if selected_ids else None))

        existing_ids = set(_normalize_id(v) for v in flat_options.values())
        updated_sel = [sid for sid in current if sid in existing_ids]
        selected_ids.clear()
        selected_ids.extend(updated_sel)

        sel_parent.options = build_parent_options(_normalize_id(sel_target.value))
        cur_val = _normalize_id(sel_target.value)
        if cur_val not in existing_ids:
            sel_target.value = selected_ids[0] if selected_ids else None
            sel_target_display.value = _label_for_id(sel_target.value)
        if sel_parent.value and sel_parent.value not in sel_parent.options.values():
            sel_parent.value = None
        # 선택이 없을 때 폼과 그리드 선택을 초기화
        if not selected_ids and not sel_target.value:
            try:
                planner_table.selection = []
            except Exception:
                pass
            sel_target_display.value = ""
            sel_parent.value = None
            inp_title.value = ""
            sel_type.value = None
            sel_status.value = None
            inp_owner.value = ""
            inp_due.value = None
            inp_notes.value = ""
            inp_order.value = ""
        # 상태 메시지 및 알림
        planner_msg.object = message

    def load_selection(event=None):
        target_id = _normalize_id(sel_target.value)
        selected_ids.clear()
        if target_id:
            selected_ids.append(target_id)
        item = planner_store.get_item(target_id) if target_id else None
        if not item:
            inp_title.value = ""
            sel_type.value = None
            sel_status.value = None
            inp_owner.value = ""
            inp_due.value = None
            inp_notes.value = ""
            sel_parent.value = None
            return
        inp_title.value = item.get("title", "")
        sel_type.value = item.get("type", "Architecture")
        sel_status.value = item.get("status", "Planned")
        inp_owner.value = item.get("owner", "")
        inp_due.value = _parse_date(item.get("due"))
        inp_notes.value = item.get("notes", "")
        sel_parent.value = item.get("parent_id")
        sel_parent.options = build_parent_options(target_id)
        sel_target_display.value = _label_for_id(target_id)
        inp_order.value = str(item.get("order", "") or "")

    sel_target.param.watch(load_selection, 'value')

    def sync_selection_from_table(event):
        selected_ids.clear()
        if not event.new:
            sel_target.value = None
            sel_target_display.value = ""
            return

        if tree_supported:
            flat_ids = []

            def flatten(nodes):
                for n in nodes:
                    flat_ids.append(n.get("id"))
                    if "_children" in n:
                        flatten(n["_children"])

            flatten(planner_table.value or [])
            for idx in event.new:
                if isinstance(idx, (int, float)) and int(idx) < len(flat_ids):
                    selected_ids.append(flat_ids[int(idx)])
                elif isinstance(idx, str):
                    selected_ids.append(idx)
        else:
            df = planner_table.value if isinstance(planner_table.value, pd.DataFrame) else pd.DataFrame()
            for idx in event.new:
                if isinstance(idx, (int, float)) and idx < len(df):
                    selected_ids.append(df.iloc[int(idx)]["id"])
                elif isinstance(idx, str):
                    selected_ids.append(idx)

        selected_ids[:] = [sid for sid in selected_ids if sid in sel_target.options.values()]
        sel_target.value = selected_ids[0] if selected_ids else None
        sel_target_display.value = _label_for_id(sel_target.value)

    planner_table.param.watch(sync_selection_from_table, 'selection')

    def on_add(event):
        planner_store.add_item(
            parent_id=_normalize_id(sel_parent.value),
            title=inp_title.value,
            item_type=sel_type.value,
            status=sel_status.value,
            owner=inp_owner.value,
            due=str(inp_due.value) if inp_due.value else "",
            notes=inp_notes.value,
            order=inp_order.value,
        )
        refresh_planner("새 항목이 추가되었습니다.")

    def on_update(event):
        target_id = _normalize_id(sel_target.value)
        parent_id = _normalize_id(sel_parent.value)
        if not target_id:
            planner_msg.object = "수정할 항목을 선택하세요."
            return
        # 자기 자신/자손을 부모로 지정하는 것 방지
        items = planner_store.list_items()
        blocked = {target_id} | _descendants(target_id, items)
        if parent_id in blocked:
            planner_msg.object = "자신이나 하위 노드를 부모로 지정할 수 없습니다."
            return
        planner_store.update_item(
            target_id,
            {
                "title": inp_title.value,
                "type": sel_type.value,
                "status": sel_status.value,
                "owner": inp_owner.value,
                "due": str(inp_due.value) if inp_due.value else None,
                "notes": inp_notes.value,
                "order": inp_order.value,
                "parent_id": parent_id,
            }
        )
        refresh_planner("항목이 수정되었습니다.")

    def on_delete(event):
        # 테이블에서 여러 항목을 선택했으면 그것들을 사용하고, 아니면 드롭다운의 현재 값을 사용
        targets_to_delete = selected_ids if selected_ids else [sel_target.value]
        # None이나 빈 값을 제외하고 유효한 ID만 필터링
        targets = [_normalize_id(t) for t in targets_to_delete if _normalize_id(t)]

        if not targets:
            planner_msg.object = "삭제할 항목을 선택하세요."
            return
        for tid in targets:
            planner_store.delete_item(tid)

        refresh_planner(f"{len(targets)}건 삭제 완료.")

    btn_add = pn.widgets.Button(name="추가", button_type="success", width=60, height=26)
    btn_update = pn.widgets.Button(name="저장", button_type="primary", width=60, height=26)
    btn_delete = pn.widgets.Button(name="삭제", button_type="danger", width=60, height=26)
    btn_reload = pn.widgets.Button(name="리로드", button_type="default", width=70, height=26)

    btn_add.on_click(on_add)
    btn_update.on_click(on_update)
    btn_delete.on_click(on_delete)
    btn_reload.on_click(lambda e: refresh_planner("새로고침했습니다."))

    planner_left = pn.Column(
        pn.pane.Markdown("**Tree**", margin=(0, 0, 6, 0)),
        pn.Column(
            planner_table,
            sizing_mode='stretch_both',
        ),
        sizing_mode='stretch_both',
        css_classes=['planner-left'], # CSS 클래스 지정
    )

    # 모든 입력/셀렉트 높이/스타일 통일
    # 모든 위젯의 높이를 자동으로 설정하여 내용에 맞게 조절되도록 합니다.
    for w in (sel_target_display, sel_parent, inp_title, sel_type, sel_status, inp_owner, inp_due):
        # 기존 스타일을 유지하면서 새 스타일을 추가/업데이트합니다.
        existing_styles = w.styles or {}
        existing_styles.update({"font-size": "11px", "color": "#212121"})
        w.width = None
        w.sizing_mode = 'stretch_width'
        w.styles = existing_styles # height를 설정하지 않아 자동 높이 사용
    inp_notes.width = None
    inp_notes.sizing_mode = 'stretch_width'
    # 메모 영역을 넉넉히 확보
    inp_notes.rows = 10  # 메모 줄 수 지정
    inp_notes.height = 250
    inp_notes.styles = {"font-size": "11px", "color": "#212121", "min-height": "250px", "resize": "vertical"}

    # 버튼 정렬 및 글자 위치 조정
    btn_add.height = btn_update.height = btn_delete.height = btn_reload.height = 24
    for idx, b in enumerate((btn_add, btn_update, btn_delete, btn_reload)):
        b.styles = {"font-weight": "500", "font-size": "9px", "padding": "0px 8px", "line-height": "9px"}
        b.margin = (0, 8 if idx < 3 else 0, 0, 0)
    btn_reload.button_type = "warning"

    # 레이블과 위젯을 Column으로 재구성
    def field_col(label, widget):
        widget.name = ""  # Panel 자동 레이블 제거
        label_pane = pn.pane.Markdown(
            f"**{label}**",
            width=80,
            align='center',
            styles={'font-size': '12px', 'color': '#333', 'text-align': 'right', 'margin-right': '10px'}
        )
        return pn.Row(
            label_pane,
            widget,
            sizing_mode='stretch_width', align='center', margin=(0, 10, 8, 10)
        )

    btn_row = pn.Row(
        pn.Spacer(),
        btn_add, btn_update, btn_delete, btn_reload,
        pn.Spacer(),
        sizing_mode='stretch_width',
        align='center',
        margin=(12, 10, 4, 10),
    )

    planner_right = pn.Column(
        field_col("선택/수정 대상", sel_target_display),
        field_col("부모 노드", sel_parent),
        field_col("제목", inp_title),
        field_col("구분", sel_type),
        field_col("상태", sel_status),
        field_col("담당", inp_owner),
        field_col("Due Date", inp_due),
        field_col("정렬", inp_order),
        field_col("메모", inp_notes),
        btn_row,
        planner_msg,
        sizing_mode='stretch_both',
        css_classes=['planner-right'], # CSS 클래스 지정
        styles={'margin-left': '12px'},
    )
    planner_panel = pn.Column(
        pn.Row(
            planner_left,
            planner_right,
            sizing_mode='stretch_both',
            styles={'height': '100%'},
            css_classes=['planner-split'],
        ),
        sizing_mode='stretch_both',
        styles={'padding': '6px', 'height': '100%'}
    )

    refresh_planner("Planner를 로드했습니다.")

    # 히스토리 버튼 저장/복원 (간단 버전)
    def save_history():
        if not bot.logs.get(bot.session_id):
            return
        title = bot.logs[bot.session_id][0]['content'][:20] + "..."
        sid = bot.session_id
        btn = pn.widgets.Button(
            name=title, button_type='light',
            sizing_mode='stretch_width', height=24,
            styles={'text-align': 'left'}
        )

        def load_hist(e):
            chat_log.objects = []
            for log in bot.logs.get(sid, []):
                if log['role'] == 'user':
                    chat_log.append(make_user_bubble(log['content']))
                else:
                    # 단순히 "다시 질의"하지 않고 저장된 텍스트만 복원할 수도 있지만
                    # 여기서는 간단히 텍스트/구분 정도만
                    chat_log.append(
                        pn.pane.HTML(
                            f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">{html.escape(str(log["content"]))}</div>',
                            sizing_mode='stretch_width',
                            margin=0,
                            styles={'padding': '0'}
                        )
                    )
            bot.session_id = sid

        btn.on_click(load_hist)
        history_buttons.append(btn)
        update_history_view()

    def reset_chat(e):
        save_history()
        bot.reset_memory()
        chat_log.objects = [
            pn.pane.HTML(
                f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE} color:gray;">_새로운 대화를 시작합니다._</div>',
                sizing_mode='stretch_width',
                margin=0,
                styles={'padding': '0'}
            )
        ]

    btn_new.on_click(reset_chat)

    # Main Layout
    sw_mode = pn.widgets.Switch(name="Admin", width=40, align='center')
    toolbar = pn.Row(
        pn.pane.Markdown(
            "**SPA AI**",
            styles={'font-size': '12px', 'font-weight': 'bold',
                    'color': '#333', 'margin': '6px'}
        ),
        pn.Spacer(),
        btn_pdf,
        styles={'background': '#f8f9fa', 'padding': '4px', 'border-bottom': '1px solid #ddd'},
        sizing_mode='stretch_width'
    )

    main_tabs = pn.Tabs(
        ("Chat", chat_box),
        ("Planner", planner_panel),
        ("Upload", upload_tab),
        sizing_mode='stretch_both'
    )
    main_content = pn.Column(toolbar, main_tabs, sizing_mode='stretch_both')

    def _has_admin_tab():
        try:
            return any(name == "Admin" for name, _ in main_tabs.items())
        except Exception:
            return False

    @pn.depends(sw_mode, watch=True)
    def switch_view(admin):
        # Admin 모드: Admin 탭 추가 (Chat, Planner 탭은 유지)
        if admin:
            if not _has_admin_tab():
                main_tabs.append(("Admin", editor_box))
        else:
            # 일반 모드: Admin 탭 제거
            if _has_admin_tab():
                try:
                    idx = [i for i, (n, _) in enumerate(main_tabs.items()) if n == "Admin"][0]
                    main_tabs.pop(idx)
                except Exception:
                    pass
            # Chat 탭이 보이도록 설정
            main_tabs.active = 0

    template = pn.template.MaterialTemplate(
        title="SPA AIOps",
        sidebar=[sidebar],
        header=[pn.Row(pn.Spacer(), sw_mode, sizing_mode='stretch_width')],
        main=[main_content],
        raw_css=[chat_css, PLANNER_CSS],
        sidebar_width=220,
        header_background="#2b3e50"
    )
    return template


if __name__ == "__main__":
    # Panel과 FastAPI를 동일 프로세스/포트에서 함께 서비스
    pn.serve(
        create_app,
        port=5006,
        show=True,
        static_dirs={'assets': 'assets', 'uploads': 'uploads'},
        rest_app=rest_app  # FastAPI 엔드포인트를 같은 서버에 마운트
    )
    
