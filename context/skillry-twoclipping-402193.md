# Skillry — Opus 5.5 video prompt (twoclipping-402193)

Источник: https://skillry.dev/ai-videos/opus-5-5/twoclipping-402193
Изучено: 2026-09-29

## Что это
Страница Skillry с промптом автора @twoclipping для Claude Opus 5.5.
Формат: галерея AI-видео + копируемый оригинальный промпт (+ live remake по описанию сайта).

## Суть промпта
Один HTML-ролик 1440×1440: один UI-элемент бесшовно морфится по битам трека ~120 BPM (7 bars).
Цепочка состояний: button → loader → check → dynamic island → music player → progress scrub → volume slider → toggle → liquid tabs → chart → ⌘K palette → toast → снова button.
Рендер: Playwright + ffmpeg tmix (motion blur 60fps), пружины как closed-form функции времени seek(t).

## Зачем может быть полезно BuildWatch
Референс motion/UI-демо и структура «агентского» промпта для генерации loop-видео без After Effects.

## Внедрено в продукт (2026-09-29)
Не promo-loop, а живые микроанимации:
- токены `--ease-spring`, `--motion-*` в `frontend/app/globals.css`
- главная: карточки, chips, segmented, portfolio switcher
- карта: маркеры (morph radius), panel swap, issue cards stagger
- объект: filmstrip, detection boxes, plan-fact / verdict / stages
- без новых npm-зависимостей; `prefers-reduced-motion` учтён
