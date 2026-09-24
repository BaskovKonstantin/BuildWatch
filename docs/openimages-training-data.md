# Open Images V6 equipment subset

## Why this source is used

Kaggle links from the original project note currently return HTTP 404 in this environment, and the available Roboflow page is protected by Cloudflare. To obtain an independently downloadable source with bounding boxes, BuildWatch uses the official [Open Images download page](https://storage.googleapis.com/openimages/web/download.html), its [V6 training bounding-box CSV](https://storage.googleapis.com/openimages/v6/oidv6-train-annotations-bbox.csv), and its [V6 image metadata CSV](https://storage.googleapis.com/openimages/v6/oidv6-train-images-with-labels-with-rotation.csv).

The Open Images page identifies the images as Creative Commons Attribution sources, but also says that consumers must verify the licence status of each image. The generated `attribution.json` therefore preserves the source image URL, landing URL, declared licence, author profile, author and title for every downloaded image. The subset is research/experiment data until a licence review approves its intended use.

## Safe class mapping

[`context/ontology/openimages_v6_equipment_v1.json`](../context/ontology/openimages_v6_equipment_v1.json) maps only these Open Images IDs:

| Open Images label | BuildWatch class |
|---|---|
| `/m/07r04` Truck | `truck` |
| `/m/075t5x` Road roller | `road roller` |
| `/m/01tkqg` Bulldozer | `bulldozer` |
| `/m/04jgrq` Concrete mixer | `concrete mixer` |

The exhaustive scan of the official V6 train bbox CSV found downloadable annotations only for `Truck`. The other three mapped IDs do not occur in that train annotation file. `Crane (Machine)` is deliberately excluded: it does not distinguish mobile/tower/fixed cranes, so mapping it to `mobile crane` would introduce unsafe supervision. Open Images does not supply an explicit safe `dump truck`, `crane manipulator`, or `excavator` class for this subset.

## Generated subset

Command used:

```bash
.venv/bin/python scripts/fetch_openimages_subset.py \
  --output context/external/openimages_equipment_v1 \
  --mapping context/ontology/openimages_v6_equipment_v1.json \
  --max-images-per-class 500 \
  --holdout 0.2
```

Result:

| Field | Value |
|---|---:|
| Candidate Truck image IDs | 500 |
| Downloaded images | 424 |
| Bounding boxes | 610 |
| Train / holdout images | 341 / 83 |
| Failed source downloads | 76 |
| Rotated images admitted | 0 |

The 76 failures come from no-longer-available Flickr URLs in the official image metadata. They are written into ignored `dataset.json` under `failed_downloads`; the preparation never replaces them with untracked images or silently claims that the requested cap was reached.

## Combined exploratory run

[`scripts/merge_yolo_datasets.py`](../scripts/merge_yolo_datasets.py) merges only BuildWatch-format `ground_truth: true` sources that have the same canonical class order and their own `train` + `holdout` directories. It prefixes source names in output filenames and records full source manifests in `sources.json`.

The initial combined external dataset has:

- 223 GitHub excavator annotations (184 train / 39 holdout), research-only due to absent SPDX licence;
- 610 Open Images truck annotations (341 train / 83 holdout), with per-image attribution;
- 647 images and 833 boxes total (525 train / 122 holdout).

A 30-epoch YOLOv8s GPU run on RTX 5070 produced an exploratory model. On this source-local holdout only, its metrics were:

| Metric | Value |
|---|---:|
| precision | 0.906 |
| recall | 0.835 |
| mAP@50 | 0.874 |
| mAP@50–95 | 0.703 |

These values were reproduced by validating `best.pt` on the merged 122-image holdout after training. They are **not production metrics**: the holdout originates from the same two external sources and the model has no positive training examples for the other six BuildWatch classes. Weights and reports remain ignored under `context/external/equipment_external_v1/training_run/`.

MOCS validation and test images are not part of this dataset, and the model is not connected to the live BuildWatch detector.
