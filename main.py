import warnings
import logging

import panel as pn

from chatbot import AIOpsChatbot, generate_pdf_report
from llm.utils import log_openai_key_status
from logging_config import setup_logging
from api import app as rest_app
from stores.planner_store import PlannerStore
from styles import CHAT_CSS, PLANNER_CSS
from ui.admin_tab import build_admin_editor
from ui.chat_tab import build_chat_ui
from ui.planner_tab import build_planner_tab
from ui.upload_tab import build_upload_tab

warnings.filterwarnings("ignore")
pn.config.inline = True
pn.extension('codeeditor', 'tabulator',
             design='material',
             sizing_mode='stretch_width',
             css_files=['assets/font-awesome.min.css'])

def create_app():
    bot = AIOpsChatbot()
    planner_store = PlannerStore()

    chat_sidebar, chat_tab = build_chat_ui(bot)
    upload_tab = build_upload_tab()
    planner_panel = build_planner_tab(planner_store)
    editor_box = build_admin_editor()

    btn_pdf = pn.widgets.FileDownload(
        callback=pn.bind(lambda: generate_pdf_report(bot.last_topo_buffer, bot.last_chart_buffer), watch=False),
        filename="Report.pdf",
        label="PDF",
        button_type="success",
        width=54,
        height=30
    )

    sw_mode = pn.widgets.Switch(name="Admin", width=80, align='center')
    toolbar = pn.Row(
        pn.pane.Markdown(
            "**SPA AI**",
            styles={'font-size': '11px', 'font-weight': 'bold',
                    'color': '#333', 'margin': '3px 6px'}
        ),
        pn.Spacer(),
        btn_pdf,
        styles={'background': '#f8f9fa', 'padding': '2px 6px', 'border-bottom': '1px solid #ddd'},
        sizing_mode='stretch_width'
    )

    main_tabs = pn.Tabs(
        ("Chat", chat_tab),
        ("Planner", planner_panel),
        ("Upload", upload_tab),
        sizing_mode='stretch_both',
        styles={'height': '100%', 'overflow': 'hidden', 'flex': '1 1 auto', 'min-height': '0'}
    )
    main_content = pn.Column(
        toolbar,
        main_tabs,
        sizing_mode='stretch_both',
        # 뷰포트 높이에 맞춰 메인 영역을 확보하고 내부만 스크롤
        styles={'height': '100%', 'overflow': 'hidden', 'min-height': '0', 'display': 'flex', 'flex-direction': 'column'}
    )

    def _admin_tab_indexes():
        try:
            # Tabs.objects는 (이름, 객체) 튜플이 아니라 '객체' 목록이므로
            # Admin 에디터 객체 동일성으로 인덱스를 찾는다.
            return [i for i, obj in enumerate(main_tabs.objects) if obj is editor_box]
        except Exception:
            return []

    def _ensure_admin_open():
        idxs = _admin_tab_indexes()
        if not idxs:
            main_tabs.append(("Admin", editor_box))
            idxs = _admin_tab_indexes()
        try:
            main_tabs.active = idxs[0]
        except Exception:
            pass

    def _ensure_admin_closed():
        idxs = _admin_tab_indexes()
        for i in reversed(idxs):
            try:
                main_tabs.pop(i)
            except Exception:
                pass
        try:
            main_tabs.active = 0
        except Exception:
            pass

    def _on_admin_switch(event):
        admin = bool(getattr(event, "new", False))
        if admin:
            _ensure_admin_open()
        else:
            _ensure_admin_closed()

    # Switch의 value 파라미터를 명시적으로 감시해서 토글 시 탭을 정확히 열고/닫음
    sw_mode.param.watch(_on_admin_switch, "value")

    template = pn.template.MaterialTemplate(
        title="SPA AIOps",
        sidebar=[chat_sidebar],
        header=[pn.Row(pn.Spacer(), sw_mode, sizing_mode='stretch_width')],
        main=[main_content],
        raw_css=[CHAT_CSS, PLANNER_CSS],
        sidebar_width=260,
        header_background="#2b3e50"
    )
    return template


import os
import socket

if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    setup_logging()
    log_openai_key_status()
    logger = logging.getLogger(__name__)
    logger.info("Starting SPA AI application...")

    base_port = int(os.getenv("PORT", "5006"))

    def _is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            return s.connect_ex(("127.0.0.1", port)) == 0

    try:
        pn.serve(
            create_app,
            port=base_port,
            show=True,
            static_dirs={'assets': 'assets', 'uploads': 'uploads'},
            rest_app=rest_app,
            autoreload=True
        )
    except OSError as e:
        if getattr(e, "winerror", None) == 10048 or "address already in use" in str(e).lower() or _is_port_in_use(base_port):
            fallback_port = base_port + 1
            logging.getLogger(__name__).warning(f"Port {base_port} in use, retrying on {fallback_port}...")
            pn.serve(
                create_app,
                port=fallback_port,
                show=True,
                static_dirs={'assets': 'assets', 'uploads': 'uploads'},
                rest_app=rest_app,
                autoreload=True
            )
        else:
            raise
