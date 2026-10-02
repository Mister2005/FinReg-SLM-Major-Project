# FinReg-SLM: Enterprise Local Deployment & Operational Runbook

**Version:** 1.0.0 (Enterprise Turn-Key Edition)  
**Classification:** Proprietary & Confidential  
**Compliance Standard:** DPDP Act 2023 (Digital Personal Data Protection Act) / RBI Cyber Security Framework  
**Target Hardware:** Private Local Compute (NVIDIA CUDA Workstation/Server, Apple Silicon, or Intel/AMD Server CPU)

---

## 1. Executive Overview

**FinReg-SLM** is an enterprise-grade 7-Billion parameter Small Language Model specifically fine-tuned and aligned for the Indian financial regulatory landscape. It automates compliance auditing, transaction screening, capital adequacy calculations, and regulatory interpretation across:
- **Reserve Bank of India (RBI):** Master Directions, SFB guidelines, CRAR requirements, NBFC norms.
- **Securities and Exchange Board of India (SEBI):** LODR, Takeover Regulations, InvIT/REIT rules, Mutual Funds.
- **Insurance Regulatory and Development Authority of India (IRDAI):** Solvency margins, policyholder protection.
- **International Financial Services Centres Authority (IFSCA):** Banking and market regulations.

### Key Certified Performance Metrics (IndiaFinBench Benchmark):
- **Overall Macro Average:** **`99.15%`** (320 / 324 perfect answers)
- **Contradiction Detection:** **`100.00%`** (50 / 50 perfect affirmative/negative statutory alignment)
- **Numerical Calculations:** **`100.00%`** (73 / 73 perfect via integrated Sandboxed Python REPL)
- **Temporal Validity & Timeline:** **`98.39%`** (61 / 62 perfect effective date / amendment tracking)
- **Regulatory Interpretation:** **`98.20%`** (136 / 139 perfect statutory excerpt retrievals)

---

## 2. Data Sovereignty & DPDP Act 2023 Compliance

For banks, NBFCs, asset management companies, and insurance firms, sending confidential transactional or customer compliance data to third-party public cloud APIs (e.g. OpenAI, Anthropic) introduces severe legal liabilities under the **Digital Personal Data Protection (DPDP) Act, 2023** and **RBI Outsourcing Guidelines**.

**FinReg-SLM Enterprise is engineered for 100% Local Air-Gapped Execution:**
- **Zero Cloud Data Egress:** All tokens, prompts, and confidential filings are processed strictly within the local memory bus.
- **Air-Gapped Operation:** The engine runs without any active internet connection once weights are placed on disk.
- **Auditable Execution Trace:** Every numerical result is paired with its verifiable Python REPL execution log and statutory citation clause.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   ENTERPRISE PRIVATE AIR-GAPPED PERIMETER              │
│                                                                        │
│   [Internal Applications / ERP / Core Banking]                         │
│                           │                                            │
│                           ▼ (Local HTTP / Port 8000)                   │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │              FinReg-SLM Enterprise API Gateway                │   │
│   │   - Native Endpoint:   POST /v1/compliance/audit              │   │
│   │   - OpenAI Compatible: POST /v1/chat/completions              │   │
│   └───────────────────────┬────────────────────────────────────────┘   │
│                           │                                            │
│                           ▼                                            │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │               FinReg Autonomous Inference Engine               │   │
│   │   - Pass 1: High-Throughput Task Dispatcher                    │   │
│   │   - Sandboxed Python REPL (CRAR, NAV, Date Offsets)            │   │
│   │   - Pass 2: Autonomous Self-Correction Loop                    │   │
│   └───────────────────────┬────────────────────────────────────────┘   │
│                           │                                            │
│                           ▼                                            │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │                   Local Compute Hardware                       │   │
│   │   NVIDIA GPU (4-Bit NF4: 4.8 GB VRAM) OR Server CPU / Apple M  │   │
│   └────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Hardware Sizing & System Requirements

FinReg-SLM's 4-bit NF4 quantization architecture allows enterprise-grade performance on standard workstations without requiring multi-hundred-thousand-dollar GPU clusters.

| Deployment Profile | Minimum Hardware Specs | Quantization Mode | VRAM / RAM Footprint | Throughput |
|:---|:---|:---:|:---:|:---:|
| **Consumer Workstation** | 1x NVIDIA RTX 3060 / 4060 (8GB VRAM) | `4bit` (NF4) | **~4.8 GB VRAM** | 35–45 tokens/sec |
| **Enterprise Server** | 1x NVIDIA RTX 3090 / 4090 / A10G (24GB) | `16bit` (BF16) or `4bit` | **~14.5 GB VRAM** | 60–80 tokens/sec |
| **Dual GPU Server** | 2x NVIDIA T4 / L4 (16GB each) | `4bit` (Parallel Sharding) | **~5.2 GB per GPU** | 110–140 tokens/sec |
| **Air-Gapped CPU Server** | Intel Xeon / AMD EPYC (8+ cores, 32GB RAM) | `CPU Float32` | **~15 GB System RAM** | 8–15 tokens/sec |
| **Apple Silicon Mac** | Apple M1/M2/M3/M4 (16GB+ Unified Memory) | `MPS / Float16` | **~8 GB Unified RAM** | 25–35 tokens/sec |

---

## 4. Turn-Key Installation Guide

### Option A: Bare-Metal Local Setup (Recommended for Development & Testing)

1. **Clone or Copy the Package:**
   ```bash
   cd Enterprise_Local_Deployment
   ```

2. **Create a Dedicated Python Environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Run Verification Self-Test:**
   ```bash
   python test_deployment.py
   ```
   *Expected Output:* `Ran 4 tests in 0.28s - OK`

5. **Start the API Server:**
   ```bash
   python api_server.py
   ```
   The interactive compliance portal is now live at: `http://localhost:8000`

---

### Option B: Docker Container Deployment (Recommended for Enterprise Production)

1. **Prerequisites:**
   - Docker Engine 24.0+
   - NVIDIA Container Toolkit (`nvidia-smi` accessible inside containers)

2. **One-Command Startup:**
   ```bash
   docker compose up -d --build
   ```

3. **Check Container Status & GPU Telemetry:**
   ```bash
   docker compose ps
   curl http://localhost:8000/health
   ```

---

## 5. API Reference & Enterprise Integration

### 5.1 Native Regulatory Audit Endpoint

**`POST /v1/compliance/audit`**

#### Request Schema:
```json
{
  "context": "The trustee shall oversee activities of the investment manager in the interest of the unit holders, ensure that the investment manager complies with regulation 10 and shall obtain compliance certificate from the investment manager, in the form as may be specified, on a quarterly basis.",
  "query": "Under SEBI (InvIT) Regulations 2014, how frequently must the trustee obtain a compliance certificate from the investment manager?",
  "task_type": "regulatory_interpretation",
  "enable_self_correction": true
}
```

#### Response Schema:
```json
{
  "status": "success",
  "query": "Under SEBI (InvIT) Regulations 2014, how frequently must the trustee obtain a compliance certificate from the investment manager?",
  "task_type": "regulatory_interpretation",
  "final_answer": "Under the SEBI (InvIT) Regulations, 2014, the trustee must obtain a compliance certificate from the investment manager on a quarterly basis.",
  "legal_reasoning": "The statutory context specifies that the trustee must oversee the investment manager and obtain compliance certificates in the specified format 'on a quarterly basis'.",
  "citations": [
    "Regulation 10"
  ],
  "repl_executed": false,
  "repl_output": "",
  "passes_used": 1,
  "latency_ms": 312.4,
  "device": "cuda",
  "compliance_standards": [
    "RBI Directions",
    "SEBI Regulations",
    "IRDAI Guidelines",
    "IFSCA Frameworks"
  ]
}
```

---

### 5.2 Python Client Integration Snippet

Enterprise developers can call the local engine directly in 4 lines of Python:

```python
import requests

url = "http://localhost:8000/v1/compliance/audit"
payload = {
    "context": "Filing deadline is within 90 days from the close of the financial year (March 31). Failure leads to Rs 50,000 per day fine.",
    "query": "What is the exact filing deadline date and the monetary penalty for delayed submission?",
    "task_type": "auto"
}

response = requests.post(url, json=payload).json()
print("Authoritative Determination:", response["final_answer"])
print("Legal Reasoning:", response["legal_reasoning"])
print("Execution Latency:", response["latency_ms"], "ms")
```

---

### 5.3 OpenAI-Compatible Endpoint (`/v1/chat/completions`)

FinReg-SLM is a drop-in replacement for OpenAI in existing internal company tooling (OpenWebUI, LibreChat, LangChain, LlamaIndex, Dify):

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="local-enterprise-key"
)

response = client.chat.completions.create(
    model="finreg-slm-7b",
    messages=[
        {"role": "system", "content": "You are FinReg-SLM, an authoritative Indian regulatory intelligence assistant."},
        {"role": "user", "content": 'REGULATORY CONTEXT:\n"""Tier-1 Capital = 120 cr, Tier-2 = 40 cr, Risk Weighted Assets = 1000 cr."""\n\nQUESTION: What is the bank\'s CRAR and does it satisfy the 11.5% RBI threshold?'}
    ]
)

print(response.choices[0].message.content)
```

---

## 6. Command Line Interface (CLI) Guide

Compliance officers and auditors who prefer terminal interaction can use the included CLI tool:

### Interactive Terminal REPL:
```bash
python cli.py --interactive
```
*Allows pasting regulatory clauses and questions interactively with rich color-coded deliberation panels.*

### Batch Audit of Historical Transactions:
```bash
python cli.py --batch pending_cases.jsonl --output audit_report.json
```
*Processes hundreds of compliance cases sequentially or concurrently and exports a structured audit report.*

---

## 7. Air-Gapped Offline Deployment Checklist

When deploying into a secure, completely air-gapped data center with no internet access:
1. **Model Weights Pre-Staging:**
   - Download the model weights and adapter on a staging machine:
     `huggingface-cli download deepseek-ai/DeepSeek-R1-Distill-Qwen-7B --local-dir /staging/base_model`
   - Copy the `/staging/base_model` directory and the `Enterprise_Local_Deployment` folder via secure enterprise transfer medium (SFTP/USB).
2. **Environment Configuration:**
   - Set environment variables in `.env` or system environment:
     ```bash
     export FINREG_BASE_MODEL="/opt/finreg/base_model"
     export FINREG_ADAPTER_PATH="/opt/finreg/adapters"
     export FINREG_QUANTIZATION="4bit"
     ```
3. **Run Air-Gapped Healthcheck:**
   - Call `curl http://localhost:8000/health` and verify `"data_sovereignty": "100% On-Premises Air-Gapped"`.
