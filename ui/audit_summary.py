"""Human-readable formatting of existing audit outputs, without recomputation."""

from ui.reveals import number
from ui.story import finite


def audit_summary(audit, mapping=None):
    values = audit.get("computed_values") or {}
    metric = str(audit.get("metric") or "metric")
    aggregation = (mapping or {}).get("aggregation")
    descriptor = {"mean": "average", "sum": "total"}.get(aggregation, "reported")
    difference = audit.get("difference")
    if all(finite(values.get(side)) for side in ("right", "left")) and finite(difference):
        direction = "increased" if difference > 0 else "decreased" if difference < 0 else "was unchanged"
        return (f"The {descriptor} {metric} {direction} from {number(values['right'])} to "
                f"{number(values['left'])}, a change of {difference:+,.6g}.")
    if finite(values.get("overall")):
        return f"The {descriptor} {metric} across the dataset was {number(values['overall'])}."
    limitations = audit.get("limitations") or []
    return str(limitations[0]) if limitations else "The calculation is incomplete. Review the computational receipt."
