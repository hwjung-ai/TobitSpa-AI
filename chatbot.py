import io
import os
import uuid
import html
import logging
from urllib.parse import quote

import panel as pn

from orchestrator import AIOpsOrchestrator
from data_sources.graph import GraphDataSource
from services.report_generator import generate_pdf_report

logger = logging.getLogger(__name__)

BOT_BUBBLE_STYLE = (
    "float:left; clear:both; background:#fff; color:#222; border:1px solid #e5e7eb;"
    " border-radius:14px; padding:10px 14px; margin:6px 40px 6px 12px;"
    " width:fit-content; max-width:90%; font-size:12px;"
    " box-shadow:0 1px 2px rgba(0,0,0,0.08);"
    " word-break: break-word; overflow-wrap: anywhere; white-space: pre-wrap; display:inline-block;"
)


class AIOpsChatbot:
    """Panel UI에서 사용하는 챗봇 상태/렌더 헬퍼."""

    def __init__(self):
        self.orchestrator = AIOpsOrchestrator()
        self.session_id = self.orchestrator.session_id
        self.logs = {}
        self.last_topo_buffer = None
        self.last_chart_buffer = None

    def _strip_mock_prefix(self, text: str) -> str:
        try:
            t = (text or "").lstrip()
            for prefix in ("[MOCK]", "MOCK:", "[Mock]", "[mock]", "MOCK"):
                if t.startswith(prefix):
                    t = t[len(prefix):].lstrip("-: \n\t")
            return t
        except Exception:
            return text

    def _log(self, role: str, kind: str, content):
        self.logs.setdefault(self.session_id, []).append({"role": role, "kind": kind, "content": content})

    def reset_memory(self):
        self.orchestrator.reset_session()
        self.session_id = self.orchestrator.session_id
        self.last_topo_buffer = None
        self.last_chart_buffer = None

    def get_all_sessions(self):
        return self.orchestrator.chat_history_ds.get_all_sessions()

    def get_history(self, session_id: str):
        return self.orchestrator.chat_history_ds.get_history(session_id)

    def delete_session(self, session_id: str) -> int:
        try:
            deleted = self.orchestrator.chat_history_ds.delete_session(session_id)
            if session_id == self.session_id:
                self.reset_memory()
            return deleted
        except Exception:
            logger.exception("Failed to delete session: %s", session_id)
            return 0

    def build_table_panel(self):
        import pandas as pd

        df = pd.DataFrame(
            {
                "Time": ["13:00", "13:01", "13:05"],
                "Device": ["SW-Core-01", "WAS-01", "DB-Master"],
                "Status": ["⚠️ Critical", "⚠️ Warning", "✅ Normal"],
                "Metric": ["Link Down", "Latency 2s", "CPU 40%"],
            }
        )
        table_widget = pn.widgets.Tabulator(df, show_index=False, sizing_mode="stretch_width", theme="site", height=150)
        return pn.Column(
            pn.pane.Markdown("**Incident Status Table (샘플)**", styles={"font-size": "12px", "font-weight": "bold"}),
            table_widget,
            sizing_mode="stretch_width",
        )

    def build_line_chart_panel(self, metric_info=None):
        try:
            import matplotlib.pyplot as plt
        except Exception as e:
            logger.warning("Matplotlib unavailable for chart rendering: %s", e)
            return pn.pane.Markdown(
                "차트 렌더링을 건너뜨리다 (matplotlib 로드 실패).",
                styles={"font-size": "11px", "color": "gray"},
                sizing_mode="stretch_width",
            )

        if metric_info:
            times, values = metric_info["times"], metric_info["values"]
            title = f"{metric_info['asset']} - {metric_info['metric']} ({metric_info['period']})"
        else:
            times, values = ["09:00", "10:00", "11:00", "12:00", "13:00"], [20, 35, 45, 30, 95]
            title = "CPU Trend Analysis"

        fig, ax = plt.subplots(figsize=(5, 3))
        ax.plot(times, values, "o-")
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("Value")
        ax.grid(True, linestyle="--", alpha=0.5)

        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format="png", dpi=100, bbox_inches="tight")
        img_buffer.seek(0)
        self.last_chart_buffer = img_buffer
        plt.close(fig)

        return pn.Column(
            pn.pane.PNG(img_buffer, width=400),
            pn.pane.Markdown("미니 **Timeseries Trend**", styles={"font-size": "11px", "color": "gray"}),
            sizing_mode="stretch_width",
        )

    def build_topology_panel(self, graph_info=None):
        import networkx as nx
        from pyvis.network import Network
        try:
            import matplotlib.pyplot as plt
            matplotlib_ok = True
        except Exception as e:
            logger.warning("Matplotlib unavailable for topology snapshot: %s", e)
            matplotlib_ok = False

        if not graph_info:
            graph_info = GraphDataSource().get_topology_for_asset("default")

        G = nx.DiGraph()
        for node in graph_info["nodes"]:
            G.add_node(
                node["id"],
                label=node["label"],
                title=node["label"],
                shape="icon",
                icon={
                    "face": "Font Awesome 5 Free",
                    "code": chr(int(node["icon"], 16)),
                    "weight": "bold",
                    "color": node["color"],
                },
            )
        for edge in graph_info["edges"]:
            G.add_edge(edge[0], edge[1])

        nt = Network(
            height="350px", width="100%", bgcolor="#ffffff", font_color="black", notebook=True, cdn_resources="remote"
        )
        nt.from_nx(G)
        nt.force_atlas_2based(gravity=-50, spring_length=100, damping=0.4)

        tmp_html = f"topo_{uuid.uuid4().hex}.html"
        nt.save_graph(tmp_html)
        with open(tmp_html, "r", encoding="utf-8") as f:
            html_content = f.read()
        try:
            os.remove(tmp_html)
            logger.debug("Removed temporary topology HTML file: %s", tmp_html)
        except Exception as e:
            logger.error("Error removing temporary topology HTML file %s: %s", tmp_html, e)

        iframe_html = (
            f'<iframe srcdoc="{html.escape(html_content)}" '
            'style="width:100%; height:350px; border:1px solid #ddd;"></iframe>'
        )

        if matplotlib_ok:
            plt.figure(figsize=(6, 4))
            pos = nx.spring_layout(G)
            nx.draw(G, pos, with_labels=True, node_color="lightblue", node_size=1200, font_size=8, edge_color="gray")
            pdf_buffer = io.BytesIO()
            plt.savefig(pdf_buffer, format="png", dpi=100)
            pdf_buffer.seek(0)
            self.last_topo_buffer = pdf_buffer
            plt.close()
        else:
            self.last_topo_buffer = None

        return pn.Column(
            pn.pane.HTML(iframe_html, height=360, sizing_mode="stretch_width"),
            pn.pane.Markdown("미니 *Interactive Network Map*", styles={"font-size": "10px", "color": "gray"}),
            sizing_mode="stretch_width",
        )


    def build_config_table_panel(self, config_info):
        """Render configuration results as a simple table."""
        import pandas as pd

        items = [config_info] if isinstance(config_info, dict) else (config_info or [])
        rows = []
        for item in items:
            if not isinstance(item, dict):
                continue
            attrs = item.get('attributes', {}) if isinstance(item.get('attributes', {}), dict) else {}
            rows.append(
                {
                    'name': item.get('name', ''),
                    'type': item.get('asset_type', item.get('type', '')),
                    'ip': attrs.get('ip', ''),
                    'os': attrs.get('os', ''),
                    'details': attrs if attrs else '',
                }
            )
        df = pd.DataFrame(rows)
        table = pn.widgets.Tabulator(df, show_index=False, sizing_mode='stretch_width', theme='simple', height=260)
        return pn.Column(
            pn.pane.Markdown('**설정 요약 테이블**', styles={'font-size': '12px', 'font-weight': 'bold'}),
            table,
            sizing_mode='stretch_width',
        )

    def _render_manual_links(self, manuals, search_text: str = ""):
        def _viewer_link(m):
            src = str(m.get("link") or "").replace("\\", "/").lstrip("/")
            if not src:
                return ""
            page = m.get("page") or 1
            return f"/assets/pdf_viewer.html?file={quote(src)}&page={page}&query={search_text}"

        items = []
        for m in manuals:
            url = _viewer_link(m)
            title = html.escape(m.get("title") or "제목 없음")
            if url:
                items.append(f'<div>- <a href="{url}" target="_blank" rel="noopener">{title}</a></div>')
            else:
                items.append(f"<div>- {title}</div>")
        links_md = "".join(items)
        return pn.pane.HTML(
            f'<div><div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">아래 매뉴얼을 확인하세요:<br/>{links_md}</div>'
            '<div style="clear:both"></div></div>',
            sizing_mode="stretch_width",
        )


    def render_from_metadata(self, result: dict):
        """Rebuild the assistant composite view from stored metadata."""
        try:
            answer_text_raw = (result or {}).get("answer_text", "") or ""
            answer_text = self._strip_mock_prefix(answer_text_raw)
            metric_info = (result or {}).get("metric")
            graph_info = (result or {}).get("graph")
            manuals = (result or {}).get("manuals") or []
            work_history_info = (result or {}).get("work_history")

            composite_views = [
                pn.pane.HTML(
                    f'<div><div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">'
                    f"{html.escape(answer_text).replace('\n', '<br/>')}</div><div style='clear:both'></div></div>",
                    sizing_mode="stretch_width",
                )
            ]

            if manuals:
                composite_views.append(self._render_manual_links(manuals))

            common_styles = {
                "float": "left",
                "clear": "both",
                "background-color": "#f0f0f0",
                "border-radius": "0 15px 15px 15px",
                "padding": "10px",
                "margin": "5px 10px",
            }

            if metric_info:
                try:
                    chart_panel = self.build_line_chart_panel(metric_info)
                    composite_views.append(pn.Column(chart_panel, css_classes=["bot-msg-box"], styles=common_styles))
                except Exception as e:
                    composite_views.append(
                        pn.pane.HTML(
                            f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">차트 렌더 오류: {html.escape(str(e))}</div>',
                            sizing_mode="stretch_width",
                        )
                    )

            if graph_info:
                try:
                    topo_panel = self.build_topology_panel(graph_info)
                    composite_views.append(pn.Column(topo_panel, css_classes=["bot-msg-box"], styles=common_styles))
                except Exception as e:
                    composite_views.append(
                        pn.pane.HTML(
                            f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">토폴로지 렌더 오류: {html.escape(str(e))}</div>',
                            sizing_mode="stretch_width",
                        )
                    )

            if work_history_info:
                try:
                    table_panel = self.build_table_panel()
                    composite_views.append(pn.Column(table_panel, css_classes=["bot-msg-box"], styles=common_styles))
                except Exception as e:
                    composite_views.append(
                        pn.pane.HTML(
                            f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">작업 이력 렌더 오류: {html.escape(str(e))}</div>',
                            sizing_mode="stretch_width",
                        )
                    )

            return pn.Column(*composite_views, sizing_mode="stretch_width")
        except Exception as e:
            logger.exception("Failed to render assistant view from metadata: %s", e)
            return pn.pane.HTML(
                f'<div><div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">렌더링 중 오류: {html.escape(str(e))}</div>'
                "<div style='clear:both'></div></div>",
                sizing_mode="stretch_width",
            )

    
    def answer(self, contents: str):
        logger.info("User query received: %s", contents)
        self._log("user", "text", contents)
        result = self.orchestrator.route_and_answer(contents)
        logger.info("Orchestrator returned keys: %s", list(result.keys()))

        answer_text = self._strip_mock_prefix(result.get("answer_text", ""))
        metric_info = result.get("metric")
        graph_info = result.get("graph")
        config_info = result.get("config")
        manuals = result.get("manuals") or []
        modes = result.get("modes") or []
        work_history_info = result.get("work_history")
        search_text = quote(contents)

        q = contents.lower()
        composite_views = [
            pn.pane.HTML(
                f'<div><div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">' +
                f"{html.escape(answer_text).replace('\n', '<br/>')}</div><div style='clear:both'></div></div>",
                sizing_mode="stretch_width",
            )
        ]

        common_styles = {
            "float": "left",
            "clear": "both",
            "background-color": "#f0f0f0",
            "border-radius": "0 15px 15px 15px",
            "padding": "10px",
            "margin": "5px 10px",
        }

        if metric_info:
            try:
                chart_panel = self.build_line_chart_panel(metric_info)
                composite_views.append(pn.Column(chart_panel, css_classes=["bot-msg-box"], styles=common_styles))
            except Exception as e:
                composite_views.append(
                    pn.pane.HTML(
                        f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">차트 생성 오류: {html.escape(str(e))}</div>',
                        sizing_mode="stretch_width",
                    )
                )

        if config_info:
            try:
                table_panel = self.build_config_table_panel(config_info or [])
                composite_views.append(pn.Column(table_panel, css_classes=["bot-msg-box"], styles=common_styles))
            except Exception as e:
                composite_views.append(
                    pn.pane.HTML(
                        f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">설정 테이블 생성 오류: {html.escape(str(e))}</div>',
                        sizing_mode="stretch_width",
                    )
                )

        if graph_info:
            try:
                topo_panel = self.build_topology_panel(graph_info)
                composite_views.append(pn.Column(topo_panel, css_classes=["bot-msg-box"], styles=common_styles))
            except Exception as e:
                composite_views.append(
                    pn.pane.HTML(
                        f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">토폴로지 생성 오류: {html.escape(str(e))}</div>',
                        sizing_mode="stretch_width",
                    )
                )

        if work_history_info:
            try:
                table_panel = self.build_table_panel()
                composite_views.append(pn.Column(table_panel, css_classes=["bot-msg-box"], styles=common_styles))
            except Exception as e:
                composite_views.append(
                    pn.pane.HTML(
                        f'<div class="bot-msg-box" style="{BOT_BUBBLE_STYLE}">작업 이력 테이블 오류: {html.escape(str(e))}</div>',
                        sizing_mode="stretch_width",
                    )
                )

        manual_keywords = ["manual", "매뉴얼", "문서", "가이드", "설명서"]
        if manuals and ("manual" in modes or any(k in q for k in manual_keywords)):
            composite_views.append(self._render_manual_links(manuals, search_text))

        self._log("assistant", "composite", result)
        logger.info("Assistant response generated.")
        return pn.Column(*composite_views, sizing_mode="stretch_width")
