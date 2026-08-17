"""Gold answer generation for RAFT training examples (T-204).

Generates grounded answers with inline citations using the same prompt template
as the evaluation system (Invariant E13), ensuring training distribution matches
inference distribution.
"""

from __future__ import annotations

import re
import logging
from typing import List, Dict, Any, Tuple

from finreg3.raft.question_gen import TeacherLLM
from finreg3.raft.schema import RetrievedChunkRecord, SkillType

logger = logging.getLogger(__name__)

GOLD_ANSWER_SYSTEM_PROMPT = """You are an expert Indian regulatory compliance assistant generating training data for a fine-tuned model. Your task is to answer the given question using ONLY the provided regulatory context chunks.

CRITICAL RULES:
1. Ground every statement strictly in the retrieved context chunks.
2. Provide inline citations for EVERY claim using the exact format: [doc_id / provision_path]
   Example: [RBI_MD_KYC / para 38]
3. State the applicable as-of date at the beginning of your response.
4. Use ONLY chunks marked as relevant (not distractors) for your answer.
5. Be specific — cite exact provision numbers, not vague references.
6. If the question asks about temporal applicability, explicitly state effective dates from the chunks.
7. Keep the answer concise but complete (150-300 words)."""

GOLD_ANSWER_USER_TEMPLATE = """AS-OF DATE CONTEXT: {as_of_date}

RETRIEVED REGULATORY CHUNKS:
{context_blocks}

QUESTION: {question}

Generate a well-cited answer grounding every claim in the chunks above. Use [doc_id / provision_path] citations inline."""

ABSTENTION_ANSWER_TEMPLATE = """INSUFFICIENT_CORPUS_EVIDENCE: The retrieved context does not contain regulatory provisions relevant to answering this question. The available chunks address {available_topics}, which do not pertain to the query about {query_topic}. No answer can be reliably grounded in the provided corpus."""

FALSE_PREMISE_ANSWER_PROMPT = """You are an expert Indian regulatory compliance assistant generating training data for a fine-tuned model. The question below asserts a specific regulatory detail that is NOT actually supported by the retrieved provision text below. Your task is to write a refusal that:
1. Begins EXACTLY with "INSUFFICIENT_CORPUS_EVIDENCE:"
2. Names the actual retrieved provision using [doc_id / provision_path] format and briefly states what it DOES say
3. Explicitly states that the specific claim in the question is NOT supported by that provision
4. Does not fabricate, confirm, or elaborate on the false detail

AS-OF DATE CONTEXT: {as_of_date}

RETRIEVED PROVISION:
{context_block}

QUESTION: {question}

Write the refusal now, starting with INSUFFICIENT_CORPUS_EVIDENCE:"""


class GoldAnswerGenerator:
    """Generates teacher-model gold answers for RAFT training (T-204)."""

    def __init__(self, teacher: TeacherLLM):
        self.teacher = teacher

    def generate_grounded_answer(
        self,
        question: str,
        as_of_date: str,
        chunks: List[RetrievedChunkRecord],
        skill_type: SkillType,
    ) -> str:
        """Generate a gold answer grounded in the provided chunks.

        For abstention examples, generates INSUFFICIENT_CORPUS_EVIDENCE response.
        For all other types, generates a cited answer.
        """
        if skill_type == SkillType.ABSTENTION:
            return self._generate_abstention_answer(question, chunks)

        # Format chunks into context blocks (same format as eval prompt — Invariant E13)
        blocks = []
        for idx, chunk in enumerate(chunks, start=1):
            blocks.append(
                f"--- CHUNK {idx} [{chunk.doc_id} / {chunk.provision_path}] ---\n"
                f"HEADER: {chunk.header_prefix}\n"
                f"CONTENT:\n{chunk.content}\n"
            )
        context_str = "\n".join(blocks)

        user_prompt = GOLD_ANSWER_USER_TEMPLATE.format(
            as_of_date=as_of_date,
            context_blocks=context_str,
            question=question,
        )

        raw_answer = self.teacher.generate(
            f"{GOLD_ANSWER_SYSTEM_PROMPT}\n\n{user_prompt}",
            temperature=0.2,  # Lower temp for factual grounding
            max_tokens=768,
        )

        # Validate the answer contains citations
        if not self._has_citations(raw_answer):
            logger.warning(f"Gold answer lacks citations, regenerating with stronger prompt")
            raw_answer = self._regenerate_with_citations(question, as_of_date, context_str, raw_answer)

        return raw_answer

    def generate_false_premise_answer(
        self,
        question: str,
        as_of_date: str,
        chunk: RetrievedChunkRecord,
    ) -> str:
        """Generate a refusal that names the real retrieved provision and explains
        why it does not support the false claim in the question (see
        generate_false_premise_question)."""
        context_block = (
            f"--- CHUNK 1 [{chunk.doc_id} / {chunk.provision_path}] ---\n"
            f"HEADER: {chunk.header_prefix}\n"
            f"CONTENT:\n{chunk.content}\n"
        )
        prompt = FALSE_PREMISE_ANSWER_PROMPT.format(
            as_of_date=as_of_date,
            context_block=context_block,
            question=question,
        )
        raw_answer = self.teacher.generate(prompt, temperature=0.2, max_tokens=400)
        if not raw_answer.strip().startswith("INSUFFICIENT_CORPUS_EVIDENCE"):
            raw_answer = "INSUFFICIENT_CORPUS_EVIDENCE: " + raw_answer.strip()
        return raw_answer.strip()

    def _generate_abstention_answer(
        self,
        question: str,
        distractor_chunks: List[RetrievedChunkRecord],
    ) -> str:
        """Generate a properly formatted abstention response."""
        available_topics = set()
        for c in distractor_chunks[:3]:
            # Extract regulator and rough topic from header
            if c.regulator:
                available_topics.add(f"{c.regulator} provisions")
            if c.provision_path:
                available_topics.add(c.provision_path)

        topics_str = ", ".join(list(available_topics)[:3]) or "unrelated Indian regulatory provisions"

        # Extract the query topic from the question
        query_topic = question.split("requirements for")[-1].strip().rstrip("?") if "requirements for" in question else "the queried topic"

        return ABSTENTION_ANSWER_TEMPLATE.format(
            available_topics=topics_str,
            query_topic=query_topic,
        )

    def _has_citations(self, answer: str) -> bool:
        """Check if answer contains at least one [doc_id / provision] citation."""
        # Match patterns like [RBI_MD_KYC / para 38] or [rbi:rbi_notifications:10566 / Chapter III]
        pattern = r'\[[^/\]]+ / [^\]]+\]'
        return bool(re.search(pattern, answer))

    def _regenerate_with_citations(
        self, question: str, as_of_date: str, context_str: str, first_attempt: str
    ) -> str:
        """Retry with explicit citation instruction."""
        retry_prompt = f"""{GOLD_ANSWER_SYSTEM_PROMPT}

IMPORTANT: Your previous answer lacked proper inline citations. You MUST cite specific provisions.

{GOLD_ANSWER_USER_TEMPLATE.format(
    as_of_date=as_of_date,
    context_blocks=context_str,
    question=question,
)}

PREVIOUS ATTEMPT (missing citations):
{first_attempt}

Now rewrite with proper [doc_id / provision_path] citations for every claim."""

        return self.teacher.generate(retry_prompt, temperature=0.1, max_tokens=768)
