import io
import os
import time
import logging


logger = logging.getLogger(__name__)

def generate_pdf_report(topo_buffer, chart_buffer):
    """토폴로지, 차트, 표를 모두 포함한 PDF 생성"""
    # Lazy import heavy reportlab dependencies to avoid C-extensions at import time
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as PDFImage, Table, TableStyle

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
            logger.info("Topology image added to PDF report.")
        except Exception as e:
            logger.error(f"Error adding topology image to PDF: {e}")
            story.append(Paragraph("(Image Error)", styles['Normal']))
    else:
        story.append(Paragraph("(No topology generated)", styles['Italic']))
        logger.info("No topology image available for PDF report.")
    story.append(Spacer(1, 20))

    story.append(Paragraph("<b>3. Performance Trends</b>", styles['Heading2']))
    story.append(Spacer(1, 10))
    if chart_buffer is not None:
        try:
            chart_buffer.seek(0)
            img = PDFImage(chart_buffer, width=400, height=200)
            story.append(img)
            logger.info("Chart image added to PDF report.")
        except Exception as e:
            logger.error(f"Error adding chart image to PDF: {e}")
            story.append(Paragraph("(Image Error)", styles['Normal']))
    else:
        story.append(Paragraph("(No trend chart generated)", styles['Italic']))
        logger.info("No chart image available for PDF report.")
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
