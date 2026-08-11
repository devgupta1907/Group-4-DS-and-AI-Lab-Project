"""
Parse promptfoo's results.json (from `promptfoo eval -o results.json`)
and print a clean pass/fail summary.

Usage:
    python get_results.py
    python get_results.py path/to/results.json
"""

import json
import sys


def get_final_results(results_path: str = "results.json") -> dict:
    """
    Read a promptfoo results.json file and return a summary dict:
    {
        "total": int,
        "passed": int,
        "failed": int,
        "pass_rate": float,        # 0-100
        "failures": [              # details for each failed case
            {
                "description": str,
                "vars": dict,
                "error": str | None,
                "output": Any,
            },
            ...
        ],
    }
    """
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # promptfoo's results.json nests everything under results.results
    results = data.get("results", {}).get("results", [])
    if not results:
        # older/newer promptfoo versions sometimes put it at the top level
        results = data.get("results", [])

    total = len(results)
    passed = 0
    failures = []

    for r in results:
        # promptfoo marks each row's outcome under different keys depending
        # on version; check the common ones.
        success = r.get("success")
        if success is None:
            success = (r.get("gradingResult") or {}).get("pass")

        test_vars = r.get("vars", {})
        description = r.get("testCase", {}).get("description") or r.get(
            "description", "(no description)"
        )

        if success:
            passed += 1
        else:
            error_msg = r.get("error")
            if not error_msg:
                grading = r.get("gradingResult") or {}
                error_msg = grading.get("reason")

            failures.append(
                {
                    "description": description,
                    "vars": test_vars,
                    "error": error_msg,
                    "output": r.get("response", {}).get("output")
                    if isinstance(r.get("response"), dict)
                    else r.get("output"),
                }
            )

    failed = total - passed
    pass_rate = round((passed / total) * 100, 1) if total else 0.0

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "failures": failures,
    }


def print_summary(summary: dict) -> None:
    print("=" * 50)
    print("PROMPTFOO EVAL RESULTS")
    print("=" * 50)
    print(f"Total:     {summary['total']}")
    print(f"Passed:    {summary['passed']}")
    print(f"Failed:    {summary['failed']}")
    print(f"Pass rate: {summary['pass_rate']}%")

    if summary["failures"]:
        print("\n--- Failed cases ---")
        for i, f in enumerate(summary["failures"], 1):
            print(f"\n{i}. {f['description']}")
            print(f"   vars:  {f['vars']}")
            if f["error"]:
                print(f"   error: {f['error']}")
            if f["output"] is not None:
                out_str = json.dumps(f["output"])[:300]
                print(f"   output: {out_str}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "results.json"
    summary = get_final_results(path)
    print_summary(summary)