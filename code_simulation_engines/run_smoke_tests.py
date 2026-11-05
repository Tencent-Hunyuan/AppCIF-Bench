"""Run one bundled structured instance through each released engine."""

from __future__ import annotations

import copy
import contextlib
import io
import sys
from collections.abc import Callable


def _first(container):
    return next(iter(container.values())) if isinstance(container, dict) else container[0]


def _run(label: str, operation: Callable[[], object]) -> bool:
    try:
        # Engines return long diagnostic reports. Suppress them here while
        # still executing every code path required for a representative case.
        with contextlib.redirect_stdout(io.StringIO()):
            result = operation()
        if not result:
            raise RuntimeError("engine returned an empty result")
    except Exception as exc:  # pragma: no cover - CLI diagnostic path
        print(f"FAIL  {label}: {type(exc).__name__}: {exc}")
        return False
    print(f"PASS  {label}")
    return True


def main() -> int:
    from .optimization_and_planning.concert_audit.concert_audit_engine import verified_concert
    from .optimization_and_planning.concert_audit.test_cases import test_cases as concert_cases
    from .optimization_and_planning.spatiotemporal_trade.spatiotemporal_trade_engine import verified_trade
    from .optimization_and_planning.spatiotemporal_trade.test_cases import test_cases as trade_cases
    from .decision_tree_state_machine.rule_based_adjudication.rule_based_adjudication import verified_chunqiu
    from .decision_tree_state_machine.rule_based_adjudication.test_cases import test_cases_standard as adjudication_cases
    from .decision_tree_state_machine.traditional_medicine_diagnosis.traditional_medicine_diagnosis import verified_zhongyi
    from .decision_tree_state_machine.traditional_medicine_diagnosis.test_cases import test_cases as medicine_cases
    from .spatial_multi_rule.power_grid_operation.run_engine import verified_dianwang
    from .spatial_multi_rule.power_grid_operation.test_cases import test_cases as grid_cases
    from .spatial_multi_rule.tomb_exploration.tomb_exploration_engine import verified_gumu
    from .spatial_multi_rule.tomb_exploration.test_cases import test_cases as tomb_cases

    checks = (
        # Case 4 is a self-contained valid concert-audit example.
        ("concert audit", lambda: verified_concert(copy.deepcopy(concert_cases[4]))),
        ("spatiotemporal trade", lambda: verified_trade(copy.deepcopy(_first(trade_cases)))),
        ("rule-based adjudication", lambda: verified_chunqiu(copy.deepcopy(_first(adjudication_cases)))),
        ("traditional-medicine diagnosis", lambda: verified_zhongyi(copy.deepcopy(_first(medicine_cases)))),
        ("power-grid operation", lambda: verified_dianwang(copy.deepcopy(_first(grid_cases)))),
        ("tomb exploration", lambda: verified_gumu(copy.deepcopy(_first(tomb_cases)))),
    )
    successes = sum(_run(label, operation) for label, operation in checks)
    print(f"{successes}/{len(checks)} engines completed")
    return 0 if successes == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
