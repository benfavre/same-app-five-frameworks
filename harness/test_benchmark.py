"""Regression checks for publishing invalid evidence and stopping foreign servers."""
import importlib.util
import argparse
import json
from pathlib import Path
import socket
import os
import subprocess
import sys
import tempfile
import time
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

    def test_rechecks_required_warmup_evidence(self):
        self.write("metadata.json", {"parameters": {"warmupHttp200Required": True}})
        for i in range(3):
            self.write(f"run-{i}/next.warmup.json", {"summary": {"successRate": 1},
                       "statusCodeDistribution": {"200": 100}, "errorDistribution": {}})
        summarize_campaign(self.root)
        self.change("run-0/next.warmup.json", statusCodeDistribution={"200": 99, "503": 1})
        with self.assertRaisesRegex(ValueError, "warmup"):
            summarize_campaign(self.root)
        (self.root / "run-0/next.warmup.json").unlink()
        with self.assertRaises(FileNotFoundError):
            summarize_campaign(self.root)

    def test_cpu_campaign_requires_valid_audits_for_every_entry(self):
        self.write("metadata.json", {"cpuBudget": {"serverCpus": [0]}})
        for i in range(3):
            self.write(f"run-{i}/next.cpu.json", {
                "requestedCpuAffinity": [0], "cpuSeconds": 1, "averageCpuCores": 0.9,
                "errors": [], "affinityViolations": [], "samples": [{}, {}],
                "processes": [{"threadCpuAffinities": [[0]]}]})
        summarize_campaign(self.root)
        self.change("run-0/next.cpu.json", processes=[{"threadCpuAffinities": [[1]]}])
        with self.assertRaises(ValueError):
            summarize_campaign(self.root)
        (self.root / "run-0/next.cpu.json").unlink()
        with self.assertRaises(FileNotFoundError):
            summarize_campaign(self.root)


class ProcessSafetyTests(unittest.TestCase):
    def test_two_framework_sweeps_alternate_the_first_framework(self):
        frameworks = ["astro", "bext"]
        orders = [runner.sweep_order(frameworks, n) for n in range(3)]
        self.assertEqual(orders, [["astro", "bext"], ["bext", "astro"], ["astro", "bext"]])
        self.assertEqual(frameworks, ["astro", "bext"])

    def test_warmup_and_load_reject_http_errors_even_with_transport_success(self):
        result = {"summary": {"successRate": 1}, "statusCodeDistribution": {"200": 100}, "errorDistribution": {}}
        runner.require_http_200(result, "warmup")
        for label in ["warmup", "load"]:
            for statuses in [{"200": 100, "503": 1}, {"503": 100}, {"200": 0}]:
                with self.assertRaisesRegex(RuntimeError, label):
                    runner.require_http_200({**result, "statusCodeDistribution": statuses}, label)
        with self.assertRaises(RuntimeError):
            runner.require_http_200({**result, "errorDistribution": {"timeout": 1}}, "warmup")

    def test_performance_options_preserve_response_caching_and_transport_defaults(self):
        for option in ["BEXT_PRISM_RENDER_CACHE=1", "BEXT_V8_SUBPROCESS=1"]:
            with self.assertRaises(argparse.ArgumentTypeError):
                runner.performance_flag(option)

    def test_cpu_audit_detects_a_thread_outside_the_budget(self):
        cpus = sorted(os.sched_getaffinity(0))
        if len(cpus) < 2:
            self.skipTest("requires two available CPU IDs")
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            os.sched_setaffinity(child.pid, {cpus[0]})
            audit = runner.CpuAudit(child.pid, [cpus[0]])
            audit.started = time.perf_counter()
            audit.sample()
            self.assertFalse(audit.violations)
            os.sched_setaffinity(child.pid, {cpus[1]})
            audit.sample()
            self.assertTrue(audit.violations)
        finally:
            child.terminate()
            child.wait(timeout=5)

    def test_cpu_audit_accounts_for_the_server_child_process(self):
        child = subprocess.Popen([sys.executable, "-c",
            "import subprocess,sys,time; subprocess.run([sys.executable,'-c',"
            "'import time; end=time.monotonic()+0.5; exec(\"while time.monotonic()<end: pass\")'])"])
        try:
            audit = runner.CpuAudit(child.pid)
            audit.start()
            time.sleep(0.35)
            result = audit.stop()
            self.assertGreaterEqual(len(result["processes"]), 2)
            self.assertGreater(result["cpuSeconds"], 0.05)
            self.assertFalse(result["errors"])
        finally:
            child.wait(timeout=5)

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
