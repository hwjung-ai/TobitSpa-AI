import io
import os
import time
import uuid
import html

import panel as pn
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from pyvis.network import Network

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as PDFImage, Table, TableStyle

from orchestrator import AIOpsOrchestrator
from data_sources import GraphDataSource


def generate_pdf_report(topo_buffer, chart_buffer):
    """토폴로지, 차트, 표를 모두 포함한 PDF 생성"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph("<b>SPA System Report</b>", styles['Title']))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 20))

    story.append(Paragraph("<b>1. Executive Summary</b>", styles['Heading2']))
    story.append(Paragraph("Integrated analysis report including topology status, performance trends, and incident logs.", styles['Normal']))
    story.append(Spacer(1, 20))

    story.append(Paragraph("<b>2. Network Topology</b>", styles['Heading2']))
    story.append(Spacer(1, 10))
    if topo_buffer is not None:
        try:
            topo_buffer.seek(0)
            img = PDFImage(topo_buffer, width=400, height=250)
            story.append(img)
        except Exception:
            story.append(Paragraph("(Image Error)", styles['Normal']))
    else:
        story.append(Paragraph("(No topology generated)", styles['Italic']))
    story.append(Spacer(1, 20))

    story.append(Paragraph("<b>3. Performance Trends</b>", styles['Heading2']))
    story.append(Spacer(1, 10))
    if chart_buffer is not None:
        try:
            chart_buffer.seek(0)
            img = PDFImage(chart_buffer, width=400, height=200)
            story.append(img)
        except Exception:
            story.append(Paragraph("(Image Error)", styles['Normal']))
    else:
        story.append(Paragraph("(No trend chart generated)", styles['Italic']))
    story.append(Spacer(1, 20))

    story.append(Paragraph("<b>4. Incident Logs</b>", styles['Heading2']))
    story.append(Spacer(1, 10))
    data = [
        ['Time', 'Device', 'Event', 'Severity'],
        ['13:00', 'SW-Core-01', 'Link Flapping', 'CRITICAL'],
        ['13:01', 'WAS-01', 'High Latency', 'WARNING'],
    ]
    table = Table(data, colWidths=[80, 100, 120, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer


class AIOpsChatbot:
    """Panel UI에서 사용되는 챗봇 상태

    - 내부적으로 AIOpsOrchestrator를 사용
    - topology/chart/table Panel 생성 로직 포함
    """

    def __init__(self):
        self.orchestrator = AIOpsOrchestrator()
        self.session_id = self.orchestrator.session_id
        self.logs = {}  # 히스토리 저장(UI 복원용)
        self.last_topo_buffer = None
        self.last_chart_buffer = None

    def _log(self, role: str, kind: str, content):
        self.logs.setdefault(self.session_id, []).append({
            "role": role,
            "kind": kind,
            "content": content
        })

    def reset_memory(self):
        self.orchestrator.reset_session()
        self.session_id = self.orchestrator.session_id
        self.last_topo_buffer = None
        self.last_chart_buffer = None

    def build_table_panel(self):
        df = pd.DataFrame({
            'Time': ['13:00', '13:01', '13:05'],
            'Device': ['SW-Core-01', 'WAS-01', 'DB-Master'],
            'Status': ['🚨 Critical', '⚠️ Warning', '✅ Normal'],
            'Metric': ['Link Down', 'Latency 2s', 'CPU 40%']
        })
        table_widget = pn.widgets.Tabulator(
            df, show_index=False, sizing_mode='stretch_width', theme='site', height=150
        )
        return pn.Column(
            pn.pane.Markdown("**📅 Incident Status Table**", styles={'font-size': '12px', 'font-weight': 'bold'}),
            table_widget, sizing_mode='stretch_width'
        )

    def build_line_chart_panel(self, metric_info=None):
        if metric_info:
            times, values = metric_info["times"], metric_info["values"]
            title = f"{metric_info['asset']} - {metric_info['metric']} ({metric_info['period']})"
        else:
            times, values = ['09:00', '10:00', '11:00', '12:00', '13:00'], [20, 35, 45, 30, 95]
            title = 'CPU Trend Analysis'

        fig, ax = plt.subplots(figsize=(5, 3))
        ax.plot(times, values, 'o-')
        ax.set_title(title, fontsize=10)
        ax.set_ylabel('Value')
        ax.grid(True, linestyle='--', alpha=0.5)

        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', dpi=100, bbox_inches='tight')
        img_buffer.seek(0)
        self.last_chart_buffer = img_buffer
        plt.close(fig)

        return pn.Column(
            pn.pane.PNG(img_buffer, width=400),
            pn.pane.Markdown("📈 **Timeseries Trend**", styles={'font-size': '11px', 'color': 'gray'}),
            sizing_mode='stretch_width'
        )

    def build_topology_panel(self, graph_info=None):
        if not graph_info:
            graph_info = GraphDataSource().get_topology_for_asset("default")

        G = nx.DiGraph()
        for node in graph_info["nodes"]:
            G.add_node(node["id"], label=node["label"], title=node["label"], shape="icon",
                       icon={"face": "Font Awesome 5 Free", "code": chr(int(node["icon"], 16)),
                             "weight": "bold", "color": node["color"]})
        for edge in graph_info["edges"]:
            G.add_edge(edge[0], edge[1])

        nt = Network(height="350px", width="100%", bgcolor="#ffffff", font_color="black", notebook=True, cdn_resources='remote')
        nt.from_nx(G)
        nt.force_atlas_2based(gravity=-50, spring_length=100, damping=0.4)

        tmp_html = f"topo_{uuid.uuid4().hex}.html"
        nt.save_graph(tmp_html)
        with open(tmp_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
        try:
            os.remove(tmp_html)
        except Exception:
            pass

        iframe_html = f'<iframe srcdoc="{html.escape(html_content)}" style="width:100%; height:350px; border:1px solid #ddd;"></iframe>'

        plt.figure(figsize=(6, 4))
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color='lightblue', node_size=1200, font_size=8, edge_color='gray')
        pdf_buffer = io.BytesIO()
        plt.savefig(pdf_buffer, format='png', dpi=100)
        pdf_buffer.seek(0)
        self.last_topo_buffer = pdf_buffer
        plt.close()

        return pn.Column(
            pn.pane.HTML(iframe_html, height=360, sizing_mode='stretch_width'),
            pn.pane.Markdown("🌐 *Interactive Network Map*", styles={'font-size': '10px', 'color': 'gray'}),
            sizing_mode='stretch_width'
        )

    def answer(self, contents: str):
        self._log("user", "text", contents)
        result = self.orchestrator.route_and_answer(contents)

        answer_text = result["answer_text"]
        metric_info = result["metric"]
        graph_info = result["graph"]
        manuals = result["manuals"]

        q = contents.lower()
        composite_views = []

        composite_views.append(
            pn.pane.Markdown(f'<div class="bot-msg-box">{html.escape(answer_text)}</div>', sizing_mode='stretch_width')
        )

        if manuals:
            links_md = "\n".join(f"- [{m['title']}]({m['link']})" for m in manuals)
            composite_views.append(
                pn.pane.Markdown(f'<div class="bot-msg-box">📚 관련 매뉴얼<br/>{links_md}</div>', sizing_mode='stretch_width')
            )

        common_styles = {
            'float': 'left', 'clear': 'both', 'background-color': '#f0f0f0',
            'border-radius': '0 15px 15px 15px', 'padding': '10px', 'margin': '5px 10px'
        }

        if metric_info or any(k in q for k in ["차트", "추세", "trend", "시계열"]):
            chart_panel = self.build_line_chart_panel(metric_info)
            composite_views.append(
                pn.Column(chart_panel, css_classes=['bot-msg-box'], styles=common_styles)
            )

        if graph_info or any(k in q for k in ["연결", "구성도", "토폴로지", "topology"]):
            topo_panel = self.build_topology_panel(graph_info)
            composite_views.append(
                pn.Column(topo_panel, css_classes=['bot-msg-box'], styles=common_styles)
            )

        if any(k in q for k in ["표", "테이블", "incident", "이벤트"]):
            table_panel = self.build_table_panel()
            composite_views.append(
                pn.Column(table_panel, css_classes=['bot-msg-box'], styles=common_styles)
            )

        self._log("assistant", "composite", result)
        return pn.Column(*composite_views, sizing_mode='stretch_width')