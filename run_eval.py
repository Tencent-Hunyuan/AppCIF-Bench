"""
run_eval.py
-----------
Main entry point for AppCIF-Bench evaluation.

Pipeline stages
---------------
1. pull_answer   — call a model (an OpenAI-compatible endpoint or a registered
                   Python function) for every item in the benchmark and save
                   raw answers as JSONL.
2. evaluate      — judge the saved answers rubric by rubric with an LLM judge
                   and write per-rubric results as JSONL.
3. calculate_accuracy — score the judged results against the benchmark file:
                         SSR (per-rubric) and HSR (per-sample) accuracy split
                         by difficulty level and category, saved as Excel.

Quick start
-----------
    # 1. put your keys in .env (see README)
    python run_eval.py pull_answer \\
        --data_file data/AppCIF_bench_dataset.jsonl \\
        --model_name GPT-5.4-xhigh \\
        --output_dir results \\
        --concurrency 20

    python run_eval.py evaluate \\
        --data_file data/AppCIF_bench_dataset.jsonl \\
        --model_name GPT-5.4-xhigh \\
        --answers_file results/answers_GPT-5.4-xhigh.jsonl \\
        --output_dir results \\
        --concurrency 20

    python run_eval.py calculate_accuracy \\
        --data_file data/AppCIF_bench_dataset.jsonl \\
        --model_names GPT-5.4-xhigh \\
        --eval_dir results \\
        --output_dir results

    # Models outside the registry: register them in a Python file and add
    # --models_file my_models.py to pull_answer and evaluate (see README).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import sys
import threading
from typing import Any, Callable

import pandas as pd
from dotenv import load_dotenv

from eval.model_registry import DEFAULT_EVAL_MODEL, ModelConfigError, load_models_file

load_dotenv()

LEVELS = ("level1", "level2", "level3", "level4")

# ---------------------------------------------------------------------------
# Lazy import of the evaluator and client modules (only the stages that call
# models need them).
# ---------------------------------------------------------------------------

def _import_evaluator():
    from eval.eval_pipeline import Evaluator
    from eval.llm_client import LLM
    return Evaluator, LLM


def _import_client():
    from eval.llm_client import chat_with_retries, get_model
    return chat_with_retries, get_model


def _load_models_files(paths: list[str] | None) -> None:
    for path in paths or []:
        try:
            load_models_file(path)
        except ModelConfigError as exc:
            sys.exit(f"[models] {exc}")


# ---------------------------------------------------------------------------
# History conversion
# ---------------------------------------------------------------------------

def _convert_history_to_messages(history: Any) -> list[dict]:
    """Convert the benchmark ``history`` field to OpenAI messages format.

    The history stored in the dataset can be either:
    - A list of ``{"role": ..., "content": [{"type": "text", "value": "..."}]}``
      dicts (internal format), or
    - Already a plain list of ``{"role": ..., "content": "..."}`` dicts.

    ``system`` role messages are skipped because they are handled separately
    via the ``system_prompt`` field.
    """
    if isinstance(history, str):
        try:
            history = json.loads(history)
        except json.JSONDecodeError:
            history = eval(history)  # noqa: S307
    if not isinstance(history, list):
        return []

    messages: list[dict] = []
    for msg in history:
        role = msg.get("role", "")
        if role == "system":
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            # Internal format: list of content blocks
            text = "".join(part.get("value", "") for part in content if isinstance(part, dict))
        else:
            text = str(content) if content else ""
        messages.append({"role": role, "content": text})
    return messages


# ---------------------------------------------------------------------------
# Model requests
# ---------------------------------------------------------------------------

def _build_messages(record: dict) -> list[dict]:
    """Return the system prompt, dialogue history and final question of *record*.

    Only the parameters in a model's ``extra_params`` are sent with the
    request; temperature and other decoding parameters stay at the provider
    default.
    """
    messages: list[dict] = []
    system_prompt = record.get("system_prompt") or ""
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(_convert_history_to_messages(record.get("history", [])))
    messages.append({"role": "user", "content": record["question"]})
    return messages


def _run_all(label: str, work: Callable[[str], None], ids: list[str], concurrency: int) -> list[str]:
    """Run ``work(id)`` for every id on *concurrency* threads; return the ids that failed.

    A :class:`ModelConfigError` stops the run, since every further request would fail too.
    """
    failed: list[str] = []
    with cf.ThreadPoolExecutor(concurrency) as pool:
        futures = {pool.submit(work, rid): rid for rid in ids}
        for n, future in enumerate(cf.as_completed(futures), 1):
            rid = futures[future]
            try:
                future.result()
            except ModelConfigError as exc:
                pool.shutdown(wait=False, cancel_futures=True)
                sys.exit(f"\n[{label}] stopped: {exc}")
            except Exception as exc:
                failed.append(rid)
                print(f"\n[{label}] FAILED id={rid}: {type(exc).__name__}: {exc}")
            print(f"\r[{label}] {n}/{len(ids)} failed={len(failed)}", end="", flush=True)
    print()
    return failed


# ---------------------------------------------------------------------------
# pull_answer
# ---------------------------------------------------------------------------

def _run_pull_answers(
    records: list[dict],
    model_name: str,
    output_path: str,
    concurrency: int,
    max_retries: int,
    timeout: float,
) -> None:
    """Pull model answers for all records concurrently with checkpoint resume."""
    # Checkpoint: load already-done ids
    done_ids: set[str] = set()
    if os.path.exists(output_path):
        try:
            with open(output_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    if model_name in obj and obj[model_name]:
                        done_ids.add(str(obj["id"]))
            print(f"[checkpoint] already done: {len(done_ids)}")
        except Exception as exc:
            print(f"[checkpoint] could not read existing file: {exc}")

    todo = [r for r in records if str(r.get("id")) not in done_ids]
    print(f"[pull_answer] model={model_name}  todo={len(todo)}/{len(records)}")
    if not todo:
        return

    chat_with_retries, get_model = _import_client()
    try:
        model = get_model(model_name, timeout=timeout)
    except ModelConfigError as exc:
        sys.exit(f"[pull_answer] {exc}")

    by_id = {str(r.get("id")): r for r in todo}
    write_lock = threading.Lock()

    def work(rid: str) -> None:
        record = by_id[rid]
        answer = chat_with_retries(
            model, _build_messages(record), max_retries, retry_delay=5.0,
            label=f"{model_name} id={rid}",
        )
        result = dict(record)
        result[model_name] = answer
        with write_lock, open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")

    failed = _run_all("pull_answer", work, list(by_id), concurrency)
    print(f"[pull_answer] finished  done={len(by_id) - len(failed)} err={len(failed)}")
    if failed:
        print("[pull_answer] re-run the same command to retry the failed items.")


def cmd_pull_answer(args: argparse.Namespace) -> None:
    _load_models_files(args.models_file)
    records = _load_jsonl(args.data_file)
    os.makedirs(args.output_dir, exist_ok=True)

    model_name: str = args.model_name
    output_path = os.path.join(
        args.output_dir, f"answers_{_safe_name(model_name)}.jsonl"
    )
    if args.reset and os.path.exists(output_path):
        os.remove(output_path)

    _run_pull_answers(
        records=records,
        model_name=model_name,
        output_path=output_path,
        concurrency=args.concurrency,
        max_retries=args.max_retries,
        timeout=args.timeout,
    )
    print(f"[pull_answer] answers saved → {output_path}")


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------

def _eval_path(eval_dir: str, model_name: str, eval_model: str) -> str:
    return os.path.join(
        eval_dir, f"eval_{_safe_name(model_name)}_{_safe_name(eval_model)}.jsonl"
    )


def cmd_evaluate(args: argparse.Namespace) -> None:
    Evaluator, LLM = _import_evaluator()
    _load_models_files(args.models_file)

    # Load benchmark data (for question text + rubrics)
    bench = {str(r["id"]): r for r in _load_jsonl(args.data_file)}

    # Load answers
    if not os.path.exists(args.answers_file):
        sys.exit(f"[evaluate] answers file not found: {args.answers_file}")
    answers: dict[str, str] = {}
    for obj in _load_jsonl(args.answers_file):
        model_ans = obj.get(args.model_name, "")
        if model_ans:
            answers[str(obj["id"])] = model_ans
    unknown = [rid for rid in answers if rid not in bench]
    if unknown:
        print(f"[evaluate] WARNING: {len(unknown)} answered ids are not in {args.data_file}; ignored")

    print(f"[evaluate] loaded {len(answers)} answers for model={args.model_name}")

    # Output path
    os.makedirs(args.output_dir, exist_ok=True)
    eval_model = args.eval_model or os.getenv("EVAL_MODEL") or DEFAULT_EVAL_MODEL
    output_path = _eval_path(args.output_dir, args.model_name, eval_model)
    if args.reset and os.path.exists(output_path):
        os.remove(output_path)

    # Checkpoint
    done_ids: set[str] = set()
    if os.path.exists(output_path):
        done_ids = {str(obj["id"]) for obj in _load_jsonl(output_path) if obj.get("id")}
        print(f"[evaluate] checkpoint: {len(done_ids)} already done")

    todo_ids = [rid for rid in bench if rid in answers and rid not in done_ids]
    print(f"[evaluate] judge={eval_model}  todo={len(todo_ids)}")
    if not todo_ids:
        print(f"[evaluate] done → {output_path}")
        return

    try:
        llm = LLM(model_name=eval_model)
    except ModelConfigError as exc:
        hint = "; pass --eval_model to use another judge" if eval_model == DEFAULT_EVAL_MODEL else ""
        sys.exit(f"[evaluate] {exc}{hint}")
    evaluator = Evaluator(llm)
    write_lock = threading.Lock()

    def work(rid: str) -> None:
        record = dict(bench[rid])
        record[args.model_name] = answers[rid]
        result = evaluator.eval_pipeline(record, [args.model_name])
        out = {
            "id": rid,
            args.model_name: answers[rid],
            f"{args.model_name}_pred": result[f"{args.model_name}_pred"],
            f"{args.model_name}_details": result[f"{args.model_name}_details"],
        }
        with write_lock, open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(out, ensure_ascii=False) + "\n")

    failed = _run_all("evaluate", work, todo_ids, args.concurrency)
    print(f"[evaluate] done → {output_path}")
    if failed:
        print(
            f"[evaluate] {len(failed)} items could not be judged and count as failures "
            f"until judged; re-run the same command to retry: {', '.join(failed[:20])}"
        )


# ---------------------------------------------------------------------------
# calculate_accuracy
# ---------------------------------------------------------------------------

def _details(obj: dict, model_name: str) -> list[dict]:
    details = obj.get(f"{model_name}_details") or []
    return json.loads(details) if isinstance(details, str) else details


def _check_judgments(
    items: dict[str, dict], records: list[dict], model_name: str, eval_file: str
) -> dict[str, dict]:
    """Return ``{id: eval record}`` after checking the records against the data file.

    Stops if an id is judged twice or is missing from the data, if the number
    of judged rubrics or their text differs from the data (e.g. judged on
    another data version), or if a rubric tag is not 0/1.
    """
    judged: dict[str, dict] = {}
    problems: list[str] = []
    for obj in records:
        rid = str(obj.get("id"))
        details = _details(obj, model_name)
        rubrics = items[rid]["rubrics"] if rid in items else None
        if rid in judged:
            problems.append(f"{rid}: judged more than once")
        elif rubrics is None:
            problems.append(f"{rid}: not in the data file")
        elif len(details) != len(rubrics):
            problems.append(f"{rid}: {len(details)} judged rubrics, the data has {len(rubrics)}")
        elif any(d.get("tag") not in (0, 1) for d in details):
            problems.append(f"{rid}: a rubric tag is neither 0 nor 1")
        elif any(d.get("constraint") != rb["desc"] for d, rb in zip(details, rubrics)):
            problems.append(f"{rid}: rubric text differs from the data file (judged on another data version?)")
        else:
            judged[rid] = {**obj, f"{model_name}_details": details}
    if problems:
        sys.exit(
            f"[accuracy] {len(problems)} record(s) in {eval_file} do not match the data file:\n  "
            + "\n  ".join(problems[:20]) + ("\n  ..." if len(problems) > 20 else "")
        )
    return judged


def _scores(
    items: dict[str, dict], judged: dict[str, dict], model_name: str, ids: list[str]
) -> tuple[float, float]:
    """SSR and HSR (in %) over *ids*; unjudged items count as failures."""
    n_rubrics = sum(len(items[i]["rubrics"]) for i in ids)
    tags = {i: [d["tag"] for d in judged[i][f"{model_name}_details"]] for i in ids if i in judged}
    passed = sum(sum(t) for t in tags.values())
    hard = sum(1 for t in tags.values() if all(t))
    ssr = passed / n_rubrics * 100 if n_rubrics else 0.0
    hsr = hard / len(ids) * 100 if ids else 0.0
    return ssr, hsr


def cmd_calculate_accuracy(args: argparse.Namespace) -> None:
    # Load benchmark data; denominators are fixed by this file
    bench = _load_jsonl(args.data_file)
    items = {str(r["id"]): r for r in bench}
    print(f"[accuracy] benchmark size: {len(items)}")

    groups: dict[str, list[str]] = {
        level: [i for i, r in items.items() if r.get("Difficulty") == level] for level in LEVELS
    }
    groups["all"] = list(items)
    categories = list(dict.fromkeys(r.get("category") or r.get("scenario") or "" for r in bench))
    category_ids = {
        c: [i for i, r in items.items() if (r.get("category") or r.get("scenario") or "") == c]
        for c in categories
    }

    level_stats: dict[str, dict] = {}
    for level, ids in groups.items():
        level_stats[level] = {
            "sample_count": len(ids),
            "constraint_count": sum(len(items[i]["rubrics"]) for i in ids),
        }
        print(
            f"  {level}: samples={level_stats[level]['sample_count']}  "
            f"constraints={level_stats[level]['constraint_count']}"
        )

    eval_model = args.eval_model or os.getenv("EVAL_MODEL") or DEFAULT_EVAL_MODEL
    judged_all: dict[str, dict[str, dict]] = {}
    for model_name in args.model_names:
        eval_file = _eval_path(args.eval_dir, model_name, eval_model)
        if not os.path.exists(eval_file):
            print(f"[accuracy] WARNING: eval file not found: {eval_file}")
            continue
        judged_all[model_name] = _check_judgments(items, _load_jsonl(eval_file), model_name, eval_file)
        missing = len(items) - len(judged_all[model_name])
        if missing:
            print(f"[accuracy] {model_name}: {missing} items have no judgment and count as failures")

    # ── per-model accuracy ───────────────────────────────────────────────────
    acc_rows: list[dict] = []
    category_rows: list[dict] = []
    for model_name, judged in judged_all.items():
        row: dict[str, Any] = {"model": model_name}
        level_scores = {level: _scores(items, judged, model_name, ids) for level, ids in groups.items()}
        for acc_type, k in (("constraint", 0), ("sample", 1)):
            for level, values in level_scores.items():
                row[f"{acc_type}_{level}"] = round(values[k], 2)
        row["valid_count"] = len(judged)
        row["total_count"] = len(items)
        acc_rows.append(row)
        for category, ids in category_ids.items():
            ssr, hsr = _scores(items, judged, model_name, ids)
            category_rows.append(
                {"model": model_name, "category": category, "samples": len(ids),
                 "constraints": sum(len(items[i]["rubrics"]) for i in ids),
                 "constraint_acc": round(ssr, 2), "sample_acc": round(hsr, 2)}
            )

    accs_df = pd.DataFrame(acc_rows)
    if not accs_df.empty:
        accs_df = accs_df.sort_values(
            by=["sample_all", "constraint_all"], ascending=False
        ).reset_index(drop=True)
    print(accs_df.to_string())

    # ── save results ─────────────────────────────────────────────────────────
    os.makedirs(args.output_dir, exist_ok=True)
    level_stats_df = (
        pd.DataFrame(level_stats).T.reset_index().rename(columns={"index": "level"})
    )
    summary_path = os.path.join(args.output_dir, "accuracy_summary.xlsx")
    with pd.ExcelWriter(summary_path) as writer:
        accs_df.to_excel(writer, sheet_name="accuracy", index=False)
        level_stats_df.to_excel(writer, sheet_name="level_stats", index=False)
        pd.DataFrame(category_rows).to_excel(writer, sheet_name="category", index=False)
    print(f"[accuracy] summary saved → {summary_path}")

    # Detailed tagged results
    detail_path = os.path.join(args.output_dir, "results_tagged.jsonl")
    with open(detail_path, "w", encoding="utf-8") as f:
        for rid, record in items.items():
            out = dict(record)
            for model_name, judged in judged_all.items():
                obj = judged.get(rid, {})
                out[model_name] = obj.get(model_name)
                out[f"{model_name}_pred"] = obj.get(f"{model_name}_pred")
                out[f"{model_name}_details"] = obj.get(f"{model_name}_details")
            f.write(json.dumps(out, ensure_ascii=False, default=str) + "\n")
    print(f"[accuracy] tagged results saved → {detail_path}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_jsonl(path: str) -> list[dict]:
    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _safe_name(name: str) -> str:
    """Replace characters that are unsafe in file names."""
    return name.replace("/", "_").replace("\\", "_").replace(":", "_")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_eval",
        description="AppCIF-Bench evaluation pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── pull_answer ──────────────────────────────────────────────────────────
    p_pull = sub.add_parser("pull_answer", help="Call a model and save answers.")
    p_pull.add_argument("--data_file", required=True, help="Benchmark JSONL file.")
    p_pull.add_argument("--model_name", required=True, help="Model name / identifier.")
    p_pull.add_argument(
        "--models_file",
        action="append",
        metavar="PATH",
        help="Python file that registers models with register_model() (repeatable).",
    )
    p_pull.add_argument(
        "--output_dir", default="results", help="Directory to write output files."
    )
    p_pull.add_argument(
        "--concurrency", type=int, default=20, help="Max concurrent API calls."
    )
    p_pull.add_argument(
        "--max_retries", type=int, default=10, help="Per-item retry limit."
    )
    p_pull.add_argument(
        "--timeout", type=float, default=7200, help="Per-request timeout in seconds."
    )
    p_pull.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing output file and start fresh.",
    )

    # ── evaluate ─────────────────────────────────────────────────────────────
    p_eval = sub.add_parser("evaluate", help="Judge saved answers against the rubrics.")
    p_eval.add_argument("--data_file", required=True, help="Benchmark JSONL file.")
    p_eval.add_argument("--model_name", required=True, help="Model whose answers to evaluate.")
    p_eval.add_argument("--answers_file", required=True, help="JSONL file with model answers.")
    p_eval.add_argument(
        "--eval_model",
        default=None,
        help=f"Judge model (default: $EVAL_MODEL or {DEFAULT_EVAL_MODEL}).",
    )
    p_eval.add_argument(
        "--models_file",
        action="append",
        metavar="PATH",
        help="Python file that registers models with register_model() (repeatable).",
    )
    p_eval.add_argument(
        "--output_dir", default="results", help="Directory to write eval output."
    )
    p_eval.add_argument(
        "--concurrency", type=int, default=8, help="Number of items judged in parallel."
    )
    p_eval.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing eval file and start fresh.",
    )

    # ── calculate_accuracy ───────────────────────────────────────────────────
    p_acc = sub.add_parser("calculate_accuracy", help="Compute accuracy metrics.")
    p_acc.add_argument("--data_file", required=True, help="Benchmark JSONL file.")
    p_acc.add_argument(
        "--model_names",
        nargs="+",
        required=True,
        help="One or more model names to include.",
    )
    p_acc.add_argument(
        "--eval_dir",
        default="results",
        help="Directory containing eval JSONL files.",
    )
    p_acc.add_argument(
        "--eval_model",
        default=None,
        help="Judge model used during the evaluate step (to locate files).",
    )
    p_acc.add_argument(
        "--output_dir", default="results", help="Directory for output files."
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "pull_answer":
        cmd_pull_answer(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "calculate_accuracy":
        cmd_calculate_accuracy(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
