# Validation set

The repository has detector outputs but no official ground truth. Do not use the
cached `context/detector_compare.json` as a quality label. Create a manually
annotated subset of the real images before comparing models.

## Annotation format

Copy `annotations.example.json` and add one entry per selected image. Coordinates
are absolute pixels in `[x1, y1, x2, y2]` format. Use canonical English labels:

- `excavator`
- `dump truck`
- `truck`
- `bulldozer`
- `road roller`
- `concrete mixer`
- `mobile crane`
- `tower crane`
- `truck crane`
- `crane manipulator`
- `concrete pump`
- `drilling rig`

Annotate visible equipment even when it is partly occluded. Add an `ignore: true`
object only for an unresolvable object; ignored objects must not be used in the
metrics until a class is agreed.

## Sonnet-assisted pseudo-labels

The project includes a resumable Sonnet Vision annotator. It reads the API key
only from `FREEMODEL_API_KEY` or `ANTHROPIC_API_KEY`; never place the key in a
manifest, `.env` committed to Git, or a result file.

```bash
.venv/bin/python scripts/sonnet_annotate.py \\
  --images context/dgp_extract/samples \\
  --output /tmp/buildwatch-sonnet \\
  --model claude-sonnet-4-6

.venv/bin/python scripts/merge_sonnet_annotations.py \\
  --input /tmp/buildwatch-sonnet \\
  --output /tmp/buildwatch-sonnet-pseudo.json
```

The command skips completed images and writes each result atomically, so it can
be interrupted and resumed. The merged file deliberately contains
`"ground_truth": false` and `review_status: "candidate"`. Review it in CVAT or
manually before converting it to a validation annotation file.


```bash
.venv/bin/python scripts/evaluate_detectors.py \
  --annotations context/validation/annotations.json \
  --report context/detector_compare.json \
  --model yolo_world \
  --threshold 0.35 \
  --iou 0.5
```

Run the same command for `uisikdag`. Report per-class precision, recall, false
positives, false negatives, and latency. Thresholds are experiment parameters,
not claims about model confidence quality.
