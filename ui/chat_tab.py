import html
from urllib.parse import quote
import panel as pn
import logging

logger = logging.getLogger(__name__)

USER_BUBBLE_STYLE = (
    "float:right; clear:both; background:#f3f4f6; color:#222; border-radius:18px;"
    " padding:10px 14px; margin:6px 12px 6px 40px; width:fit-content; max-width:80%;"
    " text-align:left; font-size:12px; box-shadow:0 1px 2px rgba(0,0,0,0.08);"
    " word-break: break-word; overflow-wrap: anywhere; white-space: pre-wrap; display:inline-block;"
)
BOT_BUBBLE_STYLE = (
    "float:left; clear:both; background:#fff; color:#222; border:1px solid #e5e7eb;"
    " border-radius:14px; padding:10px 14px; margin:6px 40px 6px 12px;"
    " width:fit-content; max-width:90%; font-size:12px;"
    " box-shadow:0 1px 2px rgba(0,0,0,0.08);"
    " word-break: break-word; overflow-wrap: anywhere; white-space: pre-wrap; display:inline-block;"
)


def build_chat_ui(bot):
    """Chat UI (sidebar + chat tab)."""
    pdf_viewer = pn.pane.HTML(sizing_mode="stretch_both", min_height=600)
    pdf_modal = pn.Modal(pdf_viewer, sizing_mode="stretch_width")

    chat_log = pn.Column(
        sizing_mode="stretch_both",
        css_classes=["chat-log-container"],
        styles={
            "padding": "10px",
            "flex": "1 1 auto",
            "min-height": "0",
            "overflow-y": "auto",
            "display": "block",
        },
    )
    chat_log.append(
        pn.pane.HTML(
            f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE} color:gray;">무엇을 도와드릴까요?</div>',
            sizing_mode="stretch_width",
        )
    )
    chat_input = pn.widgets.TextInput(
        placeholder="무엇이든 물어보세요",
        sizing_mode="stretch_width",
        height=36,
        css_classes=["chat-text-input"],
        styles={"margin-top": "4px"},
    )
    chat_send = pn.widgets.Button(
        name="➤",
        button_type="primary",
        width=44,
        height=36,
        css_classes=["chat-send-btn"],
        styles={
            "margin-top": "0",
            "margin-bottom": "0",
            "font-size": "12px",
            "display": "flex",
            "align-items": "center",
            "justify-content": "center",
            "line-height": "1",
            "padding": "0",
            "min-height": "36px",
        },
    )
    notice_bar = pn.pane.Markdown(
        "SPA AI는 참고용 응답을 제공합니다. 중요한 결정 전에는 결과를 검토해주세요.",
        sizing_mode="stretch_width",
        styles={
            "font-size": "10px",
            "color": "#475569",
            "margin": "0 0 2px 6px",
            "padding": "0 0 0 4px",
            "background": "transparent",
            "border": "none",
            "text-align": "left",
        },
    )

    # Viewport size info to help when the input bar is hidden on small windows
    size_info = pn.pane.HTML(
        """
<div id="vp-info" style="font-size:10px; color:#666; text-align:right; margin:0 0 4px 0"></div>
<script>
(function(){
  function upd(){
    var el = document.currentScript.previousElementSibling || document.getElementById('vp-info');
    if (el) {
      el.textContent = '창 크기: ' + window.innerWidth + '×' + window.innerHeight +
        'px (입력창이 안 보이면 창 높이를 조금 늘려주세요)';
    }
  }
  window.addEventListener('resize', upd);
  upd();
})();
</script>
""",
        sizing_mode="stretch_width",
    )

    def make_user_bubble(text):
        safe = html.escape(text)
        return pn.pane.HTML(
            f'<div><div class="user-msg-box" style="{USER_BUBBLE_STYLE}">{safe}</div><div style="clear:both"></div></div>',
            sizing_mode="stretch_width",
        )

    def make_bot_bubble(content, metadata=None):
        # Render markdown so links/lists/bold are preserved
        try:
            import markdown as md

            rendered = md.markdown(content or "", extensions=["extra"])
        except Exception:
            rendered = content or ""
        return pn.pane.HTML(
            f'<div><div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">{rendered}</div><div style="clear:both"></div></div>',
            sizing_mode="stretch_width",
        )

    def open_pdf_viewer(path, page, query, event=None):
        norm = str(path).replace("\\", "/").lstrip("/")
        src = f"/assets/pdf_viewer.html?file={quote(norm)}&page={page}&query={quote(str(query) or '')}"
        pdf_viewer.object = f'<iframe src="{src}" style="width:100%; height:600px; border:none;"></iframe>'
        pdf_modal.open = True

    def send_message(event=None):
        # Use value_input to capture text before the widget syncs on blur/click
        text = (chat_input.value_input or chat_input.value or "").strip()
        logger.info("send_message invoked text='%s'", text)
        if not text:
            logger.info("send_message ignored: empty input")
            return

        chat_log.append(make_user_bubble(text))
        chat_input.value = ""
        chat_input.value_input = ""

        loading = pn.pane.HTML(
            f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE} color:gray;">생각 중...</div>',
            sizing_mode="stretch_width",
        )
        chat_log.append(loading)

        try:
            logger.info("calling bot.answer")
            composite_view = bot.answer(text)
            chat_log[-1] = composite_view
            populate_history_sidebar(inp_search.value)
        except Exception as e:
            logger.exception("send_message failed: %s", e)
            chat_log[-1] = pn.pane.HTML(
                f'<div class="bot-msg-box">Error: {html.escape(str(e))}</div>', sizing_mode="stretch_width"
            )

    chat_send.on_click(send_message)
    chat_input.param.watch(send_message, "enter_pressed")

    # Input area fixed at the bottom; chat_log scrolls independently above it.
    # NOTE: removed pdf_modal from the layout to avoid nested in-chat modal/pane that
    # previously limited available space for the chat log.
    bottom_bar = pn.Column(
        pn.Row(
            chat_input,
            chat_send,
            sizing_mode="stretch_width",
            css_classes=["chat-input-row"],
            styles={
                "align-items": "center",
                "gap": "8px",
                "padding": "6px 8px 0 0",
                "flex": "0 0 auto",
                "background": "#fff",
                "border-top": "1px solid #e5e7eb",
            },
        ),
        notice_bar,
        sizing_mode="stretch_width",
        styles={
            "position": "sticky",
            "bottom": "0",
            "z-index": "10",
            "background": "#fff",
            "padding": "0 0 8px 0",
            "margin": "0",
        },
    )

    chat_box = pn.Column(
        chat_log,
        pn.pane.HTML(
            """
<script>
(function(){
  function scroll() {
    const el = document.querySelector('.chat-log-container');
    if (el) { el.scrollTop = el.scrollHeight; }
  }
  const observer = new MutationObserver(scroll);
  function hook() {
    const el = document.querySelector('.chat-log-container');
    if (el) {
      observer.observe(el, { childList: true, subtree: true });
      scroll();
    } else {
      setTimeout(hook, 300);
    }
  }
  hook();
})();
</script>
""",
            height=0,
            sizing_mode="stretch_width",
        ),
        size_info,
        bottom_bar,
        sizing_mode="stretch_both",
        css_classes=["chat-box"],
        styles={
            "display": "flex",
            "flex-direction": "column",
            "gap": "6px",
            "height": "100%",
            "flex": "1 1 auto",
            "min-height": "0",
            "overflow": "hidden",
        },
        margin=(0, 0, 0, 0),
        min_height=0,
    )
    btn_new = pn.widgets.Button(name="＋ 새 채팅", button_type="primary", sizing_mode="stretch_width", height=28)
    inp_search = pn.widgets.TextInput(placeholder="Search...", sizing_mode="stretch_width", height=26)
    hist_col = pn.Column(
        sizing_mode="stretch_both", css_classes=["history-list"], styles={"overflow-y": "auto", "min-height": "0", "flex": "1 1 auto"}
    )

    def load_history_in_chat_log(session_id):
        chat_log.clear()
        try:
            history = bot.get_history(session_id) or []
        except Exception as e:
            chat_log.append(
                pn.pane.HTML(
                    f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE} color:gray;">이력 로드 오류: {html.escape(str(e))}</div>'
                )
            )
            bot.session_id = session_id
            return

        logger.info("load_history_in_chat_log session=%s count=%s", session_id, len(history))
        chat_log.append(
            pn.pane.HTML(
                f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE} color:#6b7280;">세션 불러오기: {html.escape(str(session_id))} / {len(history)}개</div>'
            )
        )

        if not history:
            chat_log.append(
                pn.pane.HTML(
                    f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE} color:#6b7280;">이 세션에는 대화가 없습니다.</div>'
                )
            )
            bot.session_id = session_id
            return

        for msg in history:
            role = (msg.get("role") if isinstance(msg, dict) else None) or ""
            content = (msg.get("content") if isinstance(msg, dict) else None) or ""
            if role == "user":
                chat_log.append(make_user_bubble(content))
            else:
                meta = None
                if isinstance(msg, dict):
                    meta = msg.get("metadata")
                    if isinstance(meta, str):
                        try:
                            import json

                            meta = json.loads(meta)
                        except Exception:
                            meta = None
                if meta:
                    chat_log.append(bot.render_from_metadata(meta))
                else:
                    chat_log.append(make_bot_bubble(content))
        bot.session_id = session_id

    def populate_history_sidebar(filter_text: str = ""):
        sessions = bot.get_all_sessions()
        ft = filter_text.lower().strip()
        rows = []
        for session in sessions:
            sid = session.get("session_id")
            first_msg = session.get("first_message") or "대화 시작"
            title = first_msg[:40] + "..." if len(first_msg) > 40 else first_msg
            if ft and ft not in title.lower():
                continue
            load_btn = pn.widgets.Button(
                name=title,
                button_type="light",
                sizing_mode="stretch_width",
                height=22,
                styles={"flex": "1 1 auto", "min-width": "0", "overflow": "hidden"},
                stylesheets=[
                    """
button {
  font-size: 12px !important;
  text-align: left !important;
  padding-left: 2px !important;
  max-width: 100% !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  display: inline-block !important;
}
"""
                ],
            )
            del_btn = pn.widgets.Button(
                name="×",
                button_type="light",
                width=18,
                height=18,
                styles={
                    "background": "transparent",
                    "border": "none",
                    "color": "#9ca3af",
                    "box-shadow": "none",
                    "padding": "0",
                    "margin-left": "6px",
                },
                stylesheets=[
                    """
button {
  background: transparent !important;
  border: none !important;
  color: #9ca3af !important;
  font-size: 12px !important;
  padding: 0 !important;
  box-shadow: none !important;
}
button:hover {
  color: #6b7280 !important;
}
"""
                ],
            )

            def _make_handlers(s):
                def _load(event):
                    load_history_in_chat_log(s)

                def _delete(event):
                    current = bot.session_id
                    bot.delete_session(s)
                    populate_history_sidebar(inp_search.value)
                    if s == current:
                        chat_log.clear()
                        chat_log.append(
                            pn.pane.HTML(
                                f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE} color:gray;">새 대화를 시작해 주세요.</div>'
                            )
                        )

                return _load, _delete

            _load, _delete = _make_handlers(sid)
            load_btn.on_click(_load)
            del_btn.on_click(_delete)
            row = pn.Row(
                load_btn,
                del_btn,
                sizing_mode="stretch_width",
                styles={"align-items": "center", "gap": "6px"},
                css_classes=["history-item"],
            )
            rows.append(row)
        hist_col.objects = rows

    def reset_chat(event=None):
        bot.reset_memory()
        chat_log.clear()
        chat_log.append(
            pn.pane.HTML(
                f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE} color:gray;">새 대화를 시작해 주세요.</div>'
            )
        )
        populate_history_sidebar()

    btn_new.on_click(reset_chat)
    inp_search.param.watch(lambda e: populate_history_sidebar(e.new), "value")

    populate_history_sidebar()

    sidebar = pn.Column(
        btn_new,
        pn.pane.Markdown("---", margin=(5, 0)),
        inp_search,
        pn.pane.Markdown(
            "**최근 대화**",
            styles={"font-size": "12px", "color": "gray", "margin": "8px 0", "padding-left": "12px"},
        ),
        hist_col,
        sizing_mode="stretch_both",
        css_classes=["sidebar-col"],
        styles={
            "display": "flex",
            "flex-direction": "column",
            "min-height": "0",
            "height": "100%",
            "flex": "1 1 auto",
            "overflow": "hidden",
            "padding-left": "4px",
        },
    )

    return sidebar, chat_box
