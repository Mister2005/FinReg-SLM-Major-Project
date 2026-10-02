"""
Automated Deployment Verification Suite for FinReg-SLM Enterprise
=================================================================
Validates local compute execution, deterministic REPL mathematics,
regulatory interpretation, and API endpoint readiness.
"""

import sys
import os
import unittest
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from finreg_engine import SandboxedFinancialREPL, PROMPTS


class TestFinRegEnterpriseDeployment(unittest.TestCase):

    def setUp(self):
        self.repl = SandboxedFinancialREPL()

    def test_01_repl_percentage_crar(self):
        """Validates that REPL computes CRAR and percentages with 100% precision."""
        code = """
tier1 = 150.0
tier2 = 50.0
rwa = 1600.0
crar = ((tier1 + tier2) / rwa) * 100
print(f"{crar:.2f}%")
"""
        success, out = self.repl.execute(code)
        self.assertTrue(success, f"Execution failed: {out}")
        self.assertEqual(out, "12.50%")

    def test_02_repl_date_arithmetic(self):
        """Validates calendar date offsets for compliance filing deadlines."""
        code = """
from datetime import date, timedelta
filing_date = date(2026, 3, 31)
deadline = filing_date + timedelta(days=90)
print(deadline.strftime("%Y-%m-%d"))
"""
        success, out = self.repl.execute(code)
        self.assertTrue(success, f"Execution failed: {out}")
        self.assertEqual(out, "2026-06-29")

    def test_03_prompts_integrity(self):
        """Verifies that all 4 required regulatory task prompts are loaded."""
        required = [
            "regulatory_interpretation",
            "contradiction_detection",
            "temporal_validity",
            "numerical_calculations"
        ]
        for req in required:
            self.assertIn(req, PROMPTS)
            self.assertIn("CRITICAL MANDATES", PROMPTS[req])

    def test_04_api_imports_and_routing(self):
        """Verifies FastAPI route declarations and schema validations."""
        from api_server import app, ComplianceAuditRequest
        routes = [r.path for r in app.routes]
        self.assertIn("/v1/compliance/audit", routes)
        self.assertIn("/v1/chat/completions", routes)
        self.assertIn("/health", routes)
        self.assertIn("/metrics", routes)


if __name__ == "__main__":
    print("=" * 70)
    print("Running FinReg-SLM Enterprise Local Deployment Verification Suite")
    print("=" * 70)
    unittest.main(verbosity=2)
