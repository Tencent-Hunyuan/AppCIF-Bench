try:
    from .spatiotemporal_trade_optimizer import PsychedelicCity
    from .event_catalog import EVENTS_DB
except ImportError:
    from spatiotemporal_trade_optimizer import PsychedelicCity
    from event_catalog import EVENTS_DB
import math

def format_coords(pos, k=None, t=None):
    """格式化坐标输出（4维：x, y, z, t）"""
    if t is not None:
        return f"({pos[0]}, {pos[1]}, {pos[2]}, {t})"
    return f"({pos[0]}, {pos[1]}, {pos[2]}, 0)"

def format_path_string(path, t=0):
    """
    将路径点列表格式化为 System.md 要求的格式（4维）
    例如: (0,0,0,0) -> (100,100,100,0) -> (200,200,200,0)
    """
    return " → ".join([f"({p[0]}, {p[1]}, {p[2]}, {t})" for p in path])

def trace_manhattan_move(start_pos, end_pos, start_k):
    """
    分解曼哈顿移动，返回详细步骤字符串列表
    """
    moves = []
    curr = list(start_pos)
    
    dims = ['X', 'Y', 'Z']
    
    for i in range(3):
        if start_pos[i] != end_pos[i]:
            prev_coords = f"({curr[0]}, {curr[1]}, {curr[2]})"
            curr[i] = end_pos[i]
            new_coords = f"({curr[0]}, {curr[1]}, {curr[2]})"
            moves.append(f"{prev_coords} → 沿{dims[i]}轴 → {new_coords}")
            
    return moves

# 按照时间顺序排序path
# # 只把Buy动作插入到合适位置，其他动作保持原始顺序
# # Buy必须在至少一次穿越(KW/SW)之后，且buy_k >= 穿越后的k
# # Buy必须在MoveToSell之前（买入必须在卖出前）
# # Buy只能插到原始位置及之前的位置
# def insert_buy_action(path):
# # 记录Buy动作在原始列表中的位置（作为插入位置的上限）
# buy_original_indices = {}
# for i, action in enumerate(path):
#     if action['action'] == 'Buy':
#         buy_original_indices[id(action)] = i

# # 分离Buy动作和其他动作
# buy_actions = [a for a in path if a['action'] == 'Buy']
# other_actions = [a for a in path if a['action'] != 'Buy']

# # 如果没有Buy动作，直接返回原始路径
# if not buy_actions:
#     return other_actions

# # 获取穿越动作后的时间点（穿越完成后的k值）
# def get_jump_end_time(action):
#     """获取穿越动作完成后的k值"""
#     if action['action'] in ['KW', 'SW']:
#         return action['k_arrive'] + action.get('dk', 0)
#     return None

# # 获取非Buy动作的时间点（用于确定Buy的插入位置）
# def get_action_time(action):
#     if action['action'] in ['KW', 'SW']:
#         return action['k_arrive'] + action.get('dk', 0)
#     elif 'k_arrive' in action:
#         return action['k_arrive'] + action.get('dk', 0)
#     elif 'k_start' in action:
#         return action['k_start']
#     else:
#         return float('inf')

# # 将每个Buy动作插入到合适的位置
# result = other_actions.copy()
# for buy in buy_actions:
#     buy_k = buy['k']
    
#     # 获取Buy在原始列表中的位置（作为插入位置的上限）
#     # 在other_actions中，原始位置之前有多少个非Buy动作，就是最大可插入位置
#     original_idx = buy_original_indices.get(id(buy), len(path))
#     # 计算原始位置之前有多少个非Buy动作
#     max_insert_idx = sum(1 for i, a in enumerate(path) if i < original_idx and a['action'] != 'Buy')
    
#     # 找到合适的插入位置：
#     # 1. 必须在至少一次穿越(KW/SW)之后
#     # 2. buy_k >= 穿越后的k
#     # 3. 必须在MoveToSell之前（买入必须在卖出前）
#     # 4. 在满足条件的位置中，插入到第一个时间点 > buy_k 的动作之前
#     # 5. 不能超过原始位置（max_insert_idx）
    
#     insert_idx = max_insert_idx  # 默认插入到原始位置
#     found_valid_jump = False  # 是否找到了满足 buy_k >= 穿越后k 的穿越
    
#     # 先找到MoveToSell的位置，Buy必须在它之前
#     move_to_sell_idx = len(result)
#     for i, action in enumerate(result):
#         if action['action'] == 'MoveToSell':
#             move_to_sell_idx = i
#             break
    
#     for i, action in enumerate(result):
#         # 不能超过原始位置上限
#         if i > max_insert_idx:
#             break
        
#         # 检查是否是穿越动作
#         if action['action'] in ['KW', 'SW']:
#             jump_end_k = get_jump_end_time(action)
#             # 检查 buy_k 是否 >= 这次穿越后的 k
#             if jump_end_k is not None and buy_k >= jump_end_k:
#                 found_valid_jump = True
        
#         # 只有在找到满足条件的穿越之后，才考虑插入位置
#         if found_valid_jump:
#             # 如果遇到MoveToSell，必须在它之前插入
#             if action['action'] == 'MoveToSell':
#                 insert_idx = i
#                 break
            
#             action_time = get_action_time(action)
#             # 找到第一个时间点 > buy_k 的位置，在其前面插入
#             if action_time > buy_k:
#                 insert_idx = i
#                 break
    
#     # 如果没有找到满足条件的穿越，则插入到最后一个穿越之后（但不超过原始位置）
#     if not found_valid_jump:
#         # 找到最后一个穿越动作的位置（不超过max_insert_idx）
#         last_jump_idx = -1
#         for i, action in enumerate(result):
#             if i > max_insert_idx:
#                 break
#             if action['action'] in ['KW', 'SW']:
#                 last_jump_idx = i
#         if last_jump_idx >= 0:
#             insert_idx = min(last_jump_idx + 1, max_insert_idx)
    
#     # 确保Buy在MoveToSell之前
#     if insert_idx > move_to_sell_idx:
#         insert_idx = move_to_sell_idx
    
#     # 最终确保不超过原始位置上限
#     insert_idx = min(insert_idx, max_insert_idx)
    
#     result.insert(insert_idx, buy)

# return result

def insert_buy_action(path):
    """
    将 Buy 动作插入到正确的时间位置，确保时间线连贯。
    
    核心逻辑：
    1. 买入必须在至少一次穿越之后（这是交易规则）
    2. 通过模拟时间线，找到满足以下条件的插入位置：
       - 前一个动作结束后的时间 <= buy_k（可以等待到 buy_k）
       - 插入后，后续动作的时间仍然合理（buy_k <= 后续动作的开始时间）
    
    例如：
    - 第一次 SW1: k_arrive=63, dk=-30 → 穿越后 k=33
    - 第二次 SW1: k_arrive=35, dk=-30 → 穿越后 k=5
    - Buy k=35, MoveToSell k_start=5
    - 第一次穿越后 k=33，可以等待到 k=35 买入
    - 买入后 k=35，可以到达第二次穿越的 k_arrive=35
    - 第二次穿越后 k=5，满足 MoveToSell k_start=5
    """
    # 1. 预处理：提取 Buy 动作，保留其他动作的顺序
    buy_actions = []
    others = []
    
    for i, action in enumerate(path):
        if action['action'] == 'Buy':
            buy_actions.append(action)
        else:
            others.append(action)

    # 如果没有 Buy 动作，直接返回
    if not buy_actions:
        return path

    # 辅助函数：获取动作结束后的时间 k
    def get_time_after_action(act):
        if act['action'] in ['KW', 'SW']:
            return act['k_arrive'] + act.get('dk', 0)
        elif act['action'] == 'MoveToSell':
            return act['k_end']
        return None
    
    # 辅助函数：获取动作开始需要的时间 k（到达时间）
    def get_time_needed_for_action(act):
        if act['action'] in ['KW', 'SW']:
            return act['k_arrive']
        elif act['action'] == 'MoveToSell':
            return act['k_start']
        return None

    # 2. 对每个 Buy，通过时间线模拟找到正确的插入位置
    result = others.copy()
    
    for buy_act in buy_actions:
        buy_k = buy_act['k']
        
        # 找到第一个穿越的索引（买入必须在第一次穿越之后）
        first_jump_idx = -1
        for i, action in enumerate(result):
            if action['action'] in ['KW', 'SW']:
                first_jump_idx = i
                break
        
        # 如果没有穿越，无法买入（理论上不应该发生）
        if first_jump_idx < 0:
            result.append(buy_act)
            continue
        
        # 从第一个穿越之后开始，寻找合适的插入位置
        insert_idx = first_jump_idx + 1  # 默认插入到第一个穿越之后
        
        for i in range(first_jump_idx + 1, len(result) + 1):
            # 获取前一个动作结束后的时间
            prev_action = result[i - 1]
            time_after_prev = get_time_after_action(prev_action)
            
            if time_after_prev is None:
                continue
            
            # 条件1: 前一个动作结束后的时间 <= buy_k（可以等待到 buy_k）
            if time_after_prev > buy_k:
                continue
            
            # 条件2: 检查插入后，后续动作是否仍然合理
            if i < len(result):
                next_action = result[i]
                time_needed = get_time_needed_for_action(next_action)
                
                if time_needed is not None and buy_k <= time_needed:
                    # 找到合适的位置
                    insert_idx = i
                    break
            else:
                # 没有后续动作，可以插入到末尾
                insert_idx = i
                break
        
        # 确保不超过 MoveToSell 的位置（Buy 必须在 Sell 之前）
        for i, action in enumerate(result):
            if action['action'] == 'MoveToSell':
                if insert_idx > i:
                    insert_idx = i
                break
        
        # 插入 Buy 动作
        result.insert(insert_idx, buy_act)

    return result

def save_to_excel_with_multiple_sheets(file_path, data_dict):
    """Export diagnostic caches when explicitly requested by a developer.

    This optional helper is deliberately lazy-imported so the executable
    ground-truth engine itself has no third-party runtime dependency.
    """
    try:
        import openpyxl
        import pandas as pd
        from openpyxl.utils.dataframe import dataframe_to_rows
    except ImportError as exc:
        raise RuntimeError(
            "Intermediate Excel export requires `pandas` and `openpyxl`."
        ) from exc
    """
    将不同数据保存到Excel的多个sheet中
    
    Args:
        file_path: 保存的Excel文件路径（如: 'data.xlsx'）
    """
    
    # 1. 创建工作簿对象
    wb = openpyxl.Workbook()
    
    # 删除默认创建的Sheet（可选，根据需要）
    wb.remove(wb.active)
    
    # 2. 准备测试数据（实际使用时替换为你的真实数据）
    # 数据1：学生信息
    for sheet_name, data in data_dict.items():
        if sheet_name != 'ik_cache':
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame({'ik':data})
        # pandas 2.1+ 移除了 DataFrame.applymap（改名为 DataFrame.map）。
        # 此处仅为 Excel 导出的格式化，与核心求解逻辑无关。
        _elementwise = getattr(df, "map", None) or df.applymap
        df = _elementwise(lambda x: f'{x}' if isinstance(x, tuple) else x)
        ws = wb.create_sheet(title=sheet_name)
        for r in dataframe_to_rows(df, index=True, header=True):
            ws.append(r)
    
    
    # 6. 保存Excel文件
    wb.save(file_path)
    print(f"Excel文件已成功保存到: {file_path}")

def verified_trade(test_case, save_intermediate: bool = False, output_path: str = None):
    """Run the executable trade simulator for one structured test case.

    Intermediate spreadsheets are disabled by default so evaluation does not
    create side-effect files. They can be enabled explicitly for debugging.
    """
    current_k = test_case['current_k']
    current_t = test_case['current_t']
    current_pos = test_case['current_pos']
    initial_assets = test_case['initial_assets']
    max_jumps = test_case['max_jumps']
    max_time_leap = test_case['max_time_leap']
    event_configs = test_case['event_configs']
    specific_speed_limit = test_case['specific_speed_limit'] if 'specific_speed_limit' in test_case else None
    item_limit = test_case.get('item_limit', None)  # 获取商品限定范围，默认为None表示搜索全部商品
    jump_type_limit = test_case.get('jump_type_limit', None)  # 获取穿越类型限制，如['SW']或['KW']，默认为None表示搜索全部类型
    trade_times_limit = test_case.get('trade_times_limit', 1)  # 获取交易次数限制，默认为1次（单次交易）
    trade_mode = test_case.get('trade_mode', 'strict')  # 交易模式: 'strict'(严格模式) 或 'flexible'(灵活模式，支持多商品持仓)

    events_list = []
    unknown_events = [name for name, _ in event_configs if name not in EVENTS_DB]
    if unknown_events:
        print(f"[WARNING] 以下event不在EVENTS_DB中，将被跳过: {unknown_events}")
    for name, start_k in event_configs:
        if name in EVENTS_DB:
            e = EVENTS_DB[name].copy()
            e['start_k'] = start_k
            events_list.append(e)
    # 3. Initialize City
    city = PsychedelicCity(current_k, current_pos, events_list, initial_assets, max_time_leap, specific_speed_limit, item_limit, jump_type_limit)
    inter_results = {'price_cache': city.price_cache, 'ik_cache': city.ik_cache, 'kw_pos_cache': city.kw_pos_cache}
    if save_intermediate:
        save_to_excel_with_multiple_sheets(
            output_path or './intermediate_results.xlsx', inter_results
        )
    # p1 = (232, 220, 200)
    # p2 = (197,197,197)
    # dist, detour = city.get_distance_with_detour(p1, p2, current_k)
    # report.append(dist, detour)
    # return
    # 4. Optimize
    # 根据trade_times_limit和trade_mode选择优化策略
    if trade_times_limit == 1:
        # 单次交易，使用原有的optimize函数
        best_plan, all_plans, trends = city.optimize(max_time_leap=max_time_leap, max_jumps=max_jumps)
    elif trade_mode == 'flexible':
        # 灵活多次交易模式：支持同时持有多个商品，首次穿越后可自由进行买卖和穿越
        multi_result = city.optimize_flexible_trade(max_time_leap=max_time_leap, max_jumps=max_jumps, trade_times_limit=trade_times_limit)
        trends = multi_result['trends']
        
        # 将灵活交易结果转换为兼容格式
        if multi_result['trade_count'] > 0:
            all_trades = multi_result['trades']
            total_profit = multi_result['total_profit']
            stats = multi_result['stats']
            
            # 构建best_plan（综合信息）
            best_plan = {
                'profit': total_profit,
                'item': '多商品组合(灵活)',
                'trades': all_trades,
                'trade_count': multi_result['trade_count'],
                'fuel': stats['total_fuel'],
                'tax': stats['total_tax'],
                'jump_count': stats['total_jumps_used'],
                'buy_k': all_trades[0]['buy_k'] if all_trades else 0,
                'sell_k': all_trades[-1]['sell_k'] if all_trades else 0,
                'buy_lvl': all_trades[0]['buy_lvl'] if all_trades else 0,
                'sell_lvl': all_trades[-1]['sell_lvl'] if all_trades else 0,
                'path': [],
                'full_path': multi_result.get('full_path', []),
                'is_multi_trade': True,
                'trade_mode': 'flexible'
            }
            
            all_plans = {}
            for idx, trade in enumerate(all_trades):
                plan_key = f"Trade{idx+1}_{trade['item']}"
                all_plans[plan_key] = trade
        else:
            best_plan = None
            all_plans = {item: {'profit': -float('inf')} for item in city.destinations}
    else:
        # 严格多次交易模式：每次交易必须先穿越，只能持有一个商品
        multi_result = city.optimize_multi_trade(max_time_leap=max_time_leap, max_jumps=max_jumps, trade_times_limit=trade_times_limit)
        trends = multi_result['trends']
        
        # 将多次交易结果转换为兼容格式
        if multi_result['trade_count'] > 0:
            # 合并所有交易为一个综合方案
            all_trades = multi_result['trades']
            total_profit = multi_result['total_profit']
            total_fuel = sum(t['fuel'] for t in all_trades)
            total_tax = sum(t['tax'] for t in all_trades)
            total_jumps = sum(t['jumps_used'] for t in all_trades)
            
            # 构建best_plan（综合信息）
            best_plan = {
                'profit': total_profit,
                'item': '多商品组合',
                'trades': all_trades,  # 包含所有交易详情
                'trade_count': multi_result['trade_count'],
                'fuel': total_fuel,
                'tax': total_tax,
                'jump_count': total_jumps,
                'buy_k': all_trades[0]['buy_k'] if all_trades else 0,
                'sell_k': all_trades[-1]['sell_k'] if all_trades else 0,
                'buy_lvl': all_trades[0]['buy_lvl'] if all_trades else 0,
                'sell_lvl': all_trades[-1]['sell_lvl'] if all_trades else 0,
                'path': [],  # 多次交易的path在trades中分别存储
                'is_multi_trade': True,
                'trade_mode': 'strict'
            }
            
            # 为兼容性构建all_plans（每个交易单独列出）
            all_plans = {}
            for idx, trade in enumerate(all_trades):
                plan_key = f"Trade{idx+1}_{trade['item']}"
                all_plans[plan_key] = trade
        else:
            best_plan = None
            all_plans = {item: {'profit': -float('inf')} for item in city.destinations}
    
    
    # 5. Output Market Trends
    report = []

    report.append("\n=== 市场趋势扫描 (价格窗口分析) ===")
    for item, data in trends.items():
        min_p = data['min_lvl']
        max_p = data['max_lvl']
        buy_k_list = [str(x[0]) for x in data['buy_windows'][:3]]
        sell_k_list = [str(x[0]) for x in data['sell_windows'][:3]]
        report.append(f"商品 {item}: 最低价 Lv{min_p} (k={','.join(buy_k_list)}...) | 最高价 Lv{max_p} (k={','.join(sell_k_list)}...)")
    report.append("-" * 50)

    # 6. Output Plans
    report.append("\n=== 多跳路径规划报告 ===")
    
    item_names = {'SM': '结构物质', 'CB': '信息流量', 'NL': '合成营养液', 'HL': '居住许可'}
    dest_names = {'SM': '居民区', 'CB': '科技区', 'NL': 'CBD区', 'HL': '政府区'}
    
    # 检查是否为多次交易模式
    # if best_plan and best_plan.get('is_multi_trade'):
    #     # ========== 多次交易报告输出 ==========
    #     report.append(f"\n{'='*60}")
    #     report.append(f"📊 多次交易优化结果 (共{best_plan['trade_count']}笔交易)")
    #     report.append(f"{'='*60}")
        
    #     all_trades = best_plan['trades']
    #     curr_t = current_t  # 跟踪t值
        
    #     for trade_idx, trade in enumerate(all_trades):
    #         item = trade['item']
    #         item_cn = item_names.get(item, item)
    #         dest_cn = dest_names.get(item, '目的地')
            
    #         report.append(f"\n{'─'*50}")
    #         report.append(f"【第{trade_idx + 1}笔交易】商品: {item}({item_cn})")
    #         report.append(f"{'─'*50}")
            
    #         # 方案概要
    #         report.append(f"\n  【方案概要】")
    #         report.append(f"    • 起始位置: {trade['start_pos']}, 起始时间: k={trade['start_k']}")
    #         report.append(f"    • 买入时间: k={trade['buy_k']} (价格等级 Lv{trade['buy_lvl']})")
    #         report.append(f"    • 卖出时间: k={trade['sell_k']} (价格等级 Lv{trade['sell_lvl']})")
    #         report.append(f"    • 穿越次数: {trade['jumps_used']} 次")
    #         report.append(f"    • 本次利润: {trade['profit']} 迷幻币")
            
    #         # 详细行动步骤
    #         report.append(f"\n  【详细行动步骤】")
            
    #         sorted_path = insert_buy_action(trade['path'])
    #         curr_p = trade['start_pos']
    #         curr_k = trade['start_k']
    #         step_num = 0
            
    #         for idx, step in enumerate(sorted_path):
    #             action = step['action']
                
    #             # 1. 计算此动作的计划开始时间
    #             target_start_k = curr_k
    #             if action == 'Buy':
    #                 target_start_k = step['k']
    #             elif action == 'MoveToSell':
    #                 target_start_k = step['k_start']
    #             elif action in ['KW', 'SW']:
    #                 fuel = step.get('fuel', 0)
    #                 travel_time = math.ceil(fuel / 10)
    #                 target_start_k = step['k_arrive'] - travel_time 

    #             # 2. 插入动态等待
    #             wait_needed = target_start_k - curr_k
    #             if wait_needed > 0:
    #                 step_num += 1
    #                 next_k = curr_k + wait_needed
    #                 report.append(f"\n    {step_num}. **等待{wait_needed}旬** (k={curr_k}→k={next_k})")
    #                 curr_k = next_k

    #             # 处理 Buy 动作
    #             if action == 'Buy':
    #                 buy_k = step['k']
    #                 if curr_k != buy_k:
    #                     step_num += 1
    #                     report.append(f"\n    {step_num}. **等待{buy_k - curr_k}旬到最佳买入时间** (k={curr_k}→k={buy_k})")
    #                     curr_k = buy_k
                    
    #                 step_num += 1
    #                 buy_cost = 10 * city.base_prices[item] * trade['buy_lvl']
    #                 report.append(f"\n    {step_num}. **买入{item_cn}({item})** (k={curr_k})")
    #                 report.append(f"       - 价格等级: Lv{trade['buy_lvl']}")
    #                 report.append(f"       - 买入成本: {buy_cost} 迷幻币")
    #                 continue
                
    #             # 处理移动
    #             target_pos = None
    #             target_name = ""
    #             if action == 'SW':
    #                 target_pos = city.sw_config[step['id']]['pos']
    #                 target_name = f"SW{step['id']}"
    #             elif action == 'KW':
    #                 target_pos = step.get('pos_before')
    #                 target_name = f"KW{step['id']}"
    #             elif action == 'MoveToSell':
    #                 target_pos = city.destinations[item]
    #                 target_name = dest_cn
                
    #             if target_pos is None:
    #                 continue
                
    #             # 计算路径信息
    #             detour = step.get('detour')
    #             fuel_cost = step.get('fuel', 0)
    #             travel_time = math.ceil(fuel_cost / 10)
    #             arrival_k = step.get('k_arrive') if 'k_arrive' in step else (step.get('k_end') - step.get('wait', 0))
                
    #             # 输出移动步骤
    #             if curr_p != target_pos:
    #                 step_num += 1
    #                 report.append(f"\n    {step_num}. **移动至{target_name}** (k={curr_k}→k={arrival_k})")
    #                 report.append(f"       - 燃料消耗: {fuel_cost} 迷幻币")
                
    #             curr_p = target_pos
    #             curr_k = arrival_k
                
    #             # 处理穿越
    #             if action in ['SW', 'KW']:
    #                 tax = step['tax']
    #                 dk = step.get('dk', 0)
    #                 next_k = arrival_k + dk
                    
    #                 next_pos_jump = curr_p
    #                 if action == 'KW':
    #                     kw_id = step['id']
    #                     x, y, z = curr_p
    #                     if kw_id == 1: nx, ny, nz = x+50, y+50, z+50
    #                     elif kw_id == 2: nx, ny, nz = 2*x, 2*y, 2*z
    #                     elif kw_id == 3: nx, ny, nz = 500-x, 500-y, 500-z
    #                     elif kw_id == 4: nx, ny, nz = int(x*0.5), int(y*0.5), int(z*0.5)
    #                     next_pos_jump = (nx % 500, ny % 500, nz % 500)
                    
    #                 step_num += 1
    #                 jump_type = "SW" if action == 'SW' else "KW"
    #                 report.append(f"\n    {step_num}. **穿越{jump_type}{step['id']}** (k={curr_k})")
    #                 if dk != 0:
    #                     report.append(f"       - 时间跳跃: k {'+' if dk > 0 else ''}{dk} → k={next_k}")
    #                 report.append(f"       - 穿越税: {tax} 迷幻币")
                    
    #                 curr_p = next_pos_jump
    #                 curr_k = next_k
    #                 if action == 'SW':
    #                     curr_t += 1
                    
    #             elif action == 'MoveToSell':
    #                 wait_sell = step.get('wait', 0)
    #                 final_k = step['k_end']
                    
    #                 if wait_sell > 0:
    #                     step_num += 1
    #                     report.append(f"\n    {step_num}. **等待{wait_sell}旬到最佳卖出时间** (k={curr_k}→k={final_k})")
    #                     curr_k = final_k
                    
    #                 step_num += 1
    #                 sell_price = 10 * city.base_prices[item] * trade['sell_lvl']
    #                 report.append(f"\n    {step_num}. **卖出{item_cn}({item})** (k={curr_k})")
    #                 report.append(f"       - 价格等级: Lv{trade['sell_lvl']}")
    #                 report.append(f"       - 卖出收入: {sell_price} 迷幻币")
            
    #         # 单笔交易结算
    #         buy_cost = 10 * city.base_prices[item] * trade['buy_lvl']
    #         sell_price = 10 * city.base_prices[item] * trade['sell_lvl']
    #         report.append(f"\n  【本笔交易结算】")
    #         report.append(f"    卖出收入: {sell_price} | 买入成本: {buy_cost} | 燃料: {trade['fuel']} | 税金: {trade['tax']}")
    #         report.append(f"    本笔净利润: {trade['profit']} 迷幻币")
        
    #     # 多次交易总结
    #     report.append(f"\n{'='*60}")
    #     report.append(f"📈 多次交易总结算")
    #     report.append(f"{'='*60}")
    #     report.append(f"  ┌─────────────────────────────────────┐")
    #     report.append(f"  │ 交易次数      {best_plan['trade_count']:>6} 笔            │")
    #     report.append(f"  │ 总利润        {best_plan['profit']:>6} 迷幻币          │")
    #     report.append(f"  │ 总燃料消耗    {best_plan['fuel']:>6} 迷幻币          │")
    #     report.append(f"  │ 总穿越税金    {best_plan['tax']:>6} 迷幻币          │")
    #     report.append(f"  │ 总穿越次数    {best_plan['jump_count']:>6} 次            │")
    #     report.append(f"  └─────────────────────────────────────┘")
        
    #     # 各笔交易明细
    #     report.append(f"\n  【交易明细】")
    #     for idx, trade in enumerate(all_trades):
    #         report.append(f"    第{idx+1}笔: {trade['item']}({item_names.get(trade['item'], trade['item'])}) "
    #                      f"利润={trade['profit']} (买k={trade['buy_k']}, 卖k={trade['sell_k']})")
        
    #     report.append(f"\n{'★'*20}")
    #     report.append(f"  多次交易最优方案")
    #     report.append(f"  总利润: {best_plan['profit']} 迷幻币")
    #     report.append(f"{'★'*20}")
        
    #     # 输出报告
    #     final_report = "\n".join(report)
    #     print(final_report)
    #     return final_report
    
    # ========== 原有单次交易报告输出 ==========
    print_false = False
    only_best = False # 改为 False 可打印全部计划
    _plans_to_print = {best_plan['item']: all_plans[best_plan['item']]} if (only_best and best_plan and best_plan['item'] in all_plans) else all_plans
    for item, plan in _plans_to_print.items():
        # print(plan)
        item_cn = item_names.get(item, item)
        dest_cn = dest_names.get(item, '目的地')
        
        if plan['profit'] == -float('inf'):
            continue
        if print_false:
            report.append(f"\n{'='*60}")
            report.append(f"商品: {item}({item_cn}) | ❌ 无可行方案")
            report.append(f"{'='*60}")
            
            # 展示市场信息
            trend = trends[item]
            report.append(f"\n【市场分析】")
            report.append(f"  • 最低价: Lv{trend['min_lvl']} @ k={[x[0] for x in trend['buy_windows'][:5]]}")
            report.append(f"  • 最高价: Lv{trend['max_lvl']} @ k={[x[0] for x in trend['sell_windows'][:5]]}")
            
            # 展示诊断信息（新格式）
            diagnostics = plan.get('diagnostics', {})
            
            # 第一部分：可达穿越点分析
            reachable_jumps = diagnostics.get('reachable_jumps', [])
            unreachable_jumps = diagnostics.get('unreachable_jumps', [])
            
            report.append(f"\n【第一步：穿越点可达性分析】")
            report.append(f"  规则: 买入必须通过至少一次穿越(SW/KW)完成")
            report.append(f"  时间范围: k ∈ [{current_k - max_time_leap}, {current_k + max_time_leap}]")
            
            if reachable_jumps:
                report.append(f"\n  ✓ 可达穿越点 ({len(reachable_jumps)}个):")
                for jump_info in reachable_jumps[:5]:
                    report.append(f"    • {jump_info}")
            else:
                report.append(f"\n  ✗ 没有可达的穿越点")
            
            if unreachable_jumps:
                report.append(f"\n  ✗ 不可达穿越点 (部分示例):")
                for jump_info in unreachable_jumps[:3]:
                    report.append(f"    • {jump_info}")
            
            # 详细展示 SW 可达性
            report.append(f"\n【SW 详细可达性分析】")
            for sw_id, conf in city.sw_config.items():
                sw_pos = conf['pos']
                dk = conf['dk']
                dist = city.manhattan_distance(current_pos, sw_pos)
                travel_time = math.ceil((10 + dist) / 10)
                
                report.append(f"\n  SW{sw_id} (位置{sw_pos}, 时间跳跃{dk:+d}旬):")
                report.append(f"    到达SW需要: ⌈(10+{dist})/10⌉ = {travel_time}旬")
                
                trend_min_k = current_k - max_time_leap
                trend_max_k = current_k + max_time_leap
                
                for wait in range(3):  # 展示等待 0-2 旬的情况
                    arrival_k = current_k + wait + travel_time
                    after_jump_k = arrival_k + dk
                    
                    arrival_in_range = trend_min_k <= arrival_k <= trend_max_k
                    after_in_range = trend_min_k <= after_jump_k <= trend_max_k
                    
                    if arrival_in_range and after_in_range:
                        report.append(f"    等待{wait}旬: 到达k={arrival_k}, 跳跃后k={after_jump_k} ✓ 可用于买入")
                    elif not arrival_in_range:
                        reason = f"< 下限{trend_min_k}" if arrival_k < trend_min_k else f"> 上限{trend_max_k}"
                        report.append(f"    等待{wait}旬: 到达k={arrival_k} ✗ 超出范围({reason})")
                    else:
                        reason = f"< 下限{trend_min_k}" if after_jump_k < trend_min_k else f"> 上限{trend_max_k}"
                        report.append(f"    等待{wait}旬: 到达k={arrival_k}, 跳跃后k={after_jump_k} ✗ 超出范围({reason})")
            
            # 详细展示 KW 可达性
            report.append(f"\n【KW 详细可达性分析】")
            report.append(f"  拦截条件: 到达KW位置所需时间 == KW到达该位置的时间")
            
            for kw_id in city.kw_config:
                cfg = city.kw_config[kw_id]
                report.append(f"\n  KW{kw_id} (基速{cfg['base']}, 方向{cfg['vec']}):")
                
                intercept_found = False
                best_attempt = None
                min_diff = float('inf')
                
                for wait in range(8):
                    for dt in range(0, 20):  # 从0开始，支持原地穿越
                        target_k = current_k + wait + dt
                        if target_k > current_k + max_time_leap:
                            break
                        kw_pos = city.get_kw_pos(kw_id, target_k)
                        dist = city.manhattan_distance(current_pos, kw_pos)
                        
                        # 与 spatiotemporal_trade_optimizer.py 保持一致的燃料/时间计算
                        if dist != 0:
                            fuel_to_kw = 10 + dist
                        else:
                            fuel_to_kw = 0  # 原地穿越，无燃料消耗
                        travel_time = math.ceil(fuel_to_kw / 10) if fuel_to_kw > 0 else 0
                        
                        if travel_time == dt:
                            intercept_found = True
                            if dt == 0:
                                report.append(f"    ✓ 原地穿越: k={target_k}时KW恰好在当前位置{kw_pos}")
                            else:
                                report.append(f"    ✓ 可拦截: 等{wait}旬+行驶{dt}旬 → k={target_k}到达{kw_pos}")
                            
                            # 计算传送后位置
                            x, y, z = kw_pos
                            if kw_id == 1: nx, ny, nz = x+50, y+50, z+50
                            elif kw_id == 2: nx, ny, nz = 2*x, 2*y, 2*z
                            elif kw_id == 3: nx, ny, nz = 500-x, 500-y, 500-z
                            elif kw_id == 4: nx, ny, nz = int(x*0.5), int(y*0.5), int(z*0.5)
                            pos_after = (nx % 500, ny % 500, nz % 500)
                            report.append(f"      传送后位置: {pos_after}, 可用于买入(k={target_k})")
                            break
                        else:
                            diff = abs(travel_time - dt)
                            if diff < min_diff:
                                min_diff = diff
                                best_attempt = {'wait': wait, 'dt': dt, 'k': target_k,
                                               'pos': kw_pos, 'dist': dist, 'travel_time': travel_time}
                    if intercept_found:
                        break
                
                if not intercept_found and best_attempt:
                    ba = best_attempt
                    report.append(f"    ✗ 无法拦截")
                    report.append(f"      最近尝试: 等{ba['wait']}旬+计划行驶{ba['dt']}旬, 实际需{ba['travel_time']}旬, 差{abs(ba['travel_time']-ba['dt'])}旬")
            
            # 第二部分：交易可行性分析
            trade_issues = diagnostics.get('trade_issues', [])
            report.append(f"\n【第二步：交易可行性分析】")
            report.append(f"  规则: 从穿越后位置到卸货点必须在时间范围内")
            
            if reachable_jumps:
                # 为每个可达穿越点分析到各卸货点的可行性
                report.append(f"\n  对可达穿越点的交易分析:")
                for jump_info in reachable_jumps[:3]:
                    report.append(f"    {jump_info}")
                    dest = city.destinations[item]
                    dest_name = dest_names.get(item, str(dest))
                    report.append(f"      → 到卸货点{dest_name}: 需进一步计算距离和时间")
            
            if trade_issues:
                report.append(f"\n  交易问题详情:")
                for i, issue in enumerate(trade_issues[:5], 1):
                    # 支持新旧两种格式
                    if 'jump' in issue:
                        jump = issue['jump']
                        report.append(f"\n    方案{i}: 穿越{jump['type']}{jump['id']}")
                        report.append(f"      穿越后位置: {jump['pos_after']}, 时间: k={jump['k_after']}")
                    elif 'path' in issue:
                        path = issue['path']
                        if path:
                            path_desc = " → ".join([f"{s['action']}{s.get('id','')}" for s in path])
                            report.append(f"\n    方案{i}: 路径 [{path_desc}]")
                        else:
                            report.append(f"\n    方案{i}:")
                    
                    if 'buy_k' in issue:
                        report.append(f"      买入k={issue['buy_k']}(Lv{issue['buy_lvl']}), 卖出k={issue['sell_k']}(Lv{issue['sell_lvl']})")
                        if 'profit' in issue:
                            report.append(f"      预计利润: {issue['profit']}")
                    report.append(f"      ⚠ {issue['reason']}")
            
            # 第三部分：利润分析
            report.append(f"\n【第三步：利润分析】")
            report.append(f"  最优策略: 最低价买入 → 最高价卖出")
            if trend['buy_windows'] and trend['sell_windows']:
                best_buy_k, best_buy_lvl = trend['buy_windows'][0]
                best_sell_k, best_sell_lvl = trend['sell_windows'][0]
                buy_cost = 10 * city.base_prices[item] * best_buy_lvl
                sell_price = 10 * city.base_prices[item] * best_sell_lvl
                potential_profit = sell_price - buy_cost
                report.append(f"  理想买入: k={best_buy_k}(Lv{best_buy_lvl}), 成本={buy_cost}")
                report.append(f"  理想卖出: k={best_sell_k}(Lv{best_sell_lvl}), 收入={sell_price}")
                report.append(f"  理想差价: {potential_profit} (还需减去燃料和税)")
                
                if best_sell_k < best_buy_k:
                    report.append(f"\n  ⚠ 注意: 卖出时间k={best_sell_k} < 买入时间k={best_buy_k}")
                    report.append(f"    需要SW时间回溯才能实现最优交易")
            
            report.append(f"\n【结论】")
            if not reachable_jumps:
                report.append(f"  无可行方案: 没有可达的穿越点")
            elif trade_issues:
                report.append(f"  无可行方案: 从穿越点无法到达卸货点，或利润为负")
            else:
                report.append(f"  无可行方案: 所有可能的交易组合利润为负或超出时间范围")
            
            report.append("-" * 60)
            continue
            
        report.append(f"\n{'='*60}")
        report.append(f"商品: {item}({item_cn})")
        report.append(f"{'='*60}")
        
        # 方案概要
        report.append(f"\n【方案概要】")
        report.append(f"  • 买入时间: k={plan['buy_k']} (价格等级 Lv{plan['buy_lvl']} - 最低价)")
        report.append(f"  • 卖出时间: k={plan['sell_k']} (价格等级 Lv{plan['sell_lvl']} - 最高价)")
        report.append(f"  • 穿越次数: {plan['jump_count']} 次")
        report.append(f"  • 预计净利润: {plan['profit']} 迷幻币")
        
        # 详细行动步骤
        report.append(f"\n【详细行动步骤】")
        
        # 对path进行处理：只把Buy插入到合适位置，其他保持原顺序
        sorted_path = plan['path']
        # report.append('sorted_path:'+str(sorted_path))
        sorted_path = insert_buy_action(sorted_path)
        
        # print(sorted_path)

        curr_p = current_pos
        curr_k = current_k
        curr_t = current_t  # 初始化t值
        step_num = 0
        plan_path = []
       
        
        for idx, step in enumerate(sorted_path):
            action = step['action']
            
            # 1. 计算此动作的计划开始时间
            target_start_k = curr_k
            if action == 'Buy':
                target_start_k = step['k']
            elif action == 'MoveToSell':
                target_start_k = step['k_start']
            elif action in ['KW', 'SW']:
                fuel = step.get('fuel', 0)
                travel_time = math.ceil(fuel / 10)
                target_start_k = step['k_arrive'] - travel_time 

            # 2. 插入动态等待
            wait_needed = target_start_k - curr_k
            if wait_needed > 0:
                step_num += 1
                next_k = curr_k + wait_needed
                report.append(f"\n{step_num}. **等待{wait_needed}旬** (k={curr_k}→k={next_k})")
                if action == 'Buy':
                     report.append(f"   - 等待至最佳买入时间")
                elif action == 'KW':
                     report.append(f"   - 等待KW{step['id']}移动到可拦截位置")
                curr_k = next_k

            # 处理 Buy 动作
            if action == 'Buy':
                wait = step.get('wait_before', 0)
                buy_k = step['k']
                
                if wait > 0 and curr_k != buy_k:
                    step_num += 1
                    report.append(f"\n{step_num}. **等待{buy_k - curr_k}旬到最佳买入时间** (k={curr_k}→k={buy_k})")
                    report.append(f"   - 等待价格降至最低点")
                    curr_k = buy_k
                
                step_num += 1
                buy_cost = 10 * city.base_prices[item] * plan['buy_lvl']
                report.append(f"\n{step_num}. **买入{item_cn}({item})** (k={curr_k})")
                report.append(f"   - 价格等级: Lv{plan['buy_lvl']}（最低价）")
                report.append(f"   - 买入成本: 10 × P_{item}({city.base_prices[item]}) × Lv{plan['buy_lvl']} = {buy_cost} 迷幻币")
                continue
            
            # 处理移动
            target_pos = None
            target_name = ""
            if action == 'SW':
                target_pos = city.sw_config[step['id']]['pos']
                target_name = f"SW{step['id']}"
            elif action == 'KW':
                target_pos = step.get('pos_before')
                target_name = f"KW{step['id']}"
            elif action == 'MoveToSell':
                target_pos = city.destinations[item]
                target_name = dest_cn
            
            if target_pos is None:
                continue
            
            # 计算路径信息
            detour = step.get('detour')
            fuel_cost = step.get('fuel', 0)
            travel_time = math.ceil(fuel_cost / 10)
            arrival_k = step.get('k_arrive') if 'k_arrive' in step else (step.get('k_end') - step.get('wait', 0))
            
            # 构建路径
            full_path = [curr_p]
            if detour:
                if isinstance(detour, tuple) and len(detour) == 3 and isinstance(detour[0], int):
                    full_path.append(detour)
                elif isinstance(detour, list):
                    full_path.extend(detour)
            full_path.append(target_pos)
            
            # 输出移动步骤
            if curr_p != target_pos:
                step_num += 1
                report.append(f"\n{step_num}. **移动至{target_name}** (k={curr_k}→k={arrival_k})")
                report.append(f"   - 路线: {format_path_string(full_path, curr_t)}")
                if detour:
                    report.append(f"   - 绕行原因: 直达路径穿越不可穿越地形")
                report.append(f"   - 燃料消耗: {fuel_cost} 迷幻币")
                report.append(f"   - 行驶时间: ⌈{fuel_cost}/10⌉ = {travel_time} 旬")
            
            curr_p = target_pos
            curr_k = arrival_k
            
            # 处理穿越
            if action in ['SW', 'KW']:
                tax = step['tax']
                dk = step.get('dk', 0)
                next_k = arrival_k + dk
                
                next_pos_jump = curr_p
                transform_desc = ""
                if action == 'KW':
                    kw_id = step['id']
                    x, y, z = curr_p
                    if kw_id == 1: 
                        nx, ny, nz = x+50, y+50, z+50
                        transform_desc = f"(x+50, y+50, z+50, t) = ({nx}, {ny}, {nz}, {curr_t})"
                    elif kw_id == 2: 
                        nx, ny, nz = 2*x, 2*y, 2*z
                        transform_desc = f"(2x, 2y, 2z, t) = ({nx}, {ny}, {nz}, {curr_t})"
                    elif kw_id == 3: 
                        nx, ny, nz = 500-x, 500-y, 500-z
                        transform_desc = f"(500-x, 500-y, 500-z, t) = ({nx}, {ny}, {nz}, {curr_t})"
                    elif kw_id == 4: 
                        nx, ny, nz = int(x*0.5), int(y*0.5), int(z*0.5)
                        transform_desc = f"(0.5x, 0.5y, 0.5z, t) = ({nx}, {ny}, {nz}, {curr_t})"
                    next_pos_jump = (nx % 500, ny % 500, nz % 500)
                
                step_num += 1
                jump_type = "SW" if action == 'SW' else "KW"
                report.append(f"\n{step_num}. **穿越{jump_type}{step['id']}** (k={curr_k})")
                if action == 'KW':
                    report.append(f"   - 位置变换: {transform_desc}")
                if dk != 0:
                    report.append(f"   - 时间跳跃: k {'+' if dk > 0 else ''}{dk} → k={next_k}")
                
                # 检查税率优惠
                tax_note = ""
                for e in events_list:
                    if e['start_k'] <= curr_k < e['start_k'] + 1:
                        if 'tax_mul_all' in e and e['tax_mul_all'] < 1:
                            tax_note = f"（享受税率{int((1-e['tax_mul_all'])*100)}%折扣）"
                        if 'first_free' in e and step.get('tax', 0) == 0:
                            tax_note = "（首次穿越免税）"
                report.append(f"   - 穿越税: {tax} 迷幻币{tax_note}")
                
                curr_p = next_pos_jump
                curr_k = next_k
                if action == 'SW':
                    curr_t += 1  # 经过SW，t+1
                
            elif action == 'MoveToSell':
                buy_at_dest = step.get('buy_at_dest', False)
                final_k = step['k_end']
                
                if buy_at_dest:
                    # 先移动至卖出点，到达后等待买入再卖出
                    buy_k_dest = step['buy_k']
                    
                    # 等待买入（到达卖出点后等待至最佳买入时间）
                    wait_before_buy = buy_k_dest - curr_k
                    if wait_before_buy > 0:
                        step_num += 1
                        report.append(f"\n{step_num}. **等待{wait_before_buy}旬到最佳买入时间** (k={curr_k}→k={buy_k_dest})")
                        report.append(f"   - 等待价格降至最低点")
                        curr_k = buy_k_dest
                    
                    # 买入
                    step_num += 1
                    buy_cost = 10 * city.base_prices[item] * plan['buy_lvl']
                    report.append(f"\n{step_num}. **买入{item_cn}({item})** (k={curr_k})")
                    report.append(f"   - 价格等级: Lv{plan['buy_lvl']}（最低价）")
                    report.append(f"   - 买入成本: 10 × P_{item}({city.base_prices[item]}) × Lv{plan['buy_lvl']} = {buy_cost} 迷幻币")
                    
                    # 等待卖出
                    wait_after_buy = final_k - curr_k
                    if wait_after_buy > 0:
                        step_num += 1
                        report.append(f"\n{step_num}. **等待{wait_after_buy}旬到最佳卖出时间** (k={curr_k}→k={final_k})")
                        for e in events_list:
                            if e['start_k'] <= final_k < e['start_k'] + 10 and e.get('item') == item:
                                if e.get('delta', 0) > 0:
                                    report.append(f"   - 等待事件加成生效")
                        curr_k = final_k
                    
                    # 卖出
                    step_num += 1
                    sell_price = 10 * city.base_prices[item] * plan['sell_lvl']
                    report.append(f"\n{step_num}. **卖出{item_cn}({item})** (k={curr_k})")
                    report.append(f"   - 价格等级: Lv{plan['sell_lvl']}（最高价）")
                    for e in events_list:
                        if e['start_k'] <= curr_k < e['start_k'] + 10 and e.get('item') == item:
                            if e.get('delta', 0) > 0:
                                report.append(f"   - 包含事件加成: +{e['delta']}")
                    report.append(f"   - 卖出收入: 10 × P_{item}({city.base_prices[item]}) × Lv{plan['sell_lvl']} = {sell_price} 迷幻币")
                else:
                    # 原有逻辑：先买入再移动至卖出点
                    wait_sell = step.get('wait', 0)
                    
                    if wait_sell > 0:
                        step_num += 1
                        report.append(f"\n{step_num}. **等待{wait_sell}旬到最佳卖出时间** (k={curr_k}→k={final_k})")
                        # 检查是否有事件加成
                        for e in events_list:
                            if e['start_k'] <= final_k < e['start_k'] + 10 and e.get('item') == item:
                                if e.get('delta', 0) > 0:
                                    report.append(f"   - 等待事件加成生效")
                        curr_k = final_k
                    
                    step_num += 1
                    sell_price = 10 * city.base_prices[item] * plan['sell_lvl']
                    report.append(f"\n{step_num}. **卖出{item_cn}({item})** (k={curr_k})")
                    report.append(f"   - 价格等级: Lv{plan['sell_lvl']}（最高价）")
                    # 检查是否有事件加成
                    for e in events_list:
                        if e['start_k'] <= curr_k < e['start_k'] + 10 and e.get('item') == item:
                            if e.get('delta', 0) > 0:
                                report.append(f"   - 包含事件加成: +{e['delta']}")
                    report.append(f"   - 卖出收入: 10 × P_{item}({city.base_prices[item]}) × Lv{plan['sell_lvl']} = {sell_price} 迷幻币")
        
        # 交易结算
        report.append(f"\n【交易结算】")
        buy_cost = 10 * city.base_prices[item] * plan['buy_lvl']
        sell_price = 10 * city.base_prices[item] * plan['sell_lvl']
        report.append(f"  ┌─────────────────────────────────────┐")
        report.append(f"  │ 卖出收入      {sell_price:>6} 迷幻币          │")
        report.append(f"  │ - 买入成本    {buy_cost:>6} 迷幻币          │")
        report.append(f"  │ - 燃料消耗    {plan['fuel']:>6} 迷幻币          │")
        report.append(f"  │ - 穿越税金    {plan['tax']:>6} 迷幻币          │")
        report.append(f"  ├─────────────────────────────────────┤")
        report.append(f"  │ 净利润        {plan['profit']:>6} 迷幻币          │")
        report.append(f"  └─────────────────────────────────────┘")
        
        # 最终状态
        report.append(f"\n【交易完成后状态】")
        final_pos = city.destinations[item]
        report.append(f"  • 新坐标: ({final_pos[0]}, {final_pos[1]}, {final_pos[2]}, {curr_t})")
        report.append(f"  • 新时间: k={plan['sell_k']}")
        report.append(f"  • 资产变化: +{plan['profit']} 迷幻币")
        report.append(f"  • 已用穿越: {plan['jump_count']}次 (剩余{max_jumps - plan['jump_count']}次)")
        report.append("-" * 60)

    if best_plan:
        report.append(f"\n{'★'*20}")
        report.append(f"  最终推荐: {best_plan['item']}({item_names.get(best_plan['item'], best_plan['item'])})")
        report.append(f"  预计利润: {best_plan['profit']} 迷幻币")
        report.append(f"{'★'*20}")

    # ========== Checklist 输出 ==========
    if best_plan and not best_plan.get('is_multi_trade'):
        item = best_plan['item']
        plan = all_plans.get(item, best_plan)
        sorted_path = insert_buy_action(plan.get('path', []))

        # 提取穿越序列
        jump_seq = []
        for step in sorted_path:
            if step['action'] in ['KW', 'SW']:
                jump_seq.append(f"{step['action']}{step['id']}")
        jump_seq_str = "、".join(jump_seq) if jump_seq else "无"

        # 统计等待旬数合计
        total_wait = 0
        _curr_k = current_k
        for step in sorted_path:
            action = step['action']
            target_start_k = _curr_k
            if action == 'Buy':
                target_start_k = step['k']
            elif action == 'MoveToSell':
                target_start_k = step['k_start']
            elif action in ['KW', 'SW']:
                fuel = step.get('fuel', 0)
                travel_time = math.ceil(fuel / 10)
                target_start_k = step['k_arrive'] - travel_time

            wait_needed = target_start_k - _curr_k
            if wait_needed > 0:
                total_wait += wait_needed
                _curr_k = target_start_k

            if action == 'Buy':
                pass
            elif action in ['KW', 'SW']:
                arrival_k = step.get('k_arrive', _curr_k)
                dk = step.get('dk', 0)
                _curr_k = arrival_k + dk
            elif action == 'MoveToSell':
                wait_sell = step.get('wait', 0)
                total_wait += wait_sell
                _curr_k = step['k_end']

        # 结束状态
        final_pos = city.destinations[item]
        _curr_t = current_t
        for step in sorted_path:
            if step['action'] == 'SW':
                _curr_t += 1

        report.append(f"\n{'='*60}")
        report.append(f"【Checklist】")
        report.append(f"{'='*60}")
        report.append(f"1. 模型回复的交易结算单中，交易商品是否为{item}？")
        report.append(f"2. 模型回复的是否共进行{len(jump_seq)}次穿越，穿越序列为\"{jump_seq_str}\"，且穿越顺序与之一致？")
        report.append(f"3. 模型回复的卖出时刻是否为 k={plan['sell_k']}？")
        report.append(f"4. 模型回复的等待旬数合计是否为 {total_wait} 旬？")
        report.append(f"5. 模型回复的最小燃料消耗是否为 {plan['fuel']} 迷幻币（在净利润最大化的前提下）？")
        report.append(f"6. 模型回复的净利润是否为 {plan['profit']} 迷幻币？")
        report.append(f"7. 模型回复的结束状态是否为 ({final_pos[0]}, {final_pos[1]}, {final_pos[2]}, {_curr_t}) k={plan['sell_k']}？")
        report.append(f"{'='*60}")

    # 输出报告
    final_report = "\n".join(report)
    print(final_report)
    return final_report

if __name__ == "__main__":
    # usage: python -m code_simulation_engines.optimization_and_planning.spatiotemporal_trade.spatiotemporal_trade_engine [question id], e.g. timespace_1
    import ast
    import json
    import sys
    from pathlib import Path

    qid = sys.argv[1] if len(sys.argv) > 1 else "timespace_1"
    with open(Path(__file__).resolve().parents[2] / "structured_inputs.jsonl", encoding="utf-8") as f:
        rows = {r["id"]: r for r in map(json.loads, f)}
    raw = rows[qid]["structured_input"]
    try:
        case = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        case = json.loads(raw)
    print(verified_trade(case))
