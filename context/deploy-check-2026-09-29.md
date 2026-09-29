# Deploy check — 2026-09-29 11:50 / updated 11:55

Публичный URL: https://buildwatch.baski.pro/

## Обновление 2026-09-29 ~13:35

- GitHub `main`: `32cd652` — view-morph (`PageTransition` + View Transitions API)
- Сервер: `next build` → BUILD_ID `yOSRaWcrJ3m4iBD_TBOrQ`, frontend recreated
- Live: CSS `bw-page` / `view-morph`, `document.startViewTransition` доступен

## Обновление 2026-09-29 ~12:50

- Локальный GitHub `BuildWatch` main: `a94fbd0` (гайд хронологии, без panTo при клике маркера)
- Публичный стенд: `frontend` пересобран на сервере, файлы синхронизированы через scp (`ObjectMap.tsx`, `PageGuide.tsx`, `objects/[id]/page.tsx`)
- Проверка: `grep panTo` в `ObjectMap.tsx` на сервере → 0; `curl https://buildwatch.baski.pro/` → 200
SSH: baski.pro (kon@192.168.0.6), каталог `/home/kon/projects/buildwatch-public`

## Вердикт: актуально (после деплоя)

| Где | Commit / маркер | Motion (`ease-spring`) |
|---|---|---|
| Локальный `main` | `d80dfb6` | есть |
| GitHub `origin/main` | `d80dfb6` (push 11:52) | есть |
| Сервер frontend src | sync tar 11:52 | 54 совпадения |
| Live build | `ylisKnuH8arj-qNj49sNU` | CSS `b2db90fe…` / `17e98941…` содержат spring/motion/seg-pop |

Действия: `git push origin main`; rsync frontend tar → extract; `next build` в node:22-alpine; `docker compose … force-recreate frontend`.
Local UI http://127.0.0.1:8701 → 200; public https → CSS markers OK.
