# 春秋断狱 - 标准输入格式规范

## 一、测试案例结构

```python
{
    'case_id':           int,       # 案例唯一编号
    'case_name':         str,       # 案例名称
    'dossiers':          dict,      # 卷宗数据（核心）
    'judgments':         list,      # 裁断任务列表
    'expected_results':  dict,      # 预期结果
    'rubrics':           str,       # 评判标准
}
```

## 二、卷宗数据（dossiers）

### 模式A - 简单卷宗（无子页）

```python
'SP-2026-009': {
    'title':      str,          # 卷宗标题
    'subjects':   list,         # 可裁断主体列表
    'background': str,          # 可选，背景约束（如"战时管理状态"）
    'identities': {             # 可选，卷宗级身份信息
        '主体名': '角色身份',
    },
    '起因':       str,          # 起因文本
    '主体名':     str,          # 该主体的行为描述
    '结果':       str,          # 结果文本
    '行为描述补充': str,        # 可选，补充材料
}
```

### 模式B - 复杂卷宗（有子页）

```python
'SP-2026-006': {
    'title':      str,
    'subjects':   list,         # 全卷宗可裁断主体
    'background': str,          # 可选，背景约束
    'identities': {             # 可选，卷宗级身份信息
        '陆临渊': '边防节度使（管理者/上级）',
        '沈从戎': '节度使亲卫（部属/下级）',
    },
    '起因':       str,          # 卷宗级起因（可选）
    '结果':       str,          # 卷宗级结果（可选）
    'sub_pages': {
        'A': {
            'page_title': str,
            'subjects':   list,   # 本子页裁断主体
            '起因':       str,
            '主体名':     str,    # 行为描述
            '结果':       str,
            '行为描述补充': str,  # 可选
        },
        # 更多子页...
    }
}
```

## 三、裁断任务（judgments）

```python
'judgments': [
    {'dossier_id': 'SP-2026-009', 'subject': '燕南飞'},
    {'dossier_id': 'SP-2026-011', 'subject': '柳依依'},
]
```

## 四、预期结果（expected_results）

```python
'expected_results': {
    ('卷宗编号', '主体名'): {
        # 主权裁断
        'M': int,           # 原心动机值 (0/2/5)
        'M_state': str,     # 动机状态 (志善/不明/志恶)
        'E': int,           # 伦理位阶值 (0/1/3/5)
        'E_state': str,     # 伦理状态
        'N': int,           # 名分正当性 (0/5)
        'N_state': str,     # 名分状态
        'Q': int,           # 权变修正值 (0/3)
        'Q_notes': list,    # 权变说明
        'J': int,           # 最终裁断值
        'verdict': str,     # 裁断结论 (礼义可原/礼义有罪)
        
        # 现代法律模块
        'CR': bool,         # 刑事责任
        'AR': bool,         # 行政责任
        'MR': bool,         # 民事责任
        'investigation': bool,  # 调查程序
        'hearing': bool,        # 听证程序
        'exemption': bool,      # 免责程序
    },
}
```

## 五、文本范围规则

| 模块 | 输入范围 | 跨子页规则 |
|------|----------|------------|
| M（原心动机） | 主体行为描述 + 补充 | 合并所有子页 |
| E（伦理位阶） | 启动：全卷宗；取值：行为描述 | 取最高E值 |
| N（名分正当性） | 主体行为描述 | 取最劣N值 |
| Q（权变修正） | 触发词：行为描述；反向拦截：全卷宗 | 任一反向表述则Q=0 |
| CR/AR/MR | 全部卷宗文本 | 纯关键词扫描 |
