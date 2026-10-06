"""
FinReg-SLM Enterprise Interactive CLI & Batch Compliance Auditor
================================================================
Command-line utility for local compliance officers and engineers to query
FinReg-SLM, run batch statutory assessments, and verify regulatory cases.

Usage:
  Interactive Mode:
    python cli.py --interactive

  Single Query Mode:
    python cli.py --context "text excerpt..." --query "question..."

  Batch Evaluation Mode:
    python cli.py --batch input_cases.jsonl --output audit_report.json
"""

import os
import sys

# Prevent broken TensorFlow / Protobuf runtime collision in Hugging Face Transformers
os.environ["USE_TF"] = "0"
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
sys.modules["tensorflow"] = None

import json
import argparse
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from finreg_engine import FinRegEngine

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()
    RICH_ENABLED = True
except ImportError:
    RICH_ENABLED = False
    console = None


def print_msg(title: str, text: str, style: str = "bold green"):
    if RICH_ENABLED:
        console.print(Panel(text, title=title, border_style=style))
    else:
        print(f"\n=== {title} ===")
        print(text)
        print("=" * 60)


def run_interactive(engine: FinRegEngine):
    print("\n" + "=" * 70)
    print(" FinReg-SLM Interactive Compliance Officer Terminal (DPDP Act Local)")
    print("=" * 70)
    print("Type 'exit' or 'quit' to close the session.\n")

    while True:
        try:
            print("\n[Step 1/2] Enter Regulatory Context (press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
            context = "\n".join(lines).strip()
            
            if context.lower() in ["exit", "quit"]:
                break
            if not context:
                continue

            query = input("\n[Step 2/2] Enter Compliance Question: ").strip()
            if query.lower() in ["exit", "quit"]:
                break
            if not query:
                continue

            print("\n[*] Auditing against Indian Financial Regulations...")
            result = engine.audit(query=query, context=context)

            if RICH_ENABLED:
                if result.get("legal_reasoning"):
                    console.print(Panel(result["legal_reasoning"], title="Legal Deliberation (<think>)", border_style="blue"))
                console.print(Panel(result["final_answer"], title="Authoritative Compliance Verdict", border_style="green"))
                
                table = Table(title="Execution Telemetry")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="magenta")
                table.add_row("Task Type", result["task_type"])
                table.add_row("Method Used", result.get("method_used", "method_1"))
                if result.get("option_selected"):
                    table.add_row("Option Selected", result["option_selected"])
                table.add_row("Passes Used", str(result["passes_used"]))
                table.add_row("Latency", f"{result['latency_ms']} ms")
                table.add_row("Hardware", result["device"])
                table.add_row("REPL Math Executed", str(result["repl_executed"]))
                if result["citations"]:
                    table.add_row("Citations", ", ".join(result["citations"]))
                console.print(table)
            else:
                if result.get("legal_reasoning"):
                    print(f"\n[LEGAL REASONING]:\n{result['legal_reasoning']}")
                print(f"\n[FINAL ANSWER]:\n{result['final_answer']}")
                print(f"[METADATA]: Method={result.get('method_used', 'method_1')} | Option={result.get('option_selected')} | Latency={result['latency_ms']}ms | Passes={result['passes_used']} | REPL={result['repl_executed']}")

        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break


def run_batch(engine: FinRegEngine, input_path: str, output_path: str, method: str = "method_1"):
    print(f"[*] Starting Batch Audit from: {input_path} (Method: {method})")
    items = []
    if input_path.endswith(".jsonl"):
        for l in open(input_path, encoding="utf-8"):
            if l.strip():
                items.append(json.loads(l))
    else:
        with open(input_path, "r", encoding="utf-8") as f:
            items = json.load(f)

    print(f"[*] Processing {len(items)} cases...")
    results = []
    for i, it in enumerate(items):
        q = it.get("question") or it.get("query")
        c = it.get("context")
        tt = it.get("task_type")
        res = engine.audit(query=q, context=c, task_type=tt, doc_id=it.get("id", f"CASE_{i+1}"), method=method)
        res["id"] = it.get("id", f"CASE_{i+1}")
        results.append(res)
        print(f"  [{i+1}/{len(items)}] Audited {res['id']} ({res['latency_ms']:.1f} ms, Method {res.get('method_used', method)})")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[✓] Batch Audit Completed. Results written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="FinReg-SLM Enterprise CLI Auditor")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive compliance session")
    parser.add_argument("--context", type=str, help="Regulatory statutory context text")
    parser.add_argument("--query", type=str, help="Compliance query / question")
    parser.add_argument("--task-type", type=str, default=None, help="Task type override")
    parser.add_argument("--method", type=str, default="method_1", choices=["method_1", "method_2"], help="Inference method: 'method_1' (Gold Standard Single-Pass, 100% Omni13) or 'method_2' (Combined with REPL & Reflection)")
    parser.add_argument("--batch", type=str, help="Path to input JSON/JSONL batch file")
    parser.add_argument("--output", type=str, default="audit_report.json", help="Path to save output audit report")
    parser.add_argument("--adapter-path", type=str, default=None, help="Custom path to LoRA adapter")
    parser.add_argument("--device", type=str, default=None, help="Target compute device ('cuda', 'cpu', 'mps')")

    args = parser.parse_args()

    engine = FinRegEngine(adapter_path=args.adapter_path, device=args.device, default_method=args.method)

    if args.interactive:
        run_interactive(engine)
    elif args.batch:
        run_batch(engine, args.batch, args.output, method=args.method)
    elif args.context and args.query:
        res = engine.audit(query=args.query, context=args.context, task_type=args.task_type, method=args.method)
        print(json.dumps(res, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
