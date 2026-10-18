'''
Runs the SUMO intersection in one of two modes and reports basic results:

  --mode fixed     lets SUMO's own default fixed-time tlLogic program run untouched
                    (the baseline: 42s NS green / 3s yellow / 42s EW green / 3s yellow)
  --mode adaptive   drives the traffic light ourselves every cycle:
                    query TraCI for per-approach vehicle counts/occupancy (standing in
                    for YOLO+density_scorer, since there's no camera footage in a sim)
                    -> fuzzy_scorer.get_all_priorities() -> phase_aggregator.aggregate_phases()
                    -> scheduler.compute_green_times() -> apply via traci.trafficlight.setPhase()

Both modes write a tripinfo XML (each vehicle's total waiting time + trip completion),
which we parse afterward for avg waiting time and throughput -- the actual comparison numbers.

Run from the project root: python3 sumo/run_experiment.py --mode fixed
'''

import argparse
import os
import sys
import xml.etree.ElementTree as ET

import traci

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from fuzzy_scorer import load_fuzzy_sets, get_all_priorities
from phase_aggregator import load_phase_pairs, aggregate_phases
from scheduler import load_scheduler_config, compute_green_times


SUMO_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(SUMO_DIR, "network.sumocfg")
TLS_ID = "C"

APPROACH_EDGES = {"north": "N_in", "south": "S_in", "east": "E_in", "west": "W_in"}
MAX_EXPECTED_COUNT = 15  # rough "edge is basically full" vehicle count for a single 200m lane

# link indices in the default netconvert-generated tlLogic (see sumo/network.net.xml)
GREEN_PHASE = {"NS": 0, "EW": 2}
YELLOW_PHASE = {"NS": 1, "EW": 3}

SIM_DURATION = 1800  # seconds, matches routes.rou.xml flow begin/end


def get_congestion_scores():
    """
    TraCI stand-in for get_all_lane_scores() -- SUMO already knows ground-truth
    vehicle count and occupancy per edge, no YOLO/density_scorer needed here.
    Same blend logic as density_scorer.compute_congestion_score() though:
    0.5 * occupancy_ratio + 0.5 * count_ratio.

    Returns {"north": 0.42, "south": 0.31, ...}
    """
    scores = {}
    for approach, edge_id in APPROACH_EDGES.items():
        count = traci.edge.getLastStepVehicleNumber(edge_id)
        count_ratio = min(count / MAX_EXPECTED_COUNT, 1.0)

        occupancy_ratio = traci.edge.getLastStepOccupancy(edge_id) / 100.0
        occupancy_ratio = min(occupancy_ratio, 1.0)

        scores[approach] = round(0.5 * occupancy_ratio + 0.5 * count_ratio, 4)
    return scores


def run_fixed(tripinfo_path):
    """Baseline: don't touch the traffic light at all, let the default program run."""
    traci.start(["sumo", "-c", CONFIG_FILE, "--tripinfo-output", tripinfo_path,
                 "--no-step-log", "true", "--duration-log.disable", "true"])

    for _ in range(SIM_DURATION):
        traci.simulationStep()

    traci.close()


def set_phase(phase_index):
    """
    setPhase alone keeps the default program's duration for that phase (42s green),
    so SUMO would advance on its own mid-green whenever we ask for longer than that.
    Pinning the duration to the whole sim length means only our loop ever switches phases.
    """
    traci.trafficlight.setPhase(TLS_ID, phase_index)
    traci.trafficlight.setPhaseDuration(TLS_ID, SIM_DURATION)


def run_adaptive(tripinfo_path):
    """Our system: recompute priorities every cycle and drive the light ourselves."""
    traci.start(["sumo", "-c", CONFIG_FILE, "--tripinfo-output", tripinfo_path,
                 "--no-step-log", "true", "--duration-log.disable", "true"])

    fuzzy_sets = load_fuzzy_sets()
    phase_pairs = load_phase_pairs()
    scheduler_config = load_scheduler_config()
    yellow_time = scheduler_config["yellow_time"]

    # wait_time = seconds since this approach last had a green -- tracked here since
    # this is the actual scheduler loop, the piece that was missing before
    last_green_time = {approach: 0 for approach in APPROACH_EDGES}
    sim_time = 0

    while sim_time < SIM_DURATION:
        congestion_scores = get_congestion_scores()
        wait_times = {approach: sim_time - last_green_time[approach] for approach in APPROACH_EDGES}

        priorities = get_all_priorities(congestion_scores, wait_times, fuzzy_sets)
        phase_priorities = aggregate_phases(priorities, phase_pairs)
        green_times = compute_green_times(phase_priorities, scheduler_config)

        for phase in ("NS", "EW"):
            set_phase(GREEN_PHASE[phase])
            for approach in phase_pairs[phase]:
                last_green_time[approach] = sim_time

            for _ in range(green_times[phase]):
                if sim_time >= SIM_DURATION:
                    break
                traci.simulationStep()
                sim_time += 1

            set_phase(YELLOW_PHASE[phase])
            for _ in range(yellow_time):
                if sim_time >= SIM_DURATION:
                    break
                traci.simulationStep()
                sim_time += 1

    traci.close()


def summarize(tripinfo_path):
    """Parses the tripinfo XML and returns (avg_waiting_time, throughput)."""
    root = ET.parse(tripinfo_path).getroot()
    trips = root.findall("tripinfo")

    if not trips:
        return 0.0, 0

    waiting_times = [float(t.get("waitingTime")) for t in trips]
    avg_waiting_time = sum(waiting_times) / len(waiting_times)
    throughput = len(trips)

    return avg_waiting_time, throughput


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fixed", "adaptive"], required=True)
    args = parser.parse_args()

    tripinfo_path = os.path.join(SUMO_DIR, f"tripinfo_{args.mode}.xml")

    if args.mode == "fixed":
        run_fixed(tripinfo_path)
    else:
        run_adaptive(tripinfo_path)

    avg_waiting_time, throughput = summarize(tripinfo_path)
    print(f"[{args.mode}] avg waiting time: {avg_waiting_time:.2f}s | vehicles completed: {throughput}")
