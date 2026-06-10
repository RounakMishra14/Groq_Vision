from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
)


def add_dark_background(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.restoreState()


def create_pdf(results, output_path, pdf_title, pdf_theme):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    if pdf_theme == "Dark":
        font_regular = "Times-Roman"
        font_bold = "Times-Bold"
        text_color = colors.cyan
        heading_color = colors.cyan
        line_color = colors.cyan
    else:
        font_regular = "Helvetica"
        font_bold = "Helvetica-Bold"
        text_color = colors.black
        heading_color = colors.HexColor("#1F4E79")
        line_color = colors.HexColor("#D9EAF7")

    styles.add(
        ParagraphStyle(
            name="CustomTitle",
            parent=styles["Title"],
            fontName=font_bold,
            fontSize=20,
            leading=24,
            textColor=heading_color,
            alignment=1,
            spaceAfter=20,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CustomHeading",
            parent=styles["Heading2"],
            fontName=font_bold,
            fontSize=14,
            leading=18,
            textColor=heading_color,
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CustomBody",
            parent=styles["BodyText"],
            fontName=font_regular,
            fontSize=11,
            leading=15,
            textColor=text_color,
            spaceAfter=8,
        )
    )

    story = []

    story.append(Paragraph(pdf_title, styles["CustomTitle"]))
    story.append(Spacer(1, 0.15 * inch))

    story.append(
        Paragraph(
            f"Generated: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}",
            styles["CustomBody"],
        )
    )

    story.append(Spacer(1, 0.2 * inch))

    for item in results:
        story.append(
            Paragraph(
                f"Image {item['image_number']}: {item['file_name']}",
                styles["CustomHeading"],
            )
        )

        safe_text = (
            item["output"]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )

        story.append(Paragraph(safe_text, styles["CustomBody"]))

        story.append(
            HRFlowable(
                width="100%",
                thickness=0.6,
                color=line_color,
                spaceBefore=10,
                spaceAfter=14,
            )
        )

    if pdf_theme == "Dark":
        doc.build(
            story,
            onFirstPage=add_dark_background,
            onLaterPages=add_dark_background,
        )
    else:
        doc.build(story)