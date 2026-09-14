'''
1. load fuzzy set boundaries
    def load_fuzzy_sets(json_config_file)
    read fuzzy_sets.json -- gives us {"congestion": {"low": [a,b,c,d], ...}, "wait_time": {...}, "priority": {...}}

2. generic trapezoidal membership function
    def membership(x, a, b, c, d)
    one function reused for every set shape (triangle = b==c, shoulder = a==b or c==d)

3. fuzzify one input value against all of its sets
    def fuzzify(value, sets)
    input: a single number (e.g. congestion score) + that variable's {set_name: (a,b,c,d)} dict
    output: {set_name: degree} for every set, e.g. {"low": 0.3, "medium": 0.7, "high": 0.0}

4. rule base -- the 3x3 grid mapping congestion x wait_time -> priority
    RULES = list of (congestion_set, wait_set, output_set) tuples
    fairness built in here: e.g. low congestion + long wait -> medium, not very_low

5. evaluate rules
    def evaluate_rules(congestion_degrees, wait_degrees, rules)
    each rule fires at strength = min(congestion_degrees[c], wait_degrees[w])  -- Mamdani AND
    if multiple rules point at the same output set, that output set's strength is the max over them -- Mamdani OR

6. aggregate + defuzzify
    def aggregate(rule_strengths, output_sets) -- combine fired/clipped output shapes into one curve
    def defuzzify(aggregated, universe_range) -- centroid method, sample the curve and take the weighted-average x

7. top-level per-approach / per-frame functions
    def get_priority(congestion_score, wait_time, fuzzy_sets) -- one approach, one cycle
    def get_all_priorities(congestion_scores, wait_times, fuzzy_sets) -- all approaches, one cycle
    mirrors get_all_lane_scores() in density_scorer.py -- {"north": 0.71, ...}
'''


import json


def load_fuzzy_sets(config_path="config/fuzzy_sets.json"):
    """
    returns something like:
    {
        "congestion": {"low": [0,0,0,0.4], "medium": [0.2,0.5,0.5,0.8], "high": [0.6,1,1,1]},
        "wait_time":  {"short": [...], "medium": [...], "long": [...]},
        "priority":   {"very_low": [...], "low": [...], "medium": [...], "high": [...], "very_high": [...]}
    }
    """
    with open(config_path) as f:
        return json.load(f)


def membership(x, a, b, c, d):
    """
    Generic trapezoidal membership function -- reused for every fuzzy set.
    a,b,c,d are the four x-coordinates of the trapezoid (rise from a->b, flat b->c, fall c->d).
    Triangle: b == c. Left shoulder: a == b. Right shoulder: c == d.

    Returns a degree between 0 and 1.
    """
    # TODO: handle x <= a or x >= d -> 0
    # TODO: handle the flat top, b <= x <= c -> 1
    # TODO: handle the rising edge a < x < b -> (x-a)/(b-a)
    # TODO: handle the falling edge c < x < d -> (d-x)/(d-c)
    # TODO: watch for division by zero when a==b (shoulder) or c==d (shoulder)
    pass


def fuzzify(value, sets):
    """
    value: a single number (e.g. one approach's congestion score, or its wait time)
    sets: this variable's {set_name: [a,b,c,d]} dict, straight from load_fuzzy_sets()

    Returns {set_name: degree} for every set in `sets`,
    e.g. {"low": 0.3, "medium": 0.7, "high": 0.0}
    """
    # TODO: call membership() once per set, collect into a dict
    pass


# Rule base: (congestion_set, wait_set) -> output priority level.
# Fairness is encoded here -- e.g. low congestion + long wait is pulled up to "medium",
# not left at "very_low", so an approach isn't starved just because it's rarely congested.
RULES = [
    ("low",    "short",  "very_low"),
    ("low",    "medium", "low"),
    ("low",    "long",   "medium"),
    ("medium", "short",  "low"),
    ("medium", "medium", "medium"),
    ("medium", "long",   "high"),
    ("high",   "short",  "medium"),
    ("high",   "medium", "high"),
    ("high",   "long",   "very_high"),
]


def evaluate_rules(congestion_degrees, wait_degrees, rules=RULES):
    """
    congestion_degrees: output of fuzzify() for congestion, e.g. {"low": 0.3, "medium": 0.7, "high": 0.0}
    wait_degrees: output of fuzzify() for wait_time
    rules: list of (congestion_set, wait_set, output_set) tuples

    Returns {output_set_name: strength} -- the firing strength for each of the 5 priority levels,
    after folding together every rule that points at the same output level (via max).
    """
    # TODO: for each (c_set, w_set, out_set) in rules:
    #   strength = min(congestion_degrees[c_set], wait_degrees[w_set])
    #   keep the max strength seen so far for out_set
    pass


def aggregate(rule_strengths, output_sets):
    """
    rule_strengths: {output_set_name: strength} from evaluate_rules()
    output_sets: {set_name: [a,b,c,d]} for the 5 priority levels, from load_fuzzy_sets()["priority"]

    Combines every output set's membership shape, clipped at its rule strength,
    into one aggregated curve (via max across sets, at each x).

    Returns something defuzzify() can sample -- e.g. a function of x, or a list of
    (x, degree) samples. Pick whichever representation makes defuzzify() cleanest.
    """
    # TODO
    pass


def defuzzify(aggregated, universe_range=(0, 1), steps=1000):
    """
    Centroid method: sample the aggregated curve across universe_range,
    return the weighted-average x -- the crisp priority value.
    """
    # TODO: sample x from universe_range[0] to universe_range[1] in `steps` increments
    # TODO: centroid = sum(x * degree) / sum(degree) across all samples
    pass


def get_priority(congestion_score, wait_time, fuzzy_sets):
    """
    Top-level -- call once per approach per cycle.

    congestion_score: 0-1 float from get_all_lane_scores() (density_scorer.py)
    wait_time: seconds since this approach last had a green
    fuzzy_sets: the full dict from load_fuzzy_sets()

    Returns a single float priority value.
    """
    # TODO: fuzzify(congestion_score, fuzzy_sets["congestion"])
    # TODO: fuzzify(wait_time, fuzzy_sets["wait_time"])
    # TODO: evaluate_rules(...) -> aggregate(...) -> defuzzify(...)
    pass


def get_all_priorities(congestion_scores, wait_times, fuzzy_sets):
    """
    congestion_scores: {"north": 0.42, ...} from get_all_lane_scores()
    wait_times: {"north": 12, ...}
    fuzzy_sets: the full dict from load_fuzzy_sets()

    Returns {"north": 0.71, ...} -- ready to feed phase aggregation.
    """
    # TODO: call get_priority() once per approach, collect into a dict
    pass


if __name__ == "__main__":
    # Quick manual sanity check -- replace with real congestion_scores/wait_times when ready
    fuzzy_sets = load_fuzzy_sets()
    fake_congestion = {"lane_a": 0.42}
    fake_wait_times = {"lane_a": 35}
    print(get_all_priorities(fake_congestion, fake_wait_times, fuzzy_sets))
