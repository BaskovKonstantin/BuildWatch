# MOCS dataset integration

## Official source files

The project uses the MOCS release supplied by the dataset authors. Raw archives and generated images stay outside Git under `context/external/`.

| Split | Source |
|---|---|
| Train annotations | [Google Drive](https://drive.google.com/file/d/1Oh0rIq2YmCZHFSTWXOpedYSE06c8Sq9j/view?usp=sharing) |
| Train images | [Google Drive](https://drive.google.com/file/d/1kzlZLdH31nm6QsTOusuL2DJnQDQbTKDt/view?usp=sharing) |
| Validation annotations | [Google Drive](https://drive.google.com/file/d/18Q7ugoRJZ8ntjM07pwqkDhWGxPvQAgBt/view?usp=sharing) |
| Validation images | [Google Drive](https://drive.google.com/file/d/1Zeqr7C5p-hWNw5ta2fvD1bgLnXd-17fW/view?usp=sharing) |
| Test image info | [Google Drive](https://drive.google.com/file/d/1yYJOdXF9SbuvU_BcVsuLb-mrgmUL5Pmj/view?usp=sharing) |
| Test images | [Google Drive](https://drive.google.com/file/d/1Uj9-oZFIAk9Jy_JGMfNZlLbERplEXj-i/view?usp=sharing) |

The validation annotations and images are currently available locally. The supplied train-images link currently returns Google Drive HTTP 404 and must be corrected before train preparation. Test images are not required for training and remain isolated from model fitting and threshold selection.

## Preparation

Convert the available validation split:

```bash
.venv/bin/python scripts/prepare_mocs.py \
  --output context/external/mocs_v1 \
  --mapping context/ontology/external_equipment_v1.json \
  --val-annotations context/external/incoming/mocs/raw/annotation_val.json \
  --val-images context/external/incoming/mocs/raw/instances_val/instances_val
```

When the official train and test image roots are available, add them with the same command:

```bash
.venv/bin/python scripts/prepare_mocs.py \
  --output context/external/mocs_v1 \
  --mapping context/ontology/external_equipment_v1.json \
  --train-annotations context/external/incoming/mocs/raw/annotation_train.json \
  --train-images context/external/incoming/mocs/raw/instances_train \
  --val-annotations context/external/incoming/mocs/raw/annotation_val.json \
  --val-images context/external/incoming/mocs/raw/instances_val/instances_val \
  --test-info context/external/incoming/mocs/raw/image_info_test.json \
  --test-images context/external/incoming/mocs/raw/instances_test
```

The converter keeps the official split boundary, writes YOLO labels and empty labels for negative images, preserves ignored-category counts, and marks the test split as `ground_truth: false`. It excludes categories that do not have a safe BuildWatch mapping, including workers, static cranes, loaders, pump trucks, pile-driving equipment, and other vehicles.

## Current local result

The available validation split contains 4,000 images and 18,965 annotations. The BuildWatch ontology currently maps 4,633 objects:

- excavator: 2,622;
- truck: 1,094;
- mobile crane: 362;
- bulldozer: 205;
- concrete mixer: 179;
- road roller: 171.

MOCS does not provide separate `dump truck` or `crane manipulator` categories in this release. Its `Truck` category remains mapped to `truck`, and `Crane` remains mapped to `mobile crane`; these are not silently relabeled as more specific classes.

The dataset is marked research-only in the existing project metadata. Commercial or production use requires confirming permission with the dataset authors.
