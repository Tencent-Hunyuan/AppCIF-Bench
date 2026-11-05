EVENTS_DB = {
    # NL (Synthesized Nutrient Liquid)
    "霓虹胃袋": {"item": "NL", "tier": 3, "delta": 1},
    "蓝调": {"item": "NL", "tier": 3, "delta": 1},
    "CBD区域封锁令": {"item": "NL", "tier": 1, "delta": 1, "cbd_blockade": True, "tax_mul_all": 1.5},
    "藻类培养槽褐变": {"item": "NL", "tier": 2, "delta": 1},
    "合成酶专利战": {"item": "NL", "tier": 2, "delta": 1},
    "光合作用皮肤补丁": {"item": "NL", "tier": 2, "delta": -1},
    "地下储备库解封": {"item": "NL", "tier": 1, "delta": -1, "tax_mul_all": 0.5, "disable_terrain_ext": True},
    "全城辟谷运动": {"item": "NL", "tier": 3, "delta": -1, "tax_mul_all": 0.7},
    "超级酵母突变": {"item": "NL", "tier": 2, "delta": -1},
    "外部救援物资抵达": {"item": "NL", "tier": 1, "delta": -1},

    # HL (Habitation License)
    "铁幕排查行动": {"item": "HL", "tier": 1, "delta": 1},
    "时空难民危机": {"item": "HL", "tier": 1, "delta": 1, "terrain_expand_all": 1, "tax_mul_all": {'value':2, 'continue': 2}},
    "中央数据库宕机": {"item": "HL", "tier": 1, "delta": 1},
    "精英分区计划": {"item": "HL", "tier": 1, "delta": 1},
    "出生率反弹": {"item": "HL", "tier": 2, "delta": 1},
    "大赦天下": {"item": "HL", "tier": 1, "delta": -1},
    "新城区拓荒奖励": {"item": "HL", "tier": 1, "delta": -1, "first_free": True}, 
    "量子审批系统上线": {"item": "HL", "tier": 2, "delta": -1},
    "人口大清洗": {"item": "HL", "tier": 1, "delta": -1},
    "虚拟公民权法案": {"item": "HL", "tier": 1, "delta": -1},

    # SM (Structural Matter)
    "灰蛊纳米虫灾": {"item": "SM", "tier": 1, "delta": 1},
    "玛丽维亚微震": {"item": "SM", "tier": 1, "delta": 1, "terrain_expand_maryvia": {'value':2, 'continue': 2}},
    "违建拆除令": {"item": "SM", "tier": 1, "delta": 1},
    "酸雨腐蚀季": {"item": "SM", "tier": 2, "delta": 1},
    "巨型摩天楼计划": {"item": "SM", "tier": 2, "delta": 1},
    "自修复混凝土问世": {"item": "SM", "tier": 2, "delta": -1},
    "烂尾楼爆破回收": {"item": "SM", "tier": 1, "delta": -1},
    "3D打印普及化": {"item": "SM", "tier": 2, "delta": -1},
    "塑料菌类养殖": {"item": "SM", "tier": 2, "delta": -1},
    "反重力力场罩": {"item": "SM", "tier": 2, "delta": -1},

    # CB (Computing Bandwidth)
    "觉醒AI的吞噬": {"item": "CB", "tier": 1, "delta": 1},
    "元宇宙电竞赛事": {"item": "CB", "tier": 3, "delta": 1, "kw_speed_add": 2},
    "海底光缆断裂": {"item": "CB", "tier": 1, "delta": 1, "kw_speed_mul": 0.5, "tax_mul_kw": 2.0},
    "挖矿病毒爆发": {"item": "CB", "tier": 2, "delta": 1},
    "量子加密强制令": {"item": "CB", "tier": 1, "delta": 1, "tax_mul_sw": 2.0},
    "超导芯片量产": {"item": "CB", "tier": 2, "delta": -1},
    "数据压缩革命": {"item": "CB", "tier": 2, "delta": -1},
    "僵尸网络被剿灭": {"item": "CB", "tier": 1, "delta": -1},
    "数字排毒周": {"item": "CB", "tier": 3, "delta": -1},
    "生物算力并网": {"item": "CB", "tier": 2, "delta": -1},
}
