# Butter 

*No jam*

A density-aware adaptive traffic light system that replaces fixed-time signal cycles with real-time, vision-driven signal control — using fuzzy inference instead of hard on/off thresholds for the decision logic.

## Overview

Fixed-time traffic signals waste green time on empty lanes and starve congested ones, because they don't know what's actually happening at the intersection. Butter watches each lane via camera feed, estimates vehicle density using object detection, and dynamically allocates green-light duration using a fuzzy inference system and priority-based scheduling — aiming to reduce average wait time versus a fixed-cycle baseline.

## Tech Stack

| Component | Tool | Purpose |
|---|---|---|
| Detection | YOLOv8 (Ultralytics) — stock COCO weights for now, fine-tuning on [BMD-45](https://huggingface.co/datasets/iisc-aim/BMD-45) planned | Per-lane vehicle detection, adapted for Indian traffic (autorickshaws, tempo-travellers, etc.) not covered by COCO |
| Lane assignment | Shapely | Point-in-polygon lane ROIs and lane area for occupancy |
| Fuzzy inference | Custom-built (Mamdani, centroid defuzzification) | Converts per-lane congestion + wait time into smooth priority weights instead of hard thresholds |
| Scheduling | Priority-scaled green times | Converts phase priorities into green-light durations between a min and max, with the min acting as a starvation floor |
| Simulation | SUMO + TraCI | Controlled testing environment — generates traffic, applies signal timing changes, measures results |
| Core | Python, OpenCV, NumPy | Glue, image handling, math |
| Evaluation | SUMO tripinfo output | Wait-time and throughput comparison against fixed-time baseline (plots planned) |

## Architecture

```
Per-lane video feed
        ↓
YOLO detection
        ↓
Density scorer (count + occupied area → congestion score per approach)
        ↓
Fuzzy inference engine (congestion + wait time → priority weight)
        ↓
Phase aggregator (max of paired approaches → NS / EW phase priority)
        ↓
Scheduler (priority → green time, min/max floor)
        ↓
Signal controller (TraCI pushes phase timing)
        ↓
Evaluator (logs wait time / throughput)
        ↺ repeats every control cycle
```

In simulation, the first two steps are replaced by SUMO's ground-truth per-edge vehicle counts and occupancy (there's no camera in a sim); everything from the fuzzy engine down is the same code. The camera path currently runs as far as phase priorities ([src/detection.py](src/detection.py)) and isn't yet wired to a signal controller.

## Layout

```
src/
  detection.py        YOLO → density → fuzzy → phase priorities, on a video clip
  density_scorer.py   lane ROI assignment + congestion score
  fuzzy_scorer.py     fuzzy inference engine
  phase_aggregator.py per-approach → per-phase priority
  scheduler.py        phase priority → green time
config/               lane ROIs, fuzzy set boundaries, phase pairs, scheduler limits
sumo/                 single-intersection network, routes, and run_experiment.py
test.py               stock-YOLO sanity check on one frame
```

## Running

```bash
pip install torch torchvision          # cpu or cuda build, your pick
pip install -r requirements.txt        # includes SUMO via eclipse-sumo

# simulation comparison (run from project root)
python sumo/run_experiment.py --mode fixed
python sumo/run_experiment.py --mode adaptive

# detection pipeline -- needs data/models/yolov8n.pt and data/samples/test_clip.webm (not in git)
python src/detection.py
```

Or with Docker, which runs the simulation comparison by default:

```bash
docker build -t butter .
docker run --rm butter
```

## Results so far

Single intersection, 30 simulated minutes, deliberately asymmetric demand (north 600 veh/h, others 150–200 veh/h), one run:

| Mode | Avg waiting time | Vehicles completed |
|---|---|---|
| Fixed-time (42s greens) | 12.89s | 535 |
| Adaptive | 7.17s | 536 |

Caveat: the fixed baseline uses SUMO's default 42s greens, which are long for this demand level, so part of the gain likely comes from shorter cycles alone. A tuned fixed-time or actuated baseline and multiple seeds are next.

## Status

🚧 In progress. Currently working through:
- [x] Baseline YOLO detection sanity check (stock COCO weights)
- [x] Lane ROI assignment logic
- [ ] Lane ROIs for all 4 approaches *(only one marked so far, pending real footage)*
- [x] Fuzzy inference engine
- [x] Phase aggregation
- [x] Priority scheduler with min-green floor
- [x] SUMO/TraCI integration
- [x] Evaluation against fixed-time baseline (single scenario)
- [ ] Stronger baselines (tuned fixed-time, SUMO actuated), multiple seeds, plots
- [ ] Wire the camera pipeline through to the scheduler/signal controller
- [ ] Fine-tuning YOLOv8 on BMD-45 for Indian vehicle classes
- [ ] Multi-intersection coordination *(planned, later phase)*
