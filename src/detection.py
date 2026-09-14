from ultralytics import YOLO
from density_scorer import load_lane_polygons, get_all_lane_scores
from fuzzy_scorer import load_fuzzy_sets, get_all_priorities
from phase_aggregator import load_phase_pairs, aggregate_phases

model = YOLO('data/models/yolov8n.pt')
lane_polygons = load_lane_polygons()
fuzzy_sets = load_fuzzy_sets()
phase_pairs = load_phase_pairs()

# config/lanes.json only has "lane_a" marked so far (ROI for the other 3 approaches is
# still pending real footage) -- ASSUMING lane_a is "north" so phase aggregation has
# something to work with; correct this mapping once the other approaches are marked
# and lanes.json is renamed to real direction names.
LANE_TO_APPROACH = {"lane_a": "north"}
ALL_APPROACHES = ["north", "south", "east", "west"]


def get_frame_scores(source, classes=[2, 3, 5, 7], conf=0.5):
    """
    Runs detection on a frame/video and returns, per frame:
    - congestion scores (from density_scorer)
    - priority scores (from fuzzy_scorer)

    Returns (all_scores, all_priorities, all_phase_priorities), each a list of one
    {approach: value} / {phase: value} dict per frame.
    """
    results = model(source, classes=classes, conf=conf)

    all_scores = []
    all_priorities = []
    all_phase_priorities = []
    
    for frame_result in results:
        boxes = frame_result.boxes.xyxy.cpu().numpy().tolist()
        scores = get_all_lane_scores(boxes, lane_polygons)
        all_scores.append(scores)

        # wait_time isn't tracked anywhere yet -- that's the scheduler's job (time since
        # this approach last had a green), and the scheduler isn't built. Stubbed at 0 for
        # every approach so the fuzzifier can be wired up and tested end-to-end; swap this
        # out for real wait times once the scheduler exists.
        wait_times = {approach: 0 for approach in scores}
        priorities = get_all_priorities(scores, wait_times, fuzzy_sets)
        all_priorities.append(priorities)

        # remap from whatever's actually in lanes.json (just "lane_a" for now) onto real
        # direction names, defaulting the 3 unmarked approaches to 0 so phase aggregation
        # has all 4 keys to work with -- replace with real per-approach priorities once
        # all 4 ROIs exist
        full_priorities = {approach: 0 for approach in ALL_APPROACHES}
        for lane_name, priority in priorities.items():
            approach = LANE_TO_APPROACH.get(lane_name, lane_name)
            full_priorities[approach] = priority

        phase_priorities = aggregate_phases(full_priorities, phase_pairs)
        all_phase_priorities.append(phase_priorities)

    return all_scores, all_priorities, all_phase_priorities


if __name__ == "__main__":
    # lets you still run `python src/detection.py` directly for a quick manual test
    all_scores, all_priorities, all_phase_priorities = get_frame_scores('data/samples/test_clip.webm')
    print(f"last frame's congestion scores: {all_scores[-1]}")
    print(f"last frame's priority scores:   {all_priorities[-1]}")
    print(f"last frame's phase priorities:  {all_phase_priorities[-1]}")