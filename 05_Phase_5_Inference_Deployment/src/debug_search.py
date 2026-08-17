import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project\Phase 5 - Inference\src")))
from rag_engine import RegulatoryRAGEngine

rag = RegulatoryRAGEngine()
q1 = "What regulatory requirements apply under Auction for Sale (Re-issue) of 7.73 per cent Government Stock 2034 (rbi:rbi_notifications:10321)?"
chunks1 = rag.search_regulatory_context(q1)
print(f"Q1 (In-Corpus) Chunks: {len(chunks1)}")
for c in chunks1:
    print("  ->", c["doc_id"], "| Score:", c["relevance_score"], "| Title:", c["title"])

q2 = "What are the mandatory capital reserve ratios for cryptocurrency staking operators under RBI Circular 99999?"
chunks2 = rag.search_regulatory_context(q2)
print(f"Q2 (Out-of-Corpus) Chunks: {len(chunks2)}")
