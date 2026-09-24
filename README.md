# BuildWatch

Локальное приложение для контроля строительных объектов по снимкам.

## Запуск

```powershell
cd D:\Projects\BuildWatch
.\scripts\start-buildwatch.ps1
```

После запуска:

- UI: http://127.0.0.1:8700
- API: http://127.0.0.1:8600
- Health: http://127.0.0.1:8600/api/health

Логи находятся в `runtime-logs/` и не попадают в Git.

## Проверки

```powershell
python -m unittest discover -s tests -v
npm --prefix frontend run build
```

## Архитектура

- `backend/` — FastAPI, SQLite, правила R-01/R-02/R-03/R-07, загрузка изображений;
- `frontend/` — Next.js 15, адаптивная панель объектов и карточка объекта;
- `scripts/detect_single.py` — CPU-детектор YOLO-World в `.venv-cpu`;
- `scripts/detect_uisikdag_single.py` — дополнительный детектор UISikDag;
- `scripts/worker.py` — очередь `detection_jobs`, WSL/Windows path conversion, retry and result finalization;
- `scripts/evaluate_detectors.py` — оценка по ручной разметке из `context/validation/`;
- `context/` — локальные образцы и кэшированные результаты моделей.

Для обработки снимка API ставит job в SQLite, а worker запускает выбранную модель: `yolo_world`, `uisikdag` или `ensemble`. Результаты содержат имя фактической модели и проходят валидацию перед записью в базу. Состояние `failed` не считается отсутствием техники.

Для официальных COCO-архивов ACID/MOCS есть importer с явным mapping:

```bash
.venv/bin/python scripts/import_external_dataset.py \\
  --coco /path/to/annotations.json \\
  --images /path/to/images \\
  --output context/external/acid_v1 \\
  --mapping context/ontology/external_equipment_v1.json \\
  --source acid \\
  --license "указать лицензию источника"
```

Импортёр сохраняет `dataset.json`, источник и лицензию, переводит классы в
BuildWatch ontology и исключает `tower crane`, `pump truck`, `loader` и другие
классы, для которых mapping намеренно не делает небезопасного преобразования.

## MOCS train/validation/test

Официальные MOCS-архивы подключаются без смешивания split-ов. Скрипт
[`scripts/prepare_mocs.py`](scripts/prepare_mocs.py) переводит COCO-аннотации в
YOLO-формат BuildWatch, сохраняет пустые labels для кадров без целевых классов
и записывает статистику mapped/ignored классов.

Сейчас локально доступны `annotation_train.json`, `annotation_val.json`,
`image_info_test.json` и validation-изображения. Validation уже подготовлен в
`context/external/mocs_v1/`. Ссылка на train images из сообщения MOCS сейчас
возвращает HTTP 404, поэтому обучение на train до исправления ссылки не
запускается. Test split не используется для обучения или подбора порогов.

```bash
.venv/bin/python scripts/prepare_mocs.py \\
  --output context/external/mocs_v1 \\
  --mapping context/ontology/external_equipment_v1.json \\
  --val-annotations context/external/incoming/mocs/raw/annotation_val.json \\
  --val-images context/external/incoming/mocs/raw/instances_val/instances_val
```

Подробные ссылки на шесть официальных файлов и инструкции для train/test
находятся в [`docs/mocs-dataset.md`](docs/mocs-dataset.md).

## MOCS validation benchmark

В рабочую копию скачан официальный MOCS validation: 4 000 изображений и
18 965 annotations. Thalos прогнан по всей выборке на GPU. Используйте:

```bash
.venv/bin/python scripts/evaluate_coco_report.py \\
  --coco context/external/incoming/mocs/raw/annotation_val.json \\
  --report context/external/mocs_val_v1/reports/thalos.json \\
  --model thalos --threshold 0.35 --iou 0.5
```

Результаты MOCS validation:

```text
excavator:       precision 0.957, recall 0.662, support 2622
road roller:     precision 0.830, recall 0.544, support 171
concrete mixer:  precision 0.713, recall 0.458, support 179
bulldozer:       precision 0.811, recall 0.522, support 205
mobile crane:    precision 0.349, recall 0.249, support 362
truck:           recall 0.000, support 1094
```

В MOCS есть класс `Truck`, но нет отдельного `dump truck`, а класс `Crane`
шире, чем `crane manipulator`. Поэтому `dump truck` и `crane manipulator`
помечаются evaluator как `not evaluated`, а не как провал модели.


```bash
.venv/bin/python scripts/sonnet_annotate.py \\
  --images context/dgp_extract/samples \\
  --output /tmp/buildwatch-sonnet \\
  --model claude-sonnet-4-6

.venv/bin/python scripts/merge_sonnet_annotations.py \\
  --input /tmp/buildwatch-sonnet \\
  --output /tmp/buildwatch-sonnet-pseudo.json
```

Чтобы сравнить Sonnet с имеющимися detector-результатами и отделить согласованные pseudo-labels от disagreement:

```bash
.venv/bin/python scripts/merge_detector_sonnet.py \\
  --pseudo context/validation/sonnet_pseudo.json \\
  --detector-report context/detector_compare.json \\
  --output context/validation/sonnet_agreement.json
```

Для disagreement можно выполнить crop-review: Sonnet получает отдельный объект, а не весь кадр, и проверяет только его класс.

```bash
.venv/bin/python scripts/sonnet_review.py \\
  --images context/dgp_extract/samples \\
  --manifest context/validation/sonnet_agreement.json \\
  --output context/validation/sonnet_reviews \\
  --model claude-sonnet-4-6

.venv/bin/python scripts/apply_sonnet_reviews.py \\
  --manifest context/validation/sonnet_agreement.json \\
  --reviews context/validation/sonnet_reviews \\
  --output context/validation/sonnet_reviewed.json
```

После crop-review экспортировать dataset для CVAT/обучения:

```bash
.venv/bin/python scripts/export_reviewed_dataset.py \\
  --manifest context/validation/sonnet_reviewed.json \\
  --images context/dgp_extract/samples \\
  --output context/validation/reviewed_dataset_v1 \\
  --holdout 0.2
```

Для exploratory-обучения на GPU текущего компьютера используется wrapper
[`scripts/train_equipment_detector.py`](scripts/train_equipment_detector.py):

```bash
/root/.pi/agent/jev-router/venv/bin/python scripts/train_equipment_detector.py \\
  --dataset context/validation/reviewed_dataset_v1 \\
  --output context/validation/exploratory_training_v2 \\
  --base-model yolov8s.pt \\
  --epochs 20 \\
  --imgsz 640 \\
  --batch 8 \\
  --workers 0 \\
  --device 0 \\
  --allow-pseudo \\
  --export-onnx
```

Без `--allow-pseudo` wrapper отказывается обучать dataset, который не имеет
`ground_truth: true`. Поэтому полученная модель является только exploratory и
не подключается в production автоматически.


