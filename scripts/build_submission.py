"""Build the LCT submission deck and PDF from the supplied template and docs."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = Path('/mnt/d/Downloads/ЛЦТ2026 Шаблон презентации.pptx')
DECK = ROOT / 'docs/BuildWatch-ЛЦТ2026.pptx'
MARKDOWN = ROOT / 'docs/submission.md'
PDF = ROOT / 'docs/submission.pdf'

from visual_deck import make_deck


def make_pdf():
    font_pairs = [
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
        (Path('C:/Windows/Fonts/arial.ttf'), Path('C:/Windows/Fonts/arialbd.ttf')),
        (Path('/mnt/c/Windows/Fonts/arial.ttf'), Path('/mnt/c/Windows/Fonts/arialbd.ttf')),
    ]
    font, bold = next(((regular, heavy) for regular, heavy in font_pairs if regular.exists() and heavy.exists()), (None, None))
    if font is None:
        raise FileNotFoundError('A Cyrillic DejaVu Sans or Arial font is required to build the PDF')
    pdfmetrics.registerFont(TTFont('DejaVu', str(font)))
    pdfmetrics.registerFont(TTFont('DejaVuBold', str(bold)))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CoverBW', fontName='DejaVuBold', fontSize=19, leading=26, textColor=colors.HexColor('#310F53'), spaceAfter=13))
    styles.add(ParagraphStyle(name='HeadingBW', fontName='DejaVuBold', fontSize=12, leading=18, textColor=colors.HexColor('#310F53'), spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name='BodyBW', fontName='DejaVu', fontSize=9, leading=14, spaceAfter=6))
    styles.add(ParagraphStyle(name='SmallBW', fontName='DejaVu', fontSize=8, leading=12, leftIndent=11, spaceAfter=3))
    story = []
    for raw in MARKDOWN.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('```') or line.startswith('|---'):
            if not line:
                story.append(Spacer(1, 2*mm))
            continue
        if line.startswith('# '):
            style = styles['CoverBW']; line = line[2:]
        elif line.startswith('## '):
            style = styles['HeadingBW']; line = line[3:]
        elif line.startswith('|'):
            style = styles['SmallBW']; line = line.strip('|').replace('|', '  ·  ')
        elif line.startswith(('- ', '1. ', '2. ', '3. ', '4. ', '5. ')):
            style = styles['SmallBW']
        else:
            style = styles['BodyBW']
        line = escape(line)
        line = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
        line = re.sub(r'`([^`]+)`', r'<font color="#520978">\1</font>', line)
        line = re.sub(r'\[([^]]+)\]\(([^)]+)\)', r'\1 (\2)', line)
        story.append(Paragraph(line, style))
    doc = SimpleDocTemplate(str(PDF), pagesize=(210*mm, 297*mm), leftMargin=20*mm, rightMargin=20*mm, topMargin=19*mm, bottomMargin=18*mm,
                            title='BuildWatch — документация ЛЦТ 2026')
    doc.build(story)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, default=DEFAULT_TEMPLATE,
                        help='Path to the supplied LCT2026 PPTX template')
    args = parser.parse_args()
    make_deck(args.template)
    make_pdf()
    print(DECK)
    print(PDF)
