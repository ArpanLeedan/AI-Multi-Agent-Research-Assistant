from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak
)
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

import os
from datetime import datetime


# ---------------------------------------------------
# Footer & Page Number
# ---------------------------------------------------
def add_page_number(canvas, doc):
    canvas.saveState()

    width, height = doc.pagesize

    canvas.setFont("Helvetica", 9)

    canvas.setFillColor(HexColor("#666666"))

    canvas.drawString(
        inch,
        0.5 * inch,
        "AI Multi-Agent Research Assistant"
    )

    canvas.drawRightString(
        width - inch,
        0.5 * inch,
        f"Page {doc.page}"
    )

    canvas.restoreState()


# ---------------------------------------------------
# PDF Export
# ---------------------------------------------------
def export_pdf(topic: str, report: str) -> str:

    os.makedirs("exports", exist_ok=True)

    safe_topic = "".join(
        c if c.isalnum() or c in (" ", "_", "-") else ""
        for c in topic
    ).strip()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"{safe_topic}_{timestamp}.pdf"

    pdf_path = os.path.join("exports", filename)

    doc = SimpleDocTemplate(
        pdf_path,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.8 * inch,
    )

    styles = getSampleStyleSheet()

    # ---------------------------------------------------
    # Custom Styles
    # ---------------------------------------------------

    title_style = styles["Title"]
    title_style.alignment = TA_CENTER
    title_style.textColor = HexColor("#1E3A8A")
    title_style.spaceAfter = 25

    subtitle_style = styles["Heading2"]
    subtitle_style.alignment = TA_CENTER
    subtitle_style.textColor = HexColor("#2563EB")

    center_style = styles["BodyText"]
    center_style.alignment = TA_CENTER
    center_style.leading = 20

    heading_style = styles["Heading1"]
    heading_style.textColor = HexColor("#1E3A8A")

    body_style = styles["BodyText"]
    body_style.leading = 18

    story = []

    # =====================================================
    # COVER PAGE
    # =====================================================

    story.append(Spacer(1, 1.2 * inch))

    story.append(
        Paragraph(
            "AI Multi-Agent Research Assistant",
            title_style,
        )
    )

    story.append(Spacer(1, 0.3 * inch))

    story.append(
        Paragraph(
            "Professional Research Report",
            subtitle_style,
        )
    )

    story.append(Spacer(1, 0.9 * inch))

    story.append(
        Paragraph(
            "<b>Research Topic</b>",
            subtitle_style,
        )
    )

    story.append(Spacer(1, 0.15 * inch))

    story.append(
        Paragraph(
            topic,
            center_style,
        )
    )

    story.append(Spacer(1, 0.7 * inch))

    story.append(
        Paragraph(
            "<b>Date Generated</b>",
            subtitle_style,
        )
    )

    story.append(
        Paragraph(
            datetime.now().strftime("%d %B %Y"),
            center_style,
        )
    )

    story.append(Spacer(1, 0.7 * inch))

    story.append(
        Paragraph(
            "<b>Powered By</b>",
            subtitle_style,
        )
    )

    story.append(
        Paragraph(
            """
            LangGraph<br/>
            Ollama (Qwen3)<br/>
            DuckDuckGo Search<br/>
            ReportLab
            """,
            center_style,
        )
    )

    story.append(Spacer(1, 1.5 * inch))

    story.append(
        Paragraph(
            "<i>This report was automatically generated using an AI Multi-Agent Workflow.</i>",
            center_style,
        )
    )

    # ----------------------------------------------------
    # New Page
    # ----------------------------------------------------

    story.append(PageBreak())

    # =====================================================
    # REPORT PAGE
    # =====================================================

    story.append(
        Paragraph(
            "Research Report",
            heading_style,
        )
    )

    story.append(Spacer(1, 0.2 * inch))

    story.append(
        Paragraph(
            f"<b>Topic:</b> {topic}",
            styles["Heading2"],
        )
    )

    story.append(Spacer(1, 0.3 * inch))

    report = report.replace("\n", "<br/>")

    story.append(
        Paragraph(
            report,
            body_style,
        )
    )

    # ----------------------------------------------------
    # Build PDF
    # ----------------------------------------------------

    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number
    )

    return pdf_path
