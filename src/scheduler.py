'''
1. load scheduler config
    def load_scheduler_config(json_config_file)
    read scheduler.json -- gives us {"min_green": 10, "max_green": 60, "yellow_time": 3}

2. convert phase priorities into actual green-light durations
    def compute_green_times(phase_priorities, config)
    each phase's green time is scaled independently between min_green and max_green
    by its own priority (0-1) -- NOT normalized against the other phase's priority,
    so the min_green floor is always guaranteed no matter what the other phase needs
    (this is what prevents starvation)
'''


import json


def load_scheduler_config(config_path="config/scheduler.json"):
    """
    returns something like {"min_green": 10, "max_green": 60, "yellow_time": 3}
    """
    with open(config_path) as f:
        return json.load(f)


def compute_green_times(phase_priorities, config):
    """
    phase_priorities: {"NS": 0.71, "EW": 0.3} from aggregate_phases()
    config: {"min_green": 10, "max_green": 60, "yellow_time": 3} from load_scheduler_config()

    Returns {"NS": 45, "EW": 19} -- actual green durations in whole seconds,
    linearly scaled between min_green and max_green by each phase's priority.
    """
    min_green = config["min_green"]
    max_green = config["max_green"]
    return {
        phase: round(min_green + priority * (max_green - min_green))
        for phase, priority in phase_priorities.items()
    }


if __name__ == "__main__":
    # Quick manual sanity check
    config = load_scheduler_config()
    fake_phase_priorities = {"NS": 0.8, "EW": 0.2}
    print(compute_green_times(fake_phase_priorities, config))
