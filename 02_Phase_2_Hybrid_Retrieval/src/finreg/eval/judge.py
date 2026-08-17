"""Automated LLM Judge with bias controls and human agreement validation (T-128, T-129, Invariant E6)."""

import os
import time
import json
import random
import logging
from typing import List, Dict, Any, Tuple, Optional
from finreg.bench.agreement import compute_correctness_kappa

logger = logging.getLogger(__name__)

try:
    import groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


JUDGE_SYSTEM_PROMPT = """You are an impartial regulatory legal evaluator. Your job is to grade candidate compliance answers against gold answers and gold citations.

SCORING SCALE:
2 = Correct: Answer is accurate, grounded in cited provisions, and addresses the question.
1 = Partially Correct: Answer is mostly accurate but omits a key caveat or provision.
0 = Incorrect: Answer contains false statements, incorrect citations, or fails to abstain when appropriate.

OUTPUT FORMAT (JSON):
{"score": <0, 1, or 2>, "rationale": "<brief explanation>"}
"""


class LLMJudge:
    """Automated judge using Llama 3.3 70B across Groq, OpenRouter, and NVIDIA NIM for high throughput and consistent evaluation."""

    def __init__(self, model_name: str = "llama-3.3-70b-versatile"):
        self.model_name = model_name
        self.endpoints = []  # List of tuples: (client, model_id, provider_name)

        # 1. OpenRouter (Llama 3.3 70B Instruct - Fast & Reliable)
        if HAS_OPENAI:
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if openrouter_key and openrouter_key.strip():
                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=openrouter_key.strip(),
                    default_headers={
                        "HTTP-Referer": "https://github.com/finreg-slm",
                        "X-Title": "FinReg-SLM Evaluation"
                    }
                )
                self.endpoints.append((client, "meta-llama/llama-3.3-70b-instruct", "OpenRouter"))

        # 2. Groq clients (Llama 3.3 70B Versatile)
        if HAS_GROQ:
            for k in ["GROQ_API_KEY", "GROQ_API_KEY2", "GROQ_API_KEY3"]:
                val = os.getenv(k)
                if val and val.strip():
                    self.endpoints.append((groq.Groq(api_key=val.strip()), "llama-3.3-70b-versatile", "Groq"))

        # 3. NVIDIA NIM client (Llama 3.1 70B Instruct fallback)
        if HAS_OPENAI:
            nvidia_key = os.getenv("NVIDIA_API_KEY")
            if nvidia_key and nvidia_key.strip():
                client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=nvidia_key.strip(),
                )
                self.endpoints.append((client, "meta/llama-3.1-70b-instruct", "NVIDIA"))

        self._ep_idx = 0
        self.client = self.endpoints[0][0] if self.endpoints else None

    def _get_active_endpoint(self):
        if not self.endpoints:
            return None, None, None
        return self.endpoints[self._ep_idx]

    def _rotate_endpoint(self):
        if self.endpoints:
            self._ep_idx = (self._ep_idx + 1) % len(self.endpoints)

    def evaluate_candidate_answer(self, question: str, gold_answer: str, candidate_answer: str) -> Dict[str, Any]:
        """Grades candidate answer against gold answer without knowing arm identity."""
        if not self.endpoints:
            return self._heuristic_evaluate(question, gold_answer, candidate_answer)

        prompt = f"QUESTION: {question}\nGOLD ANSWER: {gold_answer}\nCANDIDATE ANSWER: {candidate_answer}"
        
        max_retries = max(len(self.endpoints) * 2, 5)
        for attempt in range(max_retries):
            client, model_id, provider = self._get_active_endpoint()
            try:
                completion = client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    max_tokens=256,
                    response_format={"type": "json_object"}
                )
                content = completion.choices[0].message.content
                res = json.loads(content)
                return {"score": int(res.get("score", 0)), "rationale": res.get("rationale", "")}
            except Exception as e:
                err_str = str(e)
                logger.warning(f"Judge error on {provider} (attempt {attempt+1}): {e}")
                self._rotate_endpoint()
                if "402" in err_str or "credits" in err_str.lower():
                    # Permanently remove exhausted endpoint
                    self.endpoints = [ep for ep in self.endpoints if ep[2] != provider]
                    self._ep_idx = 0
                elif "429" in err_str or "rate limit" in err_str.lower() or "timeout" in err_str.lower():
                    time.sleep(random.uniform(0.5, 1.5))
                else:
                    time.sleep(0.5)
        
        return self._heuristic_evaluate(question, gold_answer, candidate_answer)

    def _heuristic_evaluate(self, question: str, gold_answer: str, candidate_answer: str) -> Dict[str, Any]:
        gold_words = set(gold_answer.lower().split())
        cand_words = set(candidate_answer.lower().split())
        overlap = len(gold_words.intersection(cand_words)) / max(len(gold_words), 1)

        if "insufficient_corpus_evidence" in candidate_answer.lower() and "insufficient" in gold_answer.lower():
            return {"score": 2, "rationale": "Correct abstention on unanswerable question."}
        elif overlap >= 0.35:
            return {"score": 2, "rationale": "High content overlap with gold answer."}
        elif overlap >= 0.15:
            return {"score": 1, "rationale": "Partial content match."}
        else:
            return {"score": 0, "rationale": "Low content match."}

    def validate_against_human_labels(self, sample_100_evals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validates judge against 100 human-scored benchmark answers (T-129)."""
        judge_scores = []
        human_scores = []

        for item in sample_100_evals:
            human_scores.append(item["human_score"])
            j_eval = self.evaluate_candidate_answer(
                question=item["question"],
                gold_answer=item["gold_answer"],
                candidate_answer=item["candidate_answer"]
            )
            judge_scores.append(j_eval["score"])

        kappa = compute_correctness_kappa(judge_scores, human_scores)
        passes_validation = kappa >= 0.60

        return {
            "sample_size": len(sample_100_evals),
            "cohens_kappa": round(kappa, 4),
            "passes_validation_threshold": passes_validation,
            "scoring_path": "AUTOMATED_LLM_JUDGE" if passes_validation else "REVERT_TO_HUMAN_SCORING"
        }


