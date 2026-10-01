"""
Master Validation Suite for FinReg-SLM 4-Pillar Enhancements.

Validates:
1. Pillar 1: Hugging Face Cloud Cross-Encoder Reranker Integration (Live Space)
2. Pillar 2: Program-Aided REPL Math Sandbox & 150-sample SFT Dataset
3. Pillar 3: Margin-DPO Epistemic Dataset (200 pairs) & Trainer Configuration
4. Pillar 4: Test-Time Compute Scaling (Best-of-N Candidate Selection & Certified Dockets)
"""

import sys
import json
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).parent
ROOT_DIR = SRC_DIR.parent.parent
PHASE_4_DIR = ROOT_DIR / "Phase 4 - Second Approach"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(ROOT_DIR / "Huggingface Model"))

from rag_engine import RegulatoryRAGEngine
from repl_sandbox import REPLSandbox
from verifier import ComplianceVerifier
from best_of_n_search import TestTimeSearchEngine
from docket_schema import EnterpriseComplianceDocket
from client import CloudBGERerankerClient

class TestFinReg4Pillars(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rag = RegulatoryRAGEngine()
        cls.sandbox = REPLSandbox()
        cls.verifier = ComplianceVerifier(cls.rag)
        cls.search_engine = TestTimeSearchEngine(cls.rag)

    def test_pillar_1_cloud_bge_reranker(self):
        """Pillar 1: Verify live Hugging Face Cloud BGE cross-encoder re-ranks provisions."""
        client = CloudBGERerankerClient()
        query = "What is the Priority Sector Lending target for Small and Marginal Farmers under RBI norms?"
        passages = [
            "RBI Master Direction: Priority Sector Lending target is 40% of ANBC with a 10% sub-target for Small and Marginal Farmers.",
            "SEBI LODR Regulations: Listed entities must disclose quarterly results in 45 days.",
            "PMLA Section 12: Maintain financial transaction records for 5 years."
        ]
        results = client.rerank(query, passages, top_k=2)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["rank"], 1)
        self.assertGreater(results[0]["score"], 0.5)
        self.assertIn("Priority Sector", results[0]["text"])

    def test_pillar_2_repl_math_execution_and_dataset(self):
        """Pillar 2: Verify REPL execution and 150-sample SFT dataset integrity."""
        # 1. Test calculation
        code = """
anbc = 50000e7
psl_target = (anbc * 40) / 100
smf_target = (anbc * 10) / 100
print(f"PSL={psl_target/1e7:,.0f} | SMF={smf_target/1e7:,.0f}")
"""
        ok, out = self.sandbox.execute_code(code)
        self.assertTrue(ok)
        self.assertIn("PSL=20,000", out)
        self.assertIn("SMF=5,000", out)

        # 2. Check SFT dataset file
        sft_path = PHASE_4_DIR / "data" / "repl_math_sft_150.jsonl"
        self.assertTrue(sft_path.exists())
        with open(sft_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(lines), 150)
        self.assertIn("```python", lines[0]["messages"][2]["content"])

    def test_pillar_3_epistemic_dpo_dataset_integrity(self):
        """Pillar 3: Verify 200-sample Epistemic DPO dataset for false-premise rejection."""
        dpo_path = PHASE_4_DIR / "data" / "epistemic_dpo_200.jsonl"
        self.assertTrue(dpo_path.exists())
        with open(dpo_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(lines), 200)
        
        # Verify chosen outputs contain explicit calibrated refusal
        sample = lines[0]
        self.assertIn("chosen", sample)
        self.assertIn("rejected", sample)
        self.assertIn("INSUFFICIENT_CORPUS_EVIDENCE", sample["chosen"])

    def test_pillar_4_best_of_n_test_time_verifier(self):
        """Pillar 4: Verify Test-Time Compute search selects gold reasoning trace and produces docket."""
        cand_gold = """<think>
Calculating PSL targets:
```python
anbc = 20000e7
target = (anbc * 10) / 100
print(f"SMF={target/1e7:,.0f} Cr")
```
</think>
Under [rbi:rbi_notifications:10497 / para 1], banks must achieve a 10% sub-target for Small and Marginal Farmers."""

        cand_hallucinated = """<think>
Let me provide an answer.
</think>
Under [NON_EXISTENT_CIRCULAR_8888 / para 1], the penalty is Rs 50 Lakhs."""

        winner_text, meta = self.search_engine.select_best_candidate([cand_gold, cand_hallucinated])
        self.assertEqual(meta["final_score"], 1.0)
        self.assertEqual(meta["verification_status"], "ACTIVE_AND_VALID")
        self.assertIn("rbi:rbi_notifications:10497", meta["valid_citations"])
        self.assertEqual(len(meta["invalid_citations"]), 0)

        # Generate Certified Enterprise Compliance Docket
        docket = self.search_engine.generate_certified_docket("What is SMF target?", winner_text, meta)
        self.assertIsInstance(docket, EnterpriseComplianceDocket)
        self.assertEqual(docket.determination, "COMPLIANT_STATUTORY_DETERMINATION")
        self.assertEqual(docket.audit_confidence_score, 1.0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
