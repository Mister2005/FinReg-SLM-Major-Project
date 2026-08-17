"""Pipeline script to execute Stage 2 DPO and Final Model Merge directly."""

import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("stage2_pipeline")

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
    logger.info("   RESUMING PIPELINE AT STAGE 2: MEMORY-OPTIMIZED DPO RETRAINING  ")
    logger.info("   (Stage 1 SFT is already 100% completed and merged)            ")
    logger.info("==================================================================")

    # 1. Run Optimized Stage 2 DPO
    run_step("train_stage2_dpo.py", "Stage 2 DPO Direct Preference Optimization (Optimized)")

    # 2. Merge Final DPO Model
    run_step("merge_final_dpo_model.py", "Merge Final Stage 2 DPO Model")

    logger.info("==================================================================")
    logger.info("   ALL STAGE 2 DPO RETRAINING & MERGE COMPLETED SUCCESSFULLY!    ")
    logger.info("   Final 7B Merged Model: runs/stage2_r1_7b_dpo/merged            ")
    logger.info("==================================================================")

if __name__ == "__main__":
    main()
