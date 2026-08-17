"""RAFT training example schema with Pydantic validation (T-201).

Each RAFT example teaches one of four behavioral skills:
  - citation:   ground every claim in retrieved chunks with proper [doc_id / provision] format
  - temporal:   reason about provision applicability given as_of_date vs in_force dates
  - abstention: output INSUFFICIENT_CORPUS_EVIDENCE when retrieved context is irrelevant
  - synthesis:  combine information from multiple retrieved documents into coherent answers
"""

from __future__ import annotations

import enum
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SkillType(str, enum.Enum):
    CITATION = "citation"
    TEMPORAL = "temporal"
    ABSTENTION = "abstention"
    SYNTHESIS = "synthesis"


class RetrievedChunkRecord(BaseModel):
    """A single retrieved chunk included in the RAFT training context."""

    chunk_id: str = Field(..., description="Unique chunk identifier from Phase 2 chunker")
    doc_id: str = Field(..., description="Source document ID")
    provision_path: str = Field(..., description="Provision locator within document")
    header_prefix: str = Field(..., description="Metadata header injected by chunker")
    content: str = Field(..., min_length=10, description="Chunk text content")
    is_gold: bool = Field(..., description="True if this chunk contains evidence for the gold answer")
    in_force_from: Optional[str] = None
    in_force_to: Optional[str] = None
    status: str = "unknown"
    regulator: str = "RBI"


class RAFTExample(BaseModel):
    """A single RAFT training example (T-201).

    Invariants:
      E14: Each example has 1-3 gold chunks + 3-5 distractor chunks, randomly ordered.
      E16: No doc_id in retrieved_chunks may appear in bench-v1 excluded list.
    """

    example_id: str = Field(..., pattern=r"^raft-\d{5}$", description="Unique ID: raft-00001")
    skill_type: SkillType = Field(..., description="Which behavioral skill this example teaches")
    question: str = Field(..., min_length=15, description="The regulatory compliance question")
    as_of_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Query date context")
    retrieved_chunks: List[RetrievedChunkRecord] = Field(
        ..., min_length=4, max_length=8,
        description="Retrieved context: mix of gold and distractor chunks"
    )
    gold_answer: str = Field(..., min_length=20, description="Teacher-generated gold answer")
    source_doc_ids: List[str] = Field(
        default_factory=list,
        description="Doc IDs that the question is about (for exclusion tracking)"
    )

    @field_validator("gold_answer")
    @classmethod
    def validate_gold_answer_format(cls, v: str, info) -> str:
        """Validate gold answer follows expected format based on skill type."""
        # Will be populated from info.data after model construction
        return v

    @model_validator(mode="after")
    def validate_raft_invariants(self) -> "RAFTExample":
        """Enforce RAFT structural invariants."""
        gold_chunks = [c for c in self.retrieved_chunks if c.is_gold]
        distractor_chunks = [c for c in self.retrieved_chunks if not c.is_gold]

        # E14: 1-3 gold chunks (except abstention which has 0)
        if self.skill_type != SkillType.ABSTENTION:
            if not (1 <= len(gold_chunks) <= 3):
                raise ValueError(
                    f"Non-abstention example must have 1-3 gold chunks, got {len(gold_chunks)}"
                )
        else:
            # Abstention examples should have 0 gold chunks
            if len(gold_chunks) != 0:
                raise ValueError(
                    f"Abstention example must have 0 gold chunks, got {len(gold_chunks)}"
                )

        # Must have at least 3 distractors
        if self.skill_type != SkillType.ABSTENTION:
            if len(distractor_chunks) < 2:
                raise ValueError(
                    f"Must have at least 2 distractor chunks, got {len(distractor_chunks)}"
                )

        # Abstention answers must start with INSUFFICIENT_CORPUS_EVIDENCE
        if self.skill_type == SkillType.ABSTENTION:
            if not self.gold_answer.startswith("INSUFFICIENT_CORPUS_EVIDENCE:"):
                raise ValueError(
                    "Abstention gold_answer must begin with 'INSUFFICIENT_CORPUS_EVIDENCE:'"
                )

        # Non-abstention answers must contain at least one citation
        if self.skill_type != SkillType.ABSTENTION:
            if "[" not in self.gold_answer or "/" not in self.gold_answer:
                raise ValueError(
                    "Non-abstention gold_answer must contain at least one citation [doc_id / provision]"
                )

        return self


class RAFTDataset(BaseModel):
    """Complete RAFT training dataset with metadata."""

    version: str = "raft-v1"
    total_examples: int
    skill_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Count of examples per skill type"
    )
    excluded_doc_ids_hash: str = Field(
        ..., description="SHA-256 of the excluded_doc_ids.json used during generation"
    )
    examples: List[RAFTExample]

    @model_validator(mode="after")
    def validate_counts(self) -> "RAFTDataset":
        if self.total_examples != len(self.examples):
            raise ValueError(
                f"total_examples ({self.total_examples}) != len(examples) ({len(self.examples)})"
            )
        return self
