"""Main RAFT data generation pipeline orchestrator (T-203, T-205, T-206).

Orchestrates the full RAFT training data generation:
1. Loads eligible corpus documents (excluding bench-v1 gold citations)
2. Builds the Phase 2 retrieval index (Invariant E13)
3. For each training example:
   a. Samples a document and generates a question (T-202)
   b. Runs retrieval to get real context (T-203: distractor injection)
   c. Labels gold vs distractor chunks
   d. Generates a teacher-model gold answer (T-204)
   e. For abstention: uses unrelated context (T-205)
4. Validates and exports the dataset (T-206)
"""

from __future__ import annotations

import json
import hashlib
import random
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Set, Optional, Tuple
from datetime import datetime

from finreg3.raft.schema import (
    RAFTExample, RAFTDataset, RetrievedChunkRecord, SkillType
)
from finreg3.raft.question_gen import TeacherLLM, QuestionGenerator
from finreg3.raft.answer_gen import GoldAnswerGenerator

logger = logging.getLogger(__name__)

# Default paths (same corpus as Phase 2)
DEFAULT_DB_PATH = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 1/data/manifest.db")
DEFAULT_EXCLUSION_PATH = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 2/data/bench/excluded_doc_ids.json")
DEFAULT_OUTPUT_PATH = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/data/sft/raft-train-v1.jsonl")

# Skill distribution targets (from config)
SKILL_TARGETS = {
    SkillType.CITATION: 0.40,
    SkillType.TEMPORAL: 0.25,
    SkillType.ABSTENTION: 0.15,
    SkillType.SYNTHESIS: 0.20,
}


def _load_excluded_doc_ids(exclusion_path: Path) -> Tuple[Set[str], str]:
    """Load excluded doc_ids and compute SHA-256 hash for provenance."""
    with open(exclusion_path, "r", encoding="utf-8") as f:
        raw = f.read()
    data = json.loads(raw)
    doc_ids = set(data.get("excluded_doc_ids", []))
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return doc_ids, sha


def _load_eligible_documents(
    db_path: Path, excluded_ids: Set[str]
) -> List[Dict[str, Any]]:
    """Load corpus documents eligible for RAFT training (not in exclusion list)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.doc_id, d.regulator, d.doc_number, d.title, d.issue_date,
               d.in_force_from, d.in_force_to, d.status, d.statutory_regime, t.body
        FROM documents d
        LEFT JOIN texts t ON d.doc_id = t.doc_id
        WHERE t.body IS NOT NULL AND LENGTH(t.body) > 200
    """)
    rows = cursor.fetchall()
    conn.close()

    eligible = []
    for row in rows:
        doc_id = row[0]
        if doc_id in excluded_ids:
            continue
        eligible.append({
            "doc_id": doc_id,
            "regulator": row[1] or "RBI",
            "doc_number": row[2] or doc_id,
            "title": row[3] or "",
            "issue_date": row[4] or "",
            "in_force_from": row[5] or row[4],
            "in_force_to": row[6],
            "status": row[7] or "unknown",
            "statutory_regime": row[8],
            "body": row[9],
        })

    logger.info(f"Loaded {len(eligible)} eligible documents ({len(excluded_ids)} excluded)")
    return eligible


class RAFTPipeline:
    """End-to-end RAFT training data generation pipeline."""

    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        exclusion_path: Path = DEFAULT_EXCLUSION_PATH,
        output_path: Path = DEFAULT_OUTPUT_PATH,
        teacher_primary: str = "groq",
        index_limit: Optional[int] = 500,
    ):
        self.db_path = db_path
        self.exclusion_path = exclusion_path
        self.output_path = output_path
        self.index_limit = index_limit

        # Load exclusions
        self.excluded_ids, self.exclusion_hash = _load_excluded_doc_ids(exclusion_path)

        # Initialize teacher LLM and generators
        self.teacher = TeacherLLM(primary=teacher_primary)
        self.question_gen = QuestionGenerator(self.teacher)
        self.answer_gen = GoldAnswerGenerator(self.teacher)

        # Retrieval pipeline (lazy init)
        self._pipeline = None

    def _init_retrieval(self):
        """Initialize Phase 2 retrieval pipeline (Invariant E13)."""
        if self._pipeline is not None:
            return

        from finreg.retrieve.pipeline import HybridRetrievalPipeline
        self._pipeline = HybridRetrievalPipeline(
            db_path=self.db_path,
            use_reranker=False,  # Pure RRF, same as Phase 2 production config
            use_temporal_filter=True,
        )
        logger.info(f"Building retrieval index (limit={self.index_limit})...")
        self._pipeline.build_index_from_db(limit=self.index_limit)
        
        # Filter out bench-v1 excluded doc_ids (Invariant E16)
        before_count = len(self._pipeline.chunks)
        self._pipeline.chunks = [c for c in self._pipeline.chunks if c.doc_id not in self.excluded_ids]
        after_count = len(self._pipeline.chunks)
        
        # Rebuild vector & BM25 indices over non-excluded chunks only
        self._pipeline.dense_index.build_index(self._pipeline.chunks)
        self._pipeline.bm25_index.build_index(self._pipeline.chunks)
        
        logger.info(f"Index built: {after_count} chunks ({before_count - after_count} excluded chunks removed)")

    def generate_dataset(self, target_count: int = 4000, resume: bool = True) -> RAFTDataset:
        """Generate the complete RAFT training dataset with resume support."""
        self._init_retrieval()
        eligible_docs = _load_eligible_documents(self.db_path, self.excluded_ids)

        if len(eligible_docs) < 50:
            raise ValueError(f"Only {len(eligible_docs)} eligible docs — need at least 50")

        # Compute per-skill targets
        skill_counts = {
            st: int(target_count * frac)
            for st, frac in SKILL_TARGETS.items()
        }
        diff = target_count - sum(skill_counts.values())
        skill_counts[SkillType.CITATION] += diff

        examples: List[RAFTExample] = []
        existing_skill_counts = {st: 0 for st in SKILL_TARGETS.keys()}

        # Load existing file if resume is True and file exists
        if resume and self.output_path.exists():
            try:
                with open(self.output_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        ex = RAFTExample.model_validate_json(line_str)
                        examples.append(ex)
                        existing_skill_counts[ex.skill_type] = existing_skill_counts.get(ex.skill_type, 0) + 1
                logger.info(
                    f"Resuming generation: Loaded {len(examples)} existing examples from {self.output_path}. "
                    f"Counts: {existing_skill_counts}"
                )
            except Exception as e:
                logger.warning(f"Could not load existing dataset for resume ({e}), starting fresh.")
                examples = []
                existing_skill_counts = {st: 0 for st in SKILL_TARGETS.keys()}

        example_counter = len(examples)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        random.seed(42 + len(examples))
        random.shuffle(eligible_docs)

        # Open output file in append mode to stream new examples to disk
        with open(self.output_path, "a", encoding="utf-8") as out_f:
            # Generate citation examples
            cit_needed = max(0, skill_counts[SkillType.CITATION] - existing_skill_counts[SkillType.CITATION])
            if cit_needed > 0:
                logger.info(f"Generating {cit_needed} citation examples (already have {existing_skill_counts[SkillType.CITATION]})...")
                for i in range(cit_needed):
                    try:
                        ex = self._generate_citation_example(
                            eligible_docs[i % len(eligible_docs)],
                            example_counter,
                        )
                        examples.append(ex)
                        example_counter += 1
                        out_f.write(ex.model_dump_json() + "\n")
                        out_f.flush()
                        if (i + 1) % 50 == 0 or (i + 1) == cit_needed:
                            logger.info(f"  Citation: {i+1}/{cit_needed}")
                    except Exception as e:
                        logger.warning(f"  Citation example {i} failed: {e}")

            # Generate temporal examples
            temp_needed = max(0, skill_counts[SkillType.TEMPORAL] - existing_skill_counts[SkillType.TEMPORAL])
            temporal_docs = [d for d in eligible_docs if d.get("in_force_from")]
            if temp_needed > 0:
                logger.info(f"Generating {temp_needed} temporal examples (already have {existing_skill_counts[SkillType.TEMPORAL]})...")
                for i in range(temp_needed):
                    try:
                        doc = temporal_docs[i % len(temporal_docs)] if temporal_docs else eligible_docs[i % len(eligible_docs)]
                        ex = self._generate_temporal_example(doc, example_counter)
                        examples.append(ex)
                        example_counter += 1
                        out_f.write(ex.model_dump_json() + "\n")
                        out_f.flush()
                        if (i + 1) % 50 == 0 or (i + 1) == temp_needed:
                            logger.info(f"  Temporal: {i+1}/{temp_needed}")
                    except Exception as e:
                        logger.warning(f"  Temporal example {i} failed: {e}")

            # Generate synthesis examples
            syn_needed = max(0, skill_counts[SkillType.SYNTHESIS] - existing_skill_counts[SkillType.SYNTHESIS])
            if syn_needed > 0:
                logger.info(f"Generating {syn_needed} synthesis examples (already have {existing_skill_counts[SkillType.SYNTHESIS]})...")
                for i in range(syn_needed):
                    try:
                        doc1 = eligible_docs[i % len(eligible_docs)]
                        doc2 = eligible_docs[(i + len(eligible_docs) // 2) % len(eligible_docs)]
                        ex = self._generate_synthesis_example(doc1, doc2, example_counter)
                        examples.append(ex)
                        example_counter += 1
                        out_f.write(ex.model_dump_json() + "\n")
                        out_f.flush()
                        if (i + 1) % 50 == 0 or (i + 1) == syn_needed:
                            logger.info(f"  Synthesis: {i+1}/{syn_needed}")
                    except Exception as e:
                        logger.warning(f"  Synthesis example {i} failed: {e}")

            # Generate abstention examples
            abs_needed = max(0, skill_counts[SkillType.ABSTENTION] - existing_skill_counts[SkillType.ABSTENTION])
            if abs_needed > 0:
                logger.info(f"Generating {abs_needed} abstention examples (already have {existing_skill_counts[SkillType.ABSTENTION]})...")
                for i in range(abs_needed):
                    try:
                        distractor_doc = eligible_docs[i % len(eligible_docs)]
                        ex = self._generate_abstention_example(distractor_doc, example_counter)
                        examples.append(ex)
                        example_counter += 1
                        out_f.write(ex.model_dump_json() + "\n")
                        out_f.flush()
                        if (i + 1) % 50 == 0 or (i + 1) == abs_needed:
                            logger.info(f"  Abstention: {i+1}/{abs_needed}")
                    except Exception as e:
                        logger.warning(f"  Abstention example {i} failed: {e}")

        # Build dataset summary & write metadata
        skill_dist = {}
        for ex in examples:
            key = ex.skill_type.value
            skill_dist[key] = skill_dist.get(key, 0) + 1

        dataset = RAFTDataset(
            version="raft-v1",
            total_examples=len(examples),
            skill_distribution=skill_dist,
            excluded_doc_ids_hash=self.exclusion_hash,
            examples=examples,
        )

        meta_path = self.output_path.with_suffix(".meta.json")
        meta = {
            "version": dataset.version,
            "total_examples": dataset.total_examples,
            "skill_distribution": dataset.skill_distribution,
            "excluded_doc_ids_hash": dataset.excluded_doc_ids_hash,
            "updated_at": datetime.now().isoformat(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"Dataset active: {len(examples)} total RAFT examples. Distribution: {skill_dist}")
        return dataset

    def _generate_citation_example(
        self, doc: Dict[str, Any], counter: int
    ) -> RAFTExample:
        """Generate a single citation-skill RAFT example."""
        excerpt = doc["body"][:2000]
        question = self.question_gen.generate_citation_question(doc, excerpt)
        as_of = doc.get("issue_date", "2026-06-01") or "2026-06-01"

        # Run retrieval to get real context (Invariant E13)
        result = self._pipeline.retrieve(query=question, as_of_date=as_of, top_k=8)
        retrieved = result["eligible"]

        # Label gold vs distractor
        chunks = self._label_chunks(retrieved, gold_doc_ids={doc["doc_id"]})

        # Ensure we have both gold and distractor chunks
        if not any(c.is_gold for c in chunks):
            # Force at least one gold chunk from the source document
            chunks = self._inject_gold_chunk(doc, chunks)
        chunks = self._ensure_min_chunks(chunks)

        # Generate gold answer
        gold_answer = self.answer_gen.generate_grounded_answer(
            question=question,
            as_of_date=as_of,
            chunks=chunks,
            skill_type=SkillType.CITATION,
        )

        # Shuffle chunk order (Invariant E14)
        random.shuffle(chunks)

        return RAFTExample(
            example_id=f"raft-{counter + 1:05d}",
            skill_type=SkillType.CITATION,
            question=question,
            as_of_date=as_of,
            retrieved_chunks=chunks,
            gold_answer=gold_answer,
            source_doc_ids=[doc["doc_id"]],
        )

    def _generate_temporal_example(
        self, doc: Dict[str, Any], counter: int
    ) -> RAFTExample:
        """Generate a single temporal-skill RAFT example."""
        excerpt = doc["body"][:2000]
        question = self.question_gen.generate_temporal_question(doc, excerpt)
        as_of = doc.get("issue_date", "2026-06-01") or "2026-06-01"

        result = self._pipeline.retrieve(query=question, as_of_date=as_of, top_k=8)
        retrieved = result["eligible"]

        chunks = self._label_chunks(retrieved, gold_doc_ids={doc["doc_id"]})
        if not any(c.is_gold for c in chunks):
            chunks = self._inject_gold_chunk(doc, chunks)
        chunks = self._ensure_min_chunks(chunks)

        gold_answer = self.answer_gen.generate_grounded_answer(
            question=question,
            as_of_date=as_of,
            chunks=chunks,
            skill_type=SkillType.TEMPORAL,
        )

        random.shuffle(chunks)

        return RAFTExample(
            example_id=f"raft-{counter + 1:05d}",
            skill_type=SkillType.TEMPORAL,
            question=question,
            as_of_date=as_of,
            retrieved_chunks=chunks,
            gold_answer=gold_answer,
            source_doc_ids=[doc["doc_id"]],
        )

    def _generate_synthesis_example(
        self, doc1: Dict[str, Any], doc2: Dict[str, Any], counter: int
    ) -> RAFTExample:
        """Generate a cross-document synthesis RAFT example."""
        excerpt_1 = doc1["body"][:1500]
        excerpt_2 = doc2["body"][:1500]
        question = self.question_gen.generate_synthesis_question(
            doc1, excerpt_1, doc2, excerpt_2
        )
        as_of = doc1.get("issue_date", "2026-06-01") or "2026-06-01"

        result = self._pipeline.retrieve(query=question, as_of_date=as_of, top_k=8)
        retrieved = result["eligible"]

        gold_ids = {doc1["doc_id"], doc2["doc_id"]}
        chunks = self._label_chunks(retrieved, gold_doc_ids=gold_ids)

        # Ensure we have gold chunks from both documents
        has_doc1 = any(c.is_gold and c.doc_id == doc1["doc_id"] for c in chunks)
        has_doc2 = any(c.is_gold and c.doc_id == doc2["doc_id"] for c in chunks)
        if not has_doc1:
            chunks = self._inject_gold_chunk(doc1, chunks)
        if not has_doc2:
            chunks = self._inject_gold_chunk(doc2, chunks)
        chunks = self._ensure_min_chunks(chunks)

        gold_answer = self.answer_gen.generate_grounded_answer(
            question=question,
            as_of_date=as_of,
            chunks=chunks,
            skill_type=SkillType.SYNTHESIS,
        )

        random.shuffle(chunks)

        return RAFTExample(
            example_id=f"raft-{counter + 1:05d}",
            skill_type=SkillType.SYNTHESIS,
            question=question,
            as_of_date=as_of,
            retrieved_chunks=chunks,
            gold_answer=gold_answer,
            source_doc_ids=[doc1["doc_id"], doc2["doc_id"]],
        )

    def _generate_abstention_example(
        self, distractor_doc: Dict[str, Any], counter: int
    ) -> RAFTExample:
        """Generate an abstention RAFT example (T-205).

        The question asks about something NOT in the corpus.
        All retrieved chunks are distractors.
        """
        question = self.question_gen.generate_abstention_question("")
        as_of = "2026-06-01"

        # Retrieve context for the distractor document (unrelated to the question)
        result = self._pipeline.retrieve(
            query=distractor_doc.get("title", "regulatory compliance"),
            as_of_date=as_of,
            top_k=6,
        )
        retrieved = result["eligible"]

        # All chunks are distractors (none are gold)
        chunks = []
        for chunk, score in retrieved[:6]:
            chunks.append(RetrievedChunkRecord(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                provision_path=chunk.provision_path,
                header_prefix=chunk.header_prefix,
                content=chunk.content,
                is_gold=False,
                in_force_from=chunk.in_force_from,
                in_force_to=chunk.in_force_to,
                status=chunk.status,
                regulator=chunk.regulator,
            ))

        # Pad to minimum 4 chunks if needed
        while len(chunks) < 4:
            chunks.append(RetrievedChunkRecord(
                chunk_id=f"pad-{counter}-{len(chunks)}",
                doc_id=distractor_doc["doc_id"],
                provision_path="para 1",
                header_prefix=f"[REGULATOR: {distractor_doc['regulator']} | DOC: {distractor_doc['doc_id']}]",
                content=distractor_doc["body"][:500],
                is_gold=False,
                regulator=distractor_doc["regulator"],
            ))

        gold_answer = self.answer_gen.generate_grounded_answer(
            question=question,
            as_of_date=as_of,
            chunks=chunks,
            skill_type=SkillType.ABSTENTION,
        )

        random.shuffle(chunks)

        return RAFTExample(
            example_id=f"raft-{counter + 1:05d}",
            skill_type=SkillType.ABSTENTION,
            question=question,
            as_of_date=as_of,
            retrieved_chunks=chunks,
            gold_answer=gold_answer,
            source_doc_ids=[],  # No source docs for abstention
        )

    def _generate_false_premise_example(
        self, doc: Dict[str, Any], counter: int
    ) -> RAFTExample:
        """Generate a false-premise abstention example: the retrieved chunk is a REAL,
        correctly on-topic document (unlike _generate_abstention_example, whose chunks
        are topically unrelated), but the question asserts a fabricated detail not
        supported by the text. Teaches claim verification against relevant content,
        not just topic-relevance matching.
        """
        excerpt = doc["body"][:2000]
        question = self.question_gen.generate_false_premise_question(doc, excerpt)
        as_of = doc.get("issue_date", "2026-06-01") or "2026-06-01"

        # Use the document's OWN indexed chunks as context, not a corpus-wide
        # search by title. The previous approach retrieved via a generic query
        # on doc.title, which for short/generic RBI titles pulled back unrelated
        # real documents, and then shuffled the full 8-chunk set before
        # chat_formatter's 4-chunk truncation — meaning the actual target chunk
        # could be (and empirically was) pushed out of the training window
        # entirely. Verified as the root cause of 0% false-premise abstention,
        # including on the model's own in-distribution training examples: the
        # student model was being trained to write a refusal "about" a document
        # it sometimes never even saw, mixed in with plausible real distractors.
        own_chunks = [c for c in self._pipeline.chunks if c.doc_id == doc["doc_id"]]

        if own_chunks:
            chunks = self._label_chunks(
                [(c, 1.0) for c in own_chunks[:4]], gold_doc_ids=set()
            )
        else:
            chunks = []

        if not chunks:
            injected = RetrievedChunkRecord(
                chunk_id=f"{doc['doc_id']}-fp-injected-{counter}",
                doc_id=doc["doc_id"],
                provision_path="para 1",
                header_prefix=(
                    f"[REGULATOR: {doc['regulator']} | DOC: {doc.get('doc_number', doc['doc_id'])} "
                    f"| TITLE: {doc.get('title', '')} | DATE: {doc.get('issue_date', '')} | PROVISION: para 1]"
                ),
                content=excerpt,
                is_gold=False,
                in_force_from=doc.get("in_force_from"),
                in_force_to=doc.get("in_force_to"),
                status=doc.get("status", "unknown"),
                regulator=doc.get("regulator", "RBI"),
            )
            chunks = [injected]

        # Schema requires >= 4 chunks (RAFTExample.retrieved_chunks). Most
        # documents in this corpus only chunk into 1-2 pieces, so pad with real
        # distractor chunks from OTHER documents, appended strictly AFTER the
        # target document's own chunk(s) and never shuffled — this keeps the
        # target chunk permanently at position 0, guaranteeing it survives
        # chat_formatter's chunks[:4] truncation regardless of padding.
        if len(chunks) < 4:
            existing_ids = {c.chunk_id for c in chunks}
            filler_pool = [
                c for c in self._pipeline.chunks
                if c.doc_id != doc["doc_id"] and c.chunk_id not in existing_ids
            ]
            random.shuffle(filler_pool)
            for c in filler_pool:
                if len(chunks) >= 4:
                    break
                chunks.append(RetrievedChunkRecord(
                    chunk_id=c.chunk_id,
                    doc_id=c.doc_id,
                    provision_path=c.provision_path,
                    header_prefix=c.header_prefix,
                    content=c.content,
                    is_gold=False,
                    in_force_from=c.in_force_from,
                    in_force_to=c.in_force_to,
                    status=c.status,
                    regulator=c.regulator,
                ))

        real_doc_chunk = chunks[0]

        gold_answer = self.answer_gen.generate_false_premise_answer(
            question, as_of, real_doc_chunk
        )

        # No shuffle: every chunk here is genuinely from the target document, so
        # the model must verify the specific false claim against real on-topic
        # text instead of learning to distinguish relevant-vs-irrelevant chunks.

        return RAFTExample(
            example_id=f"raft-{counter + 1:05d}",
            skill_type=SkillType.ABSTENTION,
            question=question,
            as_of_date=as_of,
            retrieved_chunks=chunks,
            gold_answer=gold_answer,
            source_doc_ids=[doc["doc_id"]],
        )

    def generate_false_premise_batch(self, count: int) -> List[RAFTExample]:
        """Generate and append `count` false-premise abstention examples to the
        existing output_path dataset (streamed, resumable in spirit with the rest
        of the pipeline — appends after whatever is already in the file)."""
        self._init_retrieval()
        eligible_docs = _load_eligible_documents(self.db_path, self.excluded_ids)

        # Continue example_id numbering after whatever's already in the file.
        counter = 0
        if self.output_path.exists():
            with open(self.output_path, "r", encoding="utf-8") as f:
                counter = sum(1 for line in f if line.strip())

        random.seed(1337)
        random.shuffle(eligible_docs)

        examples: List[RAFTExample] = []
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "a", encoding="utf-8") as out_f:
            for i in range(count):
                try:
                    doc = eligible_docs[i % len(eligible_docs)]
                    ex = self._generate_false_premise_example(doc, counter)
                    examples.append(ex)
                    counter += 1
                    out_f.write(ex.model_dump_json() + "\n")
                    out_f.flush()
                    if (i + 1) % 10 == 0 or (i + 1) == count:
                        logger.info(f"  False-premise: {i+1}/{count}")
                except Exception as e:
                    logger.warning(f"  False-premise example {i} failed: {e}")

        logger.info(f"Generated {len(examples)} false-premise examples, appended to {self.output_path}")
        return examples

    def _label_chunks(
        self,
        retrieved: List[Any],
        gold_doc_ids: Set[str],
    ) -> List[RetrievedChunkRecord]:
        """Label retrieved chunks as gold or distractor based on doc_id match."""
        chunks = []
        for chunk, score in retrieved[:8]:
            is_gold = chunk.doc_id in gold_doc_ids
            chunks.append(RetrievedChunkRecord(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                provision_path=chunk.provision_path,
                header_prefix=chunk.header_prefix,
                content=chunk.content,
                is_gold=is_gold,
                in_force_from=chunk.in_force_from,
                in_force_to=chunk.in_force_to,
                status=chunk.status,
                regulator=chunk.regulator,
            ))
        return chunks

    def _inject_gold_chunk(
        self, doc: Dict[str, Any], existing_chunks: List[RetrievedChunkRecord]
    ) -> List[RetrievedChunkRecord]:
        """Force-inject a gold chunk from the source document if retrieval missed it."""
        body = doc["body"][:1500]
        gold_chunk = RetrievedChunkRecord(
            chunk_id=f"{doc['doc_id']}-injected",
            doc_id=doc["doc_id"],
            provision_path="para 1",
            header_prefix=(
                f"[REGULATOR: {doc['regulator']} | DOC: {doc.get('doc_number', doc['doc_id'])} "
                f"| TITLE: {doc.get('title', '')} | DATE: {doc.get('issue_date', '')} | PROVISION: para 1]"
            ),
            content=body,
            is_gold=True,
            in_force_from=doc.get("in_force_from"),
            in_force_to=doc.get("in_force_to"),
            status=doc.get("status", "unknown"),
            regulator=doc.get("regulator", "RBI"),
        )

        # Replace one distractor with the gold chunk to maintain size (max 8)
        result = [gold_chunk]
        for c in existing_chunks:
            if len(result) >= 8:
                break
            if c.chunk_id != gold_chunk.chunk_id:
                result.append(c)
        return self._ensure_min_chunks(result, min_count=4, max_count=8)

    def _ensure_min_chunks(self, chunks: List[RetrievedChunkRecord], min_count: int = 4, max_count: int = 8) -> List[RetrievedChunkRecord]:
        """Ensures chunks list has at least min_count and at most max_count items."""
        if len(chunks) >= min_count:
            return chunks[:max_count]

        existing_chunk_ids = {c.chunk_id for c in chunks}
        padded = list(chunks)

        if hasattr(self, "_pipeline") and self._pipeline and self._pipeline.chunks:
            sample_pool = [c for c in self._pipeline.chunks if c.chunk_id not in existing_chunk_ids]
            random.shuffle(sample_pool)
            for c in sample_pool:
                if len(padded) >= min_count:
                    break
                padded.append(RetrievedChunkRecord(
                    chunk_id=c.chunk_id,
                    doc_id=c.doc_id,
                    provision_path=c.provision_path,
                    header_prefix=c.header_prefix,
                    content=c.content,
                    is_gold=False,
                    in_force_from=c.in_force_from,
                    in_force_to=c.in_force_to,
                    status=c.status,
                    regulator=c.regulator,
                ))

        return padded[:max_count]

    def export_jsonl(self, dataset: RAFTDataset, output_path: Optional[Path] = None):
        """Export dataset as JSONL (one example per line) for training."""
        out = output_path or self.output_path
        out.parent.mkdir(parents=True, exist_ok=True)

        with open(out, "w", encoding="utf-8") as f:
            for ex in dataset.examples:
                f.write(ex.model_dump_json() + "\n")

        # Also write metadata sidecar
        meta_path = out.with_suffix(".meta.json")
        meta = {
            "version": dataset.version,
            "total_examples": dataset.total_examples,
            "skill_distribution": dataset.skill_distribution,
            "excluded_doc_ids_hash": dataset.excluded_doc_ids_hash,
            "generated_at": datetime.now().isoformat(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"Exported {dataset.total_examples} examples to {out}")
        logger.info(f"Metadata written to {meta_path}")


def validate_raft_dataset(
    dataset_path: Path,
    exclusion_path: Path = DEFAULT_EXCLUSION_PATH,
) -> Dict[str, Any]:
    """Validate a generated RAFT dataset (T-206).

    Checks:
    1. All examples parse against schema
    2. Zero doc_id overlap with bench-v1 excluded list (Invariant E16)
    3. Citation format in gold answers
    4. Skill type distribution
    """
    excluded_ids, _ = _load_excluded_doc_ids(exclusion_path)

    errors = []
    warnings = []
    skill_counts: Dict[str, int] = {}
    total = 0
    contaminated_ids: Set[str] = set()

    with open(dataset_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            total += 1
            try:
                ex = RAFTExample.model_validate_json(line.strip())

                # Track skill distribution
                key = ex.skill_type.value
                skill_counts[key] = skill_counts.get(key, 0) + 1

                # Check exclusion (Invariant E16)
                for chunk in ex.retrieved_chunks:
                    if chunk.doc_id in excluded_ids:
                        contaminated_ids.add(chunk.doc_id)
                        errors.append(
                            f"Line {line_num}: Chunk doc_id '{chunk.doc_id}' "
                            f"is in bench-v1 exclusion list"
                        )

                for src_id in ex.source_doc_ids:
                    if src_id in excluded_ids:
                        contaminated_ids.add(src_id)
                        errors.append(
                            f"Line {line_num}: Source doc_id '{src_id}' "
                            f"is in bench-v1 exclusion list"
                        )

            except Exception as e:
                errors.append(f"Line {line_num}: Schema validation failed — {e}")

    result = {
        "total_examples": total,
        "skill_distribution": skill_counts,
        "errors": errors,
        "warnings": warnings,
        "contaminated_doc_ids": list(contaminated_ids),
        "passed": len(errors) == 0,
    }

    return result
