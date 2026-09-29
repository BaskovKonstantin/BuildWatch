"""Capture clean and guided UI screenshots of the local BuildWatch stand for the deck."""

from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8700"
OUT = Path(__file__).resolve().parent.parent / "context" / "ui_shots"
HIDE_DEV = "nextjs-portal, [data-nextjs-toast], [data-next-badge-root] { display: none !important; }"
SEEN = "try { localStorage.setItem('buildwatch_guide_seen', '1') } catch (e) {}"


def open_page(page, path, wait=2000):
    page.goto(BASE + path, wait_until="networkidle")
    page.add_style_tag(content=HIDE_DEV)
    page.wait_for_timeout(wait)


def shoot_pair(page, name):
    page.screenshot(path=OUT / f"ui_{name}.png")
    page.locator(".guide-trigger").click()
    page.wait_for_timeout(600)
    page.screenshot(path=OUT / f"ui_{name}_guide.png")
    page.locator(".guide-trigger").click()
    page.wait_for_timeout(300)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")

        first = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=2.5)
        open_page(first, "/", 2500)
        first.screenshot(path=OUT / "ui_home_first_visit.png")
        first.close()

        context = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=2.5)
        context.add_init_script(SEEN)
        page = context.new_page()

        open_page(page, "/", 2500)
        shoot_pair(page, "home")

        open_page(page, "/objects/2")
        shoot_pair(page, "object")

        page.get_by_role("button", name="Открыть ИИ-помощника").first.click()
        page.get_by_role("button", name="Почему объект требует проверки?").click()
        page.get_by_text("Источники", exact=False).first.wait_for(timeout=90000)
        page.wait_for_timeout(1000)
        shoot_pair(page, "assistant")

        open_page(page, "/objects/2/report", 1500)
        shoot_pair(page, "report")
        browser.close()


if __name__ == "__main__":
    main()
