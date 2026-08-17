"""End-to-End Smoke Test for Phase 5 Inference Engine."""

import logging
from pathlib import Path
import json

from rag_engine import RegulatoryRAGEngine
from model_server import ComplianceModelServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("e2e_verify")

def run_e2e_smoke_test():
    logger.info("=== STARTING PHASE 5 END-TO-END SMOKE TEST ===")
    
    # 1. Initialize RAG Engine
    logger.info("1. Loading RAG Engine...")
    rag = RegulatoryRAGEngine()
    
    # 2. Initialize Model Server
    logger.info("2. Loading DeepSeek-R1-7B DPO Model Server...")
    server = ComplianceModelServer(load_in_4bit=True)
    
    test_queries = [
        {
            "type": "C1 - Factual Grounding",
            "query": "What regulatory requirements apply under Auction for Sale (Re-issue) of 7.73 per cent Government Stock 2034 (rbi:rbi_notifications:10321)?",
            "as_of_date": "2026-06-01",
            "expect_abstain": False,
        },
        {
            "type": "C5 - Out-of-Corpus Abstention",
            "query": "What are the mandatory capital reserve ratios for cryptocurrency staking operators under RBI Circular 99999?",
            "as_of_date": "2026-06-01",
            "expect_abstain": True,
        }
    ]
    
    for idx, tq in enumerate(test_queries):
        logger.info(f"\n--- Testing Query {idx+1}: [{tq['type']}] ---")
        logger.info(f"Question: {tq['query']}")
        
        # Retrieve chunks
        chunks = rag.search_regulatory_context(tq['query'], as_of_date=tq['as_of_date'])
        logger.info(f"Retrieved {len(chunks)} context chunks.")
        
        # Build prompt
        messages = rag.build_inference_messages(tq['query'], chunks, as_of_date=tq['as_of_date'])
        
        # Run inference
        res = server.generate(messages, max_new_tokens=256)
        logger.info(f"Reasoning: {res['reasoning'][:120]}..." if res['reasoning'] else "Reasoning: Direct completion")
        logger.info(f"Answer: {res['answer']}")
        logger.info(f"Citations Found: {res['citations']}")
        logger.info(f"Abstained: {res['is_abstained']} (Expected: {tq['expect_abstain']})")
        logger.info(f"Latency: {res['latency_seconds']}s")
        
        if tq['expect_abstain']:
            assert res['is_abstained'], "Expected model to abstain on out-of-corpus query!"
        else:
            assert len(res['citations']) > 0, "Expected model to generate inline citations!"
            
    logger.info("\n=== ALL E2E SMOKE TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_e2e_smoke_test()
