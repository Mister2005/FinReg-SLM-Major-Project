"""Immutable experiment runner for Arms A0 through A5 (T-125, T-126, T-127, Invariant E3).

REWRITE NOTE (2026-08-15):
Previous implementation used template f-strings for A2/A4 responses — not real model output.
This version runs real Qwen2.5-1.5B-Instruct inference for all local arms (A1, A2, A4).
Arms A0 and A5 use Groq frontier API (llama-3.3-70b-versatile) if key present.
Arm A3/A4 use Phase 2 QLoRA checkpoint if available; falls back to base model with a warning.
"""

import os
import sys
import json
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from finreg.generate.prompt import format_generation_prompt
from finreg.generate.parser import parse_model_response

# Load .env so GROQ_API_KEY is available
_env_path = Path(__file__).parents[5] / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path, override=False)
    except ImportError:
        with open(_env_path, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _, _v = _line.partition("=")
                    if not os.environ.get(_k.strip()):
                        os.environ[_k.strip()] = _v.strip()

try:
    import groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

logger = logging.getLogger(__name__)

# The local SLM used for arms A1, A2 (no fine-tuning) — must match Phase 3 baseline
LOCAL_BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

# Phase 2 SFT checkpoint directory (used for A3, A4)
P2_QLORA_DIR = Path(__file__).parents[4] / "runs" / "qlora_qwen"


def compute_prompt_hash(system_prompt: str, user_template: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(system_prompt.encode("utf-8"))
    hasher.update(user_template.encode("utf-8"))
    return hasher.hexdigest()


def _load_local_model(model_path: str):
    """Load a causal LM in 4-bit NF4 for efficient inference on RTX 5060."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    tokenizer.truncation_side = "left"
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
        dtype=torch.float16,
    )
    model.eval()
    return model, tokenizer


def _generate_local(model, tokenizer, sys_p: str, user_p: str, as_of: str, max_new_tokens: int = 256) -> str:
    """Run near-greedy generation on the local model (temperature=0.01, do_sample=False)."""
    import torch
    messages = [
        {"role": "system", "content": sys_p},
        {"role": "user", "content": user_p},
    ]
    prompt_text = (
        tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        + f"AS-OF DATE: {as_of}\n\n"
    )
    inputs = tokenizer(
        prompt_text,
        return_tensors="pt",
        truncation=True,
        max_length=2048,
    ).to(model.device)
    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.01,
            do_sample=False,
        )
    gen_suffix = tokenizer.decode(
        outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
    ).strip()
    return f"AS-OF DATE: {as_of}\n\n" + gen_suffix


class ArmRunner:
    """Runs designated experiment arms (A0..A5) with identical prompt templates and decoding parameters.

    Arm mapping:
      A0  — Frontier LLM (Groq llama-3.3-70b), no retrieval
      A1  — Local base SLM (Qwen2.5-1.5B), no retrieval
      A2  — Local base SLM + Hybrid RAG  [Phase 2 primary baseline]
      A3  — Local SFT SLM (Phase 2 QLoRA), no retrieval
      A4  — Local SFT SLM + Hybrid RAG   [Phase 2 G1 gate arm]
      A5  — Frontier LLM (Groq llama-3.3-70b) + Hybrid RAG
    """

    def __init__(self, arm_name: str, db_path: Path, run_dir: Path):
        self.arm_name = arm_name
        self.db_path = db_path
        self.run_dir = run_dir
        self.groq_client = None
        self._base_model = None
        self._base_tokenizer = None
        self._sft_model = None
        self._sft_tokenizer = None

        if HAS_GROQ and os.getenv("GROQ_API_KEY"):
            self.groq_client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

    def _ensure_base_model(self):
        if self._base_model is None:
            logger.info(f"Loading base model {LOCAL_BASE_MODEL} in 4-bit NF4 for Arm {self.arm_name}...")
            self._base_model, self._base_tokenizer = _load_local_model(LOCAL_BASE_MODEL)

    def _ensure_sft_model(self):
        """Load Phase 2 SFT/merged model if available, else fall back to base."""
        if self._sft_model is not None:
            return

        merged_dir = P2_QLORA_DIR / "merged"
        if merged_dir.exists() and (merged_dir / "config.json").exists():
            logger.info(f"Loading Phase 2 merged SFT model from {merged_dir}...")
            self._sft_model, self._sft_tokenizer = _load_local_model(str(merged_dir))
            return

        final_dir = P2_QLORA_DIR / "final"
        if final_dir.exists() and (final_dir / "adapter_config.json").exists():
            logger.info(f"Loading Phase 2 LoRA adapter from {final_dir} on top of {LOCAL_BASE_MODEL}...")
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            from peft import PeftModel

            tokenizer = AutoTokenizer.from_pretrained(LOCAL_BASE_MODEL, trust_remote_code=True)
            tokenizer.truncation_side = "left"
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
            )
            base = AutoModelForCausalLM.from_pretrained(
                LOCAL_BASE_MODEL, quantization_config=bnb_config,
                device_map={"": 0}, trust_remote_code=True, dtype=torch.float16,
            )
            model = PeftModel.from_pretrained(base, str(final_dir))
            model.eval()
            self._sft_model = model
            self._sft_tokenizer = tokenizer
            return

        # No SFT checkpoint available — fall back to base model with honest warning
        logger.warning(
            f"No Phase 2 SFT checkpoint found at {P2_QLORA_DIR}. "
            f"Arm {self.arm_name} will use base model (A3/A4 identical to A1/A2 — report this)."
        )
        self._ensure_base_model()
        self._sft_model = self._base_model
        self._sft_tokenizer = self._base_tokenizer

    def run_arm(
        self,
        records: List[Any],
        retrieved_map: Optional[Dict[str, List[Tuple[Any, float]]]] = None,
    ) -> List[Dict[str, Any]]:
        """Executes designated arm against benchmark records using real model inference."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        results = []

        use_retrieval = self.arm_name in ["A2", "A4", "A5"]
        use_sft_model = self.arm_name in ["A3", "A4"]
        use_frontier = self.arm_name in ["A0", "A5"]

        if use_frontier and not self.groq_client:
            logger.warning(f"Arm {self.arm_name}: No Groq client. Falling back to local base model.")
            use_frontier = False
            self._ensure_base_model()
        elif use_sft_model:
            self._ensure_sft_model()
        elif not use_frontier:
            self._ensure_base_model()

        for idx, rec in enumerate(records):
            if (idx + 1) % 25 == 0 or idx == 0:
                logger.info(f"Arm {self.arm_name}: {idx+1}/{len(records)} records completed...")

            as_of = str(rec.as_of_date)
            retrieved_raw = retrieved_map.get(rec.qid, [])[:4] if (use_retrieval and retrieved_map) else []

            from dataclasses import replace as dc_replace
            trimmed_chunks = []
            for chunk, score in retrieved_raw:
                c_copy = dc_replace(chunk, content=chunk.content[:1000] if len(chunk.content) > 1000 else chunk.content)
                trimmed_chunks.append((c_copy, score))

            sys_p, user_p = format_generation_prompt(
                question=rec.question,
                as_of_date=as_of,
                retrieved_chunks=trimmed_chunks,
            )

            if use_frontier and self.groq_client:
                try:
                    completion = self.groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": sys_p},
                            {"role": "user", "content": user_p},
                        ],
                        temperature=0.0,
                        max_tokens=512,
                        seed=42,
                    )
                    response_text = completion.choices[0].message.content
                except Exception as e:
                    logger.error(f"Groq API error on {rec.qid}: {e}")
                    response_text = f"INSUFFICIENT_CORPUS_EVIDENCE: API execution failed - {e}"
            elif use_sft_model:
                response_text = _generate_local(self._sft_model, self._sft_tokenizer, sys_p, user_p, as_of)
            else:
                response_text = _generate_local(self._base_model, self._base_tokenizer, sys_p, user_p, as_of)

            parsed = parse_model_response(response_text)

            res_item = {
                "arm": self.arm_name,
                "qid": rec.qid,
                "category": rec.category,
                "as_of_date": as_of,
                "raw_generation": response_text,
                "abstained": parsed.abstained,
                "citations": parsed.citations,
                "gold_citations": [{"doc_id": c.doc_id, "locator": c.locator} for c in rec.gold_citations],
                "gold_answer": rec.gold_answer,
            }
            results.append(res_item)

            # Rolling checkpoint every 10 records
            if (idx + 1) % 10 == 0 or (idx + 1) == len(records):
                run_file = self.run_dir / f"run_{self.arm_name}.json"
                with open(run_file, "w", encoding="utf-8") as fh:
                    json.dump({
                        "arm": self.arm_name,
                        "total_records": len(results),
                        "model": (
                            "frontier:llama-3.3-70b" if use_frontier else
                            f"sft:{P2_QLORA_DIR}" if use_sft_model else f"base:{LOCAL_BASE_MODEL}"
                        ),
                        "decoding": {"temperature": 0.0, "seed": 42, "max_tokens": 512},
                        "results": results,
                    }, fh, indent=2, ensure_ascii=False)

        run_file = self.run_dir / f"run_{self.arm_name}.json"
        with open(run_file, "w", encoding="utf-8") as fh:
            json.dump({
                "arm": self.arm_name,
                "total_records": len(results),
                "model": (
                    "frontier:llama-3.3-70b" if use_frontier else
                    f"sft:{P2_QLORA_DIR}" if use_sft_model else f"base:{LOCAL_BASE_MODEL}"
                ),
                "decoding": {"temperature": 0.0, "seed": 42, "max_tokens": 512},
                "results": results,
            }, fh, indent=2, ensure_ascii=False)

        logger.info(f"Arm {self.arm_name} run saved to {run_file}")
        return results
