# -*- coding: utf-8 -*-
"""Construction-focused detector using the locally validated uisikdag YOLOv5 model."""
from __future__ import annotations
import json, sys
from pathlib import Path
import torch

LABEL_FIXES={"Dumb_truck":"dump truck","Bull_dozer":"bulldozer","Mobile_crane":"mobile crane","Roller":"road roller","Loader":"loader","Excavator":"excavator","Worker":"worker","Safety helmet":"safety helmet","Reflective vest":"vest"}

def main():
    args=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    import yolov5
    original=torch.load
    torch.load=lambda *a,**k: original(*a,**{**k,"weights_only":False})
    model=yolov5.load(args["weights"]); torch.load=original
    model.conf=float(args.get("conf",0.15))
    result=model(args["image"],size=640)
    detections=[]
    for *xyxy,conf,cls_id in result.pred[0].tolist():
        raw=str(model.names[int(cls_id)])
        detections.append({"label":LABEL_FIXES.get(raw,raw).lower(),"score":float(conf),"box":[float(v) for v in xyxy]})
    payload=json.dumps({"image":Path(args["image"]).name,"model":"uisikdag","detections":detections},ensure_ascii=False)
    output=Path(args["out"])
    temporary=output.with_name(output.name + ".tmp")
    temporary.write_text(payload,encoding="utf-8")
    temporary.replace(output)
if __name__=="__main__": main()
