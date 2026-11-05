"""Re-derive the Chinese gold rubrics of the 240 Real-world Simulation items from their structured inputs.

Run from the repository root:

    python -m code_simulation_engines.regenerate_gold          # all engines, skipping the very slow trade searches
    python -m code_simulation_engines.regenerate_gold --engines tomb_exploration rule_based_adjudication
    python -m code_simulation_engines.regenerate_gold --ids timespace_13 timespace_30 --include-slow

Each engine computes the scenario state from ``structured_inputs.jsonl`` and prints its derivation
followed by a ``【Checklist】`` block; the checklist lines are the gold rubric items. This script
compares them with the rubric ``desc`` fields of the Chinese data file (ignoring the "N." numbering)
and reports exact matches. Known, intentional differences are listed in README.md.
"""
import argparse
import ast
import contextlib
import importlib
import io
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / 'data' / 'AppCIF_bench_dataset.jsonl'
SLOW = {'timespace_27', 'timespace_31', 'timespace_32', 'timespace_37', 'timespace_38', 'timespace_40'}  # exhaustive search, can take many hours
PREFIX = re.compile(r'^\d+\.\s*')

ENGINES = {
    'concert_audit': ('.optimization_and_planning.concert_audit.concert_audit_engine', 'verified_concert',
                      {'is_annual_plan': False}),
    'spatiotemporal_trade': ('.optimization_and_planning.spatiotemporal_trade.spatiotemporal_trade_engine',
                             'verified_trade', {}),
    'rule_based_adjudication': ('.decision_tree_state_machine.rule_based_adjudication.rule_based_adjudication',
                                'verified_chunqiu', {}),
    'traditional_medicine_diagnosis': (
        '.decision_tree_state_machine.traditional_medicine_diagnosis.traditional_medicine_diagnosis',
        'verified_zhongyi', {}),
    'power_grid_operation': ('.spatial_multi_rule.power_grid_operation.run_engine', 'verified_dianwang', {}),
    'tomb_exploration': ('.spatial_multi_rule.tomb_exploration.tomb_exploration_engine', 'verified_gumu', {}),
}


def parse_input(s):
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return json.loads(s)


def checklist_lines(block):
    lines, started = [], False
    for l in block.split('\n'):
        s = l.strip()
        is_bar = len(s) >= 10 and set(s) == {'='}
        if is_bar and started:
            break
        if s and not is_bar:
            started = True
            if s[:1].isdigit():
                lines.append(s)
    return lines


def run(engine, structured):
    module, func, kwargs = ENGINES[engine]
    verified = getattr(importlib.import_module(module, package=__package__), func)
    with contextlib.redirect_stdout(io.StringIO()):
        out = verified(parse_input(structured), **kwargs)
    if isinstance(out, (list, tuple)):
        out = '\n'.join(map(str, out))
    idx = out.rfind('【Checklist】')
    if idx < 0:
        raise RuntimeError('no 【Checklist】 block in engine output')
    lines = checklist_lines(out[idx + len('【Checklist】'):])
    if engine == 'concert_audit':
        lines = [l for l in lines if re.match(r'^\d+\.模型回复', l)]
    return [PREFIX.sub('', l) for l in lines]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=str(DATA), help='Chinese data file with the released rubrics')
    ap.add_argument('--engines', nargs='*', choices=sorted(ENGINES))
    ap.add_argument('--ids', nargs='*')
    ap.add_argument('--include-slow', action='store_true')
    args = ap.parse_args()

    gold = {}
    with open(args.data, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            gold[r['id']] = [PREFIX.sub('', c['desc']).strip() for c in r['rubrics']]
    with open(HERE / 'structured_inputs.jsonl', encoding='utf-8') as f:
        rows = [json.loads(l) for l in f if l.strip()]

    stats = {}
    for r in rows:
        if args.engines and r['engine'] not in args.engines:
            continue
        if args.ids and r['id'] not in args.ids:
            continue
        if r['id'] in SLOW and not args.include_slow:
            continue
        s = stats.setdefault(r['engine'], [0, 0])
        s[1] += 1
        try:
            got = run(r['engine'], r['structured_input'])
        except Exception as e:
            print(f'[{r["id"]}] engine error: {type(e).__name__}: {e}')
            continue
        if got == gold[r['id']]:
            s[0] += 1
        else:
            diff = [k for k in range(max(len(got), len(gold[r['id']])))
                    if k >= len(got) or k >= len(gold[r['id']]) or got[k] != gold[r['id']][k]]
            print(f'[{r["id"]}] differs at rubric item(s) {diff}')
    for engine, (ok, n) in stats.items():
        print(f'{engine}: {ok}/{n} items reproduce the released rubrics exactly')


if __name__ == '__main__':
    main()
