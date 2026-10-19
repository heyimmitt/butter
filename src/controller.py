'''
1. the control loop, independent of where congestion comes from and what drives the signal
    def run_controller(source, actuator, duration)
    source: anything with get_scores(sim_time) -> {"north": 0.42, ...}
        -- TraCI ground truth in sumo/run_experiment.py for now, video later
    actuator: anything with set_phase(phase, state) and step()
        -- phase is "NS"/"EW" (keys of phases.json), state is "green"/"yellow",
           step() advances exactly one second

2. each cycle
    congestion (from source) + wait time (tracked here) -> fuzzy_scorer.get_all_priorities()
    -> phase_aggregator.aggregate_phases() -> scheduler.compute_green_times()
    then run each phase's green + yellow in turn through the actuator

3. decision log
    run_controller() returns one record per cycle with every intermediate value,
    so any green time can be traced back to the congestion scores that produced it
'''


from fuzzy_scorer import load_fuzzy_sets, get_all_priorities
from phase_aggregator import load_phase_pairs, aggregate_phases
from scheduler import load_scheduler_config, compute_green_times


def run_controller(source, actuator, duration):
    """
    source: has get_scores(sim_time) -> {approach: congestion score 0-1}
    actuator: has set_phase(phase, state) and step()
    duration: total seconds to run

    Returns a list of per-cycle decision records:
    [{"time": 0, "congestion": {...}, "wait_times": {...}, "priorities": {...},
      "phase_priorities": {...}, "green_times": {...}}, ...]
    """
    fuzzy_sets = load_fuzzy_sets()
    phase_pairs = load_phase_pairs()
    scheduler_config = load_scheduler_config()
    yellow_time = scheduler_config["yellow_time"]

    approaches = [approach for pair in phase_pairs.values() for approach in pair]

    # wait_time = seconds since this approach last had a green
    last_green_time = {approach: 0 for approach in approaches}
    sim_time = 0
    decisions = []

    def run_for(seconds):
        nonlocal sim_time
        for _ in range(seconds):
            if sim_time >= duration:
                break
            actuator.step()
            sim_time += 1

    while sim_time < duration:
        congestion_scores = source.get_scores(sim_time)
        wait_times = {approach: sim_time - last_green_time[approach] for approach in approaches}

        priorities = get_all_priorities(congestion_scores, wait_times, fuzzy_sets)
        phase_priorities = aggregate_phases(priorities, phase_pairs)
        green_times = compute_green_times(phase_priorities, scheduler_config)

        decisions.append({
            "time": sim_time,
            "congestion": congestion_scores,
            "wait_times": wait_times,
            "priorities": priorities,
            "phase_priorities": phase_priorities,
            "green_times": green_times,
        })

        for phase in phase_pairs:
            actuator.set_phase(phase, "green")
            for approach in phase_pairs[phase]:
                last_green_time[approach] = sim_time
            run_for(green_times[phase])

            actuator.set_phase(phase, "yellow")
            run_for(yellow_time)

    return decisions
