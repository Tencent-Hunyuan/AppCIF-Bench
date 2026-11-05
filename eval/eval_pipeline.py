"""
eval/eval_pipeline.py
---------------------
Core evaluation logic for AppCIF-Bench.

Every rubric of the dataset has exactly one evaluation of type ``llm``: an LLM
judge decides whether the model answer satisfies it. Any other evaluation type
is rejected.

Every rubric is judged independently with the prompt template below, which
contains the rubric, the item's final-turn ``question`` and the model answer;
the system prompt and the dialogue history are never given to the judge. The
same Chinese judge prompt is used for the Chinese and the English data. A judge
reply counts only if its ``tag`` is exactly 是 (pass) or 否 (fail); anything
else is retried. If a rubric cannot be judged after all retries, the whole item
is left unjudged (and is scored as a failure), never silently passed or skipped.
"""

from __future__ import annotations

import json
import re

from eval.llm_client import LLM

JUDGE_PROMPT = '''请你判断模型响应是否符合下述指定约束：
## 指定约束
{constraint}

## 问题（指定约束从问题中抽取得到，如果指令约束有不清晰之处，可以参考下述问题进行细化）
{question}

## 模型响应
{answer}

## 输出
请按照下述json格式进行输出（若满足约束“tag“字段为是，不满足则为否）：
{{
    "reason": "简要说明理由，仅关注约束“{constraint}”满足与否，禁止引入其他约束",
    "tag": "是｜否"
}}
'''

VALID_TAGS = ("是", "否")
JUDGE_MAX_RETRIES = 10

_RE_TAG = re.compile(r'["\']?\s*tag\s*["\']?\s*[:：]\s*["\']?\s*(是|否)\s*(?=["\'，,}\n]|$)', re.S)
_RE_REASON = re.compile(r'["\']?\s*reason\s*["\']?\s*[:：]\s*["\']?\s*(.+?)(?:\s*["\']?\s*[,，}\n]|$)', re.S)


class JudgeError(RuntimeError):
    """Raised when a rubric cannot be judged after all retries."""


def parse_judge_reply(raw: str | None) -> dict | None:
    """Return ``{"tag": "是"|"否", "reason": str}`` or None if *raw* is unusable.

    Tries the whole reply, a fenced code block and the outermost ``{...}`` as
    JSON, then falls back to a regex on ``"tag": "是|否"``.  A JSON ``tag``
    other than exactly 是 / 否 makes the reply unusable.
    """
    text = (raw or "").strip()
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        candidates.append(fence.group(1))
    left, right = text.find("{"), text.rfind("}")
    if 0 <= left < right:
        candidates.append(text[left:right + 1])
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "tag" in obj:
            tag = obj["tag"].strip() if isinstance(obj["tag"], str) else obj["tag"]
            if tag not in VALID_TAGS:
                return None
            return {"tag": tag, "reason": obj.get("reason", "")}
    tag_match = _RE_TAG.search(text)
    if tag_match:
        reason_match = _RE_REASON.search(text)
        reason = reason_match.group(1).strip().strip("\"'") if reason_match else ""
        return {"tag": tag_match.group(1), "reason": reason}
    return None


class Evaluator:
    """
    Evaluate model answers against a set of constraints.

    Parameters
    ----------
    llm : LLM
        An initialised :class:`~eval.llm_client.LLM` instance used for
        LLM-based constraint evaluation.
    """

    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    # ------------------------------------------------------------------
    # Rubric judging
    # ------------------------------------------------------------------

    def llm_eval(self, constraint: dict, answer: str, question: str) -> tuple[int, str, str]:
        """
        Ask the LLM whether *answer* satisfies *constraint*.

        Returns
        -------
        (tag, reason, raw) where *tag* is 1 (pass) or 0 (fail) and *raw* is
        the judge reply.  Raises :class:`JudgeError` if no usable reply is
        obtained within ``JUDGE_MAX_RETRIES`` attempts; errors of the judge
        call itself (already retried by the client) are raised unchanged.
        """
        prompt = JUDGE_PROMPT.format(
            constraint=constraint["complete_constraint"], question=question, answer=answer
        )

        last = ""
        for _ in range(JUDGE_MAX_RETRIES):
            raw = self.llm.get_model_answer(prompt)
            result = parse_judge_reply(raw)
            if result is not None:
                return (0 if result["tag"] == "否" else 1), result["reason"], raw
            last = (raw or "")[:200]
        raise JudgeError(f"no usable judge reply after {JUDGE_MAX_RETRIES} attempts: {last!r}")

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    def eval_pipeline(self, record: dict, model_names: list[str]) -> dict:
        """
        Evaluate *record* for every model in *model_names*.

        After evaluation, the record will contain:
        - ``{model}_pred``    — 1 if all constraints pass, 0 otherwise
        - ``{model}_details`` — list with per-constraint details

        Raises :class:`JudgeError` (or the evaluator's exception) if any
        constraint cannot be evaluated, so that the item is not recorded.
        """
        constraints = record["rubrics"]
        question: str = record["question"]

        if isinstance(constraints, str):
            constraints = json.loads(constraints)

        for model_name in model_names:
            answer: str = record[model_name]
            results: list[dict] = []

            for constraint_sub in constraints:
                tags: list[int] = []
                reason, raw = "", ""

                for constraint in constraint_sub["evaluation"]:
                    if constraint["type"] != "llm":
                        raise ValueError(f"Unsupported evaluation type: {constraint['type']!r}")
                    tag, r, r_raw = self.llm_eval(constraint, answer, question)
                    tags.append(tag)
                    if tag == 0 or not reason:
                        reason, raw = r, r_raw

                results.append(
                    {
                        "constraint": constraint_sub["desc"],
                        "tag": 0 if 0 in tags else 1,
                        "reason": reason,
                        "raw": raw,
                    }
                )

            record[f"{model_name}_pred"] = int(all(r["tag"] for r in results))
            record[f"{model_name}_details"] = results

        return record
