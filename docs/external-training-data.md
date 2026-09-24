# External training data

## Imported source: Construction Machines Images Dataset

The first external source that is currently downloadable in this workspace is [`miniexcav/Construction-Machines-Images-Dataset`](https://github.com/miniexcav/Construction-Machines-Images-Dataset). The repository contains 223 image/YOLO-label pairs for one class, `excavator`.

The upstream repository has **no SPDX license**. Its README says the images came from Google Image Search, are supplied only for educational/research use, and may require permission from original creators for commercial use. BuildWatch therefore marks this source as **research-only**. It must not be used in a commercial or production model without a separate rights review.

### Local import result

Raw data is stored under ignored `context/external/incoming/`; converted data is ignored under `context/external/github_construction_machines_v1/`.

| Field | Value |
|---|---:|
| Source archive SHA-256 | `792d96f6e7647983b4b23749ab93b5a0bf8b0c2370ce0e3810362ebc5c9980ac` |
| Images / annotations | 223 / 223 |
| Canonical class | `excavator` |
| Train / holdout | 184 / 39 |
| Corrected boundary boxes | 3 |
| Ignored labels | 0 |

The deterministic holdout is used only for the exploratory source-local run. It is not MOCS validation and does not replace the Moscow holdout.

## Importing a compatible external YOLO set

Use [`scripts/import_yolo_dataset.py`](../scripts/import_yolo_dataset.py) only for a directory where every image has a paired YOLO `.txt` label. The numeric source IDs must be mapped explicitly to BuildWatch classes in a JSON file. For example, an approved source whose classes are `0=excavator`, `1=dump truck` requires:

```json
{
  "0": "excavator",
  "1": "dump truck"
}
```

Then import it without mixing MOCS data:

```bash
.venv/bin/python scripts/import_yolo_dataset.py \
  --source /path/to/source-yolo \
  --output context/external/approved_source_v1 \
  --mapping context/ontology/approved_source_v1.json \
  --source-name approved-source \
  --license "exact upstream license and commercial-use terms" \
  --source-url "https://source.example/dataset" \
  --archive-sha256 "$(sha256sum /path/to/archive.zip | cut -d' ' -f1)" \
  --holdout 0.2
```

The importer rejects undeclared source IDs, missing labels, invalid normalized coordinates, and boxes with no area inside the image. It clips boxes that merely cross an image edge and records `clipped_objects` in `dataset.json`.

## Training and evaluation policy

- The present GitHub set improves only the `excavator` class; it cannot establish quality for the remaining seven target classes.
- MOCS validation stays isolated and is used for evaluation/threshold selection, never copied into this external training set.
- MOCS test remains excluded from fitting and threshold selection.
- `dump truck` and `crane manipulator` still need correctly licensed, explicitly mapped training data or human-reviewed Moscow annotations.
- Any resulting model remains exploratory until it passes evaluation on MOCS validation and a manually labeled Moscow holdout.
