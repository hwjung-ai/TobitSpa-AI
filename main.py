import warnings

import matplotlib
import matplotlib.pyplot as plt
import panel as pn

from chatbot import AIOpsChatbot, generate_pdf_report
from api import app as rest_app
from project_planner import PlannerStore
from styles import CHAT_CSS, PLANNER_CSS
from ui.admin_tab import build_admin_editor
from ui.chat_tab import build_chat_ui
from ui.planner_tab import build_planner_tab
from ui.upload_tab import build_upload_tab

matplotlib.use('Agg')

warnings.filterwarnings("ignore")
pn.extension('codeeditor', 'tabulator',
             design='material',
             sizing_mode='stretch_width',
             css_files=['assets/font-awesome.min.css'])

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


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
        width=50,
        height=26,
        styles={'font-size': '10px'}
    )

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
        ("Chat", chat_tab),
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
        if admin:
            if not _has_admin_tab():
                main_tabs.append(("Admin", editor_box))
        else:
            if _has_admin_tab():
                try:
                    idx = [i for i, (n, _) in enumerate(main_tabs.items()) if n == "Admin"][0]
                    main_tabs.pop(idx)
                except Exception:
                    pass
            main_tabs.active = 0

    template = pn.template.MaterialTemplate(
        title="SPA AIOps",
        sidebar=[chat_sidebar],
        header=[pn.Row(pn.Spacer(), sw_mode, sizing_mode='stretch_width')],
        main=[main_content],
        raw_css=[CHAT_CSS, PLANNER_CSS],
        sidebar_width=220,
        header_background="#2b3e50"
    )
    return template


if __name__ == "__main__":
    pn.serve(
        create_app,
        port=5006,
        show=True,
        static_dirs={'assets': 'assets', 'uploads': 'uploads'},
        rest_app=rest_app
    )
