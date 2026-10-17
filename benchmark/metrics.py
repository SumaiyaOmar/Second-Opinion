"""Transparent rates with denominators; execution errors are never abstentions."""


DEFINITIONS = {
    "error_detection_rate": "Non-control labeled errors with a completed non-Supported prediction and non-null detected error / all attempted labeled errors.",
    "false_alarm_rate": "Clean controls not completed as Supported with no detected error / all attempted clean controls; execution failures count as alarms.",
    "final_status_accuracy": "Exact final-status matches / all attempted cases; execution errors are incorrect.",
    "correct_abstention_rate": "Completed Inconclusive predictions / all attempted should_abstain cases; API failures are not abstentions.",
    "rank1_driver_accuracy": "Exact top driver matches / attempted cases with a non-null expected_driver.",
    "per_error_class_accuracy": "Exact status accuracy within each case_type, including clean controls.",
}


def score_row(metadata, prediction, variant):
    completed = prediction["execution_status"] == "completed"
    return {"case_id": metadata["case_id"], "split": metadata["split"], "variant": variant,
            "expected": dict(metadata), "prediction": prediction,
            "correct": completed and prediction["predicted_status"] == metadata["expected_status"],
            "error_type_correct": completed and prediction["detected_error_type"] == metadata["expected_error_type"],
            "driver_correct": None if metadata["expected_driver"] is None else (
                completed and prediction["predicted_driver"] == metadata["expected_driver"])}


def summarize(rows):
    attempted = [row for row in rows if row["prediction"]["execution_status"] not in {"not_run", "mapping_required"}]
    errors = [r for r in attempted if r["expected"]["expected_error_type"] is not None]
    clean = [r for r in attempted if r["expected"]["is_clean_control"]]
    abstain = [r for r in attempted if r["expected"]["should_abstain"]]
    drivers = [r for r in attempted if r["expected"]["expected_driver"] is not None]
    def completed(row):
        return row["prediction"]["execution_status"] == "completed"
    counts = {
        "error_detection_rate": [sum(completed(r) and r["prediction"]["predicted_status"] != "Supported" and r["prediction"]["detected_error_type"] is not None for r in errors), len(errors)],
        "false_alarm_rate": [sum(not (completed(r) and r["prediction"]["predicted_status"] == "Supported" and r["prediction"]["detected_error_type"] is None) for r in clean), len(clean)],
        "final_status_accuracy": [sum(r["correct"] for r in attempted), len(attempted)],
        "correct_abstention_rate": [sum(completed(r) and r["prediction"]["abstained"] is True for r in abstain), len(abstain)],
        "rank1_driver_accuracy": [sum(r["driver_correct"] is True for r in drivers), len(drivers)],
    }
    per_class = {}
    for kind in sorted({r["expected"]["case_type"] for r in attempted}):
        group = [r for r in attempted if r["expected"]["case_type"] == kind]
        per_class[kind] = {"correct": sum(r["correct"] for r in group), "cases": len(group),
                           "accuracy": sum(r["correct"] for r in group) / len(group)}
    return {
        "cases": len(rows), "attempted": len(attempted),
        "completed": sum(completed(r) for r in attempted),
        "execution_errors": sum(r["prediction"]["execution_status"] == "error" for r in attempted),
        "not_run": sum(row["prediction"]["execution_status"] == "not_run" for row in rows),
        "mapping_required": sum(row["prediction"]["execution_status"] == "mapping_required" for row in rows),
        "metrics": {name: n / d if d else None for name, (n, d) in counts.items()},
        "metric_counts": counts, "per_error_class_accuracy": per_class,
        "failures": [{"case_id": r["case_id"], "expected_status": r["expected"]["expected_status"],
                      "predicted_status": r["prediction"]["predicted_status"],
                      "expected_driver": r["expected"]["expected_driver"],
                      "predicted_driver": r["prediction"]["predicted_driver"],
                      "execution_status": r["prediction"]["execution_status"],
                      "error_type_correct": r["error_type_correct"]}
                     for r in attempted if not r["correct"] or r["driver_correct"] is False or not r["error_type_correct"]],
    }
