from pathlib import Path

from playwright.sync_api import sync_playwright

DIAGRAMS = Path(__file__).resolve().parents[1] / "docs" / "diagrams"
SIZES = {"scaling-axes": (1800, 610), "camera-placement": (1230, 1000)}


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge")
        for name, (w, h) in SIZES.items():
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
            page.goto((DIAGRAMS / f"{name}.svg").as_uri())
            page.screenshot(path=str(DIAGRAMS / f"{name}.png"))
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
