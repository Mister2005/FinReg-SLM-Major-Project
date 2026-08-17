"""Real (subset) general-capability probe for forgetting assessment (Gate G7).

Compares the base pre-RAFT model against the merged RAFT model on a small
sample of ARC-Challenge and HellaSwag, using multiple-choice log-likelihood
scoring: each answer option is scored by the sum of its token log-probabilities
under the model, and the highest-scoring option is taken as the prediction.

Limitation, stated plainly: this is a lightweight scorer, not the full
lm-eval-harness normalization treatment (e.g. no length/byte normalization of
choices), and the sample size (~50-100 items per task) is a small subset, not
the full benchmark. It is appropriate for a viva-level directional check of
whether RAFT fine-tuning cost general capability, not a publication-grade
capability benchmark.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

BASE_MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"


def _score_continuation(model, tokenizer, context: str, continuation: str, device) -> float:
    """Sum of log-probabilities of `continuation` tokens given `context`."""
    import torch

    ctx_ids = tokenizer(context, return_tensors="pt").input_ids
    full_ids = tokenizer(context + continuation, return_tensors="pt").input_ids.to(device)
    cont_len = full_ids.shape[1] - ctx_ids.shape[1]
    if cont_len <= 0:
        return float("-inf")

    with torch.inference_mode():
        logits = model(full_ids).logits[0]
    logprobs = torch.log_softmax(logits, dim=-1)

    total_lp = 0.0
    start = ctx_ids.shape[1]
    for i in range(cont_len):
        tok_id = full_ids[0, start + i]
        total_lp += logprobs[start + i - 1, tok_id].item()
    return total_lp


def _eval_arc_challenge(model, tokenizer, device, n: int) -> float:
    from datasets import load_dataset

    ds = load_dataset("allenai/ai2_arc", "ARC-Challenge", split=f"validation[:{n}]")
    correct = 0
    for item in ds:
        choices = item["choices"]["text"]
        labels = item["choices"]["label"]
        context = item["question"] + "\nAnswer: "
        scores = [_score_continuation(model, tokenizer, context, c, device) for c in choices]
        pred_label = labels[scores.index(max(scores))]
        if pred_label == item["answerKey"]:
            correct += 1
    return correct / len(ds) if len(ds) else 0.0


def _eval_hellaswag(model, tokenizer, device, n: int) -> float:
    from datasets import load_dataset

    ds = load_dataset("hellaswag", split=f"validation[:{n}]")
    correct = 0
    for item in ds:
        context = item["ctx"] + " "
        endings = item["endings"]
        scores = [_score_continuation(model, tokenizer, context, e, device) for e in endings]
        pred_idx = scores.index(max(scores))
        if str(pred_idx) == item["label"]:
            correct += 1
    return correct / len(ds) if len(ds) else 0.0


def _load_causal_lm(model_id_or_path: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(model_id_or_path, trust_remote_code=True)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_id_or_path,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
        dtype=torch.float16,
    )
    model.eval()
    return model, tokenizer


def evaluate_capability_subset(model_id_or_path: str, n_per_task: int = 50) -> Dict[str, float]:
    """Runs the ARC-Challenge + HellaSwag subset probe against one model, then frees it."""
    import gc
    import torch

    model, tokenizer = _load_causal_lm(model_id_or_path)
    device = model.device
    try:
        arc_acc = _eval_arc_challenge(model, tokenizer, device, n_per_task)
        hellaswag_acc = _eval_hellaswag(model, tokenizer, device, n_per_task)
    finally:
        del model, tokenizer
        gc.collect()
        torch.cuda.empty_cache()

    return {
        "arc_challenge": arc_acc,
        "hellaswag": hellaswag_acc,
        "mean_score": (arc_acc + hellaswag_acc) / 2.0,
    }


def run_capability_delta(merged_model_dir: Path, base_model_id: str = "Qwen/Qwen2.5-3B-Instruct", n_per_task: int = 50) -> Dict[str, object]:
    """Compares base vs merged model on the capability subset; returns both scores and the delta."""
    logger.info(f"Running capability probe on base model ({base_model_id})...")
    base_scores = evaluate_capability_subset(base_model_id, n_per_task)

    logger.info(f"Running capability probe on merged RAFT model ({merged_model_dir})...")
    merged_scores = evaluate_capability_subset(str(merged_model_dir), n_per_task)

    mean_loss_pts = round((base_scores["mean_score"] - merged_scores["mean_score"]) * 100.0, 2)

    return {
        "base_scores": base_scores,
        "merged_scores": merged_scores,
        "mean_capability_loss_pts": mean_loss_pts,
        "n_per_task": n_per_task,
    }
