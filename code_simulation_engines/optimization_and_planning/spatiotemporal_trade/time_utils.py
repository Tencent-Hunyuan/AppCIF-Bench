"""
迷幻之城 k 值计算器
规则：k=0 对应 3028年1月上旬，一年10个月，每月3旬（上/中/下），一年30旬
"""
import re
import json

def calc_k(year, month, period):
    """
    year: 年份，如 3028, 3029
    month: 月份 1-10
    period: 1=上旬, 2=中旬, 3=下旬
    返回: k 值
    """
    return (year - 3028) * 30 + (month - 1) * 3 + (period - 1)

def k_to_date(k):
    """k 值反推日期"""
    period_names = {0: '上旬', 1: '中旬', 2: '下旬'}
    year = 3028 + k // 30
    remainder = k % 30
    month = remainder // 3 + 1
    period = remainder % 3
    return f"{year}年{month}月{period_names[period]} (k={k})"

def extract_time_info(input_str):
    """
    从字符串中提取 "当前世界时间：xxxx 年 x 月 x旬" 格式的年份、月份、旬信息
    
    Args:
        input_str (str): 待处理的原始字符串
    
    Returns:
        tuple: (年份, 月份, 旬)，未匹配到则返回 (None, None, None)
    """
    pattern = r"当前世界时间：\s*(\d+)\s*年\s*(\d+)\s*月\s*(上|中|下)旬"
    
    # 查找匹配项
    match = re.search(pattern, input_str)
    
    map_dict = {'上': 1, '中': 2, '下': 3}
    # ten_day = None
    if match:
        year = match.group(1)    # 提取年份
        month = match.group(2)   # 提取月份
        ten_day = map_dict[match.group(3)] # 提取旬（上/中/下）
        return year, month, ten_day
    else:
        return None, None, None

def judge_match(input_str, input_json, id):
    # print(input_str, input_json, id)
    input_json = eval(input_json)
    json_k = input_json.get('current_k', None)

    year, month, ten_day = extract_time_info(input_str)
    if year is None or month is None or ten_day is None:
        raise ValueError(f"id: {id} 当前世界时间不匹配, input_str: {input_str}")
    str_k = calc_k(int(year), int(month), int(ten_day))
    if json_k != str_k:
        raise ValueError(f"id: {id} 当前世界时间不匹配, json_k: {json_k}({k_to_date(json_k)}), str_k: {str_k}")
    return True

if __name__ == '__main__':
    print("Run `python -m code_simulation_engines.run_smoke_tests` from the repository root.")
