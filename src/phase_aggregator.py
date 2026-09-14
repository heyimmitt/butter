'''
1. load phase pairing config
    def load_phase_pairs(json_config_file)
    read phases.json -- gives us {"NS": ["north", "south"], "EW": ["east", "west"]}

2. aggregate per-approach priorities into per-phase priorities
    def aggregate_phases(priorities, phase_pairs)
    for each phase, take the max of its paired approaches' priority scores --
    a jammed approach's urgency shouldn't get diluted just because it shares
    a phase with a lighter cross-approach
'''


import json


def load_phase_pairs(config_path="config/phases.json"):
    """
    returns something like {"NS": ["north", "south"], "EW": ["east", "west"]}
    """
    with open(config_path) as f:
        return json.load(f)


def aggregate_phases(priorities, phase_pairs):
    """
    priorities: {"north": 0.71, "south": 0.42, "east": 0.3, "west": 0.55} from get_all_priorities()
    phase_pairs: {"NS": ["north", "south"], "EW": ["east", "west"]} from load_phase_pairs()

    Returns {"NS": 0.71, "EW": 0.55} -- max (not average) of each phase's paired approaches,
    deliberately, so one jammed approach isn't diluted by a lighter cross-approach.
    """
    return {
        phase: max(priorities[approach] for approach in approaches)
        for phase, approaches in phase_pairs.items()
    }


if __name__ == "__main__":
    # Quick manual sanity check -- replace with real per-approach priorities when
    # all 4 approaches' ROIs exist; for now this is fake data covering all 4 directions
    phase_pairs = load_phase_pairs()
    fake_priorities = {"north": 0.71, "south": 0.42, "east": 0.3, "west": 0.55}
    print(aggregate_phases(fake_priorities, phase_pairs))
