# Engine manifest

Each row identifies the public release location and the callable used to obtain
the executable ground truth for a structured task instance.

| Public engine ID | L4 reasoning shape | Callable | Bundled examples |
| --- | --- | --- | --- |
| Concert audit | Optimization & Planning | `concert_audit_engine.verified_concert` | `test_cases.py` |
| Spatiotemporal trade | Optimization & Planning | `spatiotemporal_trade_engine.verified_trade` | `test_cases.py` |
| Rule-based adjudication | Decision-Tree State Machine | `rule_based_adjudication.verified_chunqiu` | `test_cases.py` |
| Traditional-medicine diagnosis | Decision-Tree State Machine | `traditional_medicine_diagnosis.verified_zhongyi` | `test_cases.py` |
| Power-grid operation | Spatial / Multi-Rule | `run_engine.verified_dianwang` | `test_cases.py` |
| Tomb exploration | Spatial / Multi-Rule | `tomb_exploration_engine.verified_gumu` | `test_cases.py` |

For a package-qualified import path, prepend the containing directory, e.g.,
`code_simulation_engines.spatial_multi_rule.power_grid_operation.run_engine`.
