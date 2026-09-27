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

## Работа с планом, снимками и ИИ

В карточке объекта блок «План / наблюдение» сопоставляет этап на дату снимка,
ожидаемую по методике технику и обнаруженные объекты. Сигнал означает повод для
проверки: камера видит только часть площадки, поэтому один кадр не доказывает
простой или отставание. Инспектор может подтвердить либо отклонить сигнал.

Календарный план можно заполнить вручную или загрузить в редакторе этапов из
CSV/XLSX размером до 2 МБ. Для импорта нужны столбцы «Этап», «Дата начала» и
«Дата окончания»; даты допускаются в форматах ДД.ММ.ГГГГ и ГГГГ-ММ-ДД.
Импорт сначала показывает этапы и ошибки строк, а сохраняет план только после
явного нажатия «Сохранить план». Справочник видов работ без дат нельзя
использовать как календарный план. Страница «Отчёт» собирает план, статусы
сигналов и ссылки на снимки; кнопку «Печать / PDF» можно использовать для
выгрузки браузером.

Кнопка «Спросить BuildWatch» открывает ИИ-помощника на главной и в карточке
объекта. Помощник отвечает по данным приложения и показывает ссылки на
использованные объекты или снимки. Команду на перенос дат этапа он оформляет
как предложение с датами до и после; изменение применяется только после
отдельного подтверждения пользователем. Ключ передаётся только с сервера:
приложение сначала использует существующий ключ `opencode` из авторизации
OpenCode/Pi, а при отказе авторизации переключается на ключ `opencode-go`.
Для отдельного ключа можно задать серверную
переменную `BUILDWATCH_ZEN_KEY`, а модель указать в `BUILDWATCH_ZEN_MODEL`.
Ключ нельзя помещать в `frontend/`, `.env` под Git или в браузерные настройки.

## Проверки

```powershell
python -m unittest discover -s tests -v
npm --prefix frontend run build
```

## Демо-объекты

Главная страница показывает портфель из шести объектов разных типов ЛТЦ
(жильё, школа, поликлиника, ФОК, дорога, детский сад). Их задаёт
[`backend/demo_projects.py`](backend/demo_projects.py): 17 реальных снимков ДГП
распределены по объектам по содержанию кадра, названия этапов взяты из
справочника ЛТЦ, календарные даты заданы для демонстрации. Загруженные
пользователем снимки и детекции не трогаются.

```powershell
cd D:\Projects\BuildWatch\backend
python demo_projects.py   # идемпотентно, пересчитывает предупреждения
```

Интерфейс сделан в стиле iOS: полупрозрачный навбар с большим заголовком,
виджеты-сводка, сегмент-фильтр, поиск; светлая и тёмная темы следуют
системной настройке. Фильтры главной страницы хранятся в URL.

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

## External YOLO training data

Основной внешний источник — Kaggle `xyzyxzzxy/construction-equipment`
(19 982 изображения, 29 665 объектов: самосвалы, экскаваторы, бетоносмесители,
автокраны, грузовики). В архиве нет файла классов, поэтому содержимое каждого
ID проверено визуально по контрольным листам кропов; сомнительные классы
исключены. Источник research-only.

Катки, бульдозеры и краны-манипуляторы в безопасном виде внешними источниками
пока не закрыты: они требуют MOCS train images, ручной разметки московских
кадров или проверенных наборов.

Также импортирован доступный GitHub-набор из 223 размеченных
экскаваторов: 184 кадров train и 39 deterministic holdout. Он используется
только для research/exploratory экспериментов: upstream не публикует SPDX
license и предупреждает о возможном copyright исходных изображений.

Импортёр [`scripts/import_yolo_dataset.py`](scripts/import_yolo_dataset.py)
требует явный mapping исходных numeric IDs в онтологию BuildWatch, валидирует
YOLO labels, фиксирует SHA-256 архива и исправляет только bbox, слегка
выходящие за край изображения. Он не смешивает внешний train с MOCS validation
или test. Подробности, лицензия и команда для добавления других наборов:
[`docs/external-training-data.md`](docs/external-training-data.md).

## Open Images V6 + exploratory training

Из официального Open Images V6 подготовлена attributable-подвыборка `truck`:
424 кадра, 610 bbox (341 train / 83 holdout). Скрипт
[`scripts/fetch_openimages_subset.py`](scripts/fetch_openimages_subset.py)
читает официальные bbox и metadata CSV, допускает только явно mapped классы и
нулевой rotation, сохраняет attribution по каждому фото и фиксирует недоступные
Flickr URLs. В этом train CSV отсутствовали bbox для safe-mapping классов
`road roller`, `bulldozer` и `concrete mixer`; generic crane намеренно исключён.

[`scripts/merge_yolo_datasets.py`](scripts/merge_yolo_datasets.py) собрал
внешний ground-truth dataset: 647 изображений / 833 bbox (525 train / 122
holdout) из Open Images trucks и GitHub excavators. На RTX 5070 выполнен
30-epoch exploratory YOLOv8s run: воспроизводимая проверка `best.pt` на
source-local holdout дала `mAP@50 = 0.874`, но
это не production-метрика и не оценка оставшихся шести классов. Веса не
подключены к live detector и остаются вне Git.

Полная атрибуция, ограничения лицензий, фактические class metrics и команды:
[`docs/openimages-training-data.md`](docs/openimages-training-data.md).



## Визуальный стиль

Основная тема — «Editorial» (по референсам Inspo и design-loop): тёплая бумажная подложка, чёрные рамки с печатной offset-тенью, mono-метки, сигнальный оранжевый, «аварийные» полосы прогресса. Слайдер «Стоит проверить» на главной. Переключатель стилей скрыт, доступен через `?styles=1`. Before/after: `context/design-refs/`.
