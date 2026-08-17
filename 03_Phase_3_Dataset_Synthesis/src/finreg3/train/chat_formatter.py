"""RAFT chat template formatter for Qwen 2.5 7B Instruct (T-207).

Converts RAFT training examples into the Qwen chat-ml format:
  <|im_start|>system\n{system_prompt}<|im_end|>
  <|im_start|>user\n{question + retrieved chunks}<|im_end|>
  <|im_start|>assistant\n{gold_answer}<|im_end|>

The user turn includes all retrieved chunks in the EXACT same format as the
evaluation prompt template (Invariant E13), ensuring training and inference
distributions match.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from finreg3.raft.schema import RAFTExample, SkillType

logger = logging.getLogger(__name__)

FINREG_SYSTEM_PROMPT = """You are an expert Indian regulatory compliance assistant. Your task is to answer legal, banking, tax, and securities compliance questions directly and concisely using ONLY the provided regulatory context provisions.

RULES:
1. Ground every statement strictly in the retrieved context chunks. Do NOT introduce external legal facts.
2. Provide an inline citation for EVERY factual claim using the exact format: [doc_id / provision_path] (e.g. [RBI_MD_KYC / para 38]).
3. Answer directly in 2-4 sentences without repeating the question or restating prompt headers.
4. If the retrieved context is insufficient or unhelpful to answer the question, you MUST begin your response with:
   INSUFFICIENT_CORPUS_EVIDENCE: <explanation>
5. If relying on a chunk marked with UNCERTAIN_VALIDITY, explicitly flag it in your explanation."""


def format_raft_example_to_chat(example: RAFTExample) -> Dict[str, Any]:
    """Convert a single RAFT example into a chat-format training record.

    Returns a dict with 'messages' key containing the conversation turns,
    compatible with HuggingFace datasets and TRL SFTTrainer.
    """
    # Build the context blocks in the same format AND with the same per-chunk/count
    # trimming as the evaluation/inference prompt (runner_a6.py, runner_a2.py) —
    # otherwise training examples are far larger than anything the model ever sees
    # at inference, and completions get truncated out of the training window entirely.
    blocks = []
    for idx, chunk in enumerate(example.retrieved_chunks[:4], start=1):
        content = chunk.content[:1000] if len(chunk.content) > 1000 else chunk.content
        blocks.append(
            f"--- CHUNK {idx} [{chunk.doc_id} / {chunk.provision_path}] ---\n"
            f"HEADER: {chunk.header_prefix}\n"
            f"CONTENT:\n{content}\n"
        )
    context_str = "\n".join(blocks) if blocks else "(No context provisions provided)"

    user_content = (
        f"AS-OF DATE CONTEXT: {example.as_of_date}\n\n"
        f"RETRIEVED REGULATORY CHUNKS:\n{context_str}\n\n"
        f"QUESTION: {example.question}\n\n"
        f"RESPONSE:"
    )

    messages = [
        {"role": "system", "content": FINREG_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": example.gold_answer},
    ]

    return {
        "id": example.example_id,
        "skill_type": example.skill_type.value,
        "messages": messages,
    }


def convert_raft_dataset_to_chat(
    input_path: Path,
    output_path: Path,
    format: str = "jsonl",
) -> Dict[str, Any]:
    """Convert RAFT JSONL dataset to chat-format training data (T-207).

    Args:
        input_path: Path to raft-train-v1.jsonl
        output_path: Path for chat-formatted output
        format: Output format ('jsonl' or 'json')

    Returns:
        Conversion stats.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    converted = []
    skill_counts: Dict[str, int] = {}
    total_tokens_estimate = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            example = RAFTExample.model_validate_json(line.strip())
            chat_record = format_raft_example_to_chat(example)
            converted.append(chat_record)

            key = example.skill_type.value
            skill_counts[key] = skill_counts.get(key, 0) + 1

            # Rough token estimate (4 chars ≈ 1 token)
            total_chars = sum(len(m["content"]) for m in chat_record["messages"])
            total_tokens_estimate += total_chars // 4

    # Write output
    if format == "jsonl":
        with open(output_path, "w", encoding="utf-8") as f:
            for rec in converted:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(converted, f, ensure_ascii=False, indent=2)

    stats = {
        "total_examples": len(converted),
        "skill_distribution": skill_counts,
        "estimated_total_tokens": total_tokens_estimate,
        "avg_tokens_per_example": total_tokens_estimate // max(len(converted), 1),
        "output_path": str(output_path),
    }

    logger.info(f"Converted {len(converted)} examples to chat format")
    logger.info(f"Estimated total tokens: {total_tokens_estimate:,}")
    logger.info(f"Average tokens/example: {stats['avg_tokens_per_example']}")

    return stats
