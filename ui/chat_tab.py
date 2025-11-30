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
            llm_result = bot.orchestrator.route_and_answer(text)
            answer_text = llm_result.get("answer_text", "")

            resp = chat_search(text)
            sources = resp.get("sources", []) or []

            chat_log[-1] = pn.pane.HTML(
                f'<div style="padding:6px 10px 0 10px;">{html.escape(answer_text)}</div>',
                sizing_mode='stretch_width',
                margin=0,
                styles={'padding': '0'}
            )

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

