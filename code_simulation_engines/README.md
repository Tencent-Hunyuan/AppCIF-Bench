# Code Simulation Engines

This directory contains the six executable ground-truth engines used by the
**Real-world Simulation** tasks in AppCIF-Bench. Each engine consumes a
structured task instance and produces the deterministic reference result and
its associated checking criteria.

The layout follows the three L4 reasoning-shape archetypes reported in Figure
6(b) of the paper. This is an artifact organization for inspection; it does
not introduce a new dataset split or modify the benchmark instances.

| L4 reasoning shape | Engine directory | Primary entry point |
| --- | --- | --- |
| Optimization & Planning | `optimization_and_planning/concert_audit/` | `concert_audit_engine.py` |
| Optimization & Planning | `optimization_and_planning/spatiotemporal_trade/` | `spatiotemporal_trade_engine.py` |
| Decision-Tree State Machine | `decision_tree_state_machine/rule_based_adjudication/` | `rule_based_adjudication.py` |
| Decision-Tree State Machine | `decision_tree_state_machine/traditional_medicine_diagnosis/` | `traditional_medicine_diagnosis.py` |
| Spatial / Multi-Rule | `spatial_multi_rule/power_grid_operation/` | `run_engine.py` and `power_grid_engine.py` |
| Spatial / Multi-Rule | `spatial_multi_rule/tomb_exploration/` | `tomb_exploration_engine.py` |

## Quick start

Use Python 3.10 or later. The released engine paths require only the Python
standard library. From the repository root:

```bash
python -m code_simulation_engines.run_smoke_tests
```

The smoke test runs one bundled, representative structured instance for every
engine and reports whether execution completed. The individual `test_cases.py`
files provide additional local examples. To use an engine programmatically,
import its `verified_*` function shown in `MANIFEST.md` and pass a structured
instance following that engine's `INPUT_FORMAT.md` (where present).

The optional diagnostic Excel export in the spatiotemporal trade engine needs
`pandas` and `openpyxl`; normal ground-truth execution does not.

## Benchmark instances and gold rubrics

`structured_inputs.jsonl` holds the structured engine input of each of the 240
simulation samples (`id`, `category`, `engine`, `structured_input`). Every
engine module prints its output for one sample when run directly:

```bash
python -m code_simulation_engines.spatial_multi_rule.tomb_exploration.tomb_exploration_engine tomb_18
python -m code_simulation_engines.decision_tree_state_machine.rule_based_adjudication.rule_based_adjudication adjudication_11
```

The engine output is a derivation followed by a `【Checklist】` block whose
lines are the sample's gold rubrics. The engines produce Chinese text; the
English rubrics are translations. `regenerate_gold.py` re-derives the rubrics
of all simulation samples and compares them with the Chinese data file:

```bash
python -m code_simulation_engines.regenerate_gold
python -m code_simulation_engines.regenerate_gold --engines rule_based_adjudication --ids adjudication_11
```

Notes:

- The released rubrics are final; regenerating them is optional and only
  serves to check or extend the engines. The engine output matches the
  released rubrics except `concert_3` rubric 2, which was edited by hand to
  accept two equivalent readings of the rulebook.
- Spatiotemporal trade samples run an exhaustive search: most take a few
  minutes, and six samples (`timespace_27/31/32/37/38/40`) can take many hours, so
  `regenerate_gold.py` skips those six unless `--include-slow` is given.
- The released `ground-truth derivation` texts are the engine derivations
  (the text before `【Checklist】`). A few derivations list labels in an order
  that depends on Python's string hashing; run with `PYTHONHASHSEED=0` to
  reproduce them exactly. For traditional-medicine diagnosis, source-quote
  annotations were removed and the order of the organ sub-sections follows the
  original generation. The rubrics do not depend on hashing.
- For concert audit, `structured_inputs.jsonl` is aligned with the released
  question text (ten small corrections where the original structured input
  disagreed with the question); the released derivations are computed from
  these inputs.

## Scope of this artifact

These files implement the executable ground truth and its structured inputs.
Benchmark prompts (including the scenario rulebooks, which are the
`system_prompt` of each simulation sample), evaluation instances, and model
generations remain in the benchmark data release rather than being duplicated
here. Development-only scripts, cached bytecode, generated reports, and local
spreadsheets are intentionally omitted from this public artifact.
