"""
电网模拟运行主程序
支持两种推演模式：
1. 无快照模式：从默认状态开始，按previous_events逐天推演到目标天数
2. 快照模式：从给定的状态快照开始，只推演当天的动作

优化说明：
- 统一使用 DianwangSystem 的 restore_historical_state() 方法恢复历史状态
- 统一使用 process_config_action() 方法处理配置动作
- 消除快照模式与非快照模式的冗余逻辑
"""
import json
from typing import Dict, Any, List, Tuple, Optional
try:
    from .power_grid_engine import DianwangSystem, LineMode, Policy, Event
except ImportError:
    from power_grid_engine import DianwangSystem, LineMode, Policy, Event


# ==================== 输入合法性检查模块 ====================

class ValidationError(Exception):
    """输入验证错误异常"""
    def __init__(self, message: str, path: str = "", details: List[str] = None):
        self.message = message
        self.path = path  # 错误发生的路径，如 "previous_events[0].actions[1].policy"
        self.details = details or []
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        msg = f"【输入验证错误】{self.message}"
        if self.path:
            msg += f"\n  位置: {self.path}"
        if self.details:
            msg += "\n  详情:"
            for detail in self.details:
                msg += f"\n    - {detail}"
        return msg


# 支持的动作类型
VALID_ACTION_TYPES = {'CFG', 'OBS'}

# 支持的政策ID
VALID_POLICY_IDS = {'P-101', 'P-205', 'P-301'}

# 支持的事件类型
VALID_EVENT_TYPES = {'E-TYPHOON', 'E-EARTHQUAKE'} #'E-HEATWAVE', 

# 支持的线路ID
VALID_LINE_IDS = {'L_AB', 'L_AC', 'L_BD', 'L_CD'}

# 支持的线路模式
VALID_LINE_MODES = {'PARALLEL', 'SERIES', 'OPEN', 'CHARGING'}

# 支持的电网ID
VALID_GRID_IDS = {'A', 'B', 'C', 'D'}

# 各事件类型的必要参数
EVENT_REQUIRED_PARAMS = {
    'E-TYPHOON': {
        'required': ['name', 'center', 'movement', 'radius', 'speed'],  # name, center, movement 推荐但非必须
        'param_types': {
            'name': str,
            'center': (list, tuple),  # [x, y]
            'movement': (list, tuple),  # [dx, dy]
            'radius': (int, float),
            'speed': (int, float)
        }
    },
    'E-EARTHQUAKE': {
        'required': ['epicenter', 'magnitude'], 
        'param_types': {
            'epicenter': (list, tuple),  # [x, y]
            'magnitude': (int, float)
        }
    }
}


def _validate_type(value: Any, expected_types: tuple, field_name: str, path: str) -> Optional[str]:
    """验证值的类型是否符合预期"""
    if not isinstance(expected_types, tuple):
        expected_types = (expected_types,)
    
    if not isinstance(value, expected_types):
        expected_str = ' 或 '.join([t.__name__ for t in expected_types])
        return f"字段 '{field_name}' 类型错误: 期望 {expected_str}，实际为 {type(value).__name__}"
    return None


def _validate_policy_action(policy_data: Dict, path: str) -> List[str]:
    """验证政策配置动作
    
    Args:
        policy_data: 政策数据字典
        path: 当前验证路径
    
    Returns:
        错误信息列表
    """
    errors = []
    
    # 检查必要字段 id
    if 'id' not in policy_data:
        errors.append(f"缺少必要字段 'id'")
    else:
        policy_id = policy_data['id']
        if not isinstance(policy_id, str):
            errors.append(f"'id' 必须是字符串类型，实际为 {type(policy_id).__name__}")
        elif policy_id not in VALID_POLICY_IDS:
            errors.append(f"无效的政策ID '{policy_id}'，支持的政策ID: {', '.join(sorted(VALID_POLICY_IDS))}")
    
    # 如果不是停止操作，检查 trigger_day
    if not policy_data.get('stop', False):
        if 'trigger_day' in policy_data:
            trigger_day = policy_data['trigger_day']
            if not isinstance(trigger_day, int):
                errors.append(f"'trigger_day' 必须是整数类型，实际为 {type(trigger_day).__name__}")
            elif trigger_day < 1:
                errors.append(f"'trigger_day' 必须大于等于1，实际值为 {trigger_day}")
    
    # 检查 params 类型
    if 'params' in policy_data:
        if not isinstance(policy_data['params'], dict):
            errors.append(f"'params' 必须是字典类型，实际为 {type(policy_data['params']).__name__}")
    
    return errors


def _validate_event_action(event_data: Dict, path: str) -> List[str]:
    """验证事件配置动作
    
    Args:
        event_data: 事件数据字典
        path: 当前验证路径
    
    Returns:
        错误信息列表
    """
    errors = []
    
    # 检查必要字段 type
    if 'type' not in event_data:
        errors.append(f"缺少必要字段 'type'")
        return errors  # 无法继续验证
    
    event_type = event_data['type']
    if not isinstance(event_type, str):
        errors.append(f"'type' 必须是字符串类型，实际为 {type(event_type).__name__}")
        return errors
    
    if event_type not in VALID_EVENT_TYPES:
        if event_type in ['E-HEATWAVE', "E-COLDWAVE"]:
            errors.append(f"无效的事件类型 '{event_type}'，天气事件目前靠温度监控自动生效，无需注册")
        else:
            errors.append(f"无效的事件类型 '{event_type}'，支持的事件类型: {', '.join(sorted(VALID_EVENT_TYPES))}")
        return errors
    
    # 检查 trigger_day
    if 'trigger_day' in event_data:
        trigger_day = event_data['trigger_day']
        if not isinstance(trigger_day, int):
            errors.append(f"'trigger_day' 必须是整数类型，实际为 {type(trigger_day).__name__}")
        elif trigger_day < 1:
            errors.append(f"'trigger_day' 必须大于等于1，实际值为 {trigger_day}")
    
    # 检查 params 中的参数类型
    params = event_data.get('params', {})
    if not isinstance(params, dict):
        errors.append(f"'params' 必须是字典类型，实际为 {type(params).__name__}")
        return errors
    
    event_spec = EVENT_REQUIRED_PARAMS.get(event_type, {})
    required_params = event_spec.get('required', [])
    param_types = event_spec.get('param_types', {})
    
    # 检查必要参数是否缺失
    missing_params = []
    for required_param in required_params:
        if required_param not in params:
            missing_params.append(required_param)
    
    if missing_params:
        errors.append(
            f"事件类型 '{event_type}' 缺少必要参数: {', '.join(missing_params)}。"
            f"必须提供以下参数: {', '.join(required_params)}"
        )
    
    # 检查已提供参数的类型
    for param_name, param_value in params.items():
        if param_name in param_types:
            expected_type = param_types[param_name]
            err = _validate_type(param_value, expected_type, param_name, path)
            if err:
                errors.append(err)
            
            # 特殊检查：坐标格式
            if param_name in ['center', 'epicenter', 'movement']:
                if isinstance(param_value, (list, tuple)) and len(param_value) != 2:
                    errors.append(f"'{param_name}' 必须是包含2个元素的列表/元组 [x, y]，实际长度为 {len(param_value)}")
            
            # 特殊检查：震级范围
            if param_name == 'magnitude' and isinstance(param_value, (int, float)):
                if param_value < 0 or param_value > 10:
                    errors.append(f"'magnitude' 震级应在 0-10 范围内，实际值为 {param_value}")
    
    return errors


def _validate_line_mode_action(line_data: Dict, path: str) -> List[str]:
    """验证线路模式变更动作
    
    Args:
        line_data: 线路数据字典
        path: 当前验证路径
    
    Returns:
        错误信息列表
    """
    errors = []
    
    # 检查必要字段 line_id
    if 'line_id' not in line_data:
        errors.append(f"缺少必要字段 'line_id'")
    else:
        line_id = line_data['line_id']
        if not isinstance(line_id, str):
            errors.append(f"'line_id' 必须是字符串类型，实际为 {type(line_id).__name__}")
        elif line_id not in VALID_LINE_IDS:
            errors.append(f"无效的线路ID '{line_id}'，支持的线路ID: {', '.join(sorted(VALID_LINE_IDS))}")
    
    # 检查必要字段 mode
    if 'mode' not in line_data:
        errors.append(f"缺少必要字段 'mode'")
    else:
        mode = line_data['mode']
        if not isinstance(mode, str):
            errors.append(f"'mode' 必须是字符串类型，实际为 {type(mode).__name__}")
        elif mode not in VALID_LINE_MODES:
            errors.append(f"无效的线路模式 '{mode}'，支持的模式: {', '.join(sorted(VALID_LINE_MODES))}")
    
    return errors


def _validate_grid_island_action(grid_data: Dict, path: str) -> List[str]:
    """验证电网孤岛状态动作
    
    Args:
        grid_data: 电网数据字典
        path: 当前验证路径
    
    Returns:
        错误信息列表
    """
    errors = []
    
    # 检查必要字段 grid_id
    if 'grid_id' not in grid_data:
        errors.append(f"缺少必要字段 'grid_id'")
    else:
        grid_id = grid_data['grid_id']
        if not isinstance(grid_id, str):
            errors.append(f"'grid_id' 必须是字符串类型，实际为 {type(grid_id).__name__}")
        elif grid_id not in VALID_GRID_IDS:
            errors.append(f"无效的电网ID '{grid_id}'，支持的电网ID: {', '.join(sorted(VALID_GRID_IDS))}")
    
    # 检查必要字段 is_island
    if 'is_island' not in grid_data:
        errors.append(f"缺少必要字段 'is_island'")
    else:
        is_island = grid_data['is_island']
        if not isinstance(is_island, bool):
            errors.append(f"'is_island' 必须是布尔类型，实际为 {type(is_island).__name__}")
    
    return errors


def _validate_terrain_change_action(terrain_data: Dict, path: str) -> List[str]:
    """验证地形变更动作
    
    Args:
        terrain_data: 地形数据字典
        path: 当前验证路径
    
    Returns:
        错误信息列表
    """
    errors = []
    
    # 检查必要字段 zone_id
    if 'zone_id' not in terrain_data:
        errors.append(f"缺少必要字段 'zone_id'")
    else:
        zone_id = terrain_data['zone_id']
        if not isinstance(zone_id, str):
            errors.append(f"'zone_id' 必须是字符串类型，实际为 {type(zone_id).__name__}")
    
    # 检查必要字段 resistance
    if 'resistance' not in terrain_data:
        errors.append(f"缺少必要字段 'resistance'")
    else:
        resistance = terrain_data['resistance']
        if not isinstance(resistance, (int, float)):
            errors.append(f"'resistance' 必须是数值类型，实际为 {type(resistance).__name__}")
        elif resistance < 0:
            errors.append(f"'resistance' 阻力系数不能为负数，实际值为 {resistance}")
    
    return errors


def _validate_grid_pumping_action(pump_data: Dict, path: str) -> List[str]:
    """验证电网抽水模式动作
    
    Args:
        pump_data: 抽水数据字典
        path: 当前验证路径
    
    Returns:
        错误信息列表
    """
    errors = []
    
    # 检查 grid_id（可选，默认为 B）
    if 'grid_id' in pump_data:
        grid_id = pump_data['grid_id']
        if not isinstance(grid_id, str):
            errors.append(f"'grid_id' 必须是字符串类型，实际为 {type(grid_id).__name__}")
        elif grid_id not in VALID_GRID_IDS:
            errors.append(f"无效的电网ID '{grid_id}'，支持的电网ID: {', '.join(sorted(VALID_GRID_IDS))}")
    
    # 检查必要字段 is_pumping
    if 'is_pumping' not in pump_data:
        errors.append(f"缺少必要字段 'is_pumping'")
    else:
        is_pumping = pump_data['is_pumping']
        if not isinstance(is_pumping, bool):
            errors.append(f"'is_pumping' 必须是布尔类型，实际为 {type(is_pumping).__name__}")
    
    # 检查 pump_load（可选）
    if 'pump_load' in pump_data:
        pump_load = pump_data['pump_load']
        if not isinstance(pump_load, (int, float)):
            errors.append(f"'pump_load' 必须是数值类型，实际为 {type(pump_load).__name__}")
        elif pump_load < 0:
            errors.append(f"'pump_load' 抽水负荷不能为负数，实际值为 {pump_load}")
    
    return errors


def _validate_obs_action(action: Dict, path: str) -> List[str]:
    """验证观测类动作
    
    Args:
        action: OBS动作字典
        path: 当前验证路径
    
    Returns:
        错误信息列表
    """
    errors = []
    
    # 检查 time_advance
    if 'time_advance' in action:
        time_advance = action['time_advance']
        if not isinstance(time_advance, int):
            errors.append(f"'time_advance' 必须是整数类型，实际为 {type(time_advance).__name__}")
        elif time_advance < 1:
            errors.append(f"'time_advance' 必须大于等于1，实际值为 {time_advance}")
    
    # 检查 temperature_update
    if 'temperature_update' in action:
        temp = action['temperature_update']
        if not isinstance(temp, (int, float)):
            errors.append(f"'temperature_update' 必须是数值类型，实际为 {type(temp).__name__}")
    
    # 检查 temperature
    if 'temperature' in action:
        temp = action['temperature']
        if not isinstance(temp, (int, float)):
            errors.append(f"'temperature' 必须是数值类型，实际为 {type(temp).__name__}")
    
    return errors


def _validate_single_action(action: Dict, path: str) -> List[str]:
    """验证单个动作
    
    Args:
        action: 动作字典
        path: 当前验证路径
    
    Returns:
        错误信息列表
    """
    errors = []
    
    # 检查动作是否为字典
    if not isinstance(action, dict):
        errors.append(f"动作必须是字典类型，实际为 {type(action).__name__}")
        return errors
    
    # 检查 type 字段
    if 'type' not in action:
        errors.append(f"缺少必要字段 'type'")
        return errors
    
    action_type = action['type']
    if action_type not in VALID_ACTION_TYPES:
        errors.append(f"无效的动作类型 '{action_type}'，支持的类型: {', '.join(sorted(VALID_ACTION_TYPES))}")
        return errors
    
    # 根据动作类型进行具体验证
    if action_type == 'CFG':
        # 检查是否有至少一个配置子类型
        cfg_keys = {'policy', 'event', 'line_mode', 'grid_island', 'terrain_change', 'grid_pumping'}
        found_keys = cfg_keys.intersection(action.keys())
        
        if not found_keys:
            errors.append(f"CFG 动作缺少配置内容，应包含以下之一: {', '.join(sorted(cfg_keys))}")
        elif len(found_keys) > 1:
            # 一个CFG动作只应包含一种配置
            errors.append(f"CFG 动作包含多个配置类型 {found_keys}，建议每个动作只包含一种配置")
        
        # 验证各子类型
        if 'policy' in action:
            errors.extend(_validate_policy_action(action['policy'], f"{path}.policy"))
        if 'event' in action:
            errors.extend(_validate_event_action(action['event'], f"{path}.event"))
        if 'line_mode' in action:
            errors.extend(_validate_line_mode_action(action['line_mode'], f"{path}.line_mode"))
        if 'grid_island' in action:
            errors.extend(_validate_grid_island_action(action['grid_island'], f"{path}.grid_island"))
        if 'terrain_change' in action:
            errors.extend(_validate_terrain_change_action(action['terrain_change'], f"{path}.terrain_change"))
        if 'grid_pumping' in action:
            errors.extend(_validate_grid_pumping_action(action['grid_pumping'], f"{path}.grid_pumping"))
    
    elif action_type == 'OBS':
        errors.extend(_validate_obs_action(action, path))
    
    return errors


def _validate_actions_list(actions: List, path: str) -> List[Tuple[str, List[str]]]:
    """验证动作列表
    
    Args:
        actions: 动作列表
        path: 当前验证路径
    
    Returns:
        (路径, 错误列表) 的列表
    """
    all_errors = []
    
    if not isinstance(actions, list):
        all_errors.append((path, [f"'actions' 必须是列表类型，实际为 {type(actions).__name__}"]))
        return all_errors
    
    for i, action in enumerate(actions):
        action_path = f"{path}[{i}]"
        errors = _validate_single_action(action, action_path)
        if errors:
            all_errors.append((action_path, errors))
    
    return all_errors


def validate_test_case(test_case: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """验证测试用例输入的合法性
    
    Args:
        test_case: 测试用例字典
    
    Returns:
        (是否有效, 错误信息列表)
    """
    all_errors = []
    
    # 检查根字典类型
    if not isinstance(test_case, dict):
        return False, [f"测试用例必须是字典类型，实际为 {type(test_case).__name__}"]
    
    # 1. 验证 current_action（必选）
    if 'current_action' not in test_case:
        all_errors.append("缺少必选字段 'current_action'")
    else:
        current_action = test_case['current_action']
        if not isinstance(current_action, dict):
            all_errors.append(f"'current_action' 必须是字典类型，实际为 {type(current_action).__name__}")
        else:
            # 检查 t 字段
            if 't' not in current_action:
                all_errors.append("'current_action' 缺少必要字段 't' (目标推演天数)")
            else:
                t = current_action['t']
                if not isinstance(t, int):
                    all_errors.append(f"'current_action.t' 必须是整数类型，实际为 {type(t).__name__}")
                elif t < 1:
                    all_errors.append(f"'current_action.t' 必须大于等于1，实际值为 {t}")
            
            # 验证 actions
            if 'actions' in current_action:
                action_errors = _validate_actions_list(current_action['actions'], 'current_action.actions')
                for path, errors in action_errors:
                    for err in errors:
                        all_errors.append(f"[{path}] {err}")
    
    # 2. 验证 previous_events（可选）
    if 'previous_events' in test_case:
        previous_events = test_case['previous_events']
        if not isinstance(previous_events, list):
            all_errors.append(f"'previous_events' 必须是列表类型，实际为 {type(previous_events).__name__}")
        else:
            for i, event in enumerate(previous_events):
                event_path = f"previous_events[{i}]"
                
                if not isinstance(event, dict):
                    all_errors.append(f"[{event_path}] 事件必须是字典类型，实际为 {type(event).__name__}")
                    continue
                
                # 检查 t 字段
                if 't' not in event:
                    all_errors.append(f"[{event_path}] 缺少必要字段 't' (事件发生天数)")
                else:
                    t = event['t']
                    if not isinstance(t, int):
                        all_errors.append(f"[{event_path}.t] 必须是整数类型，实际为 {type(t).__name__}")
                    elif t < 1:
                        all_errors.append(f"[{event_path}.t] 必须大于等于1，实际值为 {t}")
                
                # 验证 actions
                if 'actions' in event:
                    action_errors = _validate_actions_list(event['actions'], f"{event_path}.actions")
                    for path, errors in action_errors:
                        for err in errors:
                            all_errors.append(f"[{path}] {err}")
    
    # 3. 验证 current_state（可选）
    if 'current_state' in test_case:
        current_state = test_case['current_state']
        if not isinstance(current_state, dict):
            all_errors.append(f"'current_state' 必须是字典类型，实际为 {type(current_state).__name__}")
        else:
            # 检查 t 字段
            if 't' in current_state:
                t = current_state['t']
                if not isinstance(t, int):
                    all_errors.append(f"'current_state.t' 必须是整数类型，实际为 {type(t).__name__}")
                elif t < 0:
                    all_errors.append(f"'current_state.t' 不能为负数，实际值为 {t}")
            
            # 检查 grids
            if 'grids' in current_state:
                grids = current_state['grids']
                if not isinstance(grids, dict):
                    all_errors.append(f"'current_state.grids' 必须是字典类型")
                else:
                    for grid_id in grids.keys():
                        if grid_id not in VALID_GRID_IDS:
                            all_errors.append(f"'current_state.grids' 中存在无效的电网ID '{grid_id}'")
            
            # 检查 lines
            if 'lines' in current_state:
                lines = current_state['lines']
                if not isinstance(lines, dict):
                    all_errors.append(f"'current_state.lines' 必须是字典类型")
                else:
                    for line_id in lines.keys():
                        if line_id not in VALID_LINE_IDS:
                            all_errors.append(f"'current_state.lines' 中存在无效的线路ID '{line_id}'")
    
    is_valid = len(all_errors) == 0
    return is_valid, all_errors


def print_validation_result(is_valid: bool, errors: List[str]):
    """打印验证结果
    
    Args:
        is_valid: 是否有效
        errors: 错误列表
    """
   
    if is_valid:
         output = "【输入验证】✓ 测试用例格式正确"
    else:

        output = "【输入验证】✗ 发现以下问题:\n"
        for i, err in enumerate(errors, 1):
            output += f"  {i}. {err}\n"
        output += "\n"
    return output


# ==================== 输入合法性检查模块 END ====================


def _extract_temperature_from_actions(actions: List[Dict]) -> float:
    """从动作列表中提取温度更新
    
    Args:
        actions: 动作列表
    
    Returns:
        提取到的温度值，如果没有则返回None
    """
    temp = None
    for act in actions:
        if act.get('type') == 'OBS':
            if 'temperature_update' in act:
                temp = act['temperature_update']
            elif 'temperature' in act:
                temp = act['temperature']
    return temp


def _process_day_actions(system: DianwangSystem, actions: List[Dict]):
    """处理某一天的所有动作
    
    统一处理OBS（温度更新）和CFG（配置变更）动作
    
    Args:
        system: 电网系统实例
        actions: 动作列表
    """
    # 1. 先处理温度更新（OBS类型）
    temp = _extract_temperature_from_actions(actions)
    if temp is not None:
        system.global_temp = temp
    
    # 2. 抽水状态自动重置：若当天未显式指定继续抽水，则自动退出抽水模式
    has_pumping_action = any(
        act.get('type') == 'CFG' and 'grid_pumping' in act
        for act in actions
    )
    if not has_pumping_action:
        for gid, g in system.grids.items():
            if g.is_pumping:
                system.process_config_action({
                    'type': 'CFG',
                    'grid_pumping': {'grid_id': gid, 'is_pumping': False}
                })
    
    # 3. 处理配置动作（CFG类型）
    for act in actions:
        if act.get('type') == 'CFG':
            system.process_config_action(act)


def run_simulation_from_timeline(test_case: Dict[str, Any], include_daily_evolution: bool = True) -> str:
    """
    从测试用例运行模拟（优化版）
    
    设计思路：
    - 如果提供了 current_state（快照），则从快照状态开始推演（快照模式）
    - 如果没有提供 current_state，则从默认状态从 Day 1 开始逐天推演（无快照模式）
    
    优化点：
    - 统一使用 DianwangSystem 的方法处理政策/事件
    - 消除快照模式与非快照模式的代码冗余
    
    Args:
        test_case: 测试用例格式
            {
                'current_state': {         # 可选：状态快照（推演起点）
                    't': 4,
                    'grids': {...},
                    'lines': {...}
                },
                'previous_events': [       # 历史事件记录
                    {'t': 1, 'actions': [...]},
                    ...
                ],
                'current_action': {        # 当天请求
                    't': 5,
                    'actions': [...],
                    'user_input': '...'
                }
            }
        include_daily_evolution: 是否包含逐天推演过程
    
    Returns:
        运行报告字符串
    """
    # 1. 初始化系统
    system = DianwangSystem()
    
    # 2. 获取关键参数
    current_state = test_case.get('current_state', None)
    previous_events = test_case.get('previous_events', [])
    current_action = test_case.get('current_action', {})
    target_day = current_action.get('t', 1)
    
    # 3. 根据是否提供快照选择推演模式
    if current_state is not None and current_state.get('t', 0) > 0:
        # === 快照模式：从快照状态开始推演 ===
        snapshot_day = current_state.get('t', 0)
        
        # 加载状态快照（恢复电网物理状态，包括 temp_history）
        # 传入 previous_events 用于预计算坐标（当快照中没有提供坐标时）
        system.load_state(current_state, previous_events)
        
        # 恢复历史状态（注册政策/事件，标记已生效的为active）
        system.restore_historical_state(previous_events, snapshot_day)
        
        # 如果快照中没有 temp_history，从 previous_events 中恢复快照日及之前的温度历史
        if not system.temp_history:
            temp_by_day = {}
            for day_event in previous_events:
                day = day_event.get('t', 0)
                if day > 0 and day <= snapshot_day:
                    for action in day_event.get('actions', []):
                        if action.get('type') == 'OBS':
                            if 'temperature' in action:
                                temp_by_day[day] = action['temperature']
                            elif 'temperature_update' in action:
                                temp_by_day[day] = action['temperature_update']
            # 按天顺序添加温度到 temp_history（未告知的天沿用前一天温度，首天默认25°C）
            last_temp = 25.0
            for day in range(1, snapshot_day + 1):
                if day in temp_by_day:
                    last_temp = temp_by_day[day]
                system.temp_history.append(last_temp)
            # 同步 global_temp 为快照日最后已知温度
            system.global_temp = last_temp
        
        # 收集快照日之后的所有天的动作（按天组织）
        day_actions_map = {}
        
        # 从 previous_events 中收集快照日之后的动作
        for day_event in previous_events:
            day = day_event.get('t', 0)
            if day > snapshot_day:
                if day not in day_actions_map:
                    day_actions_map[day] = []
                day_actions_map[day].extend(day_event.get('actions', []))
        
        # 添加 current_action 的动作
        if current_action and target_day > 0:
            if target_day not in day_actions_map:
                day_actions_map[target_day] = []
            day_actions_map[target_day].extend(current_action.get('actions', []))
        
        # 从快照日的下一天开始，逐天推演到目标日
        for day in range(snapshot_day + 1, target_day + 1):
            actions = day_actions_map.get(day, [])
            
            # 处理当天的动作（设置温度、处理配置）
            _process_day_actions(system, actions)
            
            # 推演一天
            system.advance_days(1)
    else:
        # === 无快照模式：从默认状态开始逐天推演 ===
        
        # 按时间顺序收集所有天的事件
        all_day_actions = {}
        
        # 整理 previous_events
        for day_event in previous_events:
            day = day_event.get('t', 0)
            if day > 0:
                if day not in all_day_actions:
                    all_day_actions[day] = []
                all_day_actions[day].extend(day_event.get('actions', []))
        
        # 整理 current_action
        if current_action and target_day > 0:
            if target_day not in all_day_actions:
                all_day_actions[target_day] = []
            all_day_actions[target_day].extend(current_action.get('actions', []))
        
        # 从 Day 1 开始逐天推演
        for day in range(1, target_day + 1):
            actions = all_day_actions.get(day, [])
            
            # 处理当天的所有动作
            _process_day_actions(system, actions)
            
            # 推演一天
            system.advance_days(1)
    
    # 4. 生成报告
    report_parts = []
    
    if include_daily_evolution and len(system.daily_snapshots) > 0:
        evolution_report = system.generate_daily_report()
        report_parts.append(evolution_report)
    
    if len(system.daily_snapshots) > 0:
        final_report = system.generate_final_report()
        report_parts.append(final_report)
    else:
        report_parts.append("【运行评估报告】\n\n系统尚未执行任何推演步骤。\n")
    
    return "\n".join(report_parts)


def verified_dianwang(test_case, skip_validation: bool = False):
    """主函数
    
    Args:
        test_case: 测试用例
        skip_validation: 是否跳过输入验证（默认False）
    """
    # 输入合法性检查
    if not skip_validation:
        is_valid, errors = validate_test_case(test_case)
        output = print_validation_result(is_valid, errors)
        if not is_valid:
            return output  # 验证失败时返回None
    
    # 打印用例信息
    current_state = test_case.get('current_state', None)
    previous_events = test_case.get('previous_events', [])
    current_action = test_case.get('current_action', {})
    
    target_day = current_action.get('t', 1)
    
    reports = []
    reports.append(f"\n【测试用例配置】")
    
    if current_state is not None and current_state.get('t', 0) > 0:
        snapshot_day = current_state.get('t', 0)
        reports.append(f"  推演模式: 快照模式")
        reports.append(f"  状态快照: Day {snapshot_day} 24:00")
        reports.append(f"  推演目标: Day {target_day}")
        reports.append(f"  (只推演 Day {snapshot_day} → Day {target_day}，共 {target_day - snapshot_day} 天)")
        
        # 打印历史上下文
        # if previous_events:
        #     reports.append(f"\n【历史上下文 (Day 1 ~ Day {snapshot_day})】")
        #     for event in previous_events:
        #         desc = event.get('description', '无描述')
        #         status = "✓ 已发生" if event['t'] <= snapshot_day else "○ 待推演"
        #         reports.append(f"  Day {event['t']}: {desc} [{status}]")
    else:
        reports.append(f"  推演模式: 无快照模式（从默认状态开始）")
        reports.append(f"  推演目标: Day {target_day}")
        reports.append(f"  (从 Day 1 开始逐天推演到 Day {target_day})")
        
        # 打印事件时间线
        if previous_events:
            reports.append(f"\n【事件时间线】")
            for event in previous_events:
                desc = event.get('description', '无描述')
                reports.append(f"  Day {event['t']}: {desc}")
    
    # 打印当天请求
    if current_action:
        reports.append(f"\n【当天用户请求 (Day {target_day})】")
        user_input = current_action.get('user_input', '')
        if user_input:
            display_input = user_input[:80] + '...' if len(user_input) > 80 else user_input
            reports.append(f"  {display_input}")
        # 打印动作
        actions = current_action.get('actions', [])
        if actions:
            reports.append(f"  动作: {len(actions)} 个")
            for act in actions:
                if act.get('type') == 'CFG' and 'grid_pumping' in act:
                    reports.append(f"    - Grid B 抽水模式: {act['grid_pumping']['is_pumping']}")
                elif act.get('type') == 'OBS':
                    reports.append(f"    - 推进 {act.get('time_advance', 1)} 天")
    
    reports.append(f"\n{'='*80}")
    reports.append("【运行结果】\n")
    
    # 运行模拟
    report = run_simulation_from_timeline(test_case, include_daily_evolution=True)
    reports.append(report)
    return '\n'.join(reports)


if __name__ == "__main__":
    # usage: python -m code_simulation_engines.spatial_multi_rule.power_grid_operation.run_engine [question id], e.g. grid_1
    import ast
    import json
    import sys
    from pathlib import Path

    qid = sys.argv[1] if len(sys.argv) > 1 else "grid_1"
    with open(Path(__file__).resolve().parents[2] / "structured_inputs.jsonl", encoding="utf-8") as f:
        rows = {r["id"]: r for r in map(json.loads, f)}
    raw = rows[qid]["structured_input"]
    try:
        case = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        case = json.loads(raw)
    print(verified_dianwang(case))
