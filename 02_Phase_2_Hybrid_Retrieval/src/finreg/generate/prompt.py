"""Single immutable prompt template used identically across all 6 arms (T-113, Invariant E3)."""

from typing import List, Tuple, Optional
from finreg.retrieve.chunker import RegulatoryChunk

FINREG_SYSTEM_PROMPT = """You are an expert Indian regulatory compliance assistant. Your task is to answer legal, banking, tax, and securities compliance questions directly and concisely using ONLY the provided regulatory context provisions.

RULES:
1. Ground every statement strictly in the retrieved context chunks. Do NOT introduce external legal facts.
2. Provide an inline citation for EVERY claim using the exact format: [doc_id / provision_path] (e.g. [RBI_MD_KYC / para 38]).
3. Answer directly in 2-4 sentences without repeating the question or restating prompt headers.
4. If the retrieved context is insufficient or unhelpful to answer the question, you MUST begin your response with:
   INSUFFICIENT_CORPUS_EVIDENCE: <explanation>
5. If relying on a chunk marked with UNCERTAIN_VALIDITY, explicitly flag it in your explanation.
"""

FINREG_USER_TEMPLATE = """AS-OF DATE CONTEXT: {as_of_date}

RETRIEVED REGULATORY CHUNKS:
{context_blocks}

QUESTION: {question}

RESPONSE:"""


def format_generation_prompt(
    question: str,
    as_of_date: str,
    retrieved_chunks: List[Tuple[RegulatoryChunk, float]],
    uncertain_chunks: Optional[List[Tuple[RegulatoryChunk, float]]] = None
) -> Tuple[str, str]:
    """
    Formats system prompt and user prompt using identical rules for all evaluation arms.
    Returns (system_prompt, user_prompt) tuple.
    """
    blocks = []
    for idx, (chunk, score) in enumerate(retrieved_chunks, start=1):
        blocks.append(
            f"--- CHUNK {idx} [{chunk.doc_id} / {chunk.provision_path}] ---\n"
            f"HEADER: {chunk.header_prefix}\n"
            f"CONTENT:\n{chunk.content}\n"
        )

    if uncertain_chunks:
        for idx, (chunk, score) in enumerate(uncertain_chunks, start=1):
            blocks.append(
                f"--- UNCERTAIN_VALIDITY CHUNK {idx} [{chunk.doc_id} / {chunk.provision_path}] ---\n"
                f"HEADER: {chunk.header_prefix}\n"
                f"CONTENT:\n{chunk.content}\n"
            )

    context_str = "\n".join(blocks) if blocks else "(No context provisions provided)"
    user_prompt = FINREG_USER_TEMPLATE.format(
        as_of_date=as_of_date,
        context_blocks=context_str,
        question=question
    )

    return FINREG_SYSTEM_PROMPT, user_prompt
