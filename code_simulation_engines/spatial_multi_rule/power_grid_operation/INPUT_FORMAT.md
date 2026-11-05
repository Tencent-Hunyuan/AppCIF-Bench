# `run_engine.py` 测试用例输入格式说明

## 一、整体数据结构

```json
{
    "current_state": { ... },      // 可选：状态快照（推演起点）
    "previous_events": [ ... ],    // 可选：历史事件记录列表
    "current_action": { ... }      // 必选：当天请求
}
```

---

## 二、字段详细说明

### 1. `current_state`（可选）- 状态快照

| 字段 | 类型 | 说明 |
|------|------|------|
| `t` | `int` | 快照对应的天数（Day N 的 24:00 时刻状态） |
| `grids` | `Dict` | 电网状态数据 |
| `lines` | `Dict` | 线路状态数据 |
| `global_temp` | `float` | 全局温度（可选） |
| `terrain_override` | `Dict` | 地形覆盖配置（可选） |

**作用**：
- **有 `current_state`**：**快照模式** - 从给定的状态快照开始，只推演到目标天数
- **无 `current_state`**：**无快照模式** - 从默认状态从 Day 1 开始逐天推演

#### 示例

```json
"current_state": {
    "t": 4,
    "grids": {
        "A": {"frequency": 49.95, "G_actual": 3000.0},
        "B": {"frequency": 49.90},
        "C": {"frequency": 50.01},
        "D": {"frequency": 49.72, "L_actual": 8000.0}
    },
    "lines": {
        "L_AC": {"mode": "SERIES"}
    }
}
```

#### `grids` 电网状态字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `frequency` | `float` | 运行频率（Hz） |
| `G_actual` | `float` | 实际出力（MW） |
| `L_actual` | `float` | 实际负荷（MW） |
| `P_droop` | `float` | 下垂控制功率 |
| `P_res` | `float` | 备用功率 |
| `is_island` | `bool` | 是否为孤岛状态 |

#### `lines` 线路状态字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `mode` | `string` | 线路模式，可选值：`SERIES`（串联）、`OPEN`（断开）、`CHARGING`（充电）等 |

#### `terrain_override` 地形覆盖字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `zone_id` | `string` | 区域ID |
| `resistance` | `float` | 阻力系数 |

---

### 2. `previous_events`（可选）- 历史事件记录

数组类型，每个元素代表某一天的事件：

| 字段 | 类型 | 说明 |
|------|------|------|
| `t` | `int` | 事件发生的天数 |
| `description` | `string` | 事件描述（用于日志输出） |
| `actions` | `List[Dict]` | 该天执行的动作列表 |

#### 示例

```json
"previous_events": [
    {
        "t": 1,
        "description": "政策 P-301 [居民专用线保供] 生效",
        "actions": [
            {
                "type": "CFG",
                "policy": {
                    "id": "P-301",
                    "trigger_day": 1,
                    "params": {}
                }
            }
        ]
    },
    {
        "t": 3,
        "description": "政策 P-101 [蓝天保卫战] 生效；台风 Karma 被气象卫星捕捉",
        "actions": [
            {
                "type": "CFG",
                "policy": {
                    "id": "P-101",
                    "trigger_day": 3,
                    "params": {}
                }
            },
            {
                "type": "CFG",
                "event": {
                    "type": "E-TYPHOON",
                    "trigger_day": 3,
                    "params": {
                        "name": "Karma",
                        "center": [41, 25],
                        "movement": [-4, 4]
                    }
                }
            }
        ]
    }
]
```

---

### 3. `current_action`（必选）- 当天请求

| 字段 | 类型 | 说明 |
|------|------|------|
| `t` | `int` | 目标推演天数（推演终点） |
| `user_input` | `string` | 用户输入描述（可选） |
| `actions` | `List[Dict]` | 当天执行的动作列表 |

#### 示例

```json
"current_action": {
    "t": 5,
    "user_input": "又是一宿过去了，今天我这边的天气还不错...",
    "actions": [
        {
            "type": "CFG",
            "grid_pumping": {
                "grid_id": "B",
                "is_pumping": true,
                "pump_load": 1000.0
            }
        },
        {
            "type": "OBS",
            "time_advance": 1
        }
    ]
}
```

---

## 三、`actions` 动作格式详解

动作通过 `type` 字段区分类型，主要分为 **配置类（CFG）** 和 **观测类（OBS）**：

### 3.1 配置类动作 (`type: "CFG"`)

#### 3.1.1 注册政策 `policy`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `string` | 政策ID（如 `P-301`、`P-101`、`P-205`） |
| `trigger_day` | `int` | 触发生效的天数 |
| `params` | `Dict` | 政策参数 |

```json
{
    "type": "CFG",
    "policy": {
        "id": "P-301",
        "trigger_day": 1,
        "params": {}
    }
}
```

#### 3.1.2 注册事件 `event`

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `string` | 事件类型（如 `E-TYPHOON`、`E-HEATWAVE`、`E-EARTHQUAKE`） |
| `trigger_day` | `int` | 触发生效的天数 |
| `params` | `Dict` | 事件参数 |

**台风事件 `E-TYPHOON`：**
```json
{
    "type": "CFG",
    "event": {
        "type": "E-TYPHOON",
        "trigger_day": 3,
        "params": {
            "name": "Karma",
            "center": [41, 25],
            "movement": [-4, 4]
        }
    }
}
```

台风消散：再登记一条同名、`radius` 为 0 的 `E-TYPHOON` 事件，`trigger_day` 为消散日。该事件本身不产生影响，更早登记的同名台风自消散日起不再生效（已断开的线路不会自动恢复）。

**高温事件 `E-HEATWAVE`：**
```json
{
    "type": "CFG",
    "event": {
        "type": "E-HEATWAVE",
        "trigger_day": 11,
        "params": {
            "temperature": 36.0
        }
    }
}
```

**地震事件 `E-EARTHQUAKE`：**
```json
{
    "type": "CFG",
    "event": {
        "type": "E-EARTHQUAKE",
        "trigger_day": 13,
        "params": {
            "epicenter": [44, 11],
            "magnitude": 6.2
        }
    }
}
```

#### 3.1.3 线路模式变更 `line_mode`

| 字段 | 类型 | 说明 |
|------|------|------|
| `line_id` | `string` | 线路ID（如 `L_AC`、`L_CD`） |
| `mode` | `string` | 模式枚举值（`SERIES`、`OPEN`、`CHARGING`） |

```json
{
    "type": "CFG",
    "line_mode": {
        "line_id": "L_AC",
        "mode": "SERIES"
    }
}
```

#### 3.1.4 电网孤岛状态 `grid_island`

| 字段 | 类型 | 说明 |
|------|------|------|
| `grid_id` | `string` | 电网ID（如 `A`、`B`、`C`、`D`） |
| `is_island` | `bool` | 是否为孤岛 |

```json
{
    "type": "CFG",
    "grid_island": {
        "grid_id": "C",
        "is_island": false
    }
}
```

#### 3.1.5 地形变更 `terrain_change`

| 字段 | 类型 | 说明 |
|------|------|------|
| `zone_id` | `string` | 区域ID（如 `T-SC1`） |
| `resistance` | `float` | 阻力系数 |

```json
{
    "type": "CFG",
    "terrain_change": {
        "zone_id": "T-SC1",
        "resistance": 1.2
    }
}
```

#### 3.1.6 电网抽水模式 `grid_pumping`

| 字段 | 类型 | 说明 |
|------|------|------|
| `grid_id` | `string` | 电网ID |
| `is_pumping` | `bool` | 是否抽水 |
| `pump_load` | `float` | 抽水负荷（MW） |

```json
{
    "type": "CFG",
    "grid_pumping": {
        "grid_id": "B",
        "is_pumping": true,
        "pump_load": 1000.0
    }
}
```

---

### 3.2 观测类动作 (`type: "OBS"`)

#### 3.2.1 时间推进 `time_advance`

```json
{
    "type": "OBS",
    "time_advance": 1
}
```

#### 3.2.2 温度更新 `temperature_update`

```json
{
    "type": "OBS",
    "temperature_update": 37.0
}
```

---

## 四、推演模式对比

| 模式 | 条件 | 推演范围 | 典型场景 |
|------|------|----------|----------|
| **快照模式** | `current_state.t > 0` | 从快照天 → 目标天 | 已有中间状态，只需局部推演 |
| **无快照模式** | 无 `current_state` | Day 1 → 目标天 | 完整从头推演 |

---

## 五、完整示例

### 示例1：无快照模式（简单场景）

```json
{
    "query": "时间锚点：系统在终轮之前已经运行了1天...",
    "current_action": {
        "t": 2
    },
    "ground_truth": "..."
}
```

### 示例2：快照模式（台风场景）

```json
{
    "current_state": {
        "t": 4,
        "grids": {
            "A": {"frequency": 49.95, "G_actual": 3000.0},
            "B": {"frequency": 49.90},
            "C": {"frequency": 50.01},
            "D": {"frequency": 49.72, "L_actual": 8000.0}
        },
        "lines": {
            "L_AC": {"mode": "SERIES"}
        }
    },
    "previous_events": [
        {
            "t": 1,
            "description": "政策 P-301 [居民专用线保供] 生效",
            "actions": [
                {"type": "CFG", "policy": {"id": "P-301", "trigger_day": 1, "params": {}}}
            ]
        },
        {
            "t": 2,
            "description": "L_AC 线路切换为串联受限模式",
            "actions": [
                {"type": "CFG", "line_mode": {"line_id": "L_AC", "mode": "SERIES"}}
            ]
        },
        {
            "t": 3,
            "description": "政策 P-101 [蓝天保卫战] 生效；台风 Karma 被气象卫星捕捉",
            "actions": [
                {"type": "CFG", "policy": {"id": "P-101", "trigger_day": 3, "params": {}}},
                {"type": "CFG", "event": {"type": "E-TYPHOON", "trigger_day": 3, "params": {"name": "Karma", "center": [41, 25], "movement": [-4, 4]}}}
            ]
        }
    ],
    "current_action": {
        "t": 5,
        "user_input": "又是一宿过去了...",
        "actions": [
            {"type": "CFG", "grid_pumping": {"grid_id": "B", "is_pumping": true, "pump_load": 1000.0}},
            {"type": "OBS", "time_advance": 1}
        ]
    },
    "expected_output": "generate_final_report()"
}
```

### 示例3：快照模式（复杂多事件场景）

```json
{
    "current_state": {
        "t": 16,
        "grids": {
            "A": {"frequency": 50.20, "P_droop": 0, "P_res": 0, "L_actual": 4450},
            "B": {"frequency": 50.11, "P_droop": 0, "P_res": 0, "L_actual": 750},
            "C": {"frequency": 50.00, "P_droop": 0, "P_res": 0, "L_actual": 2200, "is_island": false},
            "D": {"frequency": 49.31, "P_droop": 0, "P_res": 0, "L_actual": 3600}
        },
        "lines": {
            "L_AC": {"mode": "OPEN"},
            "L_CD": {"mode": "OPEN"}
        },
        "global_temp": 38.0,
        "terrain_override": {
            "T-SC1": {"resistance": 1.2}
        }
    },
    "previous_events": [
        {"t": 3, "description": "政策 P-205 [高新人才引进计划] 发布", "actions": [...]},
        {"t": 11, "description": "全省平均气温 36°C，进入高温天气", "actions": [...]},
        {"t": 13, "description": "全省平均气温 38°C；地震局通报在坐标 (44, 11) 发生 6.2 级地震", "actions": [...]},
        {"t": 14, "description": "Grid C 恢复并网条件", "actions": [...]},
        {"t": 15, "description": "联络线 L_AC、L_CD 状态置为 Open", "actions": [...]},
        {"t": 16, "description": "T-SC1 超导试验走廊进入维护期", "actions": [...]}
    ],
    "current_action": {
        "t": 17,
        "user_input": "请为我生成今天（Day 17）的运行评估报告。",
        "actions": [
            {"type": "OBS", "time_advance": 1}
        ]
    },
    "expected_output": "generate_final_report()"
}
```

---

## 六、关键逻辑说明

1. **政策/事件生效判断**：`trigger_day <= snapshot_day` 时标记为 `active=True`
2. **动作执行顺序**：先应用 `CFG` 配置动作，再执行时间推演
3. **报告输出**：包含逐天推演过程 + 最终状态报告
4. **`ground_truth` 字段**：用于验证模型输出是否符合预期的评判标准
