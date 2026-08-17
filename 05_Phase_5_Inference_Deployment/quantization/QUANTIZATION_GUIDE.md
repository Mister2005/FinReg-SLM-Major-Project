# Local Quantization & Deployment Guide (llama.cpp & Ollama)

## 1. Quick Launch with Ollama
To create and run this model locally in Ollama:
```bash
ollama create finreg-r1-7b -f "c:\Users\Varun\Desktop\Main\Sem 7\Major Project\Phase 5 - Inference\quantization\Modelfile"
ollama run finreg-r1-7b "What are the KYC norms for small accounts under RBI Master Direction?"
```

## 2. GGUF Quantization via llama.cpp
To convert the FP16 merged model to 4-bit / 8-bit GGUF:
```bash
# Clone and build llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Convert to GGUF (FP16)
python convert_hf_to_gguf.py "c:\Users\Varun\Desktop\Main\Sem 7\Major Project\Phase 4 - Second Approach\runs\stage2_r1_7b_dpo\merged" --outfile finreg-r1-7b-fp16.gguf

# Quantize to 4-bit Medium (Q4_K_M)
./llama-quantize finreg-r1-7b-fp16.gguf finreg-r1-7b-q4_k_m.gguf Q4_K_M

# Run high-speed CPU/GPU local inference
./llama-cli -m finreg-r1-7b-q4_k_m.gguf -p "What are the KYC norms under RBI?" -n 256
```
