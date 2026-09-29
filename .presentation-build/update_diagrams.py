from pathlib import Path

DIAGRAMS = Path(__file__).resolve().parent.parent / "docs" / "diagrams"

REPLACEMENTS = {
    "software-architecture-simple.svg": [
        ("Правила R-01 / 02 / 03 / 07", "Правила R-01…03 · R-08…10"),
        (">Проверка инспектором<", ">Прогноз · зоны кадра<"),
        ("Сигнал — повод проверить", "Инспектор: верно / ошибка"),
        (
            "SQLite: очередь задач, планы, детекции и сигналы  ·  Файлы снимков хранятся отдельно",
            "SQLite: задачи, планы, детекции, зоны, сигналы и вердикты  ·  Файлы снимков отдельно",
        ),
    ],
    "software-architecture.svg": [("R-01 / 02 / 03 / 07", "R-01…03 · R-08…10")],
}

for name, pairs in REPLACEMENTS.items():
    path = DIAGRAMS / name
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if old in text:
            text = text.replace(old, new)
            print(f"{name}: {old!r} -> {new!r}")
    path.write_text(text, encoding="utf-8")
