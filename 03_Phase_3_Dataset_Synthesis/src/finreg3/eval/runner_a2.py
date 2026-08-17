"""Arm A2 runner for Base SLM + Retrieval evaluation (real pre-RAFT baseline).

Executes Arm A2 (base Qwen2.5-1.5B-Instruct model + Phase 2 hybrid retrieval,
no RAFT fine-tuning) against the frozen bench-v1 benchmark, using the identical
prompt template and decoding parameters as Arm A6 (runner_a6.py) so the two
arms are directly comparable (Invariant E17).
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from finreg.generate.prompt import format_generation_prompt
from finreg.generate.parser import parse_model_response
from finreg3.eval.citation_precision import (
    evaluate_citation_precision, evaluate_abstention_quality, evaluate_temporal_accuracy
)

logger = logging.getLogger(__name__)

BASE_MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"


class ArmA2Runner:
    """Executes Arm A2 (base SLM, pre-RAFT + Hybrid Retrieval) on benchmark records."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        if self._model is not None:
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        logger.info(f"Loading base model {BASE_MODEL_ID} in 4-bit NF4...")
        self._tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID, trust_remote_code=True)
        self._tokenizer.truncation_side = "left"
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_ID,
            quantization_config=bnb_config,
            device_map={"": 0},
            trust_remote_code=True,
            dtype=torch.float16,
        )

    def run_arm_a2(
        self,
        records: List[Any],
        retrieved_map: Dict[str, List[Tuple[Any, float]]],
        excluded_map: Optional[Dict[str, List[Tuple[Any, float]]]] = None,
    ) -> List[Dict[str, Any]]:
        """Run Arm A2 against benchmark records."""
        self._load_model()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        results = []

        import torch

        for idx, rec in enumerate(records):
            if (idx + 1) % 25 == 0 or idx == 0:
                logger.info(f"Evaluating Arm A2: {idx+1}/{len(records)} records completed...")
            as_of = str(rec.as_of_date)
            retrieved_raw = retrieved_map.get(rec.qid, [])[:4]
            excluded = (excluded_map or {}).get(rec.qid, [])

            trimmed_chunks = []
            for chunk, score in retrieved_raw:
                c_copy = replace(chunk, content=chunk.content[:1000] if len(chunk.content) > 1000 else chunk.content)
                trimmed_chunks.append((c_copy, score))

            sys_p, user_p = format_generation_prompt(
                question=rec.question,
                as_of_date=as_of,
                retrieved_chunks=trimmed_chunks,
            )

            messages = [
                {"role": "system", "content": sys_p},
                {"role": "user", "content": user_p},
            ]
            prompt_text = (
                self._tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                + f"AS-OF DATE: {as_of}\n\n"
            )
            inputs = self._tokenizer(
                prompt_text,
                return_tensors="pt",
                truncation=True,
                max_length=2048,
            ).to(self._model.device)
            with torch.inference_mode():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=256,
                    temperature=0.01,  # Greedy / near zero for reproducibility
                    do_sample=False,
                )
            gen_suffix = self._tokenizer.decode(
                outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
            ).strip()
            response_text = f"AS-OF DATE: {as_of}\n\n" + gen_suffix

            parsed = parse_model_response(response_text)

            cit_eval = evaluate_citation_precision(response_text, retrieved_raw, qid=rec.qid)
            is_context_ok = rec.category not in ["C5", "C6"]
            abs_eval = evaluate_abstention_quality(response_text, is_context_ok, qid=rec.qid)
            temp_eval = evaluate_temporal_accuracy(
                response_text,
                [{"doc_id": c.doc_id, "locator": c.locator} for c in rec.gold_citations],
                excluded,
                qid=rec.qid,
            )

            res_item = {
                "arm": "A2",
                "qid": rec.qid,
                "category": rec.category,
                "as_of_date": as_of,
                "raw_generation": response_text,
                "abstained": parsed.abstained,
                "citations": parsed.citations,
                "citation_precision": cit_eval.precision,
                "valid_citations_count": cit_eval.valid_citations,
                "abstention_classification": abs_eval.classification,
                "correct_temporal_version": temp_eval.correct_active_version_cited,
                "gold_citations": [{"doc_id": c.doc_id, "locator": c.locator} for c in rec.gold_citations],
                "gold_answer": rec.gold_answer,
            }
            results.append(res_item)

            if (idx + 1) % 10 == 0 or (idx + 1) == len(records):
                run_file = self.run_dir / "run_A2.json"
                with open(run_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "arm": "A2",
                        "total_records": len(results),
                        "decoding": {"temperature": 0.0, "max_tokens": 256},
                        "results": results,
                    }, f, indent=2)

        run_file = self.run_dir / "run_A2.json"
        with open(run_file, "w", encoding="utf-8") as f:
            json.dump({
                "arm": "A2",
                "total_records": len(results),
                "decoding": {"temperature": 0.0, "max_tokens": 512},
                "results": results,
            }, f, indent=2)

        logger.info(f"Arm A2 run logged to {run_file}")
        return results
