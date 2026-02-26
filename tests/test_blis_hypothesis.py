"""
Tests for the BLIS router hypothesis integration (using openevolve.hypothesis core module).

Covers all 6 public functions:
  parse_hypotheses, test_hypotheses, load_ledger,
  update_ledger, generate_knowledge_base_summary, format_hypothesis_results
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from openevolve.hypothesis import (
    parse_hypotheses as _parse_hypotheses_raw,
    test_hypotheses as _test_hypotheses,
    load_ledger,
    update_ledger,
    generate_knowledge_base_summary,
    format_hypothesis_results,
)

# BLIS-specific valid metrics (matches examples/blis_router/evaluator.py)
VALID_METRICS = {
    "cache_warmup_e2e_ms",
    "load_spikes_e2e_ms",
    "multiturn_e2e_ms",
    "avg_e2e_ms",
    "avg_p95_ms",
}


def parse_hypotheses(code):
    """Convenience wrapper that passes BLIS VALID_METRICS."""
    return _parse_hypotheses_raw(code, valid_metrics=VALID_METRICS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SINGLE_HYPOTHESIS_GO = """\
package sim

// HYPOTHESIS-1: Queue-depth weighting reduces latency under bursty load
// MECHANISM-1: Prioritising instances with shorter queues avoids head-of-line blocking
// EXPECT-1: cache_warmup_e2e_ms < 200

func Route() {}
"""

MULTI_HYPOTHESIS_GO = """\
package sim

// HYPOTHESIS-1: Queue-depth weighting reduces latency under bursty load
// MECHANISM-1: Prioritising instances with shorter queues avoids head-of-line blocking
// EXPECT-1: cache_warmup_e2e_ms < 200

// HYPOTHESIS-2: Prefix caching improves TTFT for shared-prefix workloads
// MECHANISM-2: Routing to instances that already cached the prefix avoids redundant
//   computation of KV pairs, reducing time-to-first-token significantly for
//   requests sharing the same system prompt.
// EXPECT-2: load_spikes_e2e_ms < 150.5

func Route() {}
"""

INCOMPLETE_HYPOTHESIS_GO = """\
package sim

// HYPOTHESIS-3: Missing expect line
// MECHANISM-3: Something something

func Route() {}
"""

NO_HYPOTHESIS_GO = """\
package sim

// This code has no hypothesis comments at all.
func Route() {}
"""

INVALID_METRIC_GO = """\
package sim

// HYPOTHESIS-1: Bogus metric hypothesis
// MECHANISM-1: Uses a metric that does not exist
// EXPECT-1: totally_fake_metric < 100

func Route() {}
"""


class TestParseHypotheses(unittest.TestCase):
    """Tests for parse_hypotheses()."""

    def test_single_hypothesis(self):
        result = parse_hypotheses(SINGLE_HYPOTHESIS_GO)
        self.assertEqual(len(result), 1)
        h = result[0]
        self.assertEqual(h["id"], 1)
        self.assertEqual(h["claim"], "Queue-depth weighting reduces latency under bursty load")
        self.assertEqual(
            h["mechanism"],
            "Prioritising instances with shorter queues avoids head-of-line blocking",
        )
        self.assertEqual(h["metric"], "cache_warmup_e2e_ms")
        self.assertEqual(h["threshold"], 200.0)

    def test_multiple_hypotheses(self):
        result = parse_hypotheses(MULTI_HYPOTHESIS_GO)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[1]["id"], 2)
        self.assertEqual(result[1]["metric"], "load_spikes_e2e_ms")

    def test_no_hypotheses(self):
        result = parse_hypotheses(NO_HYPOTHESIS_GO)
        self.assertEqual(result, [])

    def test_incomplete_hypothesis_excluded(self):
        """Missing EXPECT line means the hypothesis is skipped."""
        result = parse_hypotheses(INCOMPLETE_HYPOTHESIS_GO)
        self.assertEqual(result, [])

    def test_multiline_mechanism(self):
        result = parse_hypotheses(MULTI_HYPOTHESIS_GO)
        h2 = result[1]
        self.assertIn("computation of KV pairs", h2["mechanism"])
        self.assertIn("Routing to instances", h2["mechanism"])
        # Multi-line should be joined with spaces, not newlines
        self.assertNotIn("\n", h2["mechanism"])

    def test_decimal_threshold(self):
        result = parse_hypotheses(MULTI_HYPOTHESIS_GO)
        h2 = result[1]
        self.assertAlmostEqual(h2["threshold"], 150.5)

    def test_mixed_complete_and_incomplete(self):
        """Only complete hypotheses are returned when code has both."""
        code = SINGLE_HYPOTHESIS_GO + "\n" + INCOMPLETE_HYPOTHESIS_GO
        result = parse_hypotheses(code)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 1)

    def test_invalid_metric_excluded(self):
        """Hypothesis referencing an unknown metric is excluded from results."""
        result = parse_hypotheses(INVALID_METRIC_GO)
        self.assertEqual(result, [])


class TestTestHypotheses(unittest.TestCase):
    """Tests for test_hypotheses() (aliased as _test_hypotheses in this file)."""

    def setUp(self):
        self.hypotheses = parse_hypotheses(MULTI_HYPOTHESIS_GO)
        self.baseline = {
            "cache_warmup_e2e_ms": 220.0,
            "load_spikes_e2e_ms": 180.0,
        }

    def test_confirmed_verdict(self):
        actual = {"cache_warmup_e2e_ms": 190.0, "load_spikes_e2e_ms": 140.0}
        results = _test_hypotheses(self.hypotheses, actual, self.baseline)
        self.assertEqual(results[0]["verdict"], "CONFIRMED")  # 190 < 200
        self.assertEqual(results[1]["verdict"], "CONFIRMED")  # 140 < 150.5

    def test_refuted_verdict(self):
        actual = {"cache_warmup_e2e_ms": 250.0, "load_spikes_e2e_ms": 160.0}
        results = _test_hypotheses(self.hypotheses, actual, self.baseline)
        self.assertEqual(results[0]["verdict"], "REFUTED")  # 250 >= 200
        self.assertEqual(results[1]["verdict"], "REFUTED")  # 160 >= 150.5

    def test_inconclusive_verdict_missing_metric(self):
        actual = {"cache_warmup_e2e_ms": 190.0}  # prefix_caching missing
        results = _test_hypotheses(self.hypotheses, actual, self.baseline)
        self.assertEqual(results[0]["verdict"], "CONFIRMED")
        self.assertEqual(results[1]["verdict"], "INCONCLUSIVE")
        self.assertIsNone(results[1]["actual"])
        self.assertIsNone(results[1]["delta_vs_baseline_pct"])

    def test_inconclusive_verdict_none_metric(self):
        actual = {"cache_warmup_e2e_ms": 190.0, "load_spikes_e2e_ms": None}
        results = _test_hypotheses(self.hypotheses, actual, self.baseline)
        self.assertEqual(results[1]["verdict"], "INCONCLUSIVE")

    def test_mixed_verdicts(self):
        actual = {"cache_warmup_e2e_ms": 190.0, "load_spikes_e2e_ms": 160.0}
        results = _test_hypotheses(self.hypotheses, actual, self.baseline)
        self.assertEqual(results[0]["verdict"], "CONFIRMED")
        self.assertEqual(results[1]["verdict"], "REFUTED")

    def test_delta_vs_baseline_pct(self):
        actual = {"cache_warmup_e2e_ms": 198.0, "load_spikes_e2e_ms": 180.0}
        results = _test_hypotheses(self.hypotheses, actual, self.baseline)
        # delta for H1: (198 - 220) / 220 * 100 = -10.0%
        self.assertAlmostEqual(results[0]["delta_vs_baseline_pct"], -10.0, places=1)
        # delta for H2: (180 - 180) / 180 * 100 = 0.0%
        self.assertAlmostEqual(results[1]["delta_vs_baseline_pct"], 0.0, places=1)

    def test_result_keys(self):
        actual = {"cache_warmup_e2e_ms": 190.0, "load_spikes_e2e_ms": 140.0}
        results = _test_hypotheses(self.hypotheses, actual, self.baseline)
        expected_keys = {
            "id",
            "claim",
            "mechanism",
            "metric",
            "operator",
            "threshold",
            "actual",
            "baseline_value",
            "delta_vs_baseline_pct",
            "verdict",
        }
        self.assertEqual(set(results[0].keys()), expected_keys)


class TestLoadLedger(unittest.TestCase):
    """Tests for load_ledger()."""

    def test_nonexistent_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "does_not_exist.json"
            ledger = load_ledger(path)
            self.assertEqual(ledger, {"baseline": {}, "entries": []})

    def test_existing_file_loads_correctly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            data = {
                "baseline": {"avg_e2e_ms": 250.0},
                "entries": [{"timestamp": "2025-01-01T00:00:00Z", "hypotheses": []}],
            }
            path.write_text(json.dumps(data))
            ledger = load_ledger(path)
            self.assertEqual(ledger["baseline"], {"avg_e2e_ms": 250.0})
            self.assertEqual(len(ledger["entries"]), 1)


class TestUpdateLedger(unittest.TestCase):
    """Tests for update_ledger()."""

    def test_appends_entry_with_timestamp_and_score(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            ledger = {"baseline": {}, "entries": []}
            hypothesis_results = [
                {
                    "id": 1,
                    "claim": "test",
                    "mechanism": "mech",
                    "metric": "avg_e2e_ms",
                    "threshold": 200.0,
                    "actual": 190.0,
                    "baseline_value": 220.0,
                    "delta_vs_baseline_pct": -13.6,
                    "verdict": "CONFIRMED",
                }
            ]
            updated = update_ledger(ledger, hypothesis_results, -195.0, path)
            self.assertEqual(len(updated["entries"]), 1)
            entry = updated["entries"][0]
            self.assertIn("timestamp", entry)
            self.assertEqual(entry["overall_combined_score"], -195.0)
            self.assertEqual(len(entry["hypotheses"]), 1)

    def test_accumulates_across_multiple_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            ledger = {"baseline": {}, "entries": []}
            hr = [
                {
                    "id": 1,
                    "claim": "c",
                    "mechanism": "m",
                    "metric": "avg_e2e_ms",
                    "threshold": 200,
                    "actual": 190,
                    "baseline_value": 220,
                    "delta_vs_baseline_pct": -13.6,
                    "verdict": "CONFIRMED",
                }
            ]
            update_ledger(ledger, hr, -195.0, path)
            update_ledger(ledger, hr, -190.0, path)
            self.assertEqual(len(ledger["entries"]), 2)

    def test_persists_to_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "ledger.json"
            ledger = {"baseline": {}, "entries": []}
            hr = [
                {
                    "id": 1,
                    "claim": "c",
                    "mechanism": "m",
                    "metric": "avg_e2e_ms",
                    "threshold": 200,
                    "actual": 190,
                    "baseline_value": 220,
                    "delta_vs_baseline_pct": -13.6,
                    "verdict": "CONFIRMED",
                }
            ]
            update_ledger(ledger, hr, -195.0, path)

            # Re-read from disk
            reloaded = load_ledger(path)
            self.assertEqual(len(reloaded["entries"]), 1)
            self.assertEqual(reloaded["entries"][0]["overall_combined_score"], -195.0)


class TestGenerateKnowledgeBaseSummary(unittest.TestCase):
    """Tests for generate_knowledge_base_summary()."""

    def test_empty_ledger(self):
        ledger = {"baseline": {}, "entries": []}
        result = generate_knowledge_base_summary(ledger)
        self.assertIn("No hypothesis data yet.", result)

    def test_empty_ledger_with_baseline(self):
        """When entries are empty but baseline exists, baseline values are shown."""
        ledger = {
            "baseline": {"avg_e2e_ms": 250.0, "avg_p95_ms": 400.0},
            "entries": [],
        }
        result = generate_knowledge_base_summary(ledger)
        self.assertIn("No hypothesis data yet.", result)
        self.assertIn("BASELINE VALUES", result)
        self.assertIn("avg_e2e_ms: 250.0", result)
        self.assertIn("avg_p95_ms: 400.0", result)

    def test_confirmed_strategies_shown(self):
        ledger = {
            "baseline": {"avg_e2e_ms": 250.0},
            "entries": [
                {
                    "timestamp": "t1",
                    "overall_combined_score": -190.0,
                    "hypotheses": [
                        {
                            "id": 1,
                            "claim": "Queue-depth helps",
                            "mechanism": "shorter queues",
                            "metric": "cache_warmup_e2e_ms",
                            "threshold": 200,
                            "actual": 180,
                            "baseline_value": 220,
                            "delta_vs_baseline_pct": -18.2,
                            "verdict": "CONFIRMED",
                        }
                    ],
                },
                {
                    "timestamp": "t2",
                    "overall_combined_score": -185.0,
                    "hypotheses": [
                        {
                            "id": 1,
                            "claim": "Queue-depth helps",
                            "mechanism": "shorter queues",
                            "metric": "cache_warmup_e2e_ms",
                            "threshold": 200,
                            "actual": 175,
                            "baseline_value": 220,
                            "delta_vs_baseline_pct": -20.5,
                            "verdict": "CONFIRMED",
                        }
                    ],
                },
            ],
        }
        result = generate_knowledge_base_summary(ledger)
        self.assertIn("CONFIRMED STRATEGIES", result)
        self.assertIn("Queue-depth helps", result)
        self.assertIn("cache_warmup_e2e_ms", result)
        self.assertIn("shorter queues", result)

    def test_refuted_strategies_shown(self):
        ledger = {
            "baseline": {},
            "entries": [
                {
                    "timestamp": "t1",
                    "overall_combined_score": -300.0,
                    "hypotheses": [
                        {
                            "id": 2,
                            "claim": "Random routing is fine",
                            "mechanism": "randomness",
                            "metric": "avg_e2e_ms",
                            "threshold": 200,
                            "actual": 300,
                            "baseline_value": 250,
                            "delta_vs_baseline_pct": 20.0,
                            "verdict": "REFUTED",
                        }
                    ],
                },
                {
                    "timestamp": "t2",
                    "overall_combined_score": -310.0,
                    "hypotheses": [
                        {
                            "id": 2,
                            "claim": "Random routing is fine",
                            "mechanism": "randomness",
                            "metric": "avg_e2e_ms",
                            "threshold": 200,
                            "actual": 310,
                            "baseline_value": 250,
                            "delta_vs_baseline_pct": 24.0,
                            "verdict": "REFUTED",
                        }
                    ],
                },
            ],
        }
        result = generate_knowledge_base_summary(ledger)
        self.assertIn("REFUTED STRATEGIES", result)
        self.assertIn("Random routing is fine", result)

    def test_top_n_limits_output(self):
        # Create a ledger with many confirmed hypotheses
        entries = []
        for i in range(10):
            entries.append(
                {
                    "timestamp": f"t{i}",
                    "overall_combined_score": -190.0,
                    "hypotheses": [
                        {
                            "id": i,
                            "claim": f"Hypothesis {i}",
                            "mechanism": f"mechanism {i}",
                            "metric": "avg_e2e_ms",
                            "threshold": 200,
                            "actual": 180,
                            "baseline_value": 220,
                            "delta_vs_baseline_pct": -18.2,
                            "verdict": "CONFIRMED",
                        }
                    ],
                }
            )
        ledger = {"baseline": {}, "entries": entries}
        result = generate_knowledge_base_summary(ledger, top_n=3)
        # Each confirmed strategy produces 2 lines (main + mechanism)
        confirmed_section = result.split("=== CONFIRMED STRATEGIES ===")[1]
        # Count unique hypothesis entries (lines starting with "  [")
        strategy_lines = [l for l in confirmed_section.splitlines() if l.strip().startswith("[")]
        self.assertLessEqual(len(strategy_lines), 3)

    def test_baseline_values_shown(self):
        ledger = {
            "baseline": {"avg_e2e_ms": 250.0, "avg_p95_ms": 400.0},
            "entries": [
                {
                    "timestamp": "t1",
                    "overall_combined_score": -190.0,
                    "hypotheses": [
                        {
                            "id": 1,
                            "claim": "test",
                            "mechanism": "mech",
                            "metric": "avg_e2e_ms",
                            "threshold": 200,
                            "actual": 180,
                            "baseline_value": 250,
                            "delta_vs_baseline_pct": -28.0,
                            "verdict": "CONFIRMED",
                        }
                    ],
                }
            ],
        }
        result = generate_knowledge_base_summary(ledger)
        self.assertIn("BASELINE VALUES", result)
        self.assertIn("avg_e2e_ms", result)
        self.assertIn("250.0", result)


class TestFormatHypothesisResults(unittest.TestCase):
    """Tests for format_hypothesis_results()."""

    def test_confirmed_and_refuted(self):
        hypothesis_results = [
            {
                "id": 1,
                "claim": "Queue-depth helps",
                "mechanism": "shorter queues",
                "metric": "cache_warmup_e2e_ms",
                "threshold": 200.0,
                "actual": 190.0,
                "baseline_value": 220.0,
                "delta_vs_baseline_pct": -13.6,
                "verdict": "CONFIRMED",
            },
            {
                "id": 2,
                "claim": "Prefix caching helps",
                "mechanism": "prefix reuse",
                "metric": "load_spikes_e2e_ms",
                "threshold": 150.0,
                "actual": 160.0,
                "baseline_value": 180.0,
                "delta_vs_baseline_pct": -11.1,
                "verdict": "REFUTED",
            },
        ]
        result = format_hypothesis_results(hypothesis_results, -195.0, -220.0)
        self.assertIn("H1 [CONFIRMED]", result)
        self.assertIn("H2 [REFUTED]", result)
        self.assertIn("EXPECT cache_warmup_e2e_ms < 200.0", result)
        self.assertIn("ACTUAL 190.0", result)
        self.assertIn("delta=", result)
        self.assertIn("OVERALL", result)

    def test_inconclusive(self):
        hypothesis_results = [
            {
                "id": 3,
                "claim": "Missing metric hypothesis",
                "mechanism": "unknown",
                "metric": "nonexistent_ms",
                "threshold": 100.0,
                "actual": None,
                "baseline_value": None,
                "delta_vs_baseline_pct": None,
                "verdict": "INCONCLUSIVE",
            }
        ]
        result = format_hypothesis_results(hypothesis_results, -300.0, -250.0)
        self.assertIn("H3 [INCONCLUSIVE]", result)
        self.assertIn("ACTUAL N/A", result)

    def test_overall_score_delta(self):
        result = format_hypothesis_results([], -195.0, -220.0)
        self.assertIn("OVERALL", result)
        self.assertIn("combined_score=-195.00", result)
        # delta = -195 - (-220) = +25
        self.assertIn("+25.00", result)


class TestValidMetrics(unittest.TestCase):
    """Verify VALID_METRICS constant."""

    def test_contains_expected_metrics(self):
        expected = {
            "cache_warmup_e2e_ms",
            "load_spikes_e2e_ms",
            "multiturn_e2e_ms",
            "avg_e2e_ms",
            "avg_p95_ms",
        }
        self.assertEqual(VALID_METRICS, expected)


if __name__ == "__main__":
    unittest.main()
