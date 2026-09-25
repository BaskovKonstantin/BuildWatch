# equipment_extra_v1

Датасет BuildWatch YOLO (`buildwatch-external-yolo-v1`), собранный из трёх скачанных внешних
датасетов. Только канонические классы BuildWatch; всё остальное — игнорируется.
Все изображения в `train/` (holdout не создавался). Файлы скопированы (не symlink),
имена с префиксом источника во избежание коллизий.

**Расположение:** `context/external/equipment_extra_v1/` (в .gitignore, в git не коммитится).
**Конвертер:** `scripts/convert_equipment_extra.py`.
**Маппинг классов:** `context/ontology/equipment_extra_v1.json`.

## Сводка

| источник | картинок | боксов |
|---|---|---|
| kaggle-ppe-heavy-machinery | 10889 | 17011 |
| hf-industrial-site-safety | 328 | 788 |
| kaggle-truck-mixer | 961 | 1514 |
| **итого** | **12178** | **19313** |

## by_class (итоговый)

- excavator: 4175 (id 0)
- dump truck: 6301 (id 1)
- road roller: 4172 (id 2)
- concrete mixer: 1514 (id 4)
- bulldozer: 3151 (id 5)

## Источники

1. **kaggle-ppe-heavy-machinery** (префикс `ppe_`) — Pascal VOC-CSV
   `final_dataset_normalized.csv` (абсолютные пиксельные координаты, изображения 640x640).
   Маппинг: road_roller→road roller, bulldozer→bulldozer, dump_truck→dump truck,
   excavator→excavator. Игнор: wheel_loader и все PPE-классы. 1 файл из CSV отсутствует
   на диске. Только файлы с каноническими боксами (10889 из 24924 уникальных).
2. **hf-industrial-site-safety** (префикс `hfsafety_`) — YOLO (train+val).
   Маппинг: road_roller→road roller, bulldozer→bulldozer, excavator→excavator,
   dump_truck→dump truck. Игнор: backhoe_loader, grader, wheel_loader, PPE, trench и т.д.
   87 картинок без канонических боксов пропущено.
3. **kaggle-truck-mixer** (префикс `truckmixer_`) — YOLO (train+valid), класс 8 →
   concrete mixer (подтверждено manifest.json), классы 0 и 9 игнорируются (24 бокса).

## Проверка

- каждая картинка имеет непустой label-файл (12178/12178), пар без пары нет;
- все координаты в [0,1] (клип при конвертации), 0 некорректных строк;
- by_class сходится с ручным подсчётом по label-файлам;
- by_class по источникам сходится с их manifest.json.

## dataset.json

Полная статистика и файлы-происхождения — в `context/external/equipment_extra_v1/dataset.json`
(поле `sources`).
