import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_analyzer_counts_multimodal_calls_and_refuses_silent_free_calls(tmp_path) -> None:
    baseline = tmp_path / "omega.jsonl"
    alpha = tmp_path / "alpha.jsonl"
    rates = tmp_path / "rates.json"

    baseline.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "node_role": "resident",
                        "model": "mm",
                        "input_tokens": 1000,
                        "output_tokens": 100,
                    }
                ),
                json.dumps(
                    {
                        "node_role": "resident",
                        "model": "mm",
                        "input_tokens": 1000,
                        "output_tokens": 100,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    alpha.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "node_role": "multimodal_ingress",
                        "model": "mm",
                        "input_tokens": 500,
                        "output_tokens": 100,
                    }
                ),
                json.dumps(
                    {
                        "node_role": "resident",
                        "model": "text",
                        "input_tokens": 700,
                        "output_tokens": 100,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rates.write_text(
        json.dumps(
            {
                "models": {
                    "mm": {"input_per_million": 10.0, "output_per_million": 20.0}
                }
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "benchmarks" / "analyze.py"),
            "--baseline",
            str(baseline),
            "--alpha",
            str(alpha),
            "--rates",
            str(rates),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)

    assert report["alpha"]["multimodal_calls"] == 1
    assert report["baseline"]["multimodal_calls"] == 0
    assert report["alpha"]["unpriced_calls"] == 1
    assert report["alpha"]["estimated_cost_usd"] is None
    assert report["alpha"]["partial_estimated_cost_usd"] is not None
    assert report["alpha_minus_baseline"]["estimated_cost_usd"] is None
