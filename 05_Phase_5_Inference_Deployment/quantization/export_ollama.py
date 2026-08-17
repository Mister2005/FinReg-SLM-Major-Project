"""Ollama & llama.cpp Export Tooling for FinReg-AI DeepSeek-R1-7B DPO.

Generates Modelfile, system prompts, stop tokens, and CLI conversion commands.
"""

from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("export_ollama")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
MODEL_DIR = ROOT_DIR / "Phase 4 - Second Approach" / "runs" / "stage2_r1_7b_dpo" / "merged"
QUANT_DIR = ROOT_DIR / "Phase 5 - Inference" / "quantization"

SYSTEM_PROMPT = """You are an expert Indian regulatory compliance assistant. Your task is to answer legal, banking, tax, and securities compliance questions directly and concisely using ONLY the provided regulatory context provisions.

RULES:
1. Ground every statement strictly in the retrieved context chunks. Do NOT introduce external legal facts.
2. Provide an inline citation for EVERY factual claim using the exact format: [doc_id / provision_path] (e.g. [RBI_MD_KYC / para 38]).
3. Answer directly in 2-4 sentences without repeating the question or restating prompt headers.
4. If the retrieved context is insufficient or unhelpful to answer the question, you MUST begin your response with:
   INSUFFICIENT_CORPUS_EVIDENCE: <explanation>
5. If relying on a chunk marked with UNCERTAIN_VALIDITY, explicitly flag it in your explanation."""

MODELFILE_CONTENT = f"""# Ollama Modelfile for FinReg-AI DeepSeek-R1-7B DPO
FROM {MODEL_DIR}

TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
<think>
\"\"\"

SYSTEM \"\"\"{SYSTEM_PROMPT}\"\"\"

PARAMETER temperature 0.0
PARAMETER top_p 0.95
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
"""

def main():
    QUANT_DIR.mkdir(parents=True, exist_ok=True)
    modelfile_path = QUANT_DIR / "Modelfile"
    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(MODELFILE_CONTENT)
    logger.info(f"Saved Ollama Modelfile to: {modelfile_path}")

    instructions_path = QUANT_DIR / "QUANTIZATION_GUIDE.md"
    guide = f"""# Local Quantization & Deployment Guide (llama.cpp & Ollama)

## 1. Quick Launch with Ollama
To create and run this model locally in Ollama:
```bash
ollama create finreg-r1-7b -f "{modelfile_path}"
ollama run finreg-r1-7b "What are the KYC norms for small accounts under RBI Master Direction?"
```

## 2. GGUF Quantization via llama.cpp
To convert the FP16 merged model to 4-bit / 8-bit GGUF:
```bash
# Clone and build llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Convert to GGUF (FP16)
python convert_hf_to_gguf.py "{MODEL_DIR}" --outfile finreg-r1-7b-fp16.gguf

# Quantize to 4-bit Medium (Q4_K_M)
./llama-quantize finreg-r1-7b-fp16.gguf finreg-r1-7b-q4_k_m.gguf Q4_K_M

# Run high-speed CPU/GPU local inference
./llama-cli -m finreg-r1-7b-q4_k_m.gguf -p "What are the KYC norms under RBI?" -n 256
```
"""
    with open(instructions_path, "w", encoding="utf-8") as f:
        f.write(guide)
    logger.info(f"Saved Quantization Guide to: {instructions_path}")

if __name__ == "__main__":
    main()
