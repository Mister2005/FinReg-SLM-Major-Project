"""Quick validation of model loading and tokenization for DeepSeek-R1-Distill-Qwen-7B."""

import sys
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"

def main():
    print(f"Testing tokenizer and model loading for {MODEL_NAME}...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
        print("Tokenizer loaded successfully.")
        print(f"Vocab size: {len(tokenizer)}")
        
        # Test 4-bit quantization loading
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        print("Loading model in 4-bit...")
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            quantization_config=bnb_config,
            device_map={"": 0},
            trust_remote_code=True,
        )
        print("Model loaded successfully into VRAM.")
        print(f"Memory allocated: {torch.cuda.memory_allocated() / (1024**2):.1f} MB")
        del model
        del tokenizer
        torch.cuda.empty_cache()
        print("VRAM cleaned successfully. Ready for Stage 1 training!")
    except Exception as e:
        print(f"Error during validation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
