"""Regression checks for publishing invalid evidence and stopping foreign servers."""
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest

from summarize import summarize_campaign

spec = importlib.util.spec_from_file_location("runner", Path(__file__).with_name("run-benchmark.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("campaign.json", {"status": "complete", "repeats": 3, "frameworks": ["next"],
                                    "runs": [{"directory": f"run-{i}", "order": ["next"]} for i in range(3)],
                                    "startedAt": "2026-11-05", "finishedAt": "2026-11-05"})
        for i, rps in enumerate([100, 300, 200]):
            self.write(f"run-{i}/next.browser.json", {
                "status": 200, "ssrCards": 24, "ssrProducts": 24,
                "counterOk": True, "themeOk": True, "themePersistOk": True, "searchOk": True,
                "clientJsGzB": 2048, "initialClientJsGzB": 1024, "jsReqs": 2, "resourceErrors": []})
            self.write(f"run-{i}/next.proof", {"uncached": True, "r1": "1", "r2": "2",
                                              "loadSamples": [str(j + 1) for j in range(20)]})
            self.write(f"run-{i}/next.oha.json", {
                "summary": {"requestsPerSec": rps, "successRate": 1},
                "statusCodeDistribution": {"200": 100}, "errorDistribution": {},
                "firstBytePercentiles": {"p50": 0.002}, "latencyPercentiles": {"p99": 0.01}})
            self.write(f"run-{i}/next.build.json", {"bytes": 4096})
            self.write(f"run-{i}/next.cold.json", {"samplesMs": [1, 20, 3]})

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def change(self, name, **values):
        value = json.loads((self.root / name).read_text())
        self.write(name, {**value, **values})

    def test_reports_median_and_range_instead_of_fastest_attempt(self):
        row = summarize_campaign(self.root)["frameworks"][0]
        self.assertEqual((row["rps"], row["rps_min"], row["rps_max"]), (200, 100, 300))
        self.assertEqual(row["cold_ms"], 3)
        self.assertEqual(row["client_js_gz_kb"], 2)

    def test_rejects_failed_campaign(self):
        self.change("campaign.json", status="failed")
        with self.assertRaises(ValueError):
            summarize_campaign(self.root)

    def test_rejects_duplicate_runs(self):
        self.change("campaign.json", runs=[{"directory": "run-0", "order": ["next"]}] * 3)
        with self.assertRaises(ValueError):
            summarize_campaign(self.root)

    def test_rechecks_raw_uncached_samples(self):
        self.change("run-0/next.proof", loadSamples=["cached"] * 20)
        with self.assertRaises(ValueError):
            summarize_campaign(self.root)

    def test_rejects_non_200_even_when_oha_success_rate_is_one(self):
        self.change("run-0/next.oha.json", statusCodeDistribution={"200": 99, "500": 1})
        with self.assertRaises(ValueError):
            summarize_campaign(self.root)

    def test_rejects_failed_interaction_and_missing_evidence(self):
        self.change("run-0/next.browser.json", themePersistOk=False)
        with self.assertRaises(ValueError):
            summarize_campaign(self.root)
        self.change("run-0/next.browser.json", themePersistOk=True)
        (self.root / "run-0/next.build.json").unlink()
        with self.assertRaises(FileNotFoundError):
            summarize_campaign(self.root)


class ProcessSafetyTests(unittest.TestCase):
    def test_occupied_port_is_rejected_without_stopping_its_listener(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with self.assertRaises(RuntimeError):
                runner.port_is_free(port)
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                pass


if __name__ == "__main__":
    unittest.main()
