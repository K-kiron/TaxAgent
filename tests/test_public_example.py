from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "synthetic_2025_qc_salary_student.json"


class PublicExampleTest(unittest.TestCase):
    def run_cli(self, input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "taxagent.cli",
                "calculate",
                str(input_path),
                "--output",
                str(output_path),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_synthetic_salary_student_example_calculates_with_public_cli(self) -> None:
        with tempfile.TemporaryDirectory(prefix="taxagent-example-") as tmp:
            output = Path(tmp) / "result.json"
            completed = self.run_cli(EXAMPLE, output)

            self.assertEqual(0, completed.returncode, completed.stderr)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("complete", result["status"])
            self.assertEqual("2546.70", result["federal_refund_or_balance"])
            self.assertEqual("863.84", result["quebec_refund_or_balance"])
            self.assertEqual("2025-qc-single-salaried-student-v1", result["coverage_profile_id"])
            self.assertEqual([], result["blockers"])
            self.assertEqual("0.00", result["benefit_estimates"]["canada_workers_benefit"])
            self.assertEqual("0.00", result["benefit_estimates"]["quebec_work_premium"])
            self.assertGreaterEqual(len(result["lines"]), 600)

    def test_self_employment_variant_blocks_without_headline_amounts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="taxagent-example-") as tmp:
            input_path = Path(tmp) / "unsupported.json"
            output_path = Path(tmp) / "result.json"
            payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
            payload["taxpayer"]["has_self_employment"] = True
            input_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            completed = self.run_cli(input_path, output_path)

            self.assertEqual(2, completed.returncode, completed.stdout + completed.stderr)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual("blocked", result["status"])
            self.assertIsNone(result["federal_refund_or_balance"])
            self.assertIsNone(result["quebec_refund_or_balance"])
            self.assertIn("unsupported_situation", {blocker["code"] for blocker in result["blockers"]})
            self.assertIn(
                "taxpayer.has_self_employment",
                {path for blocker in result["blockers"] for path in blocker["input_paths"]},
            )


if __name__ == "__main__":
    unittest.main()
