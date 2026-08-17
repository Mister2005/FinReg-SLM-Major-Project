"""RAFT question generation pipeline using teacher LLM (T-202).

Generates diverse questions stratified by skill type from corpus documents.
Uses Groq (primary) or Gemini (fallback) as teacher models.
"""

from __future__ import annotations

import os
import json
import random
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal

from finreg3.raft.schema import SkillType

logger = logging.getLogger(__name__)

# Question generation prompts per skill type
QUESTION_PROMPTS: Dict[SkillType, str] = {
    SkillType.CITATION: """You are generating training questions for an Indian regulatory compliance QA system.

Given the following regulatory document metadata and excerpt, generate a question that requires the answer to cite specific provisions, sections, or paragraphs from this document.

DOCUMENT METADATA:
- Document ID: {doc_id}
- Regulator: {regulator}
- Title: {title}
- Issue Date: {issue_date}
- Statutory Regime: {statutory_regime}

DOCUMENT EXCERPT:
{excerpt}

Generate ONE specific compliance question that:
1. Requires citing a specific provision number, section, or paragraph from the document
2. Has a factual answer directly supported by the excerpt
3. Is the kind of question a compliance officer would ask
4. Is specific enough that a vague answer would be wrong

Output ONLY the question text, nothing else.""",

    SkillType.TEMPORAL: """You are generating temporal reasoning questions for an Indian regulatory compliance QA system.

Given the following regulatory document metadata and excerpt, generate a question that requires reasoning about WHEN a provision applies, whether it has been superseded, or what the effective date context is.

DOCUMENT METADATA:
- Document ID: {doc_id}
- Regulator: {regulator}
- Title: {title}
- Issue Date: {issue_date}
- In Force From: {in_force_from}
- In Force To: {in_force_to}
- Status: {status}

DOCUMENT EXCERPT:
{excerpt}

Generate ONE question that:
1. Requires reasoning about temporal applicability (e.g., "As of [date], what is the current requirement for...")
2. Would have a different answer depending on the date of the query
3. Tests whether the answerer can correctly identify the applicable version

Output ONLY the question text, nothing else.""",

    SkillType.SYNTHESIS: """You are generating cross-document synthesis questions for an Indian regulatory compliance QA system.

Given the following TWO regulatory documents, generate a question that requires combining information from both documents to answer correctly.

DOCUMENT 1:
- Document ID: {doc_id_1}
- Regulator: {regulator_1}
- Title: {title_1}
- Excerpt: {excerpt_1}

DOCUMENT 2:
- Document ID: {doc_id_2}
- Regulator: {regulator_2}
- Title: {title_2}
- Excerpt: {excerpt_2}

Generate ONE question that:
1. Cannot be answered from either document alone
2. Requires comparing, contrasting, or combining provisions from both
3. Is a realistic compliance question (e.g., "How do the requirements under [Doc1] interact with [Doc2]?")

Output ONLY the question text, nothing else.""",
}


class TeacherLLM:
    """Unified interface for teacher LLM with automatic .env loading, multi-key rotation, and fallback handling."""

    def __init__(self, primary: str = "groq"):
        self.primary = primary
        self._load_dotenv()
        
        # Collect all available API keys
        self.groq_keys = self._collect_keys(["GROQ_API_KEY", "GROQ_API_KEY2", "GROQ_API_KEY3"])
        self.gemini_keys = self._collect_keys([
            "GEMINI_API_KEY", "GEMINI_API_KEY1", "GEMINI_API_KEY2", 
            "GEMINI_API_KEY3", "GEMINI_API_KEY4", "GOOGLE_API_KEY"
        ])
        
        self.current_groq_idx = 0
        self.current_gemini_idx = 0
        
        logger.info(f"Initialized TeacherLLM with {len(self.groq_keys)} Groq keys and {len(self.gemini_keys)} Gemini keys.")

    def _load_dotenv(self):
        """Loads .env file from root or parent directories if available."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            # Fallback manual env loader if python-dotenv is missing
            env_paths = [
                Path(".env"),
                Path("../.env"),
                Path("../../.env"),
                Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/.env")
            ]
            for env_p in env_paths:
                if env_p.exists():
                    with open(env_p, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                os.environ[k.strip()] = v.strip()

    def _collect_keys(self, env_names: List[str]) -> List[str]:
        keys = []
        seen = set()
        for name in env_names:
            val = os.getenv(name)
            if val and val not in seen:
                seen.add(val)
                keys.append(val)
        return keys

    def generate(self, prompt: str, temperature: float = 0.3, max_tokens: int = 512) -> str:
        """Generate text using primary LLM provider with key rotation and automatic fallback."""
        import time
        max_outer_retries = 100
        for retry_i in range(max_outer_retries):
            try:
                if self.primary == "groq" and self.groq_keys:
                    try:
                        return self._generate_groq_with_rotation(prompt, temperature, max_tokens)
                    except Exception as e:
                        logger.warning(f"All Groq keys failed ({e}), falling back to Gemini")
                        return self._generate_gemini_with_rotation(prompt, temperature, max_tokens)
                else:
                    try:
                        return self._generate_gemini_with_rotation(prompt, temperature, max_tokens)
                    except Exception as e:
                        logger.warning(f"Gemini failed ({e}), falling back to Groq")
                        return self._generate_groq_with_rotation(prompt, temperature, max_tokens)
            except Exception as outer_err:
                logger.warning(f"All LLM keys rate-limited (attempt {retry_i+1}/{max_outer_retries}): {outer_err}. Pausing 20s for quota window reset...")
                time.sleep(20)
        raise RuntimeError("All LLM providers exhausted after outer retries")

    def _generate_groq_with_rotation(self, prompt: str, temperature: float, max_tokens: int) -> str:
        import groq
        if not self.groq_keys:
            raise RuntimeError("No Groq API keys available")

        # Truncate prompt to ~3500 chars (~900 tokens) to guarantee staying well under Groq 12k TPM rate limit
        if len(prompt) > 3500:
            prompt = prompt[:3500] + "\n...[truncated for length]"

        attempts = 0
        max_attempts = len(self.groq_keys)
        last_err = None

        models_to_try = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3.6-27b"]

        while attempts < max_attempts:
            key = self.groq_keys[self.current_groq_idx]
            client = groq.Groq(api_key=key)
            for m_id in models_to_try:
                try:
                    completion = client.chat.completions.create(
                        model=m_id,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    return completion.choices[0].message.content.strip()
                except Exception as e:
                    last_err = e
                    if "rate_limit" in str(e).lower() or "429" in str(e) or "413" in str(e):
                        logger.warning(f"Groq key idx {self.current_groq_idx} model {m_id} rate limit/TPM: {e}")
                        continue  # Try next model on this key
                    continue
            
            self.current_groq_idx = (self.current_groq_idx + 1) % len(self.groq_keys)
            attempts += 1

        raise RuntimeError(f"All Groq keys exhausted: {last_err}")

    def _generate_gemini_with_rotation(self, prompt: str, temperature: float, max_tokens: int) -> str:
        import time
        import google.generativeai as genai
        from google.generativeai.types import GenerationConfig
        
        if not self.gemini_keys:
            raise RuntimeError("No Gemini API keys available")

        # Truncate prompt if needed
        if len(prompt) > 4000:
            prompt = prompt[:4000] + "\n...[truncated for length]"

        attempts = 0
        max_attempts = len(self.gemini_keys)
        last_err = None

        models_to_try = ["gemini-2.5-flash"]

        while attempts < max_attempts:
            key = self.gemini_keys[self.current_gemini_idx]
            genai.configure(api_key=key)
            
            for m_id in models_to_try:
                try:
                    model = genai.GenerativeModel(m_id)
                    config = GenerationConfig(temperature=temperature, max_output_tokens=max_tokens)
                    response = model.generate_content(prompt, generation_config=config)
                    if response and response.text:
                        return response.text.strip()
                except Exception as e:
                    last_err = e
                    if "429" in str(e) or "quota" in str(e).lower() or "rate" in str(e).lower():
                        logger.warning(f"Gemini key idx {self.current_gemini_idx} rate limited on {m_id}. Pausing 3s...")
                        time.sleep(3)
                        break  # Try next Gemini key
                    continue

            self.current_gemini_idx = (self.current_gemini_idx + 1) % len(self.gemini_keys)
            attempts += 1

        raise RuntimeError(f"All Gemini keys exhausted: {last_err}")


class QuestionGenerator:
    """Generates diverse RAFT training questions from corpus documents (T-202)."""

    def __init__(self, teacher: TeacherLLM):
        self.teacher = teacher

    def generate_citation_question(self, doc_meta: Dict[str, Any], excerpt: str) -> str:
        """Generate a question requiring specific provision citations."""
        prompt = QUESTION_PROMPTS[SkillType.CITATION].format(
            doc_id=doc_meta.get("doc_id", ""),
            regulator=doc_meta.get("regulator", "RBI"),
            title=doc_meta.get("title", ""),
            issue_date=doc_meta.get("issue_date", ""),
            statutory_regime=doc_meta.get("statutory_regime", ""),
            excerpt=excerpt[:2000],  # Truncate long excerpts
        )
        return self.teacher.generate(prompt, temperature=0.4)

    def generate_temporal_question(self, doc_meta: Dict[str, Any], excerpt: str) -> str:
        """Generate a question requiring temporal reasoning."""
        prompt = QUESTION_PROMPTS[SkillType.TEMPORAL].format(
            doc_id=doc_meta.get("doc_id", ""),
            regulator=doc_meta.get("regulator", "RBI"),
            title=doc_meta.get("title", ""),
            issue_date=doc_meta.get("issue_date", ""),
            in_force_from=doc_meta.get("in_force_from", ""),
            in_force_to=doc_meta.get("in_force_to", "N/A (still in force)"),
            status=doc_meta.get("status", "unknown"),
            excerpt=excerpt[:2000],
        )
        return self.teacher.generate(prompt, temperature=0.4)

    def generate_synthesis_question(
        self,
        doc_meta_1: Dict[str, Any], excerpt_1: str,
        doc_meta_2: Dict[str, Any], excerpt_2: str
    ) -> str:
        """Generate a cross-document synthesis question."""
        prompt = QUESTION_PROMPTS[SkillType.SYNTHESIS].format(
            doc_id_1=doc_meta_1.get("doc_id", ""),
            regulator_1=doc_meta_1.get("regulator", "RBI"),
            title_1=doc_meta_1.get("title", ""),
            excerpt_1=excerpt_1[:1500],
            doc_id_2=doc_meta_2.get("doc_id", ""),
            regulator_2=doc_meta_2.get("regulator", "RBI"),
            title_2=doc_meta_2.get("title", ""),
            excerpt_2=excerpt_2[:1500],
        )
        return self.teacher.generate(prompt, temperature=0.4)

    def generate_false_premise_question(self, doc_meta: Dict[str, Any], excerpt: str) -> str:
        """Generate a question asserting a false, fabricated detail about a REAL,
        on-topic document (as opposed to generate_abstention_question, which pairs a
        question with topically-unrelated context). Teaches the model to catch a false
        claim about correctly-retrieved content, not just to notice an off-topic mismatch."""
        prompt = f"""You are generating adversarial training questions for an Indian regulatory compliance QA system, designed to test whether the system can detect a FALSE claim about a REAL regulation.

DOCUMENT METADATA:
- Document ID: {doc_meta.get("doc_id", "")}
- Regulator: {doc_meta.get("regulator", "RBI")}
- Title: {doc_meta.get("title", "")}
- Issue Date: {doc_meta.get("issue_date", "")}

DOCUMENT EXCERPT:
{excerpt[:2000]}

Generate ONE question that:
1. Explicitly references this document's real title, document ID, or a specific provision within it
2. Asserts a SPECIFIC, plausible-sounding but FALSE regulatory detail that is NOT actually stated anywhere in the excerpt (e.g., a fabricated numeric threshold, a fabricated deadline, a fabricated penalty amount, or a fabricated requirement)
3. Is phrased as a yes/no or "what is X" question that presupposes the false detail is true
4. Would mislead a system into confidently confirming or elaborating on the false detail if it doesn't carefully check the actual text

Output ONLY the question text, nothing else."""
        return self.teacher.generate(prompt, temperature=0.5)

    def generate_abstention_question(self, unrelated_topic: str) -> str:
        """Generate a question whose answer is NOT in the corpus (for abstention training)."""
        topics = [
            "cryptocurrency regulation in Japan",
            "European MiFID II reporting requirements",
            "US Federal Reserve monetary policy decisions",
            "Australian APRA prudential standards",
            "UK FCA consumer duty guidelines",
            "Singapore MAS technology risk management",
            "Canadian OSFI mortgage underwriting rules",
            "South African Reserve Bank exchange control",
            "Brazilian Central Bank PIX payment regulations",
            "Hong Kong SFC virtual asset licensing",
        ]
        topic = unrelated_topic or random.choice(topics)
        return f"What are the current regulatory requirements for {topic}?"
