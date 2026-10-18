import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import inch

def generate_paper_pdf(paper, questions, output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0B1D13'),
        alignment=1 # Center
    )

    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#D4AF37'),
        alignment=1
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#333333'),
        alignment=1
    )

    q_title_style = ParagraphStyle(
        'QuestionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#0B1D13')
    )

    opt_style = ParagraphStyle(
        'OptionStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1A211D')
    )

    exp_style = ParagraphStyle(
        'ExpStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#2E5A36')
    )

    story = []

    # Header
    story.append(Paragraph("DEFENCE PATH – EXAMINATION PORTAL", title_style))
    story.append(Paragraph("Your Dream. Your Discipline. Your Uniform. | Developer: Er. Prashant Mishra", sub_style))
    story.append(Spacer(1, 6))

    # Paper Info Banner
    info_text = f"<b>Paper:</b> {paper['title']}<br/><b>Exam:</b> {paper['exam_code']} | <b>Type:</b> {paper['paper_type']} | <b>Time:</b> {paper['duration_minutes']} Mins | <b>Max Marks:</b> {paper['max_marks']} | <b>Negative Marking:</b> {paper['negative_marks']}"
    story.append(Paragraph(info_text, meta_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#D4AF37'), spaceAfter=12))

    # Disclaimer
    disclaimer_text = "<i>Note: Defence Path is an independent educational portal. Authentic past questions compiled for candidate educational practice.</i>"
    story.append(Paragraph(disclaimer_text, ParagraphStyle('Disc', parent=styles['Normal'], fontSize=7.5, textColor=colors.gray, alignment=1)))
    story.append(Spacer(1, 10))

    # Questions
    for idx, q in enumerate(questions, 1):
        q_heading = f"<b>Q{idx}. [{q['subject']} - {q['topic']}]</b> {q['question_text_en']}"
        story.append(Paragraph(q_heading, q_title_style))
        story.append(Spacer(1, 4))

        options_data = [
            [Paragraph(f"<b>(A)</b> {q['option_a_en']}", opt_style), Paragraph(f"<b>(B)</b> {q['option_b_en']}", opt_style)],
            [Paragraph(f"<b>(C)</b> {q['option_c_en']}", opt_style), Paragraph(f"<b>(D)</b> {q['option_d_en']}", opt_style)]
        ]
        t = Table(options_data, colWidths=[260, 260])
        t.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(t)
        story.append(Spacer(1, 4))

        ans_box = f"<b>Correct Answer:</b> Option {q['correct_option']}<br/><b>Step-by-Step Explanation:</b> {q['explanation_en'].replace('\n', '<br/>')}"
        story.append(Paragraph(ans_box, exp_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E0E0E0'), spaceAfter=8))

    doc.build(story)
    return output_path
