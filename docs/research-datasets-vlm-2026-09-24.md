# Research: дополнительные датасеты и VLM-разметчики (2026-09-24)

Контекст: оборудование_v1 (yolov8s@640) даёт P=0.67/R=0.61; главные проблемы — мелкие объекты,
путаница truck/dump_truck, отсутствие башенных кранов в train. Идёт переобучение @1280.

## Кандидаты-датасеты (не использованы в equipment_external_v2)

| Датасет | Объём | Классы | Лицензия | Источник |
|---|---|---|---|---|
| MOCS (полная версия) | 41 668 изобр., 13 классов | worker, tower crane, vehicle crane, roller, bulldozer, excavator, ... | CC BY 4.0 (зеркало Roboflow) | anlab340.com / universe.roboflow.com/mocs/mocs-bowib |
| LouisChen15/ConstructionSite | 10 013 изобр. (7009 train) | стройплощадка, разметка прилагается | проверять | huggingface.co/datasets/LouisChen15/ConstructionSite |
| CSOD-24 | 100 видео × 10 c | dump truck, worker (+helmet), ... | проверять | researchgate 401585802 |
| SODA | large-scale site OD | site objects | — | упоминается в arXiv 2609.24075 |
| ACID | — | excavator, compactor, dozer, dump truck, mixer, truck, loader, crane | проверять | acidb.net (уже в плане) |
| OpenConstruction-каталог | агрегатор | — | — | github.com/ruoxinx/OpenConstruction-Datasets |

Важно: `context/external/mocs_v1` и `mocs_val_v1` уже подготовлены скриптом prepare_mocs.py,
но НЕ входят в equipment_external_v2 (sources.json содержит только Kaggle + GitHub).
MOCS — приоритет №1 на слияние: у него есть tower crane и аэросъёмка/реальные стройки.

## VLM-разметчики (teacher-модели)

1. **Autodistill** (github.com/autodistill/autodistill) — фреймворк: base model (Grounding DINO,
   Grounded-SAM, YOLO-World, PaliGemma) авторазмечает папку картинок → сразу train YOLOv8.
   Есть модуль autodistill-yolo-world. Простейший путь «без кода разметки».
2. **Grounding DINO / Grounding DINO 1.5 + Grounded SAM** (IDEA-Research) — zero-shot детекция
   по текстовым промптам, выдаёт bbox; Grounded-Segment-Anything добавляет маски.
3. **YOLO-World** (Tencent) — уже в проекте как baseline; промптуется произвольными классами,
   работает near-realtime. Годится для авто-разметки в связке с Autodistill.
4. **Qwen2.5-VL-7B** (open weights, Apache) — визуальный groundинг: выдаёт bbox координаты
   в JSON по текстовой инструкции (qwenlm.github.io/blog/qwen2.5-vl, arXiv 2502.13923).
   Хорош как reviewer/судья для сложных случаев и для проверки спорных боксов (по плану:
   «VLM как teacher/reviewer»). 7B влезает на текущую GPU для офлайн-разметки.

## Рекомендация

1. Слить MOCS (CC BY 4.0) в equipment_external_v3 → закрывает tower crane + domain аэросъёмки.
2. Оценить ConstructionSite (HF) после аудита лицензии.
3. Контур авто-разметки: YOLO-World/Grounding DINO через Autodistill для массовой разметки,
   Qwen2.5-VL — reviewer для спорных кадров, человек — финальная проверка (по плану quality gate).

Sources:
- https://docs.autodistill.com/quickstart/
- https://github.com/autodistill/autodistill
- https://github.com/autodistill/autodistill-yolo-world
- https://github.com/idea-research/grounded-segment-anything
- https://qwenlm.github.io/blog/qwen2.5-vl/
- https://arxiv.org/pdf/2502.13923v1
- https://learnopencv.com/object-detection-with-vlms-ft-qwen2-5-vl/
- https://universe.roboflow.com/mocs/mocs-bowib
- http://www.anlab340.com/Archives/IndexArctype/index/t_id/17.html
- https://huggingface.co/datasets/LouisChen15/ConstructionSite
- https://github.com/ruoxinx/OpenConstruction-Datasets
- https://www.mdpi.com/2076-3417/15/16/9000
