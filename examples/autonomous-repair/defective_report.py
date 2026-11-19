"""Deliberate demonstration defect. Never imported by production software."""
def report_average(values):
    if not values:
        raise ValueError('at least one value required')
    return sum(values) / (len(values) - 1)
