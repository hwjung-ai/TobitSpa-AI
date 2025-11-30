import html

import panel as pn

from api import chat_search


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


def build_chat_ui(bot):
    """Chat UI (sidebar + chat tab)."""
    history_buttons = []

    # 1. PDF 뷰어 모달 추가
    pdf_viewer = pn.pane.HTML(sizing_mode='stretch_both', min_height=600)
    pdf_modal = pn.Modal(
        pdf_viewer,
        sizing_mode='stretch_width'
    )

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

    # 2. PDF 뷰어 여는 함수
    def open_pdf_viewer(path, page, query, event=None):
        from urllib.parse import quote
        pdf_viewer.object = f'<iframe src="/pdf_viewer?file={path}&page={page}&query={quote(query)}" style="width:100%; height:600px;"></iframe>'
        pdf_modal.open = True

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
            llm_result = bot.orchestrator.route_and_answer(text)
            answer_text = llm_result.get("answer_text", "")

            resp = chat_search(text)
            sources = resp.get("sources", []) or []
            router_sources = llm_result.get("router", {}).get("sources") if isinstance(llm_result.get("router"), dict) else []

            chat_log[-1] = pn.pane.HTML(
                f'<div style="padding:6px 10px 0 10px;">{html.escape(answer_text)}</div>',
                sizing_mode='stretch_width',
                margin=0,
                styles={'padding': '0'}
            )

            if sources:
                from urllib.parse import quote
                import functools

                def _normalize_link(raw):
                    if not raw:
                        return "#"
                    path = str(raw).replace("\\", "/")
                    if "uploads/" in path:
                        path = path.split("uploads/", 1)[1]
                    return quote(path, safe="/:-_.")

                def _highlight_snippet(snippet):
                    safe = html.escape(snippet or "")[:500]
                    for token in text.split():
                        if len(token) < 2:
                            continue
                        safe = safe.replace(html.escape(token), f"<mark>{html.escape(token)}</mark>")
                    return safe or "스니펫 없음"

                source_items = []
                for s in sources:
                    title = s.get("title", "문서")
                    page = s.get("page") or 1
                    link = _normalize_link(s.get("link") or s.get("source_path"))
                    raw_snippet = s.get("snippet", "")
                    highlighted_snippet = _highlight_snippet(raw_snippet)
                    
                    # 3. <a> 태그 대신 버튼 사용
                    view_button = pn.widgets.Button(
                        name=f"{title} (p.{page})",
                        button_type='text',
                        height=24,
                        styles={'text-align': 'left'}
                    )
                    view_button.on_click(functools.partial(open_pdf_viewer, link, page, raw_snippet))

                    source_items.append(
                        pn.Column(
                            view_button,
                            pn.pane.HTML(f'<div style="font-size:11px;color:#555;">{highlighted_snippet}</div>', margin=(0, 0, 0, 10))
                        )
                    )
                
                source_layout = pn.Column(*source_items, sizing_mode='stretch_width')
                chat_log.append(
                    pn.Column(
                        pn.pane.Markdown("📚 근거 문서", styles={'font-size': '12px', 'font-weight': 'bold'}),
                        source_layout,
                        css_classes=['bot-msg-box'],
                        sizing_mode='stretch_width'
                    )
                )

            if router_sources:
                from urllib.parse import quote
                import functools

                def _normalize_link(raw):
                    if not raw:
                        return "#"
                    path = str(raw).replace("\\", "/")
                    if "uploads/" in path:
                        path = path.split("uploads/", 1)[1]
                    return quote(path, safe="/:-_.")

                router_items = []
                for s in router_sources:
                    title = s.get("title", "source")
                    page = s.get("page") or 1
                    link = _normalize_link(s.get("link") or "")
                    raw_snippet = s.get("snippet", "")
                    score = s.get("score", 0)

                    view_button = pn.widgets.Button(
                        name=f"{title} (p.{page}) • {score:.3f}",
                        button_type='light',
                        height=24,
                        styles={'text-align': 'left'}
                    )
                    view_button.on_click(functools.partial(open_pdf_viewer, link, page, raw_snippet))

                    router_items.append(
                        pn.Column(
                            view_button,
                            pn.pane.HTML(f'<div style="font-size:11px;color:#555;">{html.escape(raw_snippet)[:400]}</div>', margin=(0, 0, 0, 10))
                        )
                    )

                chat_log.append(
                    pn.Column(
                        pn.pane.Markdown("🔀 Router 결과", styles={'font-size': '12px', 'font-weight': 'bold'}),
                        pn.Column(*router_items, sizing_mode='stretch_width'),
                        css_classes=['bot-msg-box'],
                        sizing_mode='stretch_width'
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
        pdf_modal, # 4. 모달을 레이아웃에 추가
        sizing_mode='stretch_both',
        styles={'display': 'flex', 'flex-direction': 'column', 'height': '100%'}
    )

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

    def reset_chat(e=None):
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

    return sidebar, chat_box
