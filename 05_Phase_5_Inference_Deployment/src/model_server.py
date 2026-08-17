"""DeepSeek-R1-7B DPO Inference Engine for Indian Regulatory Compliance.

Loads the merged Stage 2 DPO model in 4-bit NF4 for fast, memory-efficient GPU inference.
Parses <think> reasoning chains, grounded answers, and verified citation tokens.
"""

import time
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("model_server")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
MERGED_MODEL_DIR = ROOT_DIR / "Phase 4 - Second Approach" / "runs" / "stage2_r1_7b_dpo" / "merged"
FALLBACK_ADAPTER_DIR = ROOT_DIR / "Phase 4 - Second Approach" / "runs" / "stage2_r1_7b_dpo" / "final_adapter"

class ComplianceModelServer:
    def __init__(self, model_path: Path = MERGED_MODEL_DIR, load_in_4bit: bool = True):
        self.model_path = model_path
        self.load_in_4bit = load_in_4bit
        self.tokenizer = None
        self.model = None
        self._load_model()

    def _load_model(self):
        logger.info(f"Initializing ComplianceModelServer from: {self.model_path}")
        
        target_path = self.model_path if self.model_path.exists() else FALLBACK_ADAPTER_DIR
        logger.info(f"Loading tokenizer from {target_path}...")
        self.tokenizer = AutoTokenizer.from_pretrained(str(target_path), trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        if self.load_in_4bit:
            logger.info("Configuring 4-bit NF4 Quantization for RTX 5060 GPU...")
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                str(target_path),
                quantization_config=bnb_config,
                device_map={"": 0},
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
            )
        else:
            logger.info("Loading in 16-bit Float precision...")
            self.model = AutoModelForCausalLM.from_pretrained(
                str(target_path),
                device_map={"": 0},
                trust_remote_code=True,
                torch_dtype=torch.float16,
            )

        self.model.eval()
        logger.info("ComplianceModelServer successfully loaded and ready for inference.")

    def generate(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: int = 512,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Generate response given chat template messages."""
        start_time = time.time()
        prompt_text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(prompt_text, return_tensors="pt", truncation=True, max_length=2048).to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=(temperature > 0.0),
                temperature=temperature if temperature > 0.0 else None,
                repetition_penalty=1.15,
                no_repeat_ngram_size=4,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        gen_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        raw_response = self.tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
        latency = time.time() - start_time

        # Extract reasoning (<think> ... </think>) if present
        reasoning = ""
        final_answer = raw_response
        if "<think>" in raw_response and "</think>" in raw_response:
            parts = raw_response.split("</think>")
            reasoning = parts[0].replace("<think>", "").strip()
            final_answer = parts[1].strip()
        elif "</think>" in raw_response:
            parts = raw_response.split("</think>")
            reasoning = parts[0].strip()
            final_answer = parts[1].strip()

        # Extract bracketed citations [doc_id / provision]
        citations = re.findall(r'\[(.*?)\]', final_answer)
        
        # Filter citations to real document identifiers
        valid_citations = [c for c in citations if '/' in c or ':' in c or 'para' in c.lower() or 'section' in c.lower()]

        is_abstained = ("INSUFFICIENT_CORPUS_EVIDENCE" in final_answer or 
                        final_answer.strip().startswith("INSUFFICIENT") or
                        "no applicable regulatory provisions found" in final_answer.lower())

        return {
            "raw_output": raw_response,
            "reasoning": reasoning,
            "answer": final_answer,
            "citations": list(set(valid_citations)),
            "is_abstained": is_abstained,
            "latency_seconds": round(latency, 2),
            "token_count": len(gen_tokens),
        }

if __name__ == "__main__":
    server = ComplianceModelServer()
    test_msgs = [
        {"role": "system", "content": "You are an expert Indian regulatory assistant."},
        {"role": "user", "content": "What is Priority Sector Lending under RBI norms?"}
    ]
    res = server.generate(test_msgs, max_new_tokens=100)
    print("Inference Test Result:", res)
