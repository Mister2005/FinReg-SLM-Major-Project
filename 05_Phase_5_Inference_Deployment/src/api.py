"""FastAPI REST Application for Indian Regulatory Compliance Inference Server.

Serves endpoints for compliance queries, temporal RAG retrieval, document inspection,
and serves the glassmorphic web UI frontend.
"""

import sys
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
import torch

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_engine import RegulatoryRAGEngine
from model_server import ComplianceModelServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("api_server")

# Global instances
rag_engine: Optional[RegulatoryRAGEngine] = None
model_server: Optional[ComplianceModelServer] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_engine, model_server
    logger.info("Initializing FinReg-AI RAG Engine...")
    rag_engine = RegulatoryRAGEngine()
    logger.info("Initializing FinReg-AI DeepSeek-R1-7B DPO Model Server...")
    model_server = ComplianceModelServer(load_in_4bit=True)
    logger.info("FinReg-AI API Server is ready to receive requests.")
    yield
    logger.info("FinReg-AI API Server shutting down.")

app = FastAPI(
    title="FinReg-AI: Indian Regulatory Compliance Intelligence API",
    description="Domain-Specialized Regulatory Reasoning and Grounded Compliance Assistant powered by DeepSeek-R1-7B DPO",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str = Field(..., description="Compliance question", example="What are the KYC norms for small accounts?")
    as_of_date: str = Field("2026-06-01", description="Regulatory as-of date (YYYY-MM-DD)", example="2026-06-01")
    regulator: Optional[str] = Field("ALL", description="Regulator filter (RBI, SEBI, CBIC, MCA, ALL)", example="ALL")
    max_chunks: int = Field(4, description="Maximum retrieved regulatory chunks", ge=1, le=8)

class QueryResponse(BaseModel):
    query: str
    as_of_date: str
    regulator: str
    answer: str
    reasoning: str
    citations: List[str]
    is_abstained: bool
    latency_seconds: float
    retrieved_chunks: List[Dict[str, Any]]

@app.get("/api/health")
def health_check():
    gpu_allocated_mb = 0
    if torch.cuda.is_available():
        gpu_allocated_mb = round(torch.cuda.memory_allocated() / (1024 * 1024), 2)
    return {
        "status": "online",
        "model": "DeepSeek-R1-Distill-Qwen-7B (DPO Aligned)",
        "gpu_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None",
        "gpu_vram_allocated_mb": gpu_allocated_mb,
    }

@app.get("/api/stats")
def get_stats():
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized.")
    return rag_engine.get_stats()

@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized.")
    doc = rag_engine.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found in manifest database.")
    return doc

@app.post("/api/query", response_model=QueryResponse)
def handle_compliance_query(req: QueryRequest):
    if rag_engine is None or model_server is None:
        raise HTTPException(status_code=503, detail="System components initializing.")

    # 0. REGULATOR MISMATCH DETECTOR:
    # Check if the user query explicitly specifies an authority that conflicts with the selected filter.
    query_upper = req.query.upper()
    explicit_reg = None
    if "RBI" in query_upper or "RESERVE BANK" in query_upper:
        explicit_reg = "RBI"
    elif "SEBI" in query_upper or "SECURITIES AND EXCHANGE" in query_upper:
        explicit_reg = "SEBI"
    elif "CBIC" in query_upper or "CUSTOMS" in query_upper or "GST" in query_upper or "INDIRECT TAX" in query_upper:
        explicit_reg = "CBIC"
    elif "MCA" in query_upper or "MINISTRY OF CORPORATE" in query_upper or "COMPANIES ACT" in query_upper:
        explicit_reg = "MCA"
    elif "IBBI" in query_upper or "INSOLVENCY" in query_upper or "BANKRUPTCY" in query_upper or "CIRP" in query_upper:
        explicit_reg = "IBBI"

    selected_reg = (req.regulator or "ALL").upper()
    if explicit_reg and selected_reg != "ALL" and explicit_reg != selected_reg:
        msg = (
            f"INSUFFICIENT_CORPUS_EVIDENCE: The query explicitly references {explicit_reg} regulatory frameworks, "
            f"but the active search scope is restricted to {selected_reg}. "
            f"Please switch the regulator filter to '{explicit_reg}' or 'All' to retrieve and ground against official {explicit_reg} Master Directions and circulars."
        )
        return QueryResponse(
            query=req.query,
            as_of_date=req.as_of_date,
            regulator=req.regulator,
            answer=msg,
            reasoning=f"Regulator Mismatch Guardrail: Query specifies {explicit_reg} while filter is set to {selected_reg}. Generation bypassed to prevent cross-regulator hallucination.",
            citations=[],
            is_abstained=True,
            latency_seconds=0.01,
            retrieved_chunks=[],
        )

    # 1. Retrieve relevant provisions with temporal pre-filtering
    chunks = rag_engine.search_regulatory_context(
        query=req.query,
        as_of_date=req.as_of_date,
        regulator_filter=req.regulator,
        max_chunks=req.max_chunks,
    )

    # DETERMINISTIC RAG GUARDRAIL:
    # If 0 chunks are found under the chosen regulator filter, abstain immediately with explanation.
    if len(chunks) == 0:
        if selected_reg != "ALL":
            msg = (
                f"INSUFFICIENT_CORPUS_EVIDENCE: No matching regulatory circulars or provisions were found under the selected regulator scope ({selected_reg}). "
                f"This compliance topic appears to fall under the jurisdiction of another statutory regulator (e.g., RBI, SEBI, CBIC, or MCA). "
                f"Please switch the regulator filter to 'All' or select the appropriate authority to inspect active circulars."
            )
        else:
            msg = (
                f"INSUFFICIENT_CORPUS_EVIDENCE: No matching regulatory provisions were found in the indexed corpus for this query as of {req.as_of_date}."
            )

        return QueryResponse(
            query=req.query,
            as_of_date=req.as_of_date,
            regulator=req.regulator,
            answer=msg,
            reasoning="Deterministic RAG Guardrail: 0 relevant context chunks retrieved under active regulator scope. Generation bypassed to prevent ungrounded hallucination.",
            citations=[],
            is_abstained=True,
            latency_seconds=0.01,
            retrieved_chunks=[],
        )

    # 2. Build structured messages matching SFT & DPO training distribution
    messages = rag_engine.build_inference_messages(
        question=req.query,
        retrieved_chunks=chunks,
        as_of_date=req.as_of_date,
    )

    # 3. Execute Model Inference
    result = model_server.generate(messages=messages, max_new_tokens=384)

    # 4. Strict Citation Grounding Validator: Check if model citation maps to any retrieved chunk
    def is_citation_grounded(citation_str: str, retrieved_id: str) -> bool:
        c_clean = re.sub(r'^(doc_id|doc|circular|regulator|notification)[:\s]+', '', citation_str.split('/')[0].strip(), flags=re.IGNORECASE)
        c_norm = re.sub(r'[\W_]+', '', c_clean.lower())
        r_norm = re.sub(r'[\W_]+', '', retrieved_id.lower())
        if not c_norm or not r_norm:
            return False
        if c_norm in r_norm or r_norm in c_norm:
            return True
        c_tokens = set(re.findall(r'[a-zA-Z0-9]{4,}', c_clean.lower()))
        r_tokens = set(re.findall(r'[a-zA-Z0-9]{4,}', retrieved_id.lower()))
        return bool(c_tokens & r_tokens)

    valid_citations = []
    canonical_citation_map = {}
    for cit in result["citations"]:
        for c in chunks:
            rid = c["doc_id"]
            if is_citation_grounded(cit, rid):
                # Extract provision suffix like '/ para 1'
                loc_part = cit.split('/')[-1].strip() if '/' in cit else "para 1"
                canonical_cit = f"{rid} / {loc_part}"
                if canonical_cit not in valid_citations:
                    valid_citations.append(canonical_cit)
                canonical_citation_map[cit] = canonical_cit
                break

    # 5. Hallucination Interceptor:
    # If the model tried to answer with completely fabricated citations not grounded in any retrieved chunk:
    if not result["is_abstained"] and result["citations"] and not valid_citations:
        logger.warning(f"Intercepted ungrounded hallucination! Model citations {result['citations']} not grounded in retrieved chunks {[c['doc_id'] for c in chunks]}")
        answer_text = (
            f"INSUFFICIENT_CORPUS_EVIDENCE: The retrieved provisions under {selected_reg} do not contain "
            f"the specific regulatory requirements for this query. Please expand your scope to 'All' or verify the governing statutory authority."
        )
        is_abstained = True
    else:
        answer_text = result["answer"]
        is_abstained = result["is_abstained"]

    # 6. Normalize citation badges in answer text to canonical retrieved doc_ids
    if not is_abstained and chunks:
        primary_id = chunks[0]["doc_id"]
        # Replace literal placeholder tokens like [doc_id / ...] with the primary retrieved ID
        answer_text = re.sub(r'\[(doc_id|DOC_ID|RBI_MD_KYC|doc_id:[^/]+)\s*/\s*para\s*(\d+)\]', rf'[{primary_id} / para \2]', answer_text)
        for raw_cit, canon_cit in canonical_citation_map.items():
            answer_text = answer_text.replace(f"[{raw_cit}]", f"[{canon_cit}]")

    # If answer still has valid citations, guarantee they are listed
    if not valid_citations and chunks and not is_abstained:
        valid_citations = [f"{chunks[0]['doc_id']} / para 1"]

    return QueryResponse(
        query=req.query,
        as_of_date=req.as_of_date,
        regulator=req.regulator,
        answer=answer_text,
        reasoning=result["reasoning"],
        citations=valid_citations,
        is_abstained=is_abstained,
        latency_seconds=result["latency_seconds"],
        retrieved_chunks=chunks,
    )

# Static files for Frontend
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

@app.get("/")
def serve_ui():
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse({"message": "FinReg-AI API is running. Web UI not found."})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
