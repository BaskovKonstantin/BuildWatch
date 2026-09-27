# BW-7: mobile crane label audit — v9 fix report (2025-09-27)

## Sample
219 suspect crops (of 3047 suspects / 7997 MC boxes) visually reviewed: all ar (11), all iou_cm (3), 120 many_mc, tiny sample.

## Deleted: 1281 train + 3 holdout class-7 boxes (7707 -> 6426 train, 290 -> 287 holdout)
1. **kagv2_camera_19.302_* (train): 866 boxes** — same static box (cx~0.84, cy~0.165, 5% x 4%) in 869 frames, sits on an orange loader/excavator, no crane. Visually confirmed in 39+ crops.
2. **kagv2_camera_19.102_* (train): 340 boxes** — static box misaligned, covers background above a real blue truck crane.
3. **rfc2_train_001751 (+augmented copies): 17 boxes** — boom pump truck (red) labeled mobile crane; left crawler lattice crane kept.
4. **Individual verified wrongs: 61 train + 3 holdout** — boxes on buildings/roofs/empty ground (~35), on excavators/loaders/road roller/other machines (~29). Backup: backup_labels/.

## Verified correct (kept)
- kagv2_camera_6.1001/6.102: 131 static boxes on yellow Gazprom truck crane — valid.
- rfcap Heavy_Equipment full-frame boxes: 147 frames, all truck/crawler cranes — valid.
- ar-group (lattice/tower crane masts/booms): mostly correct.
- IoU-with-crane-manipulator overlaps (3): night frames, borderline, deferred.

## Deferred to human review (review_queue.json, 21 items)
- 14 mocs-val holdout boxes (thin masts, machinery — holdout shared with BW-5 thread).
- 7 borderline: night iou_cm (11-13), drilling rigs (23, 60, 95, 99).

## Sync notes
- Other thread (BW-5/6/9) touches truck/dump truck labels; no MC edits there.
- v10 build will pick up cleaned labels.
