# План качественного распознавания строительной техники для BuildWatch

> **Для исполнителей:** выполнять этапы последовательно. Каждый этап должен завершаться артефактом, проверкой и зафиксированным решением. Не принимать pseudo-labels за ground truth.

Экран «Качество распознавания» в карточке объекта считает уже выставленные вердикты инспектора `correct` и `wrong`. Он не заменяет метрики precision и recall из этого плана.

**Цель:** построить измеримый контур обнаружения строительной техники, который соответствует ТЗ, использует GPU текущего компьютера для подготовки и обучения, а в production переносится на более слабый сервер.

**Целевое окружение:**
- подготовка данных и обучение: GPU текущего компьютера;
- production: более слабый сервер, ориентировочно CPU или ограниченный GPU;
- внешние VLM API: разрешены для разметки и проверки сложных случаев;
- первый качественный релиз: обязательные классы ТЗ;
- расширенные классы: отдельный второй этап.

**Главный принцип:** VLM и open-vocabulary-модели используются как teacher/reviewer, а финальное production-распознавание выполняется компактным специализированным detector. Бизнес-предупреждение не создаётся только на основании одной приблизительной VLM-детекции.

---

## 1. Зафиксировать ontology первого релиза

### 1.1. Обязательные классы

В первом релизе закрепить следующие канонические классы:

```text
excavator          — экскаватор
 dump_truck        — самосвал
road_roller        — каток
crane_manipulator  — кран-манипулятор
concrete_mixer     — бетоносмеситель/автобетоносмеситель
bulldozer          — бульдозер
truck              — грузовик
mobile_crane       — автокран/мобильный кран
```

`crane` использовать как родительскую категорию для анализа, но не смешивать в базе родительский и дочерний классы в одной детекции.

### 1.2. Отложенные классы

Не включать в первый quality gate как обязательные:

```text
tower_crane
truck_crane
concrete_pump
drilling_rig
loader
worker
safety_helmet
vest
```

Их можно сохранять как дополнительные candidate labels, но отсутствие этих классов не должно влиять на итоговую оценку первого релиза.

### 1.3. Правила ontology

- `dump truck` и `truck` размечаются отдельно только при визуально достаточном качестве.
- `mobile crane`, `tower crane`, `truck crane`, `crane manipulator` сначала проверяются через родительский класс `crane`.
- Если тип крана неразличим, разметка получает `crane_unknown`, а не случайный subtype.
- `loader` не преобразуется в `bulldozer`.
- Для каждого объекта сохраняются `source_label`, `canonical_label`, `visibility` и `review_status`.

**Артефакт:** `context/ontology/equipment_v1.json` с каноническими классами, aliases и правилами mapping.

---

## 2. Собрать исходные данные

### 2.1. Внешние датасеты

Проверить и скачать только после аудита лицензий:

1. [OpenConstruction](https://github.com/YUZ128pitt/OpenConstruction) — 41 668 изображений и категории, близкие к строительной технике.
2. [ACID](https://www.acidb.net/dataset) — excavator, compactor, dozer, dump truck, concrete mixer, truck, loader и crane.
3. [Construction Earthwork](https://www.openconstruction.org/datasets/detail.html?id=Object-Detection-Construction) — earthwork equipment, dump truck, excavator, bulldozer, roller и cranes.
4. [Thalos Heavy Equipment Detection](https://huggingface.co/thalostech2025/thalos-heavy-equipment-v1) — использовать как baseline/checkpoint только после проверки модели и лицензии.

Не объединять классы внешних датасетов молча. Каждое преобразование должно быть записано в mapping-файле.

### 2.2. Проектные снимки

Текущие 100 PNG разделить по группам, а не случайно по отдельным кадрам:

- `train/dev`: около 80 изображений;
- `holdout`: около 20 изображений;
- кадры одной серии или одной сцены должны оставаться в одной группе, чтобы не получить leakage.

Если на holdout недостаточно объектов какого-либо обязательного класса, добавить похожие реальные снимки и явно отметить, что метрика по классу статистически слабая.

### 2.3. Минимальный объём ground truth

Для quality gate желательно иметь:

- не менее 30–50 реальных экземпляров каждого обязательного класса;
- не менее 10 отрицательных или неоднозначных изображений;
- отдельные примеры маленьких, перекрытых и частично видимых объектов;
- минимум 20 полностью проверенных holdout-снимков.

Если класс встречается реже, его нельзя объявлять надёжным только по aggregate mAP.

---

## 3. Построить pipeline автоматической разметки

### 3.1. Инструмент разметки

Основной инструмент: self-hosted [CVAT](https://docs.cvat.ai/docs/annotation/auto-annotation/).

Причины:

- поддержка bounding boxes и видео;
- auto-annotation;
- экспорт YOLO/COCO;
- интеграция с собственными моделями;
- [SAM2 tracker](https://docs.cvat.ai/docs/annotation/auto-annotation/segment-anything-2-tracker/) для последовательных кадров.

Альтернатива — [Label Studio с Grounding DINO](https://labelstud.io/guide/ml_tutorials/grounding_dino), если потребуется сложный workflow согласования annotators.

### 3.2. Teacher-модели

На GPU текущего компьютера запускать:

1. текущий YOLO-World;
2. UISikDag для construction/PPE-кандидатов;
3. Grounding DINO для open-vocabulary proposals;
4. YOLOE как эксперимент с text/image prompts;
5. при необходимости Florence-2 или GLM-V для сложных случаев.

[Grounding DINO](https://github.com/IDEA-Research/GroundingDINO) использовать как основной teacher для автоматических bbox. [YOLO-World](https://github.com/AILab-CVC/YOLO-World) оставить быстрым baseline.

### 3.3. Agreement policy

Для каждого изображения сохранять все исходные предложения, а затем формировать pseudo-label:

```text
2+ detector-а согласны по классу и IoU >= 0.5
    → accepted_pseudo_label

найдена только одной моделью
    → candidate

модели нашли один объект, но разные классы
    → disagreement

confidence ниже 0.35 или объект слишком мал
    → manual_review
```

Pseudo-label не должен автоматически использоваться как ground truth.

### 3.4. VLM-проверка

Разрешённые внешние API использовать только для disagreement и сложных crops:

- Sonnet — внешний semantic reviewer;
- GLM-V — альтернатива, особенно если появится локальный GPU-контур;
- обычный текстовый GLM без vision не использовать для изображений.

VLM получает:

- crop объекта;
- исходный bbox;
- несколько пикселей контекста вокруг bbox;
- список допустимых классов;
- просьбу вернуть строго JSON.

VLM должен отвечать:

```json
{
  "label": "mobile_crane",
  "accepted": true,
  "box_quality": "good|rough|wrong",
  "visibility": "clear|partial|tiny",
  "needs_review": false,
  "reason": "..."
}
```

Координаты VLM нужно проверять по размерам исходного изображения. Нельзя использовать confidence VLM как confidence detector.

### 3.5. Human-in-the-loop

Человек проверяет только:

- disagreement между моделями;
- отсутствие обязательного класса на снимке;
- маленькие и перекрытые объекты;
- subtype кранов;
- псевдоразметки с одним источником;
- случайные 10–20% accepted pseudo-labels для контроля drift.

**Артефакты:**

- `datasets/raw/`;
- `datasets/pseudo/`;
- `datasets/reviewed/`;
- `datasets/holdout/`;
- `datasets/manifests/*.json`;
- `datasets/mappings/*.json`.

---

## 4. Обучить специализированный detector

### 4.1. Сформировать версии датасета

Создать три версии:

```text
v0_external_only
v1_external_plus_pseudo
v2_external_plus_reviewed_project_data
```

`holdout` никогда не смешивать с train.

### 4.2. Обучить несколько кандидатов

Минимальный benchmark:

- YOLO small/nano для скорости и CPU;
- YOLO small/medium для качества;
- RT-DETR или другой transformer detector как quality baseline;
- текущий YOLO-World без обучения;
- Grounding DINO как teacher, но не обязательно как production model.

Обучение и сравнение выполнять на GPU текущего компьютера. Для сервера подготовить экспорт:

```text
PyTorch → ONNX → CPU runtime
```

Дополнительно проверить quantization и размер inference image. Нельзя выбирать модель по mAP без измерения latency на слабом сервере.

### 4.3. Аугментации

Обязательно проверить:

- уменьшение объектов;
- drone-like crop;
- partial occlusion;
- blur и compression;
- brightness/contrast;
- снег, дождь и пыль, если такие условия встречаются;
- mosaic только при отсутствии вреда для маленьких объектов.

### 4.4. Tiling

В `scripts/detect_equipment_single.py` подключён SAHI: кадр обрабатывается
тайлами `1280 × 1280` с overlap `15%`, а confidence threshold остаётся `0.15`.
Дополнительно сохраняется один проход по целому кадру для крупной техники.
SAHI возвращает боксы в координатах исходного кадра и объединяет результаты
перекрывающихся тайлов class-aware `GREEDYNMM` по `IOS` с порогом `0.5`.

Измерение выигрыша пока остаётся отдельной задачей: сравнить обычный inference,
SAHI и latency/recall на размеченном holdout. Интеграция сама по себе не
подтверждает улучшение качества текущего checkpoint.

---

## 5. Формализовать оценку качества

### 5.1. Метрики detector

Считать отдельно для каждого обязательного класса:

- precision;
- recall;
- F1;
- AP50;
- AP50:95;
- confusion matrix;
- false positives на пустых кадрах;
- false negatives на маленьких объектах;
- latency и peak memory.

Использовать существующий evaluator и расширить его под:

- parent/subtype classes;
- ignored objects;
- visibility;
- source model;
- multiple detections per image.

### 5.2. Метрики бизнес-правил

Отдельно измерять:

- precision предупреждений R-01/R-02/R-03/R-07;
- recall реальных нарушений;
- false R-03 rate;
- долю предупреждений, отправленных на review;
- agreement между detector и VLM;
- время от загрузки изображения до предупреждения.

### 5.3. Предлагаемый quality gate

Это не официальные цифры ТЗ, а рабочие стартовые критерии:

- recall каждого обязательного класса на holdout: не ниже 0.85 при достаточном числе примеров;
- precision детекций, которые могут создавать violation: не ниже 0.90;
- false R-03 rate: не выше 5%;
- 100% снимков имеют конечный статус `detected`, `empty` или `failed`;
- ни один `candidate` не создаёт безусловное нарушение;
- latency измерена отдельно на GPU текущего компьютера и слабом сервере;
- сохранён полный provenance: model, version, threshold, image size, source box.

Если метрика не проходит, система не должна маскировать проблему снижением threshold.

---

## 6. Интегрировать в BuildWatch

### 6.1. Model registry

Добавить реестр моделей:

```json
{
  "name": "buildwatch-equipment-v2",
  "version": "2026-10-01",
  "classes": "equipment_v1",
  "weights": "...",
  "runtime": "onnx_cpu",
  "thresholds": {
    "display": 0.2,
    "review": 0.35,
    "accepted": 0.5
  }
}
```

### 6.2. Provenance

Для каждой детекции хранить:

```text
model_name
model_version
source_model
threshold
image_size
dataset_version
review_status
parent_label
canonical_label
```

### 6.3. Разделить состояния

```text
candidate       — предварительная детекция
review          — нужна проверка
accepted        — подтверждена ансамблем/VLM
verified        — подтверждена человеком
rejected        — отклонена
```

Бизнес-правила:

- R-01 может работать с `accepted` и `verified`;
- R-02 создаётся для disagreement/low confidence;
- R-03 не создаётся на основании непроверенного отсутствия;
- R-07 проверяет только подтверждённые crane-классы;
- failed и processing никогда не являются доказательством отсутствия техники.

### 6.4. Два runtime-контура

GPU/current machine:

```text
Grounding DINO
YOLO-World/YOLOE
VLM review
training
annotation
```

Weak server:

```text
ONNX/quantized custom detector
small image pipeline
asynchronous review queue
no VLM in the critical synchronous path
```

Внешний Sonnet/GLM вызывается только для review или подготовки датасета, а не для каждого обычного снимка.

---

## 7. План экспериментов

### Спринт 1 — 1–2 дня: baseline

- зафиксировать ontology v1;
- собрать OpenConstruction/ACID после проверки лицензий;
- запустить текущие YOLO-World и UISikDag на одинаковом manifest;
- подготовить CVAT;
- получить первые pseudo-labels;
- вручную проверить 20 изображений.

**Результат:** понятный список классов, mapping и первые false positives.

### Спринт 2 — 2–4 дня: teacher ensemble

- добавить Grounding DINO;
- сравнить prompt variants;
- добавить IoU agreement;
- подключить Sonnet или GLM-V к disagreement crops;
- получить reviewed dataset;
- подготовить 20 holdout-снимков.

**Результат:** первая честная validation subset и набор reviewed labels.

### Спринт 3 — 3–5 дней: custom detector

- обучить nano/small/medium кандидатов;
- сравнить с zero-shot baseline;
- проверить tiling и image size;
- экспортировать ONNX;
- замерить GPU и слабый CPU.

**Результат:** кандидат production-модели и таблица quality/latency.

### Спринт 4 — 2–3 дня: BuildWatch integration

- model registry;
- provenance;
- review statuses;
- VLM review job;
- новые warning gates;
- UI для disagreement и ручного подтверждения;
- экспорт dataset версии.

**Результат:** детекция и предупреждения отделены от pseudo-label pipeline.

### Спринт 5 — 1–2 дня: acceptance

- holdout evaluation;
- прогон 100 изображений;
- нагрузочный тест очереди;
- проверка отказов и failed jobs;
- замер server latency;
- финальная документация и demo сценарий по ТЗ.

---

## 8. Критические риски

### Внешний VLM ошибается в координатах

Митигировать crop-проверкой, нормализацией координат и обязательной визуальной проверкой случайной выборки.

### Pseudo-label закрепляет ошибку teacher

Митигировать agreement между несколькими моделями, ручной проверкой и отдельным holdout.

### Внешние данные имеют другую domain distribution

Митигировать добавлением project images, hard-negative mining и fine-tuning на reviewed кадрах.

### Слишком много subtype кранов

Начать с parent class `crane`, а subtype включать только при достаточном числе размеченных примеров.

### GPU-решение нельзя перенести на слабый сервер

С самого начала измерять не только качество, но и ONNX/CPU latency. VLM не помещать в синхронный critical path.

---

## 9. Итоговая рекомендуемая архитектура

```text
Внешние датасеты + 100 project images
                    ↓
Grounding DINO + YOLO-World + UISikDag
                    ↓
         pseudo-label agreement
                    ↓
 CVAT + Sonnet/GLM-V для disagreement
                    ↓
          reviewed train/holdout
                    ↓
    custom compact equipment detector
                    ↓
        ONNX/quantized server model
                    ↓
 BuildWatch candidate/accepted/verified states
                    ↓
       R-01/R-02/R-03/R-07 warnings
```

Главный практический выбор: GPU и внешние VLM использовать сейчас для получения качественной разметки и обучения, но не переносить тяжёлые VLM в обязательный production-путь на слабом сервере.
