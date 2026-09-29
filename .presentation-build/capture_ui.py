"""Capture clean UI screenshots of the local BuildWatch stand for the deck."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8700"
OUT = Path(__file__).resolve().parent.parent / "context" / "ui_shots"
HIDE_DEV = "nextjs-portal, [data-nextjs-toast], [data-next-badge-root] { display: none !important; }"


def boxes(page, selectors):
    result = {}
    for key, selector in selectors.items():
        loc = page.locator(selector).first
        if loc.count():
            result[key] = loc.bounding_box()
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    layout = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=2)

        page.goto(BASE + "/", wait_until="networkidle")
        page.add_style_tag(content=HIDE_DEV)
        page.wait_for_timeout(2500)
        page.screenshot(path=OUT / "ui_home.png")
        layout["home"] = boxes(page, {
            "review": "text=Начать разбор",
            "ask": "text=Спросить BuildWatch",
            "filters": "text=Все типы",
            "portfolio": "text=Состояние портфеля",
            "map": ".leaflet-container",
            "card": "text=План / факт",
            "view": "role=button[name='Карта']",
        })

        page.goto(BASE + "/objects/2", wait_until="networkidle")
        page.add_style_tag(content=HIDE_DEV)
        page.wait_for_timeout(2000)
        page.screenshot(path=OUT / "ui_object.png")
        layout["object"] = boxes(page, {
            "status": "text=Статус по графику",
            "forecast": "text=Прогноз · умеренный сценарий",
            "stages": "text=Обустройство строительной пл",
            "snapshot": "img[alt*='нимок'], main img",
            "planfact": "text=План и факт на снимке",
            "review": "text=Проверить распознавание",
            "zones": "role=button[name='Зоны']",
            "actions": "text=Отчёт",
        })

        page.get_by_role("button", name="Открыть ИИ-помощника").first.click()
        page.get_by_role("button", name="Почему объект требует проверки?").click()
        page.get_by_text("Источники", exact=False).first.wait_for(timeout=90000)
        page.wait_for_timeout(1000)
        page.screenshot(path=OUT / "ui_assistant.png")
        layout["assistant"] = boxes(page, {
            "dialog": "role=dialog",
            "context": "text=Контекст: текущий объект",
            "answer": "text=Анализ данных",
            "sources": "text=Источники",
            "input": "role=textbox[name='Ваш вопрос или команда']",
            "disclaimer": "text=Выводы ИИ требуют проверки",
        })

        page.goto(BASE + "/objects/2/report", wait_until="networkidle")
        page.add_style_tag(content=HIDE_DEV)
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT / "ui_report.png")
        layout["report"] = boxes(page, {
            "kpi": "text=Прошло времени по плану",
            "forecast": "text=Прогноз по графику",
            "dynamics": "text=Динамика",
            "quality": "text=Качество распознавания",
            "print": "text=Печать / PDF",
        })
        browser.close()
    (OUT / "ui_layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(layout, ensure_ascii=False))


if __name__ == "__main__":
    main()
