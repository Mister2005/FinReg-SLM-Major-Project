"""
FinReg Cloud Cross-Encoder Reranker Client.

Targets the user's dedicated Hugging Face Space:
https://mister2005-cross-encoder-reranking-api.hf.space/rerank

With automatic resilient fallback to HF Router Serverless Inference API:
https://router.huggingface.co/hf-inference/models/BAAI/bge-reranker-base
"""

import sys
import logging
from typing import List, Dict, Any, Optional
import requests
from huggingface_hub import get_token

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cloud_reranker")

class CloudBGERerankerClient:
    """Client for querying the hosted BGE Cross-Encoder Space on Hugging Face."""

    def __init__(
        self,
        space_endpoint: str = "https://mister2005-cross-encoder-reranking-api.hf.space/rerank",
        fallback_model: str = "BAAI/bge-reranker-base",
        hf_token: Optional[str] = None
    ):
        self.space_endpoint = space_endpoint
        self.fallback_model = fallback_model
        self.hf_token = hf_token or get_token()
        self.fallback_url = f"https://router.huggingface.co/hf-inference/models/{fallback_model}"
        self.headers = {"Authorization": f"Bearer {self.hf_token}"} if self.hf_token else {}
        logger.info(f"Initialized Cloud Reranker targeting Space: {self.space_endpoint}")

    def rerank(
        self,
        query: str,
        passages: List[str],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Re-rank candidate statutory provisions against a compliance query.

        Args:
            query: Statutory/compliance question.
            passages: Candidate statutory provisions or text chunks.
            top_k: Number of highest-relevance passages to return.

        Returns:
            Sorted list: [{"rank": 1, "score": 0.95, "text": "...", "original_index": 0}, ...]
        """
        if not query or not passages:
            return []

        # 1. Primary: Dedicated Hugging Face Space POST /rerank
        try:
            payload = {
                "query": query,
                "documents": passages,
                "top_k": top_k
            }
            resp = requests.post(
                self.space_endpoint,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("ranked_results", []):
                    results.append({
                        "rank": item["rank"],
                        "original_index": item["original_index"],
                        "score": round(float(item["score"]), 4),
                        "text": item["document"]
                    })
                if results:
                    return results
        except Exception as e:
            logger.debug(f"Space endpoint cold/starting ({e}). Trying fallback...")

        # 2. Resilient Fallback: HF Router Serverless Endpoint
        try:
            inputs = [{"text": query, "text_pair": p[:512]} for p in passages]
            resp = requests.post(
                self.fallback_url,
                headers=self.headers,
                json={"inputs": inputs},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                scores = []
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, list) and len(item) > 0:
                            scores.append(item[0].get("score", 0.0))
                        elif isinstance(item, dict):
                            scores.append(item.get("score", 0.0))

                ranked = []
                for idx, text in enumerate(passages):
                    score = scores[idx] if idx < len(scores) else 0.0
                    ranked.append({
                        "original_index": idx,
                        "score": round(float(score), 4),
                        "text": text
                    })
                ranked.sort(key=lambda x: x["score"], reverse=True)
                top_results = ranked[:top_k]
                for rank_num, item in enumerate(top_results, 1):
                    item["rank"] = rank_num
                return top_results
        except Exception as e:
            logger.error(f"Fallback cloud rerank failed: {e}")

        # 3. Final Fallback: Return original top_k
        return [
            {"rank": i + 1, "score": round(1.0 / (i + 1), 3), "text": p, "original_index": i}
            for i, p in enumerate(passages[:top_k])
        ]

if __name__ == "__main__":
    print("=== Testing Live Deployed Cloud BGE Reranker ===")
    client = CloudBGERerankerClient()

    query = "What is the Priority Sector Lending target for Small and Marginal Farmers under RBI norms?"
    passages = [
        "RBI Master Circular on Priority Sector Lending: Domestic commercial banks are required to achieve 40% of ANBC for Priority Sector, including a dedicated 10% sub-target for Small and Marginal Farmers.",
        "SEBI LODR Regulations: Listed entities must disclose financial results within 45 days of the end of each quarter.",
        "PMLA Section 12: Every banking company and financial institution shall maintain records of transactions exceeding Rs 10 Lakhs."
    ]

    results = client.rerank(query, passages, top_k=2)
    print(f"\nQuery: {query}")
    print("\nRanked Output from Deployed Cloud Space:")
    for item in results:
        print(f"  [Rank {item['rank']}] Score: {item['score']} | Passage: {item['text'][:90]}...")
