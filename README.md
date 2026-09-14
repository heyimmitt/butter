# Butter 

*No jam*

A density-aware adaptive traffic light system that replaces fixed-time signal cycles with real-time, vision-driven signal control — built without relying on hand-tuned thresholds for the decision logic.

## Overview

Fixed-time traffic signals waste green time on empty lanes and starve congested ones, because they don't know what's actually happening at the intersection. Butter watches each lane via camera feed, estimates vehicle density using object detection, and dynamically allocates green-light duration using a fuzzy inference system and weighted priority scheduling — aiming to reduce average wait time versus a fixed-cycle baseline.

## Tech Stack

| Component | Tool | Purpose |
|---|---|---|
| Detection | YOLOv8 (Ultralytics), fine-tuned on [BMD-45](https://huggingface.co/datasets/iisc-aim/BMD-45) | Per-lane vehicle detection, adapted for Indian traffic (autorickshaws, tempo-travellers, etc.) not covered by COCO |
| Fuzzy inference | Custom-built | Converts per-lane congestion scores into smooth priority weights instead of hard thresholds |
| Scheduling | Weighted priority scheduling | Converts priority weights into actual green-light durations, with a minimum time floor per lane to prevent starvation |
| Simulation | SUMO + TraCI | Controlled testing environment — generates traffic, applies signal timing changes, measures results |
| Core | Python, OpenCV, NumPy | Glue, image handling, math |
| Evaluation | Matplotlib / pandas | Wait-time and throughput comparison against fixed-time baseline |

## Architecture

```
Per-lane video feed
        ↓
YOLO detection (fine-tuned on BMD-45)
        ↓
Density scorer (count + occupied area → congestion score)
        ↓
Fuzzy inference engine (congestion → priority weight)
        ↓
Scheduler (weighted priority + min-time floor)
        ↓
Signal controller (TraCI pushes phase timing)
        ↓
Evaluator (logs wait time / throughput)
        ↺ repeats every control cycle
```

## Status

🚧 In progress. Currently working through:
- [x] Baseline YOLO detection sanity check (stock COCO weights)
- [x] Lane ROI assignment
- [ ] Fuzzy inference engine
- [ ] Weighted priority scheduler
- [ ] SUMO/TraCI integration
- [ ] Evaluation against fixed-time baseline
- [ ] Fine-tuning YOLOv8 on BMD-45 for Indian vehicle classes
- [ ] Multi-intersection coordination *(planned, later phase)*