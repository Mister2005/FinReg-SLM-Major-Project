"""Structure-aware provision chunker for regulatory text (T-107)."""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class RegulatoryChunk:
    chunk_id: str
    doc_id: str
    provision_path: str
    header_prefix: str
    content: str
    embedded_text: str
    in_force_from: Optional[str] = None
    in_force_to: Optional[str] = None
    status: str = "unknown"
    statutory_regime: Optional[str] = None
    regulator: str = "RBI"
    is_table: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


PROVISION_PATTERN = re.compile(
    r'(?=\n(?:Section\s+\d+|Para(?:graph)?\s+\d+|Chapter\s+[I|V|X]+|\(\d+\)|\d+\.\d+))',
    re.IGNORECASE
)


class StructureAwareChunker:
    """Chunker that splits documents at provision boundaries while preserving tables and injecting header prefixes."""

    def __init__(self, target_tokens: int = 512, max_tokens: int = 1024):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.target_chars = target_tokens * 4  # ~4 chars per token rule of thumb
        self.max_chars = max_tokens * 4

    def chunk_document(self, doc_metadata: Dict[str, Any], text_body: str, tables: Optional[List[str]] = None) -> List[RegulatoryChunk]:
        chunks: List[RegulatoryChunk] = []
        doc_id = doc_metadata.get("doc_id", "UNKNOWN_DOC")
        regulator = doc_metadata.get("regulator", "RBI")
        doc_number = doc_metadata.get("doc_number", "") or doc_id
        title = doc_metadata.get("title", "")
        issue_date = doc_metadata.get("issue_date", "")
        in_force_from = doc_metadata.get("in_force_from") or issue_date
        in_force_to = doc_metadata.get("in_force_to")
        status = doc_metadata.get("status", "unknown")
        statutory_regime = doc_metadata.get("statutory_regime")

        # 1. Add tables as whole standalone chunks
        if tables:
            for idx, tbl in enumerate(tables, start=1):
                path = f"Table {idx}"
                prefix = f"[REGULATOR: {regulator} | DOC: {doc_number} | TITLE: {title} | DATE: {issue_date} | PROVISION: {path}]"
                embedded = f"{prefix}\n{tbl}"
                c_id = f"{doc_id}-tbl-{idx}"
                chunks.append(RegulatoryChunk(
                    chunk_id=c_id,
                    doc_id=doc_id,
                    provision_path=path,
                    header_prefix=prefix,
                    content=tbl,
                    embedded_text=embedded,
                    in_force_from=in_force_from,
                    in_force_to=in_force_to,
                    status=status,
                    statutory_regime=statutory_regime,
                    regulator=regulator,
                    is_table=True
                ))

        if not text_body:
            return chunks

        # 2. Split body on provision boundaries
        provisions = [p.strip() for p in PROVISION_PATTERN.split(text_body) if p.strip()]
        if not provisions:
            provisions = [text_body.strip()]

        current_block = ""
        current_path = "para 1"
        chunk_counter = 1

        for prov in provisions:
            # Extract provision label if present
            label_match = re.search(r'^(Section\s+\d+|Para(?:graph)?\s+\d+|Chapter\s+[I|V|X]+|\d+\.\d+)', prov, re.IGNORECASE)
            prov_label = label_match.group(0) if label_match else current_path

            if len(current_block) + len(prov) > self.max_chars and current_block:
                # Emit accumulated chunk
                prefix = f"[REGULATOR: {regulator} | DOC: {doc_number} | TITLE: {title} | DATE: {issue_date} | PROVISION: {current_path}]"
                embedded = f"{prefix}\n{current_block}"
                c_id = f"{doc_id}-chunk-{chunk_counter}"
                chunks.append(RegulatoryChunk(
                    chunk_id=c_id,
                    doc_id=doc_id,
                    provision_path=current_path,
                    header_prefix=prefix,
                    content=current_block,
                    embedded_text=embedded,
                    in_force_from=in_force_from,
                    in_force_to=in_force_to,
                    status=status,
                    statutory_regime=statutory_regime,
                    regulator=regulator,
                    is_table=False
                ))
                chunk_counter += 1
                current_block = prov
                current_path = prov_label
            else:
                if current_block:
                    current_block += "\n\n" + prov
                else:
                    current_block = prov
                    current_path = prov_label

        if current_block:
            prefix = f"[REGULATOR: {regulator} | DOC: {doc_number} | TITLE: {title} | DATE: {issue_date} | PROVISION: {current_path}]"
            embedded = f"{prefix}\n{current_block}"
            c_id = f"{doc_id}-chunk-{chunk_counter}"
            chunks.append(RegulatoryChunk(
                chunk_id=c_id,
                doc_id=doc_id,
                provision_path=current_path,
                header_prefix=prefix,
                content=current_block,
                embedded_text=embedded,
                in_force_from=in_force_from,
                in_force_to=in_force_to,
                status=status,
                statutory_regime=statutory_regime,
                regulator=regulator,
                is_table=False
            ))

        return chunks
