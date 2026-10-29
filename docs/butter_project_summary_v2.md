# Butter — Project Chat Summary (updated)

## What this chat is about

This is the working chat for **Butter**, Anoushka Basak's (24BAI0153) AI course project: a density-aware adaptive traffic light system. The chat covers architecture planning, a pivot from classical CV to ML-based detection, an extensive Docker debugging/learning session, building the fuzzy inference engine design, identifying and speccing a density-scoring gap, and the start of implementing that density scorer. Anoushka has no prior ML experience, wants concepts explained thoroughly before touching code, prefers writing implementation herself once she understands the logic, and wants honest tradeoff-based answers over reassurance. This summary excludes a later abstract-rewrite and Word-report-generation request/response, per explicit instruction, but includes everything up through a request for 10 relevant research papers.

## Project premise and evolution

**Original abstract:** classical CV only (no ML) — MOG2 background subtraction + contour/blob detection, weighted priority scheduling, SUMO simulation testing, evaluated against a fixed-time baseline.

**Key pivot:** her teacher approved using ML. She switched detection from classical CV to YOLOv8 (via `ultralytics`), since classical CV has real weaknesses (occlusion, lighting/shadow sensitivity, camera-angle fragility) that pretrained detectors handle better. The fuzzy inference layer and weighted priority scheduler remain non-ML by design, preserving genuine intellectual content beyond "just calling a detector."

**Genuine use case discussion:** concluded the underlying problem (fixed-time signal inefficiency) is real and camera-based adaptive retrofit is a real deployed pattern; the project isn't novel research but is a legitimate engineering synthesis project, appropriate for coursework.

**Project renamed "Butter"** (tagline: "No jam.") — a README.md was already created and delivered earlier (not repeated in this summary since it predates the excluded portion's context but remains valid/up to date except its status checklist).

## Architecture (current plan)

```
Per-approach video feed
    ↓
YOLO detection (fine-tuning on BMD-45 deferred)
    ↓
Density scorer (count + occupied area → congestion score) — IN PROGRESS, being wired up now
    ↓
Fuzzy inference engine (congestion + wait time → priority weight) — DESIGNED, not yet coded
    ↓
Phase-level aggregation (max of paired approaches) — DESIGNED
    ↓
Scheduler (weighted priority + min-time floor) — NOT YET BUILT
    ↓
Signal controller (TraCI → SUMO) — NOT YET BUILT
    ↓
Evaluator (wait time / throughput vs. fixed-time baseline) — NOT YET BUILT
↺ repeats every control cycle
```

**Important terminology correction made in this chat:** what was initially called "lanes" in diagrams/config is actually **approaches** — this is a standard 4-way intersection with one approach per direction (North, South, East, West), not multiple lanes per road (Indian roads don't have functionally meaningful lane discipline; "lanes" colloquially means separate roads running the same direction). North and South approaches share one signal phase (NS-green/EW-red), East and West share the other phase, alternating — never overlapping. `lanes.json` should conceptually be understood/renamed as approach data going forward, though the literal filename hasn't been changed yet.

**Phase aggregation decision:** when combining each phase's two paired approaches' fuzzy priority outputs into one phase priority, **max (not average) was chosen deliberately** — directly justified by Anoushka's original real-world motivation (a jammed road shouldn't have its urgency diluted by a lighter cross-approach just because they share a phase). Trade-off noted: max makes the system more sensitive to single-approach detection noise/spikes than average would be; a rolling average of congestion scores over recent cycles was suggested as a future robustness improvement, not yet implemented.

## Fuzzy inference engine — full design (not yet coded)

Requested and delivered as pure logic/concepts, no code, since Anoushka wants to write this herself.

**Inputs:** congestion score (0–1, from density scorer) and wait-time-since-last-green (0–~90s) — the second input added specifically for fairness, so a moderately-busy-every-cycle approach doesn't get starved by approaches that are only occasionally very busy.

**Fuzzy sets:** low/medium/high for both inputs; output priority uses five levels (very low/low/medium/high/very high) for finer scheduling granularity.

**Rule base:** a 3×3 grid (9 rules minimum) mapping congestion × wait-time combinations to priority levels; fairness shows up in mixed cases (e.g., low congestion + long wait pulled up to medium, not left at very low).

**Membership function representation (key implementation idea):** use one generic 4-point `(a, b, c, d)` trapezoidal shape for every set — triangles are `b=c`, left/right "shoulder" shapes (e.g., low-congestion, high-congestion) are special cases with `a=b` or `c=d`. Only one `membership(x, a, b, c, d)` function is needed, not separate code per shape type.

**Suggested starting numeric boundaries** (first-guess, explicitly tunable later against real SUMO cycle data):
- Congestion: low (0,0,0,0.4), medium (0.2,0.5,0.5,0.8), high (0.6,1,1,1)
- Wait time: short (0,0,0,30), medium (15,45,45,75), long (60,90,90,90)

**Mamdani-style process explained conceptually:** fuzzification (compute membership degrees for both inputs per approach) → rule evaluation (each rule fires at strength = min of its two input memberships) → aggregation (max across all fired rules' clipped output shapes) → defuzzification (centroid method → one crisp priority number) → repeat independently per approach per cycle → feed into phase aggregation, then the scheduler.

**Config storage decision:** fuzzy set boundaries (like lane/approach ROI coordinates) should live in a separate config file, not hardcoded — same reasoning as below. A `config/fuzzy_sets.json` was named as the natural future file (not yet created — this came up when Anoushka asked "what is fuzzy_sets.json?" after seeing it referenced, and it was clarified as a not-yet-existing placeholder, not something already built).

**No file/serialization needed to pass YOLO output to the fuzzy engine or density scorer at runtime** — it's just in-memory Python data structures (a dict per cycle). A file-based intermediate format isn't required for the pipeline to function, though structuring the in-memory dict cleanly (e.g., `{approach: {count, occupancy}}`) is good practice for later evaluator logging and independent module testing.

## Critical gap identified and resolved via design (density scorer)

Anoushka correctly identified that **no density scorer existed at all** — the pipeline only had YOLO producing raw boxes, nothing turning boxes into a congestion score. This was treated as a good catch, not a setback, and became the actual next build priority, ahead of the fuzzifier itself (since the fuzzifier needs this as input).

**Full logic specified (explained twice — once abstractly, once re-explained with a concrete worked numeric example and a diagram, after Anoushka said the first explanation didn't fully land):**

1. **Define ROI polygons per approach** — manually mark pixel coordinates of each approach's boundary on a still frame from test footage, once per camera setup.
2. **Get each YOLO box's centroid** — midpoint of (x1,y1)–(x2,y2) box corners. (Also separately clarified: YOLO's `xyxy` box format stores top-left and bottom-right *corner coordinates*, not width/height or side lengths — width/height are derived via subtraction.)
3. **Point-in-polygon test** — check whether each box's centroid falls inside a given approach's polygon (standard ray-casting algorithm; not implemented by hand, done via a library call). Boxes matching no polygon are discarded.
4. **Aggregate per approach** — count of matched boxes, and total occupied area (sum of box areas).
5. **Normalize into a 0–1 congestion score** — occupancy ratio (occupied area ÷ polygon area, naturally 0–1) and count ratio (count ÷ an assumed max-expected-count, capped at 1), blended via a weighted average (default suggested: 0.5/0.5, adjustable) into the final congestion score per approach per frame.

**Actual code for this was written and delivered** (`src/density.py`) once Anoushka became too tired to write it herself late at night, with her explicit plan to read/understand it fully rather than blindly copy, and to practice git revert/rollback the next day as a deliberate learning exercise. Functions included: `load_lane_polygons()` (loads `config/lanes.json` into Shapely `Polygon` objects), `get_centroid()`, `get_box_area()`, `assign_to_lanes()` (point-in-polygon assignment using Shapely), `compute_congestion_score()` (blends count_ratio and occupancy_ratio), and `get_all_lane_scores()` (top-level per-frame function). Added `shapely` as a new dependency (not yet in `requirements.txt` at time of writing).

**Density scorer has since been tested and is reported working.** It was subsequently wired to actual YOLO output: `results[0].boxes.xyxy.cpu().numpy().tolist()` converts Ultralytics' tensor output into plain `(x1,y1,x2,y2)` lists that `get_all_lane_scores()` expects. This connection code was written into a renamed/restructured file.

**File restructuring:** `test.py` was renamed to `src/detection.py` via `git mv`, restructured from a top-to-bottom script into a reusable `get_frame_scores(source, classes, conf)` function (so `main.py` can call it repeatedly per cycle later), guarded with `if __name__ == "__main__":` so importing the module doesn't trigger an automatic test run. Requires an `__init__.py` (can be empty) in `src/` for the `from src.density import ...` style imports to work. A commit was made and its message reviewed/refined: settled on `feat: connect YOLO detection output to density scorer` (or the two-part variant `feat: add density scorer, wire up YOLO detection pipeline`), continuing her established Conventional Commits prefix convention (`feat:`, `chore:`, etc.).

## Config file decisions

- **Lane/approach ROI coordinates** — decided to store as JSON (`config/lanes.json`), not `.env` (wrong tool for structured/nested data; `.env` is for simple key-value strings). Format: `{"north": [[x,y],[x,y],...], "south": [...]}`. Loaded via `json.load()` and converted to Shapely polygons in `density.py`.
- **`config/` folder location** — lives at project root, as a peer of `src/`, `data/`, `docs/` (not nested inside `src/`, since it's data/tuning-config, not logic).
- **Decision to commit `config/` to git** (unlike `data/`, which stays gitignored) — since config values are small, human-readable, and represent tuning history worth tracking/rolling back, unlike large binary datasets/weights.
- **How to find pixel coordinates for ROI polygons** — three methods discussed: (A) extract a frame via `ffmpeg -i test_clip.webm -vframes 1 frame.jpg`, open in GIMP, read cursor position from the status bar; (B) a small OpenCV mouse-click script (`cv2.setMouseCallback`) that prints exact `(x,y)` coordinates on click — this was the recommended method, and was successfully used; (C) rough eyeballing in any image viewer showing dimensions, least precise. A real bug was hit and fixed here: `coord_finder.py`'s `cv2.imread()` failed silently due to a doubled-up relative path (script run from inside `data/samples/` while the path string also included `data/samples/`), producing a confusing `imshow` assertion error rather than a clear "file not found" — fixed by correcting the relative path, with a suggested defensive check (`if img is None: raise FileNotFoundError(...)`) added for future clarity.

## Git — mishap and recovery

Anoushka attempted to practice `git revert` for a rollback learning exercise but misunderstood its behavior (thought it would restore code to a past commit's state, like a hard reset) and accidentally ran `git revert c2931eb` (the Docker/restructure commit) without an actual prior revert existing yet to undo — this created a new commit (`a858185`) that stripped out Dockerfile, requirements.txt, docs/abstract.pdf, and restored old scattered files, sitting on top of (not destroying) her density-scorer commit (`906e4d5`), which remained intact underneath. Resolution guidance given: check `git status` to see whether `a858185` was already pushed; if not pushed, `git reset --hard 906e4d5` (safe, since discarding local-only history); if already pushed, `git revert a858185` instead (adds a corrective commit rather than rewriting shared history) — outcome of which path she took was not confirmed in this chat.

**General git concepts reinforced:** `git commit` is required after `git add` before a push has anything to send (root cause of an earlier "src refspec main does not match any" error); `git revert <hash>` creates a new commit undoing changes (safe post-push, non-destructive) vs. `git reset --hard <hash>` which rewinds the branch pointer and discards subsequent history (fine pre-push on a solo project, risky after pushing).

## Python syntax explained (beginner-level, requested explicitly)

- **Dict comprehension** — `{lane: Polygon(points) for lane, points in raw.items()}` explained as shorthand for a 3-line for-loop building a new dict; broken into `.items()` (key-value pair iteration), tuple unpacking into `lane`/`points`, and the `{key: value for ...}` construction syntax.
- **`with open(...) as f:`** — explained as a "context manager": guarantees a resource (file) is properly closed afterward even if an error occurs inside the block, contrasted against manual `open()`/`close()` where forgetting `.close()` (or an error occurring before it) leaves the file open.
- **Tuple unpacking** — `x1, y1, x2, y2 = box` explained as assigning multiple values from a tuple to multiple variable names in one line, equivalent to four separate `box[0]`, `box[1]`, etc. assignments; connected back to the same mechanism used in the dict comprehension's `for lane, points in ...`.
- **Box coordinate format** — clarified that YOLO's `(x1,y1,x2,y2)` box format represents the **top-left and bottom-right corner pixel positions**, not side lengths; width/height are derived via subtraction (`x2-x1`, `y2-y1`), used directly in `get_box_area()`.

## Docker session — full issue log (already resolved; consolidated summary)

Anoushka deliberately integrated Docker into this project for hands-on fluency-building (explicit reasoning: "you learn a language by speaking it," wants Docker experience for projects that will actually see deployment, not just resume-listed) — validated as a reasonable, deliberate tradeoff despite adding overhead to a time-bound project, and this reasoning was explicitly re-affirmed as sound when she asked "was my reasoning valid?" the following day.

She also requested and received a deep mechanistic explanation of how Docker actually works (not surface-level theory she already had): namespaces (PID/NET/MNT/UTS/IPC/USER — control what a process can *see*) vs. cgroups (control what a process can *use* — CPU/memory limits) vs. union/overlay filesystem (how image layers stack via copy-on-write, why Dockerfile instruction ordering affects build-cache efficiency); image vs. container distinction (image = read-only layers + metadata; container = image + writable layer + namespaces + cgroup + running process); why containers start in milliseconds vs. VMs (no second kernel boot); and the associated security tradeoff (weaker isolation boundary than a hypervisor). A comparison diagram (VM architecture vs. Docker architecture) was generated to illustrate this. Was also given a few hands-on commands to directly observe namespaces/cgroups on her own machine (`docker run -it ubuntu ps aux`, `docker inspect ... | grep cgroup`, `unshare --pid --fork --mount-proc bash`).

**Full chronological issue log (13+ distinct problems hit and resolved):**

1. `git push` — "src refspec main does not match any": never committed after `git add`. Fixed with `git commit` before push.
2. `nvidia-smi` — "couldn't communicate with the NVIDIA driver": fresh Ubuntu install never had NVIDIA drivers (dual-boot doesn't inherit Windows' drivers). Fixed via `ubuntu-drivers devices` → `sudo apt install nvidia-driver-595-open` (tool-recommended version for her RTX 3050 Mobile) → reboot (with a note about a possible Secure Boot MOK enrollment prompt). Confirmed working: `nvidia-smi` showed the GPU, driver 595.84, CUDA 13.2.
3. Verified PyTorch already saw the GPU once the driver was installed: `torch.cuda.is_available()` → `True`, `torch.version.cuda` = 13.0 (local venv torch 2.13.0+cu130) — confirming the earlier `False` was purely due to the missing driver, not a PyTorch/pip issue.
4. First `docker build` — DNS resolution failure reaching pypi.org from inside the container: containers have their own isolated network namespace and weren't inheriting a working host DNS resolver (host uses systemd-resolved on a loopback address meaningless inside a container). Diagnosed via `docker run --rm busybox nslookup pypi.org` (confirmed timeout, even though pulling the busybox image itself worked fine via the daemon's own network access). Fixed by setting explicit DNS servers (`{"dns": ["8.8.8.8", "8.8.4.4"]}`) in `/etc/docker/daemon.json` and restarting the Docker daemon.
5. Build context transferring 5.56GB per build: no `.dockerignore` yet, so the entire venv/dataset/video files were being sent to the Docker daemon every build. Fixed by adding a proper `.dockerignore`.
6. `ImportError: libxcb.so.1` importing cv2 in-container: regular `opencv-python` expects GUI/X11 libraries absent from the minimal `python:slim` base image (and irrelevant, since a container has no display). Attempted fix: switch to `opencv-python-headless`.
7. Same error persisted after switching: `ultralytics` itself depends on regular `opencv-python`, silently reinstalling it regardless of what was specified directly. Fixed by explicitly uninstalling both opencv variants and reinstalling headless last in the same `RUN` command. Explicitly decided *against* just installing the missing GUI system libs instead, since `cv2.imshow()` wouldn't functionally work in a container anyway without X11 forwarding — that path was flagged as false reassurance, not real future flexibility.
8. `pip install` — `ReadTimeoutError` on `files.pythonhosted.org` mid-download: a large package (torch) download stalled, likely linked to her known wifi reliability issues (RTL8852BE chip, previously partially addressed with an ASPM fix), combined with pip's short default timeout. Fixed with `--default-timeout=120 --retries 5`.
9. Rebuilds taking a very long time on every small fix: every edit to the single combined `RUN pip install...` line invalidated Docker's cached layer for that entire instruction, forcing a full torch re-download on every iteration even when only the opencv part changed. Fixed by splitting torch into its own earlier, separate `RUN` layer.
10. Realized the container was downloading full CUDA-enabled torch despite having no GPU access at all (Docker containers need the separately-installed NVIDIA Container Toolkit + `--gpus all` for GPU access, neither set up). Decided to switch this Dockerfile to CPU-only torch (`--index-url https://download.pytorch.org/whl/cpu`) for now, keeping the CUDA build only in the local venv. Explicitly discussed and validated this choice when Anoushka pushed back wondering if she should "just keep it anyway" for future training — clarified that having the wheel installed doesn't grant GPU access without the toolkit regardless, so keeping it now provided no real benefit, only cost. Planned to revisit with proper GPU passthrough (NVIDIA Container Toolkit + `--gpus all`, possibly a separate `Dockerfile.train`) once actual fine-tuning starts.
11. Confirmed `torch`/`torchvision` needed removal from `requirements.txt` itself (leftover from an earlier `pip freeze` inside the CUDA venv) to prevent the CUDA build being silently reinstalled via the second RUN command.
12. `docker image prune` reported reclaiming 0B despite expecting leftover dangling images: she's using BuildKit, which stores cached layers in a separate build-cache store rather than loose `<none>` images (legacy builder behavior). `docker builder prune` was the correct command instead.
13. `docker system prune -a` (run to reclaim ~20GB disk space, successfully) also removed `butter:dev` itself and its entire build cache, since the command removes anything not backing a *currently running* container. Forced a full ~13-minute rebuild from scratch on the next build. Lesson: use `docker builder prune` (without `-a`) for routine cleanup; reserve `system prune -a` for deliberate full resets.
14. General Docker hygiene commands covered: `docker ps`, `docker stop <name>`/`docker rm <name>` (used to stop/remove a Portainer container from an unrelated earlier project), `docker volume ls`, `docker volume prune` (only removes unattached volumes — correctly left an active Oracle XE DB volume alone), `docker system df` (usage summary). Later, a leftover 242MB Portainer image (separate from its container) and a "why does build cache show 0B reclaimable" question were both clarified as expected/correct states, not bugs.
15. Clarified `docker build` produces an *image*; `docker run` produces a *container* — previously used a bit interchangeably.
16. Benign warning on a successful run: `user config directory '/root/.config/Ultralytics' is not writable, using '/tmp/Ultralytics'` — Ultralytics' built-in graceful fallback when running as root without a writable home config dir; not an error.
17. Container re-downloading `yolov8n.pt` on every run: `.dockerignore` correctly excludes `.pt` files from the build (avoiding image bloat), but this also means the weights never get baked into the image, so Ultralytics fetches them fresh every container start. **Not yet fixed** — planned fix is `COPY yolov8n.pt .` in the Dockerfile, deliberately deferred as non-blocking.
18. Detection running on Ultralytics' bundled demo images (`bus.jpg`, `zidane.jpg`) instead of actual test footage: `test.py`'s YOLO call was missing an explicit `source` argument. **This has since been fixed** as part of wiring up `src/detection.py` — the rewritten module now explicitly passes `source` to `model()`.
19. ~40 repeated "Downloading..." lines instead of one progress bar during the weights download: cosmetic TTY quirk (`docker run` without `-t` doesn't allocate a pseudo-terminal, so progress-bar redraws print as new lines); confirmed the download itself completed correctly as one file.

**Underlying throughline drawn out explicitly for her own understanding:** nearly all of these issues trace back to containers being deliberately isolated by design (own network namespace, own filesystem, no display) — most of the debugging was really about explicitly telling Docker what to bring *into* that isolation (DNS servers, dependencies, weight files, source paths) rather than assuming anything is inherited automatically from the host.

## Project structure (current, as of this point in the chat)

```
ai_project_name_tbd/          (repo name; project itself is "Butter")
├── Dockerfile
├── .dockerignore
├── .gitignore
├── requirements.txt           (needs `shapely` added — not yet confirmed done)
├── README.md
├── config/
│   └── lanes.json              (created; conceptually "approaches", not renamed yet)
├── main.py                    (not yet created)
├── src/
│   ├── __init__.py             (needed, may not yet exist — flagged as a requirement)
│   ├── density.py              (written, tested, working)
│   └── detection.py            (renamed from test.py; wired to call density.py)
├── data/
│   ├── models/                 (yolov8n.pt)
│   └── samples/                 (test_clip.webm, detection_check.jpg, frame.jpg, coord_finder.py)
├── docs/
│   └── abstract.pdf
└── myvenv/                     (local venv, gitignored)
```

**`.gitignore` (final agreed version from this chat):**
```
.vscode/*
myvenv/
__pycache__/
*.pyc
*.pyo
*.pt
*.pth
*.onnx
runs/
data/
.env
.DS_Store
Thumbs.db
```
(`config/` is deliberately NOT gitignored — committed intentionally, per the reasoning above.)

## Environment/hardware notes

- Local dev: Python 3.12.3 (Dockerfile base image was also updated to match, `python:3.12-slim`), venv at `myvenv/`.
- Machine: ASUS TUF A15, RTX 3050 Mobile, 4GB VRAM (flagged as tight for future training — small batch sizes, `imgsz=640` recommended once fine-tuning starts).
- Known wifi reliability issue: RTL8852BE chip, previously partially addressed with an ASPM fix — identified as the likely cause of the mid-download pip timeout during Docker builds.
- VS Code reinstalled via Debian package (not Snap) earlier in the project, causing a brief Pylance/interpreter-selection issue after installing `ultralytics` — resolved by re-selecting the venv interpreter and reloading VS Code. A later related prompt ("create a virtual environment to isolate dependencies?") from VS Code's Python extension was confirmed safe to accept.

## Context window / token usage question (tangential, answered)

Anoushka asked about context window limits and whether this chat had "too much context," partly triggered by momentarily misreading an old excerpted message as a hallucination about hitting a token limit (it wasn't — clarified as an ambiguous "pause" referring to sequencing the fuzzifier vs. density scorer work, unrelated to context/tokens). Answered: Claude Sonnet 5 supports a 1M token context window on paid plans in claude.ai, with automatic compaction at 500K tokens; this conversation is nowhere near either threshold. A prior ~3.5k-word chat summary file was estimated at roughly 4,500–5,000 tokens (~1.3 tokens/word), well under 1% of the 1M window — not a meaningful cost.

## Emotional/wellbeing conversation (context worth preserving)

Late at night, Anoushka expressed distress about not being able to "do it all" — classes, personal projects, coursework, DSA practice, quizzes, lab assessments — while skipping classes, doing minimum-effort studying, and feeling unable to focus on anything beyond low-effort content when tired. She initially believed a full day's Docker debugging session had happened "today" when it had actually happened 4 days prior, and that day's actual output was much lighter (just ROI coordinate-finding and design discussion) — this was acknowledged honestly rather than glossed over once she corrected the timeline, rather than continuing to reassure her that "today" had been highly productive. The pattern named (with her own prior context, referenced but not re-explained in full here) was that self-directed projects without external deadlines tend to stall for her compared to deadline-driven work, especially amid a concurrent recruiting cycle — framed as a scheduling/attention reality rather than a moral failing, with the suggestion to revisit the question of Butter's pace rested and separately from coursework/OA deadlines, rather than trying to resolve it at 4am.

## Research papers request (included, per instruction)

Ten research papers were sourced and delivered covering: fuzzy-logic-based adaptive signal control (several, spanning foundational work from the late 1970s through modern comparative studies against Q-learning/reinforcement learning), YOLO-based vehicle density estimation and adaptive signal systems (including a recent YOLOv11-based system and a YOLOv8 + kernel density estimation approach), and SUMO-integrated computer vision intersection analysis. Delivered as a 6-item link preview card plus 4 additional papers listed in text with links. Key framing given: several papers (the SUMO+CV integration paper, the YOLO+queue-density+wait-time paper, and the three-module YOLO system paper) validate Anoushka's overall architecture choice as an established, published pattern rather than something invented from scratch; the fuzzy-vs-Q-learning comparison paper was flagged as specifically useful for her deferred multi-intersection coordination future-work section, since current literature trends toward RL for multi-intersection coordination specifically.

## Immediate next steps (as of end of this excerpted portion)

1. Confirm `shapely` is added to `requirements.txt`.
2. Confirm `src/__init__.py` exists so `from src.density import ...` imports work correctly.
3. Continue marking ROI coordinates for the remaining three approaches (only one approach's coordinates exist so far).
4. Consider renaming `lanes.json`/related variable names from "lane" to "approach" terminology for clarity, given the earlier terminology correction (not yet done, purely cosmetic/organizational).
5. Build the fuzzy inference engine itself (`membership()` function first, then `fuzzify()`, then rule evaluation/aggregation/defuzzification) — fully spec'd, not yet started in code.
6. Build phase-level aggregation (max-based) once per-approach fuzzy outputs exist.
7. Build the weighted priority scheduler.
8. Deferred, tracked, not yet done: bake `yolov8n.pt` into the Docker image via `COPY`; BMD-45 fine-tuning; GPU passthrough for Docker training; multi-intersection coordination (likely RL-based per literature).
9. Consider creating `config/fuzzy_sets.json` when the fuzzy engine is actually implemented, following the same externalized-config pattern as `lanes.json`.

## Communication/working preferences observed (for continuity)

- Wants concepts explained before code; prefers writing implementation herself once she understands the logic, though will accept full code when genuinely too exhausted to write it herself (with explicit intent to read/understand rather than blindly copy).
- Appreciates direct, honest tradeoff analysis over reassurance, including being corrected when an earlier claim was wrong or imprecise (e.g., the "today was productive" framing was corrected once she clarified the actual timeline).
- Does not want scope creep turning this into a pure ML project or pure DevOps/infra project — wants the fuzzy inference/control-logic core to remain the centerpiece — but made a deliberate, informed exception to take on Docker overhead for learning purposes.
- Casual, low-flattery communication register; comfortable with technical depth (CSE background); appreciates puns/light humor when naturally occurring.
- Genuinely new to Python/programming fundamentals in places (asked for basic syntax explanations: dict comprehensions, context managers, tuple unpacking) despite strong CS theory background — comfortable asking "dumb question" style queries and should continue to be met without condescension.
- Works late into the night; multiple sessions have run past 3–4 AM IST, with visible fatigue affecting focus and mood.
