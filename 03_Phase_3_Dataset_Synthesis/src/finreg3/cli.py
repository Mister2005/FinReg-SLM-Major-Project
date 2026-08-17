"""Main CLI Application for FinReg-SLM Phase 3 (finreg3)."""

from __future__ import annotations

import json
import typer
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="finreg3", help="FinReg-SLM Phase 3: RAFT Skill Fine-Tuning & Temporal Ablation CLI")

raft_app = typer.Typer(name="raft", help="RAFT data generation, distractor injection, formatting, and validation")
app.add_typer(raft_app, name="raft")

train_app = typer.Typer(name="train", help="RAFT QLoRA fine-tuning and adapter merging")
app.add_typer(train_app, name="train")

eval_app = typer.Typer(name="eval", help="Arm A6 runner, behavioral metrics, and Phase 3 decision gates")
app.add_typer(eval_app, name="eval")

ablation_app = typer.Typer(name="ablation", help="Temporal filtering ablation study and error taxonomy classifier")
app.add_typer(ablation_app, name="ablation")

console = Console()

DEFAULT_DB_PATH = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 1/data/manifest.db")
DEFAULT_BENCH_PATH = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 2/data/bench/seed-benchmark-v1.jsonl")
DEFAULT_EXCLUSION_PATH = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 2/data/bench/excluded_doc_ids.json")
DEFAULT_RAFT_OUTPUT = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/data/sft/raft-train-v1.jsonl")
DEFAULT_CHAT_OUTPUT = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/data/sft/raft-chat-v1.jsonl")
DEFAULT_RUNS_DIR = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/runs/raft-qwen2.5-7b")


@app.command("env")
def env_check():
    """Asserts GPU visibility, CUDA version, VRAM, and API keys for Phase 3."""
    console.print("[bold green]=== FinReg-SLM Phase 3 Environment Check ===[/bold green]")
    
    # Load .env
    from finreg3.raft.question_gen import TeacherLLM
    teacher = TeacherLLM()

    try:
        import torch
        cuda_avail = torch.cuda.is_available()
        console.print(f"PyTorch Version: {torch.__version__}")
        console.print(f"CUDA Available: {cuda_avail}")
        if cuda_avail:
            console.print(f"GPU Device: {torch.cuda.get_device_name(0)}")
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            console.print(f"Total VRAM: {vram_gb:.2f} GB")
    except ImportError:
        console.print("[bold red]PyTorch not installed![/bold red]")

    console.print(f"Groq API Keys Loaded: {len(teacher.groq_keys)}")
    console.print(f"Gemini API Keys Loaded: {len(teacher.gemini_keys)}")


@raft_app.command("generate")
def generate_raft_data(
    target_count: int = typer.Option(4000, help="Target number of RAFT training examples"),
    teacher: str = typer.Option("groq", help="Teacher LLM provider ('groq' or 'gemini')"),
    index_limit: Optional[int] = typer.Option(500, help="Index document limit for retrieval pipeline"),
    output: Path = typer.Option(DEFAULT_RAFT_OUTPUT, help="Output JSONL dataset path"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume from existing dataset file if present"),
):
    """Generate RAFT training dataset with distractor injection and resume support (M11: T-201 through T-206)."""
    console.print(f"[bold blue]Generating {target_count} RAFT training examples using teacher '{teacher}' (resume={resume})...[/bold blue]")
    from finreg3.raft.pipeline import RAFTPipeline

    pipeline = RAFTPipeline(
        db_path=DEFAULT_DB_PATH,
        exclusion_path=DEFAULT_EXCLUSION_PATH,
        output_path=output,
        teacher_primary=teacher,
        index_limit=index_limit,
    )

    dataset = pipeline.generate_dataset(target_count=target_count, resume=resume)
    console.print(f"[bold green]Dataset ready: {dataset.total_examples} RAFT examples at {output}[/bold green]")


@raft_app.command("format")
def format_chat_data(
    input_path: Path = typer.Option(DEFAULT_RAFT_OUTPUT, help="Input RAFT JSONL path"),
    output_path: Path = typer.Option(DEFAULT_CHAT_OUTPUT, help="Output chat JSONL path"),
):
    """Format RAFT dataset into Qwen chat-ml training format (T-207)."""
    from finreg3.train.chat_formatter import convert_raft_dataset_to_chat
    stats = convert_raft_dataset_to_chat(input_path, output_path)
    console.print(f"[bold green]Converted dataset to chat format at {output_path}[/bold green]")
    console.print(f"Estimated Tokens: {stats['estimated_total_tokens']:,}")


@raft_app.command("validate")
def validate_raft_data(
    dataset_path: Path = typer.Option(DEFAULT_RAFT_OUTPUT, help="RAFT JSONL dataset path"),
):
    """Validate RAFT dataset for schema correctness and bench-v1 exclusion safety (T-206)."""
    from finreg3.raft.pipeline import validate_raft_dataset
    res = validate_raft_dataset(dataset_path, DEFAULT_EXCLUSION_PATH)
    if res["passed"]:
        console.print("[bold green]PASSED: RAFT dataset is valid and zero-overlap safe![/bold green]")
    else:
        console.print(f"[bold red]FAILED: {len(res['errors'])} errors found![/bold red]")
        for err in res["errors"][:5]:
            console.print(f"  - {err}")


@train_app.command("prepare")
def prepare_train_manifest(
    train_data: Path = typer.Option(DEFAULT_CHAT_OUTPUT, help="Chat formatted dataset path"),
    runs_dir: Path = typer.Option(DEFAULT_RUNS_DIR, help="Runs output directory"),
):
    """Prepare RAFT QLoRA training manifest and validate parameters (T-208)."""
    from finreg3.train.qlora_raft import prepare_raft_training
    manifest = prepare_raft_training(train_data, runs_dir)
    console.print(f"[bold green]Prepared RAFT training manifest at {runs_dir / 'raft_train_manifest.json'}[/bold green]")


@train_app.command("run")
def run_train(
    train_data: Path = typer.Option(DEFAULT_CHAT_OUTPUT, help="Chat formatted dataset path"),
    runs_dir: Path = typer.Option(DEFAULT_RUNS_DIR, help="Runs output directory"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume from latest checkpoint if available"),
):
    """Execute RAFT QLoRA fine-tuning on RTX 5060 (T-209)."""
    from finreg3.train.qlora_raft import run_raft_qlora_training
    metrics = run_raft_qlora_training(train_data, runs_dir, resume_from_checkpoint=resume)
    console.print(f"[bold green]Training complete! Final loss: {metrics['train_loss']:.4f}[/bold green]")


@train_app.command("merge")
def merge_adapter(
    adapter_dir: Path = typer.Option(DEFAULT_RUNS_DIR / "final", help="LoRA adapter directory"),
    output_dir: Path = typer.Option(DEFAULT_RUNS_DIR / "merged", help="Output merged model directory"),
):
    """Merge LoRA adapter into base model weights for inference (T-211)."""
    from finreg3.train.qlora_raft import merge_raft_adapter
    out_p = merge_raft_adapter(adapter_dir, output_dir)
    console.print(f"[bold green]Merged model saved to {out_p}[/bold green]")


@eval_app.command("run-a6")
def run_arm_a6(
    runs_dir: Path = typer.Option(DEFAULT_RUNS_DIR, help="Runs directory"),
):
    """Run Arm A6 (RAFT-tuned model + Retrieval) against bench-v1 (T-215, T-216)."""
    from finreg.bench.validator import validate_benchmark_file
    from finreg.retrieve.pipeline import HybridRetrievalPipeline
    from finreg3.eval.runner_a6 import ArmA6Runner

    _, records = validate_benchmark_file(DEFAULT_BENCH_PATH, db_path=None, enforce_target_counts=False)

    pipeline = HybridRetrievalPipeline(db_path=DEFAULT_DB_PATH, use_temporal_filter=True)
    pipeline.build_index_from_db(limit=500)

    retrieved_map = {}
    excluded_map = {}
    for rec in records:
        res = pipeline.retrieve(query=rec.question, as_of_date=str(rec.as_of_date), top_k=8)
        retrieved_map[rec.qid] = res["eligible"]
        excluded_map[rec.qid] = res["excluded"]

    runner = ArmA6Runner(
        db_path=DEFAULT_DB_PATH,
        run_dir=runs_dir,
        merged_model_dir=runs_dir / "merged",
    )
    results = runner.run_arm_a6(records, retrieved_map, excluded_map)
    console.print(f"[bold green]Arm A6 evaluated against {len(results)} benchmark records.[/bold green]")


@eval_app.command("run-a2")
def run_arm_a2(
    runs_dir: Path = typer.Option(DEFAULT_RUNS_DIR, help="Runs directory"),
):
    """Run Arm A2 (Base SLM, pre-RAFT + Retrieval) against bench-v1 (real Phase 3 baseline)."""
    from finreg.bench.validator import validate_benchmark_file
    from finreg.retrieve.pipeline import HybridRetrievalPipeline
    from finreg3.eval.runner_a2 import ArmA2Runner

    _, records = validate_benchmark_file(DEFAULT_BENCH_PATH, db_path=None, enforce_target_counts=False)

    pipeline = HybridRetrievalPipeline(db_path=DEFAULT_DB_PATH, use_temporal_filter=True)
    pipeline.build_index_from_db(limit=500)

    retrieved_map = {}
    excluded_map = {}
    for rec in records:
        res = pipeline.retrieve(query=rec.question, as_of_date=str(rec.as_of_date), top_k=8)
        retrieved_map[rec.qid] = res["eligible"]
        excluded_map[rec.qid] = res["excluded"]

    runner = ArmA2Runner(run_dir=runs_dir)
    results = runner.run_arm_a2(records, retrieved_map, excluded_map)
    console.print(f"[bold green]Arm A2 evaluated against {len(results)} benchmark records.[/bold green]")


@ablation_app.command("run")
def run_ablation(
    index_limit: Optional[int] = typer.Option(500, help="Document index limit"),
    output: Path = typer.Option(Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/reports/temporal-ablation.md")),
):
    """Run temporal filter ablation study and error taxonomy classifier (T-221, T-222, T-223)."""
    from finreg3.eval.temporal_ablation import TemporalAblationRunner
    runner = TemporalAblationRunner(db_path=DEFAULT_DB_PATH, benchmark_path=DEFAULT_BENCH_PATH)
    summary = runner.run_ablation(index_limit=index_limit, output_report_path=output)

    table = Table(title="Temporal Ablation Results")
    table.add_column("Configuration", style="cyan")
    table.add_column("Recall@8 Accuracy", style="green")
    table.add_row("With Temporal Filter", f"{summary.with_temporal_filter['recall_at_8']*100:.2f}%")
    table.add_row("Without Temporal Filter", f"{summary.without_temporal_filter['recall_at_8']*100:.2f}%")
    table.add_row("Delta", f"+{summary.delta_accuracy:.2f} pp")
    console.print(table)


@eval_app.command("gate")
def evaluate_phase3_gates(
    output: Path = typer.Option(Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/reports/phase3-decision.md")),
    a6_run: Path = typer.Option(Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/runs/raft-qwen2.5-7b/run_A6.json")),
    a2_run: Path = typer.Option(Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/runs/raft-qwen2.5-7b/run_A2.json")),
    merged_model_dir: Path = typer.Option(DEFAULT_RUNS_DIR / "merged"),
):
    """Evaluate Phase 3 Decision Gates G4-G7 from real run data and emit decision record (T-220, T-224, T-226)."""
    from finreg3.eval.gate_phase3 import Phase3DecisionGateEvaluator
    evaluator = Phase3DecisionGateEvaluator()

    summary = evaluator.evaluate_from_run_files(
        a6_run_path=a6_run,
        a2_run_path=a2_run,
        bench_path=DEFAULT_BENCH_PATH,
        merged_model_dir=merged_model_dir,
    )
    evaluator.generate_decision_record(summary, output)
    console.print(f"[bold green]Phase 3 Decision Record exported to {output}[/bold green]")


if __name__ == "__main__":
    app()
