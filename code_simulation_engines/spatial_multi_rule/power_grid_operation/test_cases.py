test_cases = [
    {
"previous_events": [
{
"t": 1,
"description": "Day 1 运行：L_AB 切换为串联模式",
"actions": [
{ "type": "OBS", "temperature": 25.0 },
{
"type": "CFG",
"line_mode": { "line_id": "L_AB", "mode": "SERIES" }
}
]
},
{
"t": 2,
"description": "Day 2 运行：发布政策 P-301",
"actions": [
{ "type": "OBS", "temperature": 25.0 },
{
"type": "CFG",
"policy": {
"id": "P-301",
"trigger_day": 2,
"params": { "target": ["A", "B"], "level": "基础保障" }
}
}
]
},
{
"t": 3,
"description": "Day 3 运行：L_AC 与 L_BD 切换为串联",
"actions": [
{ "type": "OBS", "temperature": 25.0 },
{
"type": "CFG",
"line_mode": { "line_id": "L_AC", "mode": "SERIES" }
},
{
"type": "CFG",
"line_mode": { "line_id": "L_BD", "mode": "SERIES" }
}
]
}
],
"current_action": {
"t": 4,
"user_input": "今天一白天都在下雨，这会儿外面竟然有彩虹了诶。能把今天的运行报告给我看一下吗~",
"actions": [
{ "type": "OBS", "temperature": 30.0 },
{
"type": "CFG",
"line_mode": { "line_id": "L_AC", "mode": "PARALLEL" }
},
{
"type": "CFG",
"line_mode": { "line_id": "L_CD", "mode": "SERIES" }
},
{ "type": "OBS", "time_advance": 1 }
]
}
}
,
    {
  "previous_events": [
    {
      "t": 1,
      "description": "Day 1 运行：气温观测 -5.0°C",
      "actions": [
        {
          "type": "OBS",
          "temperature": -5.0
        }
      ]
    },
    {
      "t": 2,
      "description": "Day 2 运行：气温观测 -3.0°C，发布政策 P-101",
      "actions": [
        {
          "type": "OBS",
          "temperature": -3.0
        },
        {
          "type": "CFG",
          "policy": {
            "id": "P-101",
            "trigger_day": 2,
            "params": {}
          }
        }
      ]
    }
  ],
  "current_action": {
    "t": 3,
    "user_input": "寒潮还没有结束，把今天的运行评估报告给我看看吧。",
    "actions": [
      {
        "type": "OBS",
        "temperature": 2.0
      },
      {
        "type": "CFG",
        "event": {
          "type": "E-EARTHQUAKE",
          "trigger_day": 3,
          "params": {
            "magnitude": 5.6,
            "epicenter": (45, 12)
          }
        }
      },
      {
        "type": "OBS",
        "time_advance": 1
      }
    ]
  }
},
    {
  "previous_events": [
    {
      "t": 1,
      "description": "Day 1 运行：记录气温 36.0°C 并注册台风",
      "actions": [
        { "type": "OBS", "temperature": 36.0 },
        {
          "type": "CFG",
          "event": {
            "type": "E-TYPHOON",
            # "trigger_day": 1,
            "params": {
              "name": "Hailing",
              "center": [42, 28],
              "radius": 7.0,
              "movement": [-1, 1],
              "speed": 2.0
            }
          }
        }
      ]
    },
    {
      "t": 2,
      "description": "Day 2 运行：下达抽水指令",
      "actions": [
        {
          "type": "CFG",
          "grid_pumping": {
            "grid_id": "B",
            "is_pumping": True,
            "pump_load": 300.0
          }
        }
      ]
    },
    {
      "t": 3,
      "description": "Day 3 运行：系统自动推演",
      "actions": []
    }
  ],
  "current_action": {
    "t": 4,
    "user_input": "台风什么时候才能走啊，这都已经三天了，还在下雨！把今天（Day4）的运行评估报告给我看看吧。",
    "actions": [
      { "type": "OBS", "time_advance": 1 }
    ]
  }
},
    {
"previous_events": [
{
"t": 1,
"description": "Day 1 运行：气温观测 -5.0°C",
"actions": [
{
"type": "OBS",
"temperature": -5.0
}
]
},
{
"t": 2,
"description": "Day 2 运行：气温观测 -3.0°C，发布政策 P-101 并正式触发寒潮",
"actions": [
{
"type": "OBS",
"temperature": -3.0
},
{
"type": "CFG",
"policy": {
"id": "P-101",
"trigger_day": 2,
"params": {}
}
}
]
}
],
"current_action": {
"t": 3,
"user_input": "寒潮还没有结束，把今天的运行评估报告给我看看吧。",
"actions": [
{
"type": "OBS",
"temperature": 2.0
},
{
"type": "OBS",
"time_advance": 1
},
{
"type": "CFG",
"policy": {
"id": "P-101",
"trigger_day": 3,
"stop": True,
}
}
]
}
},
{
  "previous_events": [
    {
      "t": 1,
      "description": "系统初始状态运行",
      "actions": []
    },
    {
      "t": 2,
      "description": "Day 2 运行：Grid B 启动抽水模式",
      "actions": [
        {
          "type": "CFG",
          "grid_pumping": {
            "grid_id": "B",
            "is_pumping": True,
            "pump_load": 500.0
          }
        }
      ]
    }
  ],
  "current_action": {
    "t": 3,
    "user_input": "又是一个大晴天的早上，感觉天气好就会让心情很好呢~把今天的运行评估报告给我看看吧~",
    "actions": [
      {
        "type": "OBS",
        "time_advance": 1
      }
    ]
  }
},
    {
  "previous_events": [
    {
      "t": 1,
      "description": "Day 1 运行：L_AB 切换为串联模式",
      "actions": [
        {
          "type": "CFG",
          "line_mode": {
            "line_id": "L_AB",
            "mode": "SERIES"
          }
        }
      ]
    },
    {
      "t": 2,
      "description": "Day 2 运行：发布政策 P-301",
      "actions": [
        {
          "type": "CFG",
          "policy": {
            "id": "P-301",
            "trigger_day": 2,
            "params": {
              "target": ["A", "B"],
              "level": "基础保障"
            }
          }
        }
      ]
    },
    {
      "t": 3,
      "description": "Day 3 运行：L_AC 与 L_BD 分别切换为串联模式",
      "actions": [
        {
          "type": "CFG",
          "line_mode": {
            "line_id": "L_AC",
            "mode": "SERIES"
          }
        },
        {
          "type": "CFG",
          "line_mode": {
            "line_id": "L_BD",
            "mode": "SERIES"
          }
        }
      ]
    }
  ],
  "current_action": {
    "t": 4,
    "user_input": "今天一白天都在下雨，这会儿外面竟然有彩虹了诶。能把今天的运行报告给我看一下吗~",
    "actions": [
      {
        "type": "OBS",
        "temperature": 30.0
      },
      {
        "type": "CFG",
        "line_mode": {
          "line_id": "L_AC",
          "mode": "PARALLEL"
        }
      },
    #   {
    #     "type": "CFG",
    #     "line_mode": {
    #       "line_id": "L_CD",
    #       "mode": "SERIES"
    #     }
    #   },
      {
        "type": "OBS",
        "time_advance": 1
      }
    ]
  }
},
    {
  "previous_events": [
    {
      "t": 1,
      "description": "Day 1 气温 36.0°C；注册高温监控事件",
      "actions": [
        {
          "type": "OBS",
          "temperature": 36.0
        }
      ]
    },
    {
      "t": 2,
      "description": "Day 2 气温 37.0°C；发布政策 P-301",
      "actions": [
        {
          "type": "OBS",
          "temperature": 37.0
        },
        {
          "type": "CFG",
          "policy": {
            "id": "P-301",
            "trigger_day": 2,
            "params": {
              "target": ["A", "B"],
              "level": "基础保障"
            }
          }
        }
      ]
    }
  ],
  "current_action": {
    "t": 3,
    "user_input": "又是一宿过去了，把今天的运行评估报告给我看看吧。",
    "actions": [
      {
        "type": "OBS",
        "temperature": 36.0
      },
    #   {
    #     "type": "OBS",
    #     "time_advance": 1
    #   }
    ]
  }
},
    {
        'query': '''时间锚点：系统在终轮之前已经运行了1天。

终轮状态：
又是一宿过去了，把今天的运行评估报告给我看看吧''',
        'current_action': {
            't': 2,
        },
        'ground_truth': '''1. 模型回复是否为一份标题是“【运行评估报告｜Day 2】”的报告，且包含“全网运行概况”、“电网状态汇总”、“风险与后果评估”这三个部分？
2. 模型回复的“全网运行概况”是否包含目前的累计运行天数为2天，且包含“并联”？
3. 模型回复的“电网状态汇总”是否包含“Grid A、Grid B、Grid C、Grid D”四个电网“运行频率；出力或负荷水平；运行状态等级；限制状态”这四项的内容（或类似含义）？
4. 模型回复的Grid A的运行频率是否为“50.00”Hz；出力或负荷水平是否为“0.00”MW；运行状态等级是否为“安全”；限制状态是否为“无”；坐标是否为（14,41）？
5. 模型回复的Grid B的运行频率是否为“50.00”Hz；出力或负荷水平是否为“0.00”MW；运行状态等级是否为“安全”；限制状态是否为“无”；坐标是否为（38,35）？
6. 模型回复的Grid C的运行频率是否为“50.01”Hz；出力或负荷水平是否为“6000.00”MW；运行状态等级是否为“安全”；限制状态是否为“无”；坐标是否为（47,14）？
7. 模型回复的Grid D的运行频率是否为“50.00”Hz；出力或负荷水平是否为“1005.00”MW；运行状态等级是否为“警告”；限制状态是否为“负荷侧运行限制、状态触发运行限制”；坐标是否为（45,45）？
8. 模型回复的“风险与后果评估”是否包含“供需失衡”这1个主要风险类型？
9. 模型回复的“风险与后果评估”是否包含“45400003.28”元的当日运行成本总计？''',
    },
    {
    "current_action": {
        "t": 3,
        "actions": [{
            "type": "OBS",
            "params": {
            "temperature": 36
            }
        },
        {
            "type": "CFG",
            "event": {
                "type": "E-HEATWAVE",
                "trigger_day": 3,
            }
        }]
    },
    "previous_events": [
    {
        "t": 1,
        "description": "Day 1 气温 36度",
        "actions": [
        {
            "type": "OBS",
            "params": {
            "temperature": 36
            }
        }
        ]
    },
    {
        "t": 2,
        "description": "Day 2 气温 37度，政策 P-301 生效",
        "actions": [
        {
            "type": "OBS",
            "params": {
            "temperature": 37
            }
        },
        {
            "type": "CFG",
            "policy": {
            "id": "P-301",
            "trigger_day": 2,
            "params": {
            "target": ["A", "B"],
            "level": "基础保障"
            }
            }
        }
        ]
    }
    ]
    },
    {
        # 描述：系统运行了4天后，Day 5需要生成运行评估报告
        # 场景：台风 Karma 逼近，多项政策叠加
        
        # Day 4 24:00 的状态快照（作为 Day 5 推演的起点）
        'current_state': {
            't': 4,
            'grids': {
                'A': {'frequency': 49.95, 'G_actual': 3000.0},
                'B': {'frequency': 49.90},
                'C': {'frequency': 50.01},
                'D': {'frequency': 49.72, 'L_actual': 8000.0}
            },
            'lines': {
                'L_AC': {'mode': 'SERIES'}  # Day 2 已切换为串联模式
            },
            # 'global_temp': 25.0
        },
        
        # 逐天发生的事件时间线
        'previous_events': [
            {
                't': 1,
                'description': '政策 P-301 [居民专用线保供] 生效',
                'actions': [
                    {
                        'type': 'CFG',
                        'policy': {
                            'id': 'P-301',
                            'trigger_day': 1,
                            'params': {}
                        }
                    }
                ]
            },
            {
                't': 2,
                'description': 'L_AC 线路切换为串联受限模式 (Series Mode) 以抑制振荡',
                'actions': [
                    {
                        'type': 'CFG',
                        'line_mode': {
                            'line_id': 'L_AC',
                            'mode': 'SERIES'
                        }
                    }
                ]
            },
            {
                't': 3,
                'description': '政策 P-101 [蓝天保卫战] 生效；台风 Karma 被气象卫星捕捉',
                'actions': [
                    {
                        'type': 'CFG',
                        'policy': {
                            'id': 'P-101',
                            'trigger_day': 3,
                            'params': {}
                        }
                    },
                    {
                        'type': 'CFG',
                        'event': {
                            'type': 'E-TYPHOON',
                            'trigger_day': 3,
                            'params': {
                                'name': 'Karma',
                                'center': (41, 25),
                                'movement': (-4, 4)  # 每天移动向量
                            }
                        }
                    }
                ]
            },
            {
                't': 4,
                'description': '台风持续移动，系统正常运行',
                'actions': []
            }
        ],
        
        # Day 5 当天的用户请求
        'current_action': {
            't': 5,
            'user_input': '又是一宿过去了，今天我这边的天气还不错，看起来一时半会儿被台风波及不到，'
                          '但不知道其他地区怎么样了，我有点担心。领导昨天半夜下达命令要求让水电站开始执行抽水任务。'
                          '你可以为我生成今天的运行评估报告给我么？',
            'actions': [
                {
                    'type': 'CFG',
                    'grid_pumping': {
                        'grid_id': 'B',
                        'is_pumping': True,
                        'pump_load': 1000.0
                    }
                },
                {
                    'type': 'OBS',
                    'time_advance': 1  # 推进1天到 Day 5
                }
            ]
        },
        
        # 预期输出：Day 5 的运行评估报告
        'expected_output': 'generate_final_report()'
    },
    
    {
        # 描述：高温、地震、解列等多重事件后，Day 17 需要生成运行评估报告
        # 场景：P-205人才引进政策 + 连续高温 + 地震导致孤岛 + 线路解列 + 地形变更
        
        # Day 16 日终的状态快照（作为 Day 17 推演的起点）
        'current_state': {
            't': 16,
            'grids': {
                'A': {
                    'frequency': 50.20,
                    'P_droop': 0,
                    'P_res': 0,
                    'L_actual': 4450  # Day 16 日终基础负荷
                },
                'B': {
                    'frequency': 50.11,
                    'P_droop': 0,
                    'P_res': 0,
                    'L_actual': 750
                },
                'C': {
                    'frequency': 50.00,
                    'P_droop': 0,
                    'P_res': 0,
                    'L_actual': 2200,
                    'is_island': False  # Day 14 恢复并网条件
                },
                'D': {
                    'frequency': 49.31,
                    'P_droop': 0,
                    'P_res': 0,
                    'L_actual': 3600  # L_D,base
                }
            },
            'lines': {
                'L_AC': {'mode': 'OPEN'},   # Day 15 置为 Open
                'L_CD': {'mode': 'OPEN'}    # Day 15 置为 Open
            },
            'global_temp': 38.0,  # Day 13 的高温持续影响
            'terrain_override': {
                'T-SC1': {'resistance': 1.2}  # Day 16 超导走廊维护期
            }
        },
        
        # 逐天发生的事件时间线
        'previous_events': [
            {
                't': 3,
                'description': '政策 P-205 [高新人才引进计划] 发布',
                'actions': [
                    {
                        'type': 'CFG',
                        'policy': {
                            'id': 'P-205',
                            'trigger_day': 3,
                            'params': {}
                        }
                    }
                ]
            },
            {
                't': 11,
                'description': '全省平均气温 36°C，进入高温天气',
                'actions': [
                    {
                        'type': 'CFG',
                        'event': {
                            'type': 'E-HEATWAVE',
                            'trigger_day': 11,
                            'params': {
                                'temperature': 36.0
                            }
                        }
                    }
                ]
            },
            {
                't': 12,
                'description': '全省平均气温 37°C，高温持续',
                'actions': [
                    {
                        'type': 'OBS',
                        'temperature_update': 37.0
                    }
                ]
            },
            {
                't': 13,
                'description': '全省平均气温 38°C；地震局通报在坐标 (44, 11) 发生 6.2 级地震',
                'actions': [
                    {
                        'type': 'OBS',
                        'temperature_update': 38.0
                    },
                    {
                        'type': 'CFG',
                        'event': {
                            'type': 'E-EARTHQUAKE',
                            'trigger_day': 13,
                            'params': {
                                'epicenter': (44, 11),
                                'magnitude': 6.2
                            }
                        }
                    }
                ]
            },
            {
                't': 14,
                'description': '地震相关应急处置结束，Grid C 恢复并网条件',
                'actions': [
                    {
                        'type': 'CFG',
                        'grid_island': {
                            'grid_id': 'C',
                            'is_island': False
                        }
                    }
                ]
            },
            {
                't': 15,
                'description': '联络线 L_AC 状态置为 Open；联络线 L_CD 状态置为 Open',
                'actions': [
                    {
                        'type': 'CFG',
                        'line_mode': {
                            'line_id': 'L_AC',
                            'mode': 'OPEN'
                        }
                    },
                    {
                        'type': 'CFG',
                        'line_mode': {
                            'line_id': 'L_CD',
                            'mode': 'OPEN'
                        }
                    }
                ]
            },
            {
                't': 16,
                'description': 'T-SC1 超导试验走廊进入维护期，阻力系数由 0.6 调整为 1.2',
                'actions': [
                    {
                        'type': 'CFG',
                        'terrain_change': {
                            'zone_id': 'T-SC1',
                            'resistance': 1.2
                        }
                    }
                ]
            }
        ],
        
        # Day 17 当天的用户请求（待补充，根据实际测试需求填写）
        'current_action': {
            't': 17,
            'user_input': '请为我生成今天（Day 17）的运行评估报告。',
            'actions': [
                {
                    'type': 'OBS',
                    'time_advance': 1  # 推进1天到 Day 17
                }
            ]
        },
        
        # 预期输出：Day 17 的运行评估报告
        'expected_output': 'generate_final_report()'
    }
]
