"""Refresh docs/BuildWatch-ЛЦТ2026-final.pptx in place for the ЛЦТ submission."""

import copy
import sys
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "docs" / "BuildWatch-ЛЦТ2026-final.pptx"
BASE = ROOT / "docs" / "backups" / "BuildWatch-ЛЦТ2026-final.20260929-072347.pptx"
SHOTS = ROOT / "context" / "ui_shots"
DIAGRAMS = ROOT / "docs" / "diagrams"

DARK = RGBColor(0x1F, 0x1A, 0x2A)
PURPLE = RGBColor(0x4E, 0x1A, 0x7A)
ACCENT = RGBColor(0xFF, 0x00, 0x53)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Arial"


def shape(slide, name, text_start=None):
    for sh in slide.shapes:
        if sh.name != name:
            continue
        if text_start is None or (sh.has_text_frame and sh.text_frame.text.startswith(text_start)):
            return sh
    raise KeyError(f"{name!r} / {text_start!r}")


def remove(sh):
    sh._element.getparent().remove(sh._element)


def set_bullet(paragraph, char="•", color=ACCENT):
    pPr = paragraph._p.get_or_add_pPr()
    pPr.set("marL", str(Inches(0.18)))
    pPr.set("indent", str(-Inches(0.18)))
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum", "a:buClr"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    buClr = etree.SubElement(pPr, qn("a:buClr"))
    etree.SubElement(buClr, qn("a:srgbClr")).set("val", str(color))
    etree.SubElement(pPr, qn("a:buChar")).set("char", char)


def add_run(paragraph, text, size, color=DARK, bold=False):
    run = paragraph.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return run


def fill(tf, items, size=12, color=DARK, lead_color=PURPLE, bullets=True, space=6, heading=None,
         heading_size=16, heading_color=PURPLE, subheading=None):
    """items: list of str or (bold_lead, rest)."""
    tf.clear()
    tf.word_wrap = True
    first = tf.paragraphs[0]
    paragraphs = []
    if heading:
        add_run(first, heading, heading_size, heading_color, bold=True)
        first.space_after = Pt(2 if subheading else 8)
        first = None
        if subheading:
            sub = tf.add_paragraph()
            add_run(sub, subheading, 11, ACCENT, bold=True)
            sub.space_after = Pt(10)
    for item in items:
        p = first if first is not None else tf.add_paragraph()
        first = None
        if isinstance(item, tuple):
            add_run(p, item[0], size, lead_color, bold=True)
            add_run(p, item[1], size, color)
        else:
            add_run(p, item, size, color)
        p.space_after = Pt(space)
        if bullets:
            set_bullet(p)
        paragraphs.append(p)
    return paragraphs


def textbox(slide, x, y, w, h):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", Inches(0.05))
    return tb


def replace_picture(slide, old, image_path):
    left, top, width, height = old.left, old.top, old.width, old.height
    remove(old)
    pic = slide.shapes.add_picture(str(image_path), left, top, width=width)
    if pic.height > height:
        remove(pic)
        pic = slide.shapes.add_picture(str(image_path), left, top, height=height)
        pic.left = left + (width - pic.width) // 2
    else:
        pic.top = top + (height - pic.height) // 2
    return pic


def picture_fit(slide, path, x, y, max_w, max_h):
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), height=Inches(max_h))
    if pic.width > Inches(max_w):
        remove(pic)
        pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(max_w))
    line = pic.line
    line.color.rgb = RGBColor(0xDC, 0xD2, 0xEF)
    line.width = Pt(0.75)
    return pic


def set_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def set_text_keep_style(sh, text):
    runs = [r for p in sh.text_frame.paragraphs for r in p.runs]
    runs[0].text = text
    for r in runs[1:]:
        r.text = ""


def team_card(slide, name_role, lines):
    box = shape(slide, "Текст 8", name_role)
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    for i, (text, bold, color) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        add_run(p, text, 11 if i else 12.5, color, bold=bold)
        p.space_after = Pt(1)


def slide_team(s):
    team_card(s, "Разработчик", [
        ("Разработчик, капитан", True, DARK),
        ("Telegram: @KonstantBas", False, DARK),
        ("Тел.: +7 918 318-47-80", False, DARK),
    ])
    team_card(s, "Продуктовый менеджер", [
        ("Продуктовый менеджер", True, DARK),
        ("Telegram: @ddmanakov", False, DARK),
        ("Тел.: +7 960 000-15-17", False, DARK),
    ])


def slide_concept(s):
    label = shape(s, "Прямоугольник 14")
    set_text_keep_style(label, "КОНЦЕПЦИЯ И АРХИТЕКТУРА")
    label.text_frame.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xD6, 0xE4)
    fill(shape(s, "Текст 2").text_frame, [
        ("Портфель на карте. ", "Все площадки на одной карте: цвет маркера — проблемы, вопросы или норма."),
        ("План → снимок → сигнал. ", "Объект заводится с календарным планом, снимки распознаёт YOLO, "
                                     "техника сверяется с этапом на дату кадра."),
        ("Прогноз и динамика. ", "Оценка отставания по серии снимков, признаки простоя (R-08), "
                                 "зоны кадра: опасная зона и склад (R-09, R-10)."),
        ("Инспектор в контуре. ", "Стол разбора сигналов «верно / ошибка»; вердикты копятся "
                                  "в статистику качества распознавания."),
        ("ИИ-помощник. ", "Отвечает по данным объекта и предлагает перенос дат только с подтверждением."),
    ], size=11, space=5)
    pic = next(sh for sh in s.shapes if sh.shape_type == 13)
    replace_picture(s, pic, SHOTS / "arch_simple_crop.png")
    set_notes(s, "Концепция и архитектура. Правила: R-01…R-03 — техника и этап плана, "
                 "R-08 — вероятный простой по серии снимков, R-09 — техника в опасной зоне, "
                 "R-10 — кран в зоне склада на этапе монтажа.")


def slide_tech(s):
    fill(shape(s, "Текст 2").text_frame, [
        ("Клиент-сервер: ", "Next.js 15 — интерфейс, FastAPI — API, правила и прогноз, отдельный worker детекции."),
        ("Детектор: ", "YOLOv8m 1280 px с нарезкой SAHI; датасет из открытых наборов, размечен VLM и вручную."),
        ("ИИ-помощник: ", "GLM-5.3 Flash через OpenCode Zen."),
        ("Почему так: ", "общий Python-стек для CV и API, детекция работает и без облачного GPU."),
    ], size=10, space=3)
    pic = next(sh for sh in s.shapes if sh.shape_type == 13 and sh.width > Inches(10))
    replace_picture(s, pic, SHOTS / "s7_20_new.png")
    set_notes(s, "Обоснование технологий. YOLOv8m выбран как баланс точности и скорости на CPU/GPU; "
                 "SAHI нужен для мелкой техники на обзорных кадрах. Помощник — GLM-5.3 Flash.")


DEMOS = {
    "home": ("Пример работы. Главный экран",
             "Портфель на карте: очередь разбора, ИИ-помощник, сводка статусов и карточка объекта "
             "с планом и фактом. При первом заходе кнопка «?» подсвечивается и предлагает гайд."),
    "object": ("Пример работы. Карточка объекта",
               "От кадра до вывода: статус и прогноз по графику, этапы плана, снимок с рамками YOLO и зонами, "
               "сравнение нужной техники с увиденной."),
    "assistant": ("Пример работы. ИИ-помощник",
                  "GLM-5.3 Flash отвечает по данным объекта со ссылками на правила и снимки. "
                  "Изменения плана применяются только после подтверждения человеком."),
    "report": ("Пример работы. Отчёт по объекту",
               "Отчёт для совещания: ключевые цифры, прогноз, динамика по неделям и качество "
               "распознавания по вердиктам инспектора; печать в PDF."),
}


def duplicate_slide(prs, src, index):
    new = prs.slides.add_slide(src.slide_layout)
    for ph in list(new.placeholders):
        remove(ph)
    for el in src.shapes._spTree.iterchildren():
        if el.tag in (qn("p:sp"), qn("p:cxnSp")):
            new.shapes._spTree.append(copy.deepcopy(el))
    ids = prs.slides._sldIdLst
    moved = ids[-1]
    ids.remove(moved)
    ids.insert(index, moved)
    return new


def slide_demo(s, name):
    title, summary = DEMOS[name]
    set_text_keep_style(shape(s, "Прямоугольник 1"), title)
    box = shape(s, "Прямоугольник: скругленные углы 3")
    box.left, box.top, box.width, box.height = Inches(0.37), Inches(1.68), Inches(12.22), Inches(4.9)
    small_w, big_w = 4.4, 7.25
    picture_fit(s, SHOTS / f"ui_{name}.png", 0.55, 1.9, small_w, small_w * 9 / 16)
    picture_fit(s, SHOTS / f"ui_{name}_guide.png", 5.15, 1.9, big_w, big_w * 9 / 16)
    for x, y, w, text in ((0.55, 1.9 + small_w * 9 / 16 + 0.05, small_w, "Экран прототипа"),
                          (5.15, 1.9 + big_w * 9 / 16 + 0.05, big_w, "Тот же экран с включённым гайдом «?»")):
        lbl = textbox(s, x, y, w, 0.3)
        add_run(lbl.text_frame.paragraphs[0], text, 10, PURPLE, bold=True)
    tb = textbox(s, 0.55, 4.85, small_w, 2.0)
    tb.text_frame.word_wrap = True
    add_run(tb.text_frame.paragraphs[0], summary, 12, DARK)
    set_notes(s, f"{title}. Слева чистый скриншот рабочего прототипа (29.09.2026), справа тот же экран "
                 "с интерактивным гайдом: подписи закреплены у структурных блоков.")


def slide_scaling(s):
    remove(shape(s, "Прямоугольник: скругленные углы 3"))
    box = shape(s, "Прямоугольник: скругленные углы 2")
    box.left, box.top, box.width, box.height = Inches(0.37), Inches(1.75), Inches(12.22), Inches(4.45)
    s.shapes.add_picture(str(DIAGRAMS / "scaling-axes.png"), Inches(0.5), Inches(1.9), width=Inches(11.96))
    cap = textbox(s, 0.5, 6.35, 12.0, 0.6)
    add_run(cap.text_frame.paragraphs[0], "Горизонталь — больше данных и функций вокруг объекта. "
            "Вертикаль — точнее и быстрее распознавание. Вместе они ведут к цифровому стройконтролю.",
            11, WHITE)
    set_notes(s, "Две оси развития. Горизонталь: база знаний, планы, переписка, сметы, масштаб портфеля. "
                 "Вертикаль: дообучение по вердиктам, новые классы, геометрия площадки, реальное время, "
                 "оценка прогресса.")


def slide_cameras(s):
    replace_picture(s, shape(s, "Рисунок 6"), DIAGRAMS / "camera-placement.png")
    set_notes(s, "Рекомендации по установке камер: обзорная A и рабочая B перекрывают слепые зоны друг друга; "
                 "план площадки нарисован по типовому объекту.")


def main():
    prs = Presentation(str(BASE))
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DECK
    slides = list(prs.slides)
    slide_team(slides[2])
    slide_concept(slides[5])
    slide_tech(slides[6])
    slide_scaling(slides[10])
    slide_cameras(slides[11])
    set_notes(slides[9], "Схема обработки кадра: SAHI-нарезка, YOLO, сборка рамок, сопоставление с этапом плана "
                         "на дату снимка и отображение в карточке.")
    for sh in list(slides[8].shapes):
        if sh.name not in {"Прямоугольник 1", "Прямоугольник: скругленные углы 3", "Прямоугольник 12",
                           "Прямоугольник 13"}:
            remove(sh)
    demo = [slides[7], slides[8], duplicate_slide(prs, slides[7], 9), duplicate_slide(prs, slides[7], 10)]
    for s, name in zip(demo, ("home", "object", "assistant", "report")):
        slide_demo(s, name)
    slides = list(prs.slides)
    for i, s in enumerate(slides[5:], 6):
        for sh in s.shapes:
            if sh.name == "Прямоугольник 13" and sh.has_text_frame:
                set_text_keep_style(sh, f"{i:02d}")
    prs.save(str(out))
    print("saved", out)


if __name__ == "__main__":
    main()
