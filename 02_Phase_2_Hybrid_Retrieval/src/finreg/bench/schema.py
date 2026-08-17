"""Pydantic schema definitions for the FinReg-SLM Phase 2 Benchmark Question Record (T-101)."""

from typing import List, Optional, Literal
from datetime import date
from pydantic import BaseModel, Field, model_validator

CategoryType = Literal["C1", "C2", "C3", "C4", "C5", "C6"]
RegulatorType = Literal["RBI", "SEBI", "Income-tax", "GST", "DPDP"]
DifficultyType = Literal["easy", "medium", "hard"]


class GoldCitation(BaseModel):
    doc_id: str = Field(..., description="Phase 1 corpus doc_id")
    locator: str = Field(..., description="Provision path or locator, e.g. 'para 4.2' or 'Section 194-IA'")


class ComputationSpec(BaseModel):
    expected_value: Optional[float] = None
    tolerance: Optional[float] = None


class BenchmarkQuestionRecord(BaseModel):
    qid: str = Field(..., description="Unique question identifier, e.g. 'C3-RBI-014'")
    category: CategoryType = Field(..., description="Category code (C1..C6)")
    regulator: RegulatorType = Field(..., description="Regulator identifier")
    question: str = Field(..., min_length=10, description="Question text")
    as_of_date: date = Field(..., description="Applicable temporal context date")
    stem_id: Optional[str] = Field(None, description="Shared stem identifier for C3 stem-pair variants")
    gold_answer: str = Field(..., min_length=5, description="Gold answer text grounded in corpus")
    gold_citations: List[GoldCitation] = Field(default_factory=list, description="List of supporting Phase 1 doc_ids & locators")
    answerable: bool = Field(..., description="Whether the question is answerable from corpus text")
    false_premise: bool = Field(default=False, description="Whether the question contains a false legal premise")
    computation: ComputationSpec = Field(default_factory=ComputationSpec, description="Computation spec for C4 questions")
    difficulty: DifficultyType = Field(default="medium", description="Difficulty level")
    author: str = Field(..., description="Author identifier")
    verified_by: Optional[str] = Field(None, description="Verifier identifier")
    verification_date: Optional[date] = Field(None, description="Date of verification")
    notes: Optional[str] = Field(None, description="Authoring / verification notes")

    @model_validator(mode="after")
    def validate_citations_and_categories(self) -> "BenchmarkQuestionRecord":
        # Rule: Answerable questions (unless C6 unanswerable) MUST have non-empty gold_citations
        if self.answerable and self.category != "C6" and not self.gold_citations:
            raise ValueError(f"Question {self.qid} is answerable but missing gold_citations.")
        
        # Rule: C6 unanswerable questions should have answerable = False
        if self.category == "C6" and self.answerable:
            raise ValueError(f"Category C6 question {self.qid} must have answerable=False.")

        # Rule: C5 false premise questions must have false_premise = True
        if self.category == "C5" and not self.false_premise:
            raise ValueError(f"Category C5 question {self.qid} must have false_premise=True.")

        # Rule: C3 questions must have stem_id
        if self.category == "C3" and not self.stem_id:
            raise ValueError(f"Category C3 question {self.qid} must specify stem_id.")

        return self
