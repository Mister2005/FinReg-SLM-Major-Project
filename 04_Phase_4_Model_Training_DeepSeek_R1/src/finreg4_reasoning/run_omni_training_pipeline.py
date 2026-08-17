"""Master Omni-Regulator Retraining Pipeline.

Executes end-to-end retraining of DeepSeek-R1-Distill-Qwen-7B across all 13 Indian Compliance Regulators:
Step 1: Stage 1 LoRA SFT on omni_golden_sft_350.jsonl
Step 2: Merge Stage 1 adapter
Step 3: Stage 2 DPO alignment on omni_dpo_pairs_350.jsonl
Step 4: Merge Stage 2 DPO adapter into final merged 7B weights.
"""

import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("omni_training_pipeline")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
SRC_DIR = ROOT_DIR / "Phase 4 - Second Approach" / "src" / "finreg4_reasoning"

def run_step(script_name: str, desc: str):
    script_path = SRC_DIR / script_name
    logger.info(f"\n======================================================\n>>> STARTING: {desc} ({script_name})\n======================================================")
    cmd = [sys.executable, str(script_path)]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        logger.error(f"FATAL: Step {script_name} failed with exit code {res.returncode}")
        sys.exit(res.returncode)
    logger.info(f">>> COMPLETED SUCCESSFULLY: {desc}\n")

def main():
    logger.info("==================================================================")
    logger.info("   STARTING UNIFIED OMNI-REGULATOR 7B RETRAINING PIPELINE        ")
    logger.info("   Coverage: RBI, SEBI, CBIC, MCA, CBDT, IBBI, IRDAI, PFRDA,      ")
    logger.info("             EPFO, ESIC, MeitY, CCI, IndiaCode                    ")
    logger.info("==================================================================")

    # 1. Stage 1 SFT
    run_step("train_stage1_sft.py", "Stage 1 LoRA SFT Training (All 13 Regulators)")

    # 2. Merge Stage 1 Adapter
    run_step("merge_stage1_adapter.py", "Merge Stage 1 LoRA Weights")

    # 3. Stage 2 DPO Alignment
    run_step("train_stage2_dpo.py", "Stage 2 DPO Direct Preference Optimization")

    # 4. Merge Final DPO Model
    run_step("merge_final_dpo_model.py", "Merge Final Stage 2 DPO Model")

    logger.info("==================================================================")
    logger.info("   ALL RETRAINING STEPS COMPLETED WITH ZERO ERRORS               ")
    logger.info("   Final Model: runs/stage2_r1_7b_dpo/merged                      ")
    logger.info("==================================================================")

if __name__ == "__main__":
    main()
