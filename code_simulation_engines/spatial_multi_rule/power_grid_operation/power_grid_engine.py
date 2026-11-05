"""
汉东省电网调控维护总系统 (Revised)
基于 system_prompt.md 卷一至卷三 定义的规则实现
"""
import math
import heapq
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP


def precise_round(value: float, decimals: int) -> float:
    """精确的四舍五入函数
    
    使用 decimal 模块实现精确的四舍五入，避免 Python 内置 round() 的银行家舍入问题。
    例如: precise_round(49.99715, 4) = 49.9972 (而非 49.9971)
    
    Args:
        value: 要舍入的浮点数
        decimals: 保留的小数位数
    
    Returns:
        精确四舍五入后的浮点数
    """
    quantize_str = '0.' + '0' * decimals if decimals > 0 else '1'
    return float(Decimal(str(value)).quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP))

def _pr(value, decimals=2):
    """precise_round 的短别名，用于报告格式化，避免 :.2f 银行家舍入"""
    return precise_round(value, decimals)

# --- 常量定义 (按 system_prompt.md 第六章) ---
ALPHA = 0.000001  # 频率敏感度 (Hz/MW) - 公式7
BETA = 0.05       # 阻尼系数 - 公式7
GAMMA = 500.0     # 同步刚性系数 - 公式3
F_NOM = 50.0      # 额定频率 (Hz)
DT = 1.0          # 仿真步长 (Day)

# 限制标签必须按 rulebook 的声明顺序输出。状态内部使用 set 去重，但
# 绝不能直接遍历 set，否则不同 PYTHONHASHSEED 会改变报告/checklist 字节序。
CANONICAL_LIMIT_ORDER = (
    "出力上限限制",
    "结构运行限制",
    "负荷侧运行限制",
    "状态触发运行限制",
)
_LIMIT_ORDER_INDEX = {
    tag: index for index, tag in enumerate(CANONICAL_LIMIT_ORDER)
}


def canonical_limit_tags(tags: Set[str]) -> List[str]:
    """Return deterministic rulebook order; unknown tags sort after known ones."""
    return sorted(
        tags,
        key=lambda tag: (
            _LIMIT_ORDER_INDEX.get(tag, len(CANONICAL_LIMIT_ORDER)),
            tag,
        ),
    )


# K_droop 按电网计算: K_droop_i = 0.05 * G_base_i
# P_droop_max 按电网计算: P_droop_max_i = 0.1 * G_base_i

# 兜底占用率权重 (公式9) - 使用默认权重 (system_prompt 第567-569行)
W1 = 0.25         # P_droop 权重
W2 = 0.35         # P_res 权重  
W3 = 0.40         # L_shed 权重

# 成本相关
PRICE_WASTE = 0.30      # 网损电量计价单价 (元/kWh)
PENALTY_PER_GRID = 1000000.0  # Critical状态罚单 (元/天/电网) - 100万
E_GRID_PRICE = 1000.0   # 国家电网电价 (元/kWh)

# 刚性负荷比例 (P-301)
# 保障等级: 基础保障=0.10, 强化保障=0.20, 最高保障=0.30
RIGID_LOAD_LEVELS = {
    '基础保障': 0.10,
    '强化保障': 0.20,
    '最高保障': 0.30,
    'basic': 0.10,
    'enhanced': 0.20,
    'maximum': 0.30
}

# --- 枚举定义 ---
class GridStatus(Enum):
    SAFE = "Safe"
    PRE_WARNING = "Pre-warning"
    CRITICAL = "Critical"
    COLLAPSE = "Collapse"
    E_GRID_TAKEOVER = "E-Grid Takeover"

class LineMode(Enum):
    PARALLEL = "Parallel"
    SERIES = "Series"
    OPEN = "Open"

class GridType(Enum):
    THERMAL = "Thermal"      # 火电 (Grid A)
    HYDRO = "Hydro"          # 水电 (Grid B)
    NUCLEAR = "Nuclear"      # 核电 (Grid C)
    LOAD_CENTER = "Load_Center" # 受端 (Grid D)

# --- 数据结构 ---

@dataclass
class TerrainZone:
    name: str
    x_range: Tuple[int, int]
    y_range: Tuple[int, int]
    resistance: float
    priority: int = 0

@dataclass
class GridState:
    grid_id: str
    grid_type: GridType
    coord: Tuple[int, int]
    price_base: float
    
    # 设计容量基准
    G_base_cap: float
    
    # 动态参数
    G_max: float = 0.0      # 当前可用最大出力
    G_actual: float = 0.0   # 基础出力设定值
    
    L_base_cap: float = 0.0 # 基础负荷
    L_actual: float = 0.0   # 实际负荷 (含政策修正)
    L_shed: float = 0.0     # 切负荷量
    L_writeback: float = 0.0  # 公式6写回值: round(L_actual - L_shed, 2)，供下一日读取
    
    # 频率调节
    frequency: float = 50.0
    P_droop: float = 0.0
    P_res: float = 0.0
    
    # 状态标志
    status: GridStatus = GridStatus.SAFE
    decay: float = 1.0
    collapse_days: int = 0
    
    # 特殊状态
    is_pumping: bool = False  # Grid B 专用
    pump_load: float = 0.0    # Grid B 抽水功率（MW），用户显式设定时为正值，仅用于经济结算和日志
    is_island: bool = False   # Grid C 专用
    
    # 限制标签
    limit_tags: Set[str] = field(default_factory=set)
    
    # 初始坐标 (用于轨迹计算)
    initial_coord: Tuple[int, int] = field(default_factory=lambda: (0, 0))
    
    # Grid C 专用: 速度向量
    velocity: Tuple[int, int] = field(default_factory=lambda: (0, 0))

    @property
    def price(self) -> float:
        return self.price_base
    
    @property
    def K_droop(self) -> float:
        """一次调频增益系数: K_droop = 0.05 * G_base"""
        return 0.05 * self.G_base_cap
    
    @property
    def P_droop_max(self) -> float:
        """一次调频最大值: P_droop_max = 0.1 * G_base"""
        return 0.1 * self.G_base_cap
    
    @property
    def P_droop_min(self) -> float:
        """一次调频最小值: 
        - Grid C (核电): 0 (不能下调)
        - 其他电网: -0.1 * G_base
        """
        if self.grid_type == GridType.NUCLEAR:
            return 0.0
        return -0.1 * self.G_base_cap

@dataclass
class LineState:
    line_id: str
    from_id: str
    to_id: str
    capacity: float
    loss_coeff: float
    mode: LineMode = LineMode.PARALLEL
    power: float = 0.0  # 并联模式下的功率（正值表示from->to方向）
    # 串联模式下需要分别存储两个方向的功率
    power_forward: float = 0.0  # from -> to 方向的功率 (P_ij)
    power_backward: float = 0.0  # to -> from 方向的功率 (P_ji)
    distance: float = 0.0
    path: List[Tuple[int, int]] = field(default_factory=list)
    open_reason: str = ''  # 线路断开原因
    mode_before_pump: Optional[LineMode] = None  # 抽水前的线路模式，退出抽水时恢复

@dataclass
class Event:
    type: str
    trigger_day: int
    params: Dict[str, Any]
    active: bool = False

@dataclass
class Policy:
    id: str
    trigger_day: int
    params: Dict[str, Any]
    active: bool = False
    stopped: bool = False  # 标记政策是否已被显式停止

# --- 核心系统 ---

class DianwangSystem:
    def __init__(self, initial_state: Optional[Dict] = None):
        self.t = 0
        self.width = 50
        self.height = 50
        
        # 1. 初始化地形 (按 system_prompt.md 2.4 定义)
        # 阻力从高到低: T-W1(5.0) > T-M1(3.0) > T-U1(1.5) > T-Base(1.0) > T-Smart(0.8) > T-SC1(0.6)
        self.zones = [
            TerrainZone("T-W1", (38, 48), (5, 15), 5.0),       # 镜湖水域
            TerrainZone("T-M1", (15, 35), (0, 50), 3.0),       # 云断山脉 (纵贯南北)
            TerrainZone("T-U1", (40, 50), (40, 50), 1.5),      # 高密度核心城区
            TerrainZone("T-Smart", (35, 50), (35, 50), 0.8),   # 智能微网示范区
            TerrainZone("T-SC1", (10, 40), (25, 30), 0.6)      # 超导试验走廊
        ]
        
        # 不可驻留区域
        self.forbidden_zones = ["T-W1", 'T-M1']
        
        # 2. 初始化电网
        # 注意: L_base = 0 (除 Grid D 以外)
        # Grid D: G_base = 1000 MW (光伏), L_base = 4200 MW (system_prompt 4.4)
        self.grids = {
            'A': GridState('A', GridType.THERMAL, (10, 45), 0.4, G_base_cap=5000.0, L_base_cap=1500),
            'B': GridState('B', GridType.HYDRO, (10, 10), 0.2, G_base_cap=3000.0, L_base_cap=800),
            'C': GridState('C', GridType.NUCLEAR, (45, 10), 0.3, G_base_cap=6000.0, L_base_cap=2000.0),
            'D': GridState('D', GridType.LOAD_CENTER, (45, 45), 0.05, G_base_cap=1000.0, L_base_cap=4200.0)
        }
        
        # 设置初始坐标
        for gid, g in self.grids.items():
            g.initial_coord = g.coord
            
        # Grid C 初始速度
        s_C = 1 + int(self.grids['C'].G_base_cap // 6000)
        self.grids['C'].velocity = (s_C, s_C)
        
        # 3. 初始化线路
        self.lines = {
            'L_AB': LineState('L_AB', 'A', 'B', 2000.0, 0.8),
            'L_AC': LineState('L_AC', 'A', 'C', 1500.0, 1.5),
            'L_BD': LineState('L_BD', 'B', 'D', 1500.0, 1.5),
            'L_CD': LineState('L_CD', 'C', 'D', 3000.0, 0.5),
        }
        
        # 4. 线路过载计数器 (用于物理熔断判定)
        self.line_overload_days: Dict[str, int] = {lid: 0 for lid in self.lines}
        
        # 5. 温度历史记录 (用于高温/寒潮连续天数判定)
        self.temp_history: List[float] = []
        self.global_temp = 25.0
        
        # 初始化计算
        self._calculate_all_paths()
        self._reset_grid_params()
        
        self.events: List[Event] = []
        self.policies: List[Policy] = []
        
        # P-205 政策全局累计变量（用于多次注册时保留历史触发效果）
        self.p205_global_accumulated_level = 0  # 全局累计触发次数
        self.p205_trigger_history: List[Tuple[int, int]] = []  # 记录所有有效触发日 [(day, level_increment), ...]
        
        self.daily_snapshots: List[Dict] = []
        self.daily_cost = 0.0
        self.total_cost = 0.0
        self.cost_penalty = 0.0
        self.cost_e_grid = 0.0
        self.cost_out_of_control = False
        self.base_cost: Optional[float] = None  # 系统默认状态下的成本
        self.initial_prices: Dict[str, float] = {gid: g.price_base for gid, g in self.grids.items()}
        
        # 计算系统默认状态下的基准成本 (频率=50Hz, 出力=G_base_cap, 负荷=L_base_cap)
        self._calculate_default_cost()
        
        if initial_state:
            self.load_state(initial_state)

    # --- 地形与寻路 ---
    
    def get_resistance(self, x: int, y: int) -> float:
        """计算坐标点的地形阻力，遵循"高阻力覆盖低阻力"原则 (T-Base=1.0)
        
        规则说明 (system_prompt 2.4):
        - 若坐标同时落在两个区域，取最大阻力
        - T-U1(1.5) 覆盖 T-Smart(0.8) → max(1.5, 0.8) = 1.5
        """
        if not (0 <= x <= self.width and 0 <= y <= self.height):
            return float('inf')
            
        resistances = []  # T-Base 基础阻力
        
        for z in self.zones:
            if z.x_range[0] <= x <= z.x_range[1] and z.y_range[0] <= y <= z.y_range[1]:
                resistances.append(z.resistance)
        if not resistances:
            return 1.0
        return max(resistances)

    def get_terrain_info(self, x: int, y: int) -> Tuple[str, float]:
        """获取坐标点的地形名称和阻力值
        
        返回:
            (地形名称, 阻力值)
            若不在任何特殊区域，返回 ("平原", 1.0)
        """
        if not (0 <= x <= self.width and 0 <= y <= self.height):
            return ("越界", float('inf'))
            
        matched_zones = []
        
        for z in self.zones:
            if z.x_range[0] <= x <= z.x_range[1] and z.y_range[0] <= y <= z.y_range[1]:
                matched_zones.append((z.name, z.resistance))
        
        if not matched_zones:
            return ("平原", 1.0)
        
        # 按阻力从高到低排序，取最大阻力的区域
        matched_zones.sort(key=lambda x: x[1], reverse=True)
        return matched_zones[0]

    def format_path_segments(self, path: List[Tuple[int, int]]) -> str:
        """将路径格式化为分段表示，合并同方向同区域的连续移动
        
        格式: (起点) -> (移动方向, 地形名, w=权重) -> (终点)
        地形和权重是指当前所在点（出发点）的地形
        """
        if not path or len(path) < 2:
            return "无路径"
        
        segments = []
        i = 0
        
        # 添加起点
        start = path[0]
        segments.append(f"({start[0]}, {start[1]})")
        
        while i < len(path) - 1:
            # 当前点和下一点
            curr_point = path[i]
            next_point = path[i + 1]
            
            # 确定移动方向
            dx = next_point[0] - curr_point[0]
            dy = next_point[1] - curr_point[1]
            
            if dx != 0:
                direction = "x轴移动"
            elif dy != 0:
                direction = "y轴移动"
            else:
                i += 1
                continue
            
            # 获取当前点（出发点）的地形信息
            terrain_name, terrain_weight = self.get_terrain_info(next_point[0], next_point[1])
            
            # 向前查找连续的同方向、同地形的移动
            j = i + 1
            while j < len(path) - 1:
                curr_p = path[j]
                next_p = path[j + 1]
                
                # 计算下一步的方向
                next_dx = next_p[0] - curr_p[0]
                next_dy = next_p[1] - curr_p[1]
                
                if next_dx != 0:
                    next_direction = "x轴移动"
                elif next_dy != 0:
                    next_direction = "y轴移动"
                else:
                    break
                
                # 获取下一点（落入格点）的地形信息
                next_terrain_name, _ = self.get_terrain_info(next_p[0], next_p[1])
                
                # 如果方向相同且地形相同，继续合并
                if next_direction == direction and next_terrain_name == terrain_name:
                    j += 1
                else:
                    break
            
            # 记录这一段: (方向, 地形, 权重) -> 终点
            end_point = path[j]
            
            segments.append(f"({direction}, {terrain_name}, w={terrain_weight})")
            segments.append(f"({end_point[0]}, {end_point[1]})")
            
            i = j
        
        return " -> ".join(segments)


    def is_forbidden_zone(self, x: int, y: int) -> bool:
        """检查坐标是否在不可驻留区域
        
        不可驻留区域 (system_prompt 2.4):
        - T-W1（镜湖水域）: x ∈ [38, 48], y ∈ [5, 15]
        - T-M1（云断山脉）: x ∈ [15, 35], y ∈ [0, 50]
        """
        for z in self.zones:
            if z.name in self.forbidden_zones:
                if z.x_range[0] <= x <= z.x_range[1] and z.y_range[0] <= y <= z.y_range[1]:
                    return True
        return False


    def heuristic(self, a, b):
        # 修正：乘以全图最小阻力系数 0.6
        # 保证 h(n) <= 实际代价，确保 A* 找到最优解
        min_weight = 0.6
        return (abs(a[0] - b[0]) + abs(a[1] - b[1])) * min_weight

    def _dijkstra(self, start, end):
        # 方向优先级编码：东=0, 西=1, 北=2, 南=3（数字越小优先级越高）
        DIRECTION_PRIORITY = {
            (1, 0): 0,   # 东
            (-1, 0): 1,  # 西
            (0, 1): 2,   # 北
            (0, -1): 3,  # 南
        }
        # 四方向移动（按东西北南顺序排列，与优先级编码一致）
        DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        # 优先队列，存放 (f_score, turns, dir_priority, node, prev_direction)
        # 三级排序：① 最小f_score ② 最少拐弯次数 ③ 当前移动方向优先级（东>西>北>南）
        open_set = []
        heapq.heappush(open_set, (0, 0, -1, start, None))

        # 记录路径来源：came_from[current_node] = previous_node
        came_from = {}

        # g_score: 从起点到当前点的实际代价
        g_score = {start: 0}

        # turns_score: 到达当前点时的最少拐弯次数
        turns_score = {start: 0}

        while open_set:
            # 取出优先级最高的点
            current_f, current_turns, _, current, prev_dir = heapq.heappop(open_set)

            if current == end:
                total_cost, path = self.reconstruct_path(came_from, current, g_score[end])
                return total_cost, path

            x, y = current

            for direction in DIRECTIONS:
                dx, dy = direction
                next_node = (x + dx, y + dy)
                nx, ny = next_node

                # 越界检查
                if not (0 <= nx <= self.width and 0 <= ny <= self.height):
                    continue

                # 计算移动代价：进入 next_node 的代价取决于 next_node 的地形
                move_cost = self.get_resistance(nx, ny)
                tentative_g = g_score[current] + move_cost

                # 计算拐弯次数：方向发生变化则拐弯+1
                is_turn = 1 if (prev_dir is not None and direction != prev_dir) else 0
                new_turns = current_turns + is_turn

                prev_g = g_score.get(next_node, float('inf'))
                prev_turns = turns_score.get(next_node, float('inf'))

                # 更新条件：g更小，或g相同但拐弯更少
                if tentative_g < prev_g or (tentative_g == prev_g and new_turns < prev_turns):
                    came_from[next_node] = current
                    g_score[next_node] = tentative_g
                    turns_score[next_node] = new_turns
                    f = tentative_g + self.heuristic(next_node, end)
                    dir_priority = DIRECTION_PRIORITY[direction]
                    heapq.heappush(open_set, (f, new_turns, dir_priority, next_node, direction))

        return float('inf'), []  # 无法到达

    def reconstruct_path(self, came_from, current, total_cost):
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse() # 反转列表，使其从 Start -> End
        return total_cost, path

    def _calculate_all_paths(self):
        """预计算所有线路的物理路径和距离"""
        for line in self.lines.values():
            start = self.grids[line.from_id].coord
            end = self.grids[line.to_id].coord
            dist, path = self._dijkstra(start, end)
            line.distance = dist
            line.path = path

    def _reset_grid_params(self):
        """重置每日基准参数 (system_prompt 初始状态)
        
        根据 system_prompt:
        - G_{i,max}(t) = G_{i,base} (初始值，可被政策/事件修正)
        - G_i^{actual}(t) = G_{i,base} (出力设定值)
        - L_i(t) 从 L_{i,base} 初始化，按"上一日值追溯规则"演化
        - 公式6: L_i(t) ← L_i(t) - L_i^{shed}(t)，切负荷后的负荷作为下一日的初始值
        """
        for gid, g in self.grids.items():
            # G_max 初始化为 G_base，后续可被政策/事件修正
            g.G_max = g.G_base_cap
            
            # G_actual = G_base (system_prompt 第23行)
            # 注意：这是默认值，不是经济调度的结果
            g.G_actual = g.G_base_cap
            
            # L_actual 按"上一日值追溯规则"演化
            # 如果是首日或没有历史记录，使用 L_base
            if self.t <= 1 or len(self.daily_snapshots) == 0:
                g.L_actual = g.L_base_cap
            else:
                prev_snapshot = self.daily_snapshots[-1]
                prev_grid = prev_snapshot['grids'].get(gid)
                if prev_grid:
                    # 如果前一天是抽水状态且当天已退出抽水，负荷恢复为基础负荷
                    if gid == 'B' and prev_grid.is_pumping and not g.is_pumping:
                        g.L_actual = g.L_base_cap
                    else:
                        # 根据公式6+公式13: 使用前一天已按 round(L - L_shed, 2) 写回的值
                        g.L_actual = prev_grid.L_writeback
                else:
                    g.L_actual = g.L_base_cap
            
            g.L_shed = 0.0
            g.P_res = 0.0  # 每日重置备用出力
            g.limit_tags.clear()
            
            # Grid B 抽水状态特殊处理：负荷清零、出力清零、P_droop清零
            if gid == 'B' and g.is_pumping:
                g.L_actual = 0.0
                g.G_actual = 0.0
                g.P_droop = 0.0

    # --- 第十章: 电站坐标移动规则 ---
    
    def precompute_coordinates_to_day(self, target_day: int, previous_events: List[Dict] = None):
        """预计算坐标到指定天数
        
        用于从快照恢复时，如果快照中没有提供 coord 和 velocity，
        需要从 Day 1 预计算到快照日的坐标。
        
        注意：
        - Grid A 和 Grid B 的坐标只依赖 t，可以直接计算
        - Grid C 的坐标依赖前一天的坐标和速度，需要逐天推算
        - Grid D 的坐标依赖前一天的坐标和当天状态（温度/频率/政策），
          需要从 previous_events 中读取历史状态
        
        Args:
            target_day: 目标天数
            previous_events: 历史事件列表，用于获取每天的温度、频率、政策等状态
        """
        if target_day <= 0:
            return
        
        # 保存当前状态
        original_t = self.t
        original_temp_history = self.temp_history.copy()
        original_policies = self.policies.copy()
        original_freq_D = self.grids['D'].frequency
        
        # 重置到初始状态
        self.grids['C'].coord = self.grids['C'].initial_coord
        self.grids['D'].coord = self.grids['D'].initial_coord
        s_C = 1 + int(self.grids['C'].G_base_cap // 6000)
        self.grids['C'].velocity = (s_C, s_C)
        self.temp_history = []
        self.policies = []
        self.grids['D'].frequency = 50.0  # 默认频率
        
        # 从 previous_events 中提取每天的状态
        day_states = {}  # {day: {'temperature': ..., 'frequency_D': ..., 'policies': [...]}}
        if previous_events:
            for event in previous_events:
                day = event.get('t', 0)
                if day <= 0 or day > target_day:
                    continue
                
                if day not in day_states:
                    day_states[day] = {'temperature': None, 'frequency_D': None, 'policies': []}
                
                for action in event.get('actions', []):
                    action_type = action.get('type', '')
                    
                    # 提取温度
                    if action_type == 'OBS':
                        if 'temperature' in action:
                            day_states[day]['temperature'] = action['temperature']
                        elif 'temperature_update' in action:
                            day_states[day]['temperature'] = action['temperature_update']
                        # 提取 Grid D 的频率
                        # if 'grids' in action and 'D' in action['grids']:
                        #     if 'frequency' in action['grids']['D']:
                        #         day_states[day]['frequency_D'] = action['grids']['D']['frequency']
                    
                    # 提取政策
                    elif action_type == 'CFG':
                        # 支持两种格式：
                        # 1. {"type": "CFG", "policy_id": "P-101"}
                        # 2. {"type": "CFG", "policy": {"id": "P-101", "trigger_day": X, ...}}
                        if 'policy_id' in action:
                            day_states[day]['policies'].append({
                                'id': action['policy_id'],
                                'trigger_day': day  # 默认使用注册日
                            })
                        elif 'policy' in action and 'id' in action['policy']:
                            policy_data = action['policy']
                            day_states[day]['policies'].append({
                                'id': policy_data['id'],
                                'trigger_day': policy_data.get('trigger_day', day)  # 使用指定的trigger_day，否则默认为注册日
                            })
        
        # 逐天计算坐标
        for day in range(1, target_day + 1):
            self.t = day
            
            # 获取当天状态
            state = day_states.get(day, {})
            
            # 更新温度历史
            temp = state.get('temperature')
            if temp is not None:
                self.temp_history.append(temp)
            else:
                # 未告知温度时，沿用前一天的温度；若无历史则默认 25°C
                self.temp_history.append(self.temp_history[-1] if self.temp_history else 25.0)
            
            # 更新 Grid D 频率
            freq_D = state.get('frequency_D')
            if freq_D is not None:
                self.grids['D'].frequency = freq_D
            
            # 更新政策
            for policy_info in state.get('policies', []):
                # 支持两种格式：字符串（旧格式）或字典（新格式）
                if isinstance(policy_info, str):
                    policy_id = policy_info
                    trigger_day = day
                else:
                    policy_id = policy_info.get('id', '')
                    trigger_day = policy_info.get('trigger_day', day)
                
                # 只关注 P-101 和 P-205
                if policy_id in ['P-101', 'P-205']:
                    existing = next((p for p in self.policies if p.id == policy_id), None)
                    if existing:
                        # P-205 特殊处理：新政策覆盖旧政策的 trigger_day
                        if policy_id == 'P-205':
                            existing.trigger_day = trigger_day
                            existing.active = True
                            # 注意：在预计算阶段不需要计算 L_base_cap 的累计，
                            # 因为这里只是为了计算坐标
                    else:
                        self.policies.append(Policy(id=policy_id, trigger_day=trigger_day, params={}, active=True))
            
            # Grid A: 心形轨迹（只依赖 t）
            self._update_grid_A_coord()
            
            # Grid B: 圆形轨迹（只依赖 t）
            self._update_grid_B_coord()
            
            # Grid C: 折线反弹轨迹（依赖前一天坐标和速度）
            self._update_grid_C_coord()
            
            # Grid D: 状态决定的坐标（依赖温度、频率、政策）
            self._update_grid_D_coord()
        
        # 恢复原始状态（除了坐标和速度）
        self.t = original_t
        self.temp_history = original_temp_history
        self.policies = original_policies
        self.grids['D'].frequency = original_freq_D
        
        # 重新计算线路路径
        self._calculate_all_paths()
    
    def _update_grid_coordinates(self):
        """更新所有电站坐标 (system_prompt 第十章)"""
        if self.t <= 0:
            return
            
        # Grid A: 心形轨迹
        self._update_grid_A_coord()
        
        # Grid B: 圆形轨迹
        self._update_grid_B_coord()
        
        # Grid C: 折线反弹轨迹
        self._update_grid_C_coord()
        
        # Grid D: 状态决定的坐标
        self._update_grid_D_coord()
        
        # 重新计算线路路径
        self._calculate_all_paths()
    
    def _update_grid_A_coord(self):
        """Grid A: 心形轨迹 (10.2)"""
        g = self.grids['A']
        x0, y0 = g.initial_coord
        
        # 中心和半径
        C_x = x0 + 12
        C_y = y0 - 10
        R = 10
        
        # 角度
        theta = (2 * math.pi / 24) * self.t
        
        # 心形参数方程
        x_tilde = C_x + R * (math.sin(theta) ** 3)
        y_tilde = C_y + (R / 16) * (
            13 * math.cos(theta)
            - 5 * math.cos(2 * theta)
            - 2 * math.cos(3 * theta)
            - math.cos(4 * theta)
        )
        
        # 取整和合法性修正
        g.coord = self._legalize_coord(x_tilde, y_tilde, 'A')
    
    def _update_grid_B_coord(self):
        """Grid B: 圆形轨迹 (10.3)"""
        g = self.grids['B']
        x0, y0 = g.initial_coord
        
        # 中心和半径
        C_x = x0 + 18
        C_y = y0 + 18
        R = 12
        
        # 角度
        theta = (2 * math.pi / 20) * self.t
        
        # 圆形参数方程
        x_tilde = C_x + R * math.cos(theta)
        y_tilde = C_y + R * math.sin(theta)
        
        g.coord = self._legalize_coord(x_tilde, y_tilde, 'B')
    
    def _update_grid_C_coord(self):
        """Grid C: 折线反弹轨迹 (10.4)"""
        g = self.grids['C']
        x_prev, y_prev = g.coord
        vx, vy = g.velocity
        
        # 活动边界
        x_min, x_max = 2, 48
        y_min, y_max = 2, 48
        
        # 计算候选位置
        x_tilde = x_prev + vx
        y_tilde = y_prev + vy
        
        # 反弹检测
        if not (x_min <= x_tilde <= x_max):
            vx = -vx
        if not (y_min <= y_tilde <= y_max):
            vy = -vy
        
        # 更新速度
        g.velocity = (vx, vy)
        
        # 重新计算位置
        x_tilde = x_prev + vx
        y_tilde = y_prev + vy
        g.coord = self._legalize_coord(x_tilde, y_tilde, 'C')
    
    def _update_grid_D_coord(self):
        """Grid D: 状态决定的坐标 (10.5)"""
        g = self.grids['D']
        x_prev, y_prev = g.coord
        
        # 温度项
        dy = 0
        dy_reason = "无温度事件"
        is_heatwave = self._is_heatwave_triggered()
        is_coldwave = self._is_coldwave_triggered()
        if is_heatwave:
            dy = -1
            dy_reason = "高温触发日"
        elif is_coldwave:
            dy = +1
            dy_reason = "寒潮触发日"
        
        # 频率项
        dx_f = 0
        dx_f_reason = f"频率 {g.frequency:.4f} Hz 在正常范围 [49.8, 50.2]"
        if g.frequency < 49.8:
            dx_f = -1
            dx_f_reason = f"频率 {g.frequency:.4f} Hz < 49.8"
        elif g.frequency > 50.2:
            dx_f = +1
            dx_f_reason = f"频率 {g.frequency:.4f} Hz > 50.2"
        
        # 政策项
        dx_p = 0
        dx_p_reason = "无政策影响"
        p205_trigger_today = False
        p205_trigger_source = None  # 记录触发来源
        
        # 检查当前活跃的 P-205 政策
        p205 = next((p for p in self.policies if p.id == 'P-205' and p.active and not p.stopped), None)
        if p205 is not None:
            delta_days = self.t - p205.trigger_day
            if delta_days > 0 and delta_days % 5 == 0:
                p205_trigger_today = True
                p205_trigger_source = f"当前P-205政策 (trigger_day={p205.trigger_day}, delta_days={delta_days})"
        
        # 检查历史触发记录（来自被覆盖的旧政策，在 register_policy 时记录）
        if not p205_trigger_today:
            for trigger_day, _ in self.p205_trigger_history:
                if trigger_day == self.t:
                    p205_trigger_today = True
                    p205_trigger_source = f"历史P-205触发记录 (触发日={trigger_day})"
                    break
        
        p101_active = any(p.id == 'P-101' and p.active for p in self.policies)
        
        if p205_trigger_today and p101_active:
            dx_p = 0
            dx_p_reason = f"P-205触发({p205_trigger_source}) 与 P-101同时生效，dx_p=0"
        elif p205_trigger_today:
            dx_p = +1
            dx_p_reason = f"P-205触发: {p205_trigger_source}"
        elif p101_active:
            dx_p = -1
            dx_p_reason = "P-101生效"
        
        dx = dx_f + dx_p
        
        x_tilde = x_prev + dx
        y_tilde = y_prev + dy
        
        new_coord = self._legalize_coord(x_tilde, y_tilde, 'D')
        g.coord = new_coord
        
        # 记录 Grid D 坐标推演日志
        if hasattr(self, 'daily_calc_log'):
            self.daily_calc_log['grid_d_coord_evolution'] = {
                'prev_coord': (x_prev, y_prev),
                'new_coord': new_coord,
                'dy': dy,
                'dy_reason': dy_reason,
                'is_heatwave': is_heatwave,
                'is_coldwave': is_coldwave,
                'dx_f': dx_f,
                'dx_f_reason': dx_f_reason,
                'frequency': g.frequency,
                'dx_p': dx_p,
                'dx_p_reason': dx_p_reason,
                'p205_trigger_today': p205_trigger_today,
                'p205_trigger_source': p205_trigger_source,
                'p101_active': p101_active,
                'dx': dx,
                'x_tilde': x_tilde,
                'y_tilde': y_tilde,
                'p205_global_accumulated_level': self.p205_global_accumulated_level,
                'p205_trigger_history': list(self.p205_trigger_history),
                'l_base_cap': self.grids['D'].L_base_cap
            }
    
    def _legalize_coord(self, x_tilde: float, y_tilde: float, grid_id: str = None) -> Tuple[int, int]:
        """坐标合法化 (10.1): 取整、边界截断、禁行区域修正
        
        步骤:
        1. 四舍五入取整
        2. 边界截断 (Grid C: [2,48], 其他: [0,50])
        3. 若落入不可驻留区域（T-W1, T-M1），则修正到最近的合法坐标
        
        Args:
            x_tilde: 连续x坐标
            y_tilde: 连续y坐标
            grid_id: 电网ID，用于确定边界约束（Grid C使用[2,48]边界）
        """
        # 取整
        x = round(x_tilde)
        y = round(y_tilde)
        
        # 边界截断 - Grid C使用特殊边界[2,48]，其他使用[0,50]
        if grid_id == 'C':
            x_min, x_max = 2, 48
            y_min, y_max = 2, 48
        else:
            x_min, x_max = 0, 50
            y_min, y_max = 0, 50
        
        x = max(x_min, min(x_max, x))
        y = max(y_min, min(y_max, y))
        
        # 禁行区域修正，暂不考虑这点
        # if self.is_forbidden_zone(x, y):
        #     x, y = self._find_nearest_legal_coord(x, y, grid_id)
        
        return (x, y)
    
    def _find_nearest_legal_coord(self, x: int, y: int, grid_id: str = None) -> Tuple[int, int]:
        """找到最近的合法坐标 (10.1.4)
        
        当坐标落入禁行区域时，按以下优先级寻找替代坐标:
        1. 曼哈顿距离最小
        2. 地形阻力最小
        3. |u - x| 最小 (x方向优先)
        4. |v - y| 最小
        
        Args:
            x: 当前x坐标
            y: 当前y坐标
            grid_id: 电网ID，用于确定边界约束（Grid C使用[2,48]边界）
        """
        candidates = []
        
        # Grid C使用特殊边界[2,48]，其他使用[0,50]
        if grid_id == 'C':
            coord_min, coord_max = 2, 48
        else:
            coord_min, coord_max = 0, 50
        
        # 优化: 从近到远搜索，使用BFS思路
        # 先搜索距离较近的点，找到后可以提前终止
        max_search_dist = 60  # 最大搜索距离（曼哈顿距离）
        
        for dist in range(1, max_search_dist + 1):
            found_at_dist = []
            # 遍历所有曼哈顿距离为 dist 的点
            for dx in range(-dist, dist + 1):
                dy_abs = dist - abs(dx)
                for dy in ([-dy_abs, dy_abs] if dy_abs > 0 else [0]):
                    u = x + dx
                    v = y + dy
                    if coord_min <= u <= coord_max and coord_min <= v <= coord_max:
                        if not self.is_forbidden_zone(u, v):
                            resistance = self.get_resistance(u, v)
                            found_at_dist.append((resistance, abs(dx), abs(dy), u, v))
            
            if found_at_dist:
                # 在当前距离找到合法坐标，按次优先级排序
                found_at_dist.sort(key=lambda c: (c[0], c[1], c[2]))
                return (found_at_dist[0][3], found_at_dist[0][4])
        
        # 如果没找到（理论上不应该发生），返回原坐标
        return (x, y)

    # --- 物理逻辑 ---

    def _set_generation_output(self):
        """设置各电网出力 (system_prompt 初始状态第23行)
        
        根据 system_prompt:
        - G_i^{actual}(t) = G_{i,base} (默认值)
        - 除非用户输入或政策/事件显式修改
        - Grid B 抽水状态: G_B^{actual}(t) = 0（退化为纯负荷，出力清零）
        - Grid C 孤岛模式: 自发自用
        - 瘫痪/托管状态: G_actual = 0
        
        注意: 不存在经济调度，出力是设定好的
        """
        output_log = {}
        
        for gid, g in self.grids.items():
            # 瘫痪或托管状态：出力为0
            if g.status in [GridStatus.COLLAPSE, GridStatus.E_GRID_TAKEOVER]:
                g.G_actual = 0.0
                output_log[gid] = {
                    'G_actual': 0.0,
                    'reason': f'状态为{g.status.value}，出力为0'
                }
                continue
            
            # Grid B 抽水状态：出力清零（退化为纯负荷，不产生任何正向发电出力）
            if gid == 'B' and g.is_pumping:
                g.G_actual = 0.0
                # 记录抽水功耗（仅用于经济结算和日志，不参与系统计算）
                if g.pump_load > 0:
                    pump_power = g.pump_load
                    reason = f'抽水状态(出力清零)，记录抽水功耗={pump_power}MW（仅用于日志）'
                else:
                    pump_power = g.G_base_cap
                    reason = f'抽水状态(出力清零)，默认抽水功耗=G_base={g.G_base_cap}MW（仅用于日志）'
                output_log[gid] = {
                    'G_actual': 0.0,
                    'pump_power': pump_power,
                    'reason': reason
                }
                continue
            
            # Grid C 孤岛模式
            if gid == 'C' and g.is_island:
                # 孤岛模式：自发自用，出力按本地负荷调整
                g.G_actual = min(g.G_max, g.L_actual)
                output_log[gid] = {
                    'G_actual': g.G_actual,
                    'reason': '孤岛模式，自发自用'
                }
                continue
            
            # 默认情况：G_actual = G_base (或 G_max，取决于政策修正)
            # 注意：G_max 可能已被政策/事件修正（如 P-101 限产）
            # 但 G_actual 默认应为 G_base，除非有显式设定
            # 这里保持 G_actual 不变（在 _reset_grid_params 中已设为 G_max）
            output_log[gid] = {
                'G_actual': g.G_actual,
                'G_max': g.G_max,
                'reason': '默认出力设定'
            }
        
        # 记录出力设定过程
        if hasattr(self, 'daily_calc_log'):
            self.daily_calc_log['generation_output'] = output_log

    def _calculate_power_flow(self, freq_prev: Dict[str, float] = None):
        """计算线路潮流 (system_prompt 公式3)
        
        并联模式: P_ij(t) = clip(γ * (f_i(t-1) - f_j(t-1)), -P_max, P_max)
                  且 P_ji = -P_ij (方向一致性)
        串联模式: P_ij(t) = clip(γ * max(0, f_i(t-1) - f_j(t-1)), 0, P_max)
                  P_ji(t) = clip(γ * max(0, f_j(t-1) - f_i(t-1)), 0, P_max)
                  注意: 串联模式下两个方向独立计算，P_ji ≠ -P_ij
        
        注意: 使用 t-1 时刻的频率计算
        """
        # 如果没有提供上一时刻的频率，使用当前频率
        if freq_prev is None:
            freq_prev = {gid: g.frequency for gid, g in self.grids.items()}
        
        power_flow_log = {}
        
        for line in self.lines.values():
            if line.mode == LineMode.OPEN:
                line.power = 0.0
                line.power_forward = 0.0
                line.power_backward = 0.0
                power_flow_log[line.line_id] = {
                    'mode': line.mode.value,
                    'final_power': 0.0,
                    'power_forward': 0.0,
                    'power_backward': 0.0,
                    'open_reason': line.open_reason  # 记录断开原因
                }
                # 检查结构运行限制
                self._check_structure_limit(line, freq_prev)
                continue
            
            f_from = freq_prev[line.from_id]
            f_to = freq_prev[line.to_id]
            delta_f_forward = round(f_from - f_to, 10)  # from -> to 方向的频差，消除浮点精度误差
            delta_f_backward = round(f_to - f_from, 10)  # to -> from 方向的频差，消除浮点精度误差
            
            if line.mode == LineMode.PARALLEL:
                # 并联模式: 只需要一个功率值，P_ji = -P_ij
                raw_power = round(GAMMA * delta_f_forward, 10)  # 消除浮点精度误差
                final_power = max(-line.capacity, min(line.capacity, raw_power))
                line.power = final_power
                line.power_forward = max(0, final_power)  # from->to 方向传输的功率
                line.power_backward = max(0, -final_power)  # to->from 方向传输的功率
                
                power_flow_log[line.line_id] = {
                    'mode': line.mode.value,
                    'f_from': f_from,
                    'f_to': f_to,
                    'delta_f': delta_f_forward,
                    'raw_power': raw_power,
                    'final_power': final_power,
                    'power_forward': line.power_forward,
                    'power_backward': line.power_backward
                }
            elif line.mode == LineMode.SERIES:
                # 串联模式: 两个方向独立计算
                # P_ij = clip(γ × max(0, f_i - f_j), 0, P_max) -- from -> to
                raw_power_forward = round(GAMMA * max(0, delta_f_forward), 10)  # 消除浮点精度误差
                power_forward = min(line.capacity, raw_power_forward)
                
                # P_ji = clip(γ × max(0, f_j - f_i), 0, P_max) -- to -> from
                raw_power_backward = round(GAMMA * max(0, delta_f_backward), 10)  # 消除浮点精度误差
                power_backward = min(line.capacity, raw_power_backward)
                
                line.power_forward = power_forward
                line.power_backward = power_backward
                # 为了兼容性，line.power 存储净功率流 (from->to为正)
                line.power = power_forward - power_backward
                
                power_flow_log[line.line_id] = {
                    'mode': line.mode.value,
                    'f_from': f_from,
                    'f_to': f_to,
                    'delta_f_forward': delta_f_forward,
                    'delta_f_backward': delta_f_backward,
                    'raw_power_forward': raw_power_forward,
                    'raw_power_backward': raw_power_backward,
                    'power_forward': power_forward,
                    'power_backward': power_backward,
                    'net_power': line.power
                }
        
        # 记录功率流计算过程
        if hasattr(self, 'daily_calc_log'):
            self.daily_calc_log['power_flow'] = power_flow_log
    
    def _check_structure_limit(self, line: LineState, freq_prev: Dict[str, float] = None):
        """检查结构运行限制 (公式3注释)
        
        若线路 Open 但按并联模式计算 |P_ij| >= 0.1 * P_max，
        则判定存在"结构运行限制"
        
        注意: 因Grid B抽水而断开的联络线不参与此判定
        """
        # 因抽水而断开的联络线不参与结构运行限制判定
        if line.open_reason == 'Grid B 抽水状态，拓扑隔离':
            return
        if freq_prev is None:
            freq_prev = {gid: g.frequency for gid, g in self.grids.items()}
        
        f_from = freq_prev[line.from_id]
        f_to = freq_prev[line.to_id]
        delta_f = round(f_from - f_to, 10)  # 消除浮点精度误差
        
        hypothetical_power = round(GAMMA * delta_f, 10)  # 消除浮点精度误差
        hypothetical_power = max(-line.capacity, min(line.capacity, hypothetical_power))
        
        # 记录结构运行限制判断过程
        if hasattr(self, 'daily_calc_log'):
            if 'structure_limit_check' not in self.daily_calc_log:
                self.daily_calc_log['structure_limit_check'] = {}
            self.daily_calc_log['structure_limit_check'][line.line_id] = {
                'f_from': f_from,
                'f_to': f_to,
                'delta_f': delta_f,
                'hypothetical_power': hypothetical_power,
                'threshold': 0.1 * line.capacity,
                'triggered': abs(hypothetical_power) >= 0.1 * line.capacity,
                'reason': 'Open线路假设并联功率流检查'
            }
        
        if abs(hypothetical_power) >= 0.1 * line.capacity:
            for gid in [line.from_id, line.to_id]:
                self.grids[gid].limit_tags.add("结构运行限制")

    def _update_dynamics(self, freq_prev: Dict[str, float] = None):
        """状态演化 (公式 2, 4, 5, 6, 7)
        
        公式2: P_droop(t) = clip(P_droop(t-1) + K_droop·(f_nom - f(t-1)), P_min, P_max)
        公式4: ΔP_i(t) = G_actual + P_droop + ΣP_ji - L_i
        公式5: 备用出力计算 (步骤 A/B/C)
        公式6: L_shed = max(0, |ΔP| - P_res)
        公式7: f_i(t) = f_i(t-1) + α·ΔP_post - β·(f_i(t-1) - f_nom)
        """
        # 如果没有提供上一时刻的频率，使用当前频率
        if freq_prev is None:
            freq_prev = {gid: g.frequency for gid, g in self.grids.items()}
        
        reserve_log = {}
        shed_log = {}
        freq_log = {}
        p_droop_log = {}  # 记录P_droop的计算过程
        P_in_sums = {}  # 记录每个电网的输入功率流
        
        # 0. 先更新P_droop (公式2)，在计算delta_P之前
        # 公式2: P_droop(t) = clip(P_droop(t-1) + K_droop·(f_nom - f(t-1)), P_min, P_max)
        for gid, g in self.grids.items():
            if g.status == GridStatus.COLLAPSE:
                p_droop_log[gid] = {
                    'P_droop_prev': g.P_droop,
                    'f_prev': freq_prev[gid],
                    'K_droop': g.K_droop,
                    'P_droop_raw': g.P_droop,
                    'P_droop_min': g.P_droop_min,
                    'P_droop_max': g.P_droop_max,
                    'P_droop_new': g.P_droop,
                    'reason': '瘫痪状态，不更新'
                }
                continue
            
            # Grid B 抽水状态：禁止调频，P_droop保持为0
            if gid == 'B' and g.is_pumping:
                g.P_droop = 0.0
                p_droop_log[gid] = {
                    'P_droop_prev': 0.0,
                    'f_prev': freq_prev[gid],
                    'K_droop': g.K_droop,
                    'P_droop_raw': 0.0,
                    'P_droop_min': g.P_droop_min,
                    'P_droop_max': g.P_droop_max,
                    'P_droop_new': 0.0,
                    'reason': '抽水状态，禁止调频'
                }
                continue
            
            f_prev_val = freq_prev[gid]
            P_droop_prev = g.P_droop
            p_droop_raw = P_droop_prev + g.K_droop * (F_NOM - f_prev_val)
            p_droop_raw = round(p_droop_raw, 10)
            P_droop_new = max(g.P_droop_min, min(g.P_droop_max, p_droop_raw))
            
            p_droop_log[gid] = {
                'P_droop_prev': P_droop_prev,
                'f_prev': f_prev_val,
                'K_droop': g.K_droop,
                'P_droop_raw': p_droop_raw,
                'P_droop_min': g.P_droop_min,
                'P_droop_max': g.P_droop_max,
                'P_droop_new': P_droop_new,
                'reason': '截断' if p_droop_raw != P_droop_new else '正常'
            }
            
            # 更新P_droop
            g.P_droop = P_droop_new
        
        # 1. 计算每个电网的功率不平衡 (公式4) - 未启用备用
        delta_Ps = {}
        for gid, g in self.grids.items():
            if g.status == GridStatus.COLLAPSE:
                delta_Ps[gid] = 0.0
                P_in_sums[gid] = 0.0
                continue
            
            # Grid B 抽水状态：不参与功率平衡计算
            if gid == 'B' and g.is_pumping:
                delta_Ps[gid] = 0.0
                P_in_sums[gid] = 0.0
                continue
            
            # 计算输入功率流
            # 对于并联模式: P_in = P_ji (line.to_id == gid 时为 +line.power)
            # 对于串联模式: 需要分别计算流入和流出
            #   - 如果电网是 to_id: 流入功率 = power_forward (from->to方向)
            #   - 如果电网是 from_id: 流入功率 = power_backward (to->from方向)
            P_in_sum = 0.0
            for line in self.lines.values():
                if line.mode == LineMode.SERIES:
                    # 串联模式: 两个方向独立
                    if line.to_id == gid:
                        # 从 from 流向 to，当前电网是 to，获得 power_forward
                        P_in_sum += line.power_forward
                    if line.from_id == gid:
                        # 从 to 流向 from，当前电网是 from，仅计入正向潮流流入
                        P_in_sum += line.power_backward
                else:
                    # 并联模式或断开模式: 使用原有逻辑
                    if line.to_id == gid:
                        P_in_sum += line.power
                    elif line.from_id == gid:
                        P_in_sum -= line.power
            
            P_in_sums[gid] = round(P_in_sum, 10)  # 消除浮点精度误差
            
            # 公式4: ΔP = G_actual + P_droop(t) + ΣP_ji - L
            # 注意: 此时使用当天更新后的P_droop值，P_res = 0
            delta_P = g.G_actual + g.P_droop + P_in_sum - g.L_actual
            delta_Ps[gid] = round(delta_P, 10)  # 消除浮点精度误差
        
        # 2. 步骤A: 计算备用出力 (公式5)
        for gid, g in self.grids.items():
            if g.status == GridStatus.COLLAPSE:
                continue
            
            # Grid B 抽水状态：禁止备用，P_res=0
            if gid == 'B' and g.is_pumping:
                g.P_res = 0.0
                reserve_log[gid] = {
                    'delta_P': 0.0,
                    'P_in': 0.0,
                    'P_available': 0.0,
                    'P_available_down': 0.0,
                    'P_res': 0.0,
                    'reason': '抽水状态，禁止备用',
                    'G_actual': 0.0,
                    'L_actual': 0.0,
                    'P_droop': 0.0,
                    'G_max': g.G_max
                }
                continue
            
            delta_P = delta_Ps[gid]
            
            # 计算可用上调备用容量: P_available(t) = max(0, G_max - G_actual - P_droop)
            P_available = max(0, g.G_max - g.G_actual - g.P_droop)
            reason = ""
            
            if delta_P < 0:
                # 若存在功率缺口 (ΔP < 0)，启用上调备用
                # P_cand_res = |ΔP|, P_res = min(P_cand_res, P_available)
                g.P_res = min(abs(delta_P), P_available)
                reason = "缺口，启用上调备用"
            elif delta_P > 0:
                # 若存在功率富余 (ΔP > 0)，启用下调备用
                if g.grid_type == GridType.NUCLEAR and not g.is_island:
                    # Grid C (核电) 非孤岛模式下保持基荷刚性，不允许下调备用
                    g.P_res = 0.0
                    reason = "核电基荷刚性，不允许下调备用"
                else:
                    # 其他电网可以下调，或 Grid C 孤岛模式下允许下调（调节棒下插）
                    # P_available_down(t) = max(0, G_actual + P_droop)
                    P_available_down = max(0, g.G_actual + g.P_droop)
                    g.P_res = -min(delta_P, P_available_down)
                    if g.grid_type == GridType.NUCLEAR and g.is_island:
                        reason = "孤岛模式，允许下调备用（调节棒下插）"
                    else:
                        reason = "富余，启用下调备用"
            else:
                g.P_res = 0.0
                reason = "平衡，无需备用"
            
            # 计算下调备用容量（用于报告显示）: P_available_down = max(0, G_actual + P_droop)
            P_available_down = max(0, g.G_actual + g.P_droop)
            
            reserve_log[gid] = {
                'delta_P': delta_P,
                'P_in': P_in_sums[gid],
                'P_available': P_available,
                'P_available_down': P_available_down,
                'P_res': g.P_res,
                'reason': reason,
                'G_actual': g.G_actual,
                'L_actual': g.L_actual,
                'P_droop': g.P_droop,
                'G_max': g.G_max
            }
        
        # 3. 重新计算含备用的功率平衡
        for gid, g in self.grids.items():
            if g.status == GridStatus.COLLAPSE:
                continue
            
            # Grid B 抽水状态：不参与切负荷计算
            if gid == 'B' and g.is_pumping:
                g.L_shed = 0.0
                shed_log[gid] = {
                    'L_shed': 0.0,
                    'delta_P_original': 0.0,
                    'delta_P_post': 0.0,
                    'P_res': 0.0
                }
                continue
            
            # ΔP_post = ΔP + P_res (公式5注释)
            delta_P_post = delta_Ps[gid] + g.P_res
            
            # 计算切负荷量 (公式6)
            # L_shed = max(0, -ΔP_post)，仅当 ΔP_post < 0 时
            if delta_P_post < 0:
                g.L_shed = max(0, -delta_P_post)
            else:
                g.L_shed = 0.0
            
            shed_log[gid] = {
                'L_shed': g.L_shed,
                'delta_P_original': delta_Ps[gid],
                'delta_P_post': delta_P_post,
                'P_res': g.P_res
            }
            
            # 判定"出力上限限制" (公式5步骤B)
            # 条件: G_actual + P_droop + P_res = G_max 且 L_shed > 0
            total_out = g.G_actual + g.P_droop + g.P_res
            if abs(total_out - g.G_max) < 1e-6 and g.L_shed > 0:
                g.limit_tags.add("出力上限限制")
            
            # 更新 delta_P_post 用于频率计算 (考虑切负荷后的实际缺口)
            # 注意: 切负荷减少了实际负荷，所以 delta_P_post 应该加上 L_shed
            delta_Ps[gid] = delta_P_post #+ g.L_shed
        
        # 4. 频率演化和一次调频 (公式2, 7)
        for gid, g in self.grids.items():
            if g.status == GridStatus.COLLAPSE: 
                continue
            
            # Grid B 抽水状态：频率冻结，保持进入抽水前的最后频率值
            if gid == 'B' and g.is_pumping:
                freq_log[gid] = {
                    'f_prev': freq_prev[gid],
                    'delta_P_post': 0.0,
                    'f_next': freq_prev[gid],
                    'reason': '抽水状态，频率冻结'
                }
                g.frequency = freq_prev[gid]
                continue
            
            dP = delta_Ps[gid]
            f_prev = freq_prev[gid]
            
            # 公式7: f(t) = f(t-1) + α·ΔP_post - β·(f(t-1) - 50)
            f_next = f_prev + ALPHA * dP - BETA * (f_prev - F_NOM)
            f_next = round(f_next, 10)  # 消除浮点精度误差
            
            freq_log[gid] = {
                'f_prev': f_prev,
                'delta_P_post': round(dP, 10),  # 消除浮点精度误差
                'f_next': f_next
            }
            
            # 更新频率 (P_droop已在计算delta_P之前更新)
            g.frequency = f_next
        
        # 记录计算过程
        if hasattr(self, 'daily_calc_log'):
            self.daily_calc_log['p_droop_update'] = p_droop_log
            self.daily_calc_log['reserve_activation'] = reserve_log
            self.daily_calc_log['load_shedding'] = shed_log
            self.daily_calc_log['frequency_evolution'] = freq_log
        
        # 5. 四位精度处理 (公式12)
        self._apply_precision()
    
    def _apply_precision(self):
        """数值精度处理 (公式13)
        
        根据 system_prompt 公式13:
        - 频率变量：保留4位小数
        - 其他功率分量：保留2位小数
        
        使用 precise_round 实现精确的四舍五入，避免银行家舍入问题。
        
        公式6写回顺序：先用未舍入的 L_actual、L_shed 计算写回值，再分别舍入。
        这样避免 round(L) - round(L_shed) ≠ round(L - L_shed) 的精度丢失。
        """
        for g in self.grids.values():
            # 公式6: 先用未舍入值计算写回负荷，再四舍五入（公式13）
            g.L_writeback = precise_round(g.L_actual - g.L_shed, 2)
            
            g.frequency = precise_round(g.frequency, 4)  # 频率保留4位小数
            g.G_actual = precise_round(g.G_actual, 2)
            g.L_actual = precise_round(g.L_actual, 2)
            g.P_droop = precise_round(g.P_droop, 2)
            g.P_res = precise_round(g.P_res, 2)
            g.L_shed = precise_round(g.L_shed, 2)
        
        for line in self.lines.values():
            line.power = precise_round(line.power, 2)
            line.power_forward = precise_round(line.power_forward, 2)
            line.power_backward = precise_round(line.power_backward, 2)

    def _assess_status(self):
        """状态判定与处理 (system_prompt 第八章)
        
        状态机:
        1. Safe: U_fallback < 0.2 且 f ∈ [49.8, 50.2]
        2. Pre-warning: 0.2 <= U_fallback < 0.5 或存在未修复故障
        3. Critical: U_fallback >= 0.5 或 f 偏离 > 0.5Hz
        4. Collapse: f < 49.0 或 f > 51.0
        5. E-Grid Takeover: Collapse状态持续 >= 2天
        """
        status_log = {}
        
        for gid, g in self.grids.items():
            old_status = g.status.value
            reason = ""
            
            if g.status == GridStatus.E_GRID_TAKEOVER:
                status_log[gid] = {
                    'u_fallback': 0,
                    'freq_deviation': 0,
                    'old_status': old_status,
                    'new_status': g.status.value,
                    'reason': '已托管，状态不变'
                }
                continue
            
            # Grid B 抽水状态：状态冻结，保持进入抽水前的状态
            if gid == 'B' and g.is_pumping:
                status_log[gid] = {
                    'u_fallback': 0,
                    'freq_deviation': 0,
                    'old_status': old_status,
                    'new_status': g.status.value,
                    'reason': '抽水状态，状态冻结'
                }
                continue
                
            if g.status == GridStatus.COLLAPSE:
                g.collapse_days += 1
                if g.collapse_days >= 2:
                    g.status = GridStatus.E_GRID_TAKEOVER
                    reason = f'瘫痪持续{g.collapse_days}天，触发国网托管'
                else:
                    reason = f'瘫痪第{g.collapse_days}天'
                # 瘫痪/国网托管状态下，当日负荷全部切除
                g.L_shed = g.L_actual
                status_log[gid] = {
                    'u_fallback': 0,
                    'freq_deviation': abs(g.frequency - F_NOM),
                    'old_status': old_status,
                    'new_status': g.status.value,
                    'reason': reason
                }
                continue

            # 瘫痪判定: f < 49.0 或 f > 51.0
            if g.frequency < 49.0 or g.frequency > 51.0:
                g.status = GridStatus.COLLAPSE
                g.collapse_days = 1  # 瘫痪当日计为第1天
                reason = f'频率{g.frequency:.2f}Hz超出[49,51]范围，触发瘫痪'
                # 强制解列，但当日数值保留
                for lid in self.lines:
                    if self.lines[lid].from_id == gid or self.lines[lid].to_id == gid:
                        self.lines[lid].mode = LineMode.OPEN
                        self.lines[lid].open_reason = f'Grid {gid} 频率超限瘫痪，强制解列'
                # 瘫痪触发当日，负荷全部切除，确保次日L_actual归零
                g.L_shed = g.L_actual
                status_log[gid] = {
                    'u_fallback': 0,
                    'freq_deviation': abs(g.frequency - F_NOM),
                    'old_status': old_status,
                    'new_status': g.status.value,
                    'reason': reason
                }
                continue

            # 计算 U_fallback (公式 8)
            u_fallback = self._calculate_u_fallback(g)
            
            # 频率偏离
            freq_deviation = abs(g.frequency - F_NOM)
            
            # 状态机判定
            if u_fallback >= 0.5 or freq_deviation > 0.5:
                g.status = GridStatus.CRITICAL
                g.limit_tags.add("状态触发运行限制")
                g.decay = max(0, g.decay - 0.05)
                if u_fallback >= 0.5:
                    reason = f'U_fallback={u_fallback:.4f}>=0.5，触发Critical'
                else:
                    reason = f'频率偏离{freq_deviation:.2f}Hz>0.5，触发Critical'
                
            elif u_fallback >= 0.2:
                g.status = GridStatus.PRE_WARNING
                g.limit_tags.add("状态触发运行限制")
                reason = f'U_fallback={u_fallback:.4f}∈[0.2,0.5)，触发Pre-warning'
                
            else:
                if freq_deviation <= 0.2:
                    g.status = GridStatus.SAFE
                    reason = f'U_fallback={u_fallback:.4f}<0.2且频率偏离{freq_deviation:.2f}Hz<=0.2，Safe'
                else:
                    g.status = GridStatus.PRE_WARNING
                    reason = f'频率偏离{freq_deviation:.2f}Hz∈(0.2,0.5]，Pre-warning'
            
            status_log[gid] = {
                'u_fallback': u_fallback,
                'freq_deviation': freq_deviation,
                'old_status': old_status,
                'new_status': g.status.value,
                'reason': reason
            }
        
        # 记录状态评估过程
        if hasattr(self, 'daily_calc_log'):
            self.daily_calc_log['status_assessment'] = status_log
    
    def _calculate_u_fallback(self, g: GridState) -> float:
        """计算 U_fallback (公式9)
        
        U_fallback = w1 * (P_droop / (0.1 * G_base)) +
                     w2 * (P_res / (G_max - (G_actual + P_droop))) +
                     w3 * (L_shed / L)
        
        根据 system_prompt 第564行:
        当备用项分母 G_{i,max}(t) - (G_i^{actual}(t) + P_i^{droop}(t)) <= 0 时，
        该备用项对 U_i^{fallback}(t) 的贡献记为 0。
        """
        # Term 1: P_droop / (0.1 * G_base)
        term1 = g.P_droop / g.P_droop_max if g.P_droop_max > 0 else 0
        
        # Term 2: P_res / (G_max - (G_actual + P_droop))
        # 根据 system_prompt: 分母 <= 0 时，该项贡献为 0
        P_available = g.G_max - (g.G_actual + g.P_droop)
        if P_available <= 0:
            term2 = 0
        else:
            term2 = g.P_res / P_available
        
        # Term 3: L_shed / L
        term3 = g.L_shed / g.L_actual if g.L_actual > 0 else 0
        
        result = W1 * term1 + W2 * term2 + W3 * term3
        return round(result, 10)  # 消除浮点精度误差

    def _apply_environment(self):
        """应用环境和政策影响 (system_prompt 第七章)"""
        
        # 更新温度历史
        self.temp_history.append(self.global_temp)
        
        # 初始化事件影响日志 (用于Step 2报告)
        if hasattr(self, 'daily_calc_log'):
            self.daily_calc_log['event_effects'] = []
        
        # 1. 政策处理
        for p in self.policies:
            # 只有未被停止且未激活的政策才能被自动激活
            if not p.stopped and not p.active and self.t >= p.trigger_day:
                p.active = True
                
            if p.active:
                if p.id == 'P-101':  # 蓝天保卫战 / 环保限产
                    old_G_max = self.grids['A'].G_max
                    self.grids['A'].G_max = self.grids['A'].G_base_cap * 0.6
                    self.grids['A'].price_base = 0.6
                    
                    effects_list = [{
                        'grid': 'A',
                        'param': 'G_max',
                        'old_value': old_G_max,
                        'new_value': self.grids['A'].G_max,
                        'formula': f"G_max = G_base × 0.6 = {self.grids['A'].G_base_cap:.2f} × 0.6",
                        'reason': "环保限产政策，火电最大出力限制为60%"
                    }]
                    
                    # 只有当 G_actual 来自默认值时，才需要同步约束
                    # 如果 G_actual 是从前一天继承的，则不需要更新
                    g_actual_from_default = getattr(self.grids['A'], '_g_actual_from_default', True)
                    if g_actual_from_default and self.grids['A'].G_actual > self.grids['A'].G_max:
                        old_G_actual = self.grids['A'].G_actual
                        self.grids['A'].G_actual = self.grids['A'].G_max
                        effects_list.append({
                            'grid': 'A',
                            'param': 'G_actual',
                            'old_value': old_G_actual,
                            'new_value': self.grids['A'].G_actual,
                            'formula': f"G_actual = min(G_actual, G_max) = min({old_G_actual:.2f}, {self.grids['A'].G_max:.2f})",
                            'reason': "G_actual 来自默认值，受 G_max 约束同步下调"
                        })
                    
                    # 记录政策对G_max的影响
                    if hasattr(self, 'daily_calc_log') and 'event_effects' in self.daily_calc_log:
                        effects = {
                            'event_type': 'P-101 (蓝天保卫战)',
                            'effects': effects_list
                        }
                        self.daily_calc_log['event_effects'].append(effects)
                    
                elif p.id == 'P-205':  # 高新人才引进计划
                    if self.t >= p.trigger_day:
                        delta_days = self.t - p.trigger_day
                        # 计算当前应达到的level（每5天触发一次）
                        current_level = delta_days // 5
                        # 获取已累计的level（初始为0）
                        if not hasattr(p, 'accumulated_level'):
                            p.accumulated_level = 0
                        
                        # 检查是否有新的level增长
                        if current_level > p.accumulated_level:
                            # 计算需要新增的增量
                            level_increment = current_level - p.accumulated_level
                            old_L_base_cap = self.grids['D'].L_base_cap
                            # 永久修改 L_base_cap
                            self.grids['D'].L_base_cap += level_increment * 200.0
                            
                            # 记录触发历史（用于坐标计算）
                            self.p205_trigger_history.append((self.t, level_increment))
                            
                            effects_list = [{
                                'grid': 'D',
                                'param': 'L_base_cap',
                                'old_value': old_L_base_cap,
                                'new_value': self.grids['D'].L_base_cap,
                                'formula': f"L_base_cap = {old_L_base_cap:.2f} + {level_increment} × 200 = {self.grids['D'].L_base_cap:.2f}",
                                'reason': f"人才引进政策，第{delta_days}天，level={current_level}，永久增加基础负荷（全局累计={self.p205_global_accumulated_level}）"
                            }]
                            
                            old_L_actual = self.grids['D'].L_actual
                            self.grids['D'].L_actual += level_increment * 200.0
                            effects_list.append({
                                'grid': 'D',
                                'param': 'L_actual',
                                'old_value': old_L_actual,
                                'new_value': self.grids['D'].L_actual,
                                'formula': f"L_actual = {old_L_actual:.2f} + {level_increment} × 200 = {self.grids['D'].L_actual:.2f}",
                                'reason': f"人才引进政策同步更新实际负荷（当日新增增量计入当日负荷）"
                            })
                            
                            p.accumulated_level = current_level
                            
                            # 记录政策对L_base_cap的影响
                            if hasattr(self, 'daily_calc_log') and 'event_effects' in self.daily_calc_log:
                                effects = {
                                    'event_type': 'P-205 (高新人才引进计划)',
                                    'effects': effects_list
                                }
                                self.daily_calc_log['event_effects'].append(effects)
                        
                elif p.id == 'P-301':  # 居民专用线保供
                    pass  # 通过 _check_rigid_load_violation 实现
        
        # 2. 自动检测高温/寒潮状态 (基于历史温度自动触发，无需CFG事件)
        self._auto_process_temperature_events()
        
        # 注意：地震/台风事件在 _apply_environment_phase2() 中处理
        # 因为它们依赖当日坐标和线路路径，需要在坐标更新后执行

    def _apply_environment_phase2(self):
        """应用依赖坐标/路径的事件：地震和台风 (system_prompt 第七章)
        
        此方法在 _update_grid_coordinates() 之后调用，
        确保地震使用当日 Grid C 坐标计算加权距离，
        台风使用当日联络线路径判断是否断开。
        """
        # 处理地震/台风事件
        for e in self.events:
            if self.t < e.trigger_day:
                 continue 
            e.active = True
            if e.type == 'E-TYPHOON':
                if self._is_typhoon_dissipated(e):
                    continue
                self._process_typhoon_event(e)
            elif e.type == 'E-EARTHQUAKE':
                self._process_earthquake_event(e)
            # E-HEATWAVE 和 E-COLDWAVE 已由 _apply_environment phase1 自动处理



    def _is_heatwave_triggered(self) -> bool:
        """检查是否触发高温状态 (连续3天 > 35°C)"""
        if len(self.temp_history) < 3:
            return False
        return all(t > 35 for t in self.temp_history[-3:])
    
    def _is_coldwave_triggered(self) -> bool:
        """检查是否触发寒潮状态 (连续2天 < 10°C)"""
        if len(self.temp_history) < 2:
            return False
        return all(t < 10 for t in self.temp_history[-2:])
    
    def _auto_process_temperature_events(self):
        """自动处理高温/寒潮事件 (基于历史温度自动触发，无需CFG事件)
        
        高温: 连续3天 > 35°C
        寒潮: 连续2天 < 10°C
        
        物理影响：仅在触发对应状态的当日生效
        """
        # 高温影响 (连续3天 > 35°C)
        if self._is_heatwave_triggered():
            self.events.append(Event(type="E-HEATWAVE", trigger_day=self.t, params={'temperature': self.temp_history[-3:]},
                                     active=True))
            temp = self.global_temp
            
            # 记录事件影响前的原始值
            effects = {
                'event_type': 'E-HEATWAVE',
                'temperature': temp,
                'effects': []
            }
            
            # 全网负荷上升
            load_factor = 1 + 0.01 * (temp - 35)
            for gid, g in self.grids.items():
                old_L = g.L_actual
                g.L_actual *= load_factor
                effects['effects'].append({
                    'grid': gid,
                    'param': 'L_actual',
                    'old_value': old_L,
                    'new_value': g.L_actual,
                    'formula': f"L_actual × (1 + 0.01 × ({temp} - 35)) = {old_L:.2f} × {load_factor:.4f}",
                    'reason': f"高温({temp}°C)致全网负荷上升"
                })
            
            # Grid B 最大出力下降 70%
            old_G_max_B = self.grids['B'].G_max
            self.grids['B'].G_max *= 0.70
            effects['effects'].append({
                'grid': 'B',
                'param': 'G_max',
                'old_value': old_G_max_B,
                'new_value': self.grids['B'].G_max,
                'formula': f"G_max × 0.70 = {old_G_max_B:.2f} × 0.70",
                'reason': "高温致水电最大出力下降"
            })
            # 只有当 G_actual 来自默认值时，才需要同步约束
            g_actual_from_default_B = getattr(self.grids['B'], '_g_actual_from_default', True)
            if g_actual_from_default_B and self.grids['B'].G_actual > self.grids['B'].G_max:
                old_G_actual_B = self.grids['B'].G_actual
                self.grids['B'].G_actual = self.grids['B'].G_max
                effects['effects'].append({
                    'grid': 'B',
                    'param': 'G_actual',
                    'old_value': old_G_actual_B,
                    'new_value': self.grids['B'].G_actual,
                    'formula': f"G_actual = min(G_actual, G_max) = min({old_G_actual_B:.2f}, {self.grids['B'].G_max:.2f})",
                    'reason': "G_actual 来自默认值，受 G_max 约束同步下调"
                })
            
            # Grid A 最大出力下降 95%
            old_G_max_A = self.grids['A'].G_max
            self.grids['A'].G_max *= 0.95
            effects['effects'].append({
                'grid': 'A',
                'param': 'G_max',
                'old_value': old_G_max_A,
                'new_value': self.grids['A'].G_max,
                'formula': f"G_max × 0.95 = {old_G_max_A:.2f} × 0.95",
                'reason': "高温致火电最大出力下降"
            })
            # 只有当 G_actual 来自默认值时，才需要同步约束
            g_actual_from_default_A = getattr(self.grids['A'], '_g_actual_from_default', True)
            if g_actual_from_default_A and self.grids['A'].G_actual > self.grids['A'].G_max:
                old_G_actual_A = self.grids['A'].G_actual
                self.grids['A'].G_actual = self.grids['A'].G_max
                effects['effects'].append({
                    'grid': 'A',
                    'param': 'G_actual',
                    'old_value': old_G_actual_A,
                    'new_value': self.grids['A'].G_actual,
                    'formula': f"G_actual = min(G_actual, G_max) = min({old_G_actual_A:.2f}, {self.grids['A'].G_max:.2f})",
                    'reason': "G_actual 来自默认值，受 G_max 约束同步下调"
                })
            
            # 记录到日志
            if hasattr(self, 'daily_calc_log') and 'event_effects' in self.daily_calc_log:
                self.daily_calc_log['event_effects'].append(effects)
        
        # 寒潮影响 (连续2天 < 10°C)
        if self._is_coldwave_triggered():
            self.events.append(Event(type="E-COLDWAVE", trigger_day=self.t, params={'temperature': self.temp_history[-2:]},
                                     active=True))
            # print(f'-------------------寒潮事件触发 (自动检测): Day {self.t}')
            temp = self.global_temp
            
            # 记录事件影响前的原始值
            effects = {
                'event_type': 'E-COLDWAVE',
                'temperature': temp,
                'effects': []
            }
            
            # 全网负荷上升
            load_factor = 1 + 0.02 * (10 - temp)
            for gid, g in self.grids.items():
                old_L = g.L_actual
                g.L_actual *= load_factor
                effects['effects'].append({
                    'grid': gid,
                    'param': 'L_actual',
                    'old_value': old_L,
                    'new_value': g.L_actual,
                    'formula': f"L_actual × (1 + 0.02 × (10 - {temp})) = {old_L:.2f} × {load_factor:.4f}",
                    'reason': f"寒潮({temp}°C)致全网负荷上升"
                })
            
            # Grid A 最大出力小幅提升（G_max 增加不需要约束 G_actual）
            old_G_max_A = self.grids['A'].G_max
            self.grids['A'].G_max *= 1.2
            effects['effects'].append({
                'grid': 'A',
                'param': 'G_max',
                'old_value': old_G_max_A,
                'new_value': self.grids['A'].G_max,
                'formula': f"G_max × 1.2 = {old_G_max_A:.2f} × 1.2",
                'reason': "寒潮致火电最大出力提升"
            })

            # Grid D 光伏最大出力下降
            old_G_max_D = self.grids['D'].G_max
            self.grids['D'].G_max *= 0.70
            effects['effects'].append({
                'grid': 'D',
                'param': 'G_max',
                'old_value': old_G_max_D,
                'new_value': self.grids['D'].G_max,
                'formula': f"G_max × 0.70 = {old_G_max_D:.2f} × 0.70",
                'reason': "寒潮致光伏最大出力下降"
            })
            # 只有当 G_actual 来自默认值时，才需要同步约束
            g_actual_from_default_D = getattr(self.grids['D'], '_g_actual_from_default', True)
            if g_actual_from_default_D and self.grids['D'].G_actual > self.grids['D'].G_max:
                old_G_actual_D = self.grids['D'].G_actual
                self.grids['D'].G_actual = self.grids['D'].G_max
                effects['effects'].append({
                    'grid': 'D',
                    'param': 'G_actual',
                    'old_value': old_G_actual_D,
                    'new_value': self.grids['D'].G_actual,
                    'formula': f"G_actual = min(G_actual, G_max) = min({old_G_actual_D:.2f}, {self.grids['D'].G_max:.2f})",
                    'reason': "G_actual 来自默认值，受 G_max 约束同步下调"
                })
            
            # 记录到日志
            if hasattr(self, 'daily_calc_log') and 'event_effects' in self.daily_calc_log:
                self.daily_calc_log['event_effects'].append(effects)

    def _is_typhoon_dissipated(self, e: Event, day: Optional[int] = None) -> bool:
        """radius <= 0 的台风事件是同名台风的消散标记：标记本身不产生影响，
        更早登记的同名台风自标记的 trigger_day 起不再生效。
        已被该台风断开的线路不会因消散而自动恢复。"""
        if e.params.get('radius', 10) <= 0:
            return True
        name = e.params.get('name')
        if name is None:
            return False
        day = self.t if day is None else day
        return any(
            o is not e and o.type == 'E-TYPHOON' and o.params.get('name') == name
            and o.params.get('radius', 10) <= 0 and e.trigger_day < o.trigger_day <= day
            for o in self.events
        )

    def _process_typhoon_event(self, e: Event):
        """台风事件处理 (system_prompt 7.3 E-TYPHOON)
        
        使用圆形影响范围（马赛克化圆形）:
        - 强影响半径: R_strong = round(Radius / 2)
        - 弱影响半径: R_weak = round(Radius)
        
        影响判定:
        - 强影响区: 线路路径任意一步落入 → 线路不可用
        - 弱影响区: 仅对 Grid D 送电线路生效
        """
        center = e.params.get('center', (0, 0))
        movement = e.params.get('movement', (0, 0))
        speed = e.params.get('speed', 1)
        radius = e.params.get('radius', 10)
        
        # 计算当日台风中心坐标
        days_active = self.t - e.trigger_day
        if days_active == 0:
            # 首日使用输入的中心坐标
            curr_center = (int(center[0]), int(center[1]))
        else:
            # 后续日按移动参数推进
            x_tilde = center[0] + speed * movement[0] * days_active
            y_tilde = center[1] + speed * movement[1] * days_active
            curr_center = (
                max(0, min(50, round(x_tilde))),
                max(0, min(50, round(y_tilde)))
            )
        
        # 更新事件参数中的中心坐标
        e.params['current_center'] = curr_center
        
        # 检查台风是否已离开地图
        if not (0 <= curr_center[0] <= self.width and 0 <= curr_center[1] <= self.height):
            e.active = False
            return
        
        # 台风穿越云断山脉(T-M1)时的强度衰减逻辑
        # T-M1范围: x ∈ [15, 35], y ∈ [0, 50]
        # 条件: 从东向西移动(movement[0] < 0)时，每前进1格衰减10%
        effective_radius = radius
        if movement[0] < 0:  # 从东向西移动
            start_x = int(round(center[0]))
            curr_x = int(round(max(0, min(50, center[0] + speed * movement[0] * days_active))))
            # 台风路径 [curr_x, start_x] 与山脉 [15, 35] 的重叠区间长度即为穿越格数
            overlap_east = min(start_x, 35)
            overlap_west = max(curr_x, 15)
            grids_in_mountain = max(0, overlap_east - overlap_west)
            if grids_in_mountain > 0:
                effective_radius = radius * (0.9 ** grids_in_mountain)
        
        # 计算影响半径（使用衰减后的有效半径）
        R_weak = round(effective_radius)
        R_strong = round(effective_radius / 2)
        
        # 检查线路是否受影响
        for line in self.lines.values():
            strong_impact = False
            weak_impact = False
            
            # 检查线路路径上的每个点
            for px, py in line.path:
                dist_sq = (px - curr_center[0])**2 + (py - curr_center[1])**2
                
                if dist_sq <= R_strong**2:
                    strong_impact = True
                    break
                elif dist_sq <= R_weak**2:
                    weak_impact = True
            
            # 强影响区: 所有线路不可用
            if strong_impact:
                line.mode = LineMode.OPEN
                line.open_reason = '台风强影响区，线路不可用'
                line.power = 0
                line.power_forward = 0
                line.power_backward = 0
            # 弱影响区: 仅对 Grid D 送电线路生效
            elif weak_impact:
                if line.from_id == 'D' or line.to_id == 'D':
                    # 用 f(t-1) 频差判断理论功率方向（此时 g.frequency 仍为 f(t-1)）
                    f_from = self.grids[line.from_id].frequency
                    f_to = self.grids[line.to_id].frequency
                    theoretical_direction = f_from - f_to
                    if (line.from_id == 'D' and theoretical_direction > 0) or \
                       (line.to_id == 'D' and theoretical_direction < 0):
                        line.mode = LineMode.OPEN
                        line.open_reason = '台风弱影响区，Grid D 送电线路断开'
                        line.power = 0
                        line.power_forward = 0
                        line.power_backward = 0


    def _process_earthquake_event(self, e: Event):
        """地震事件处理 - 触发Grid C孤岛模式 (system_prompt 7.1)"""
        magnitude = e.params.get('magnitude', 0)
        epicenter = e.params.get('epicenter', (0, 0))
        
        if magnitude >= 5.0:
            d_to_C, _ = self._dijkstra(epicenter, self.grids['C'].coord)
            # d_to_C = 12
            # print('###########地震距离', d_to_C, epicenter, self.grids['C'].coord, path)
            
            if d_to_C <= 15:
                self.grids['C'].is_island = True
                
                # 记录事件影响
                effects = {
                    'event_type': 'E-EARTHQUAKE',
                    'magnitude': magnitude,
                    'epicenter': epicenter,
                    'distance_to_C': d_to_C,
                    'effects': []
                }
                
                for lid, line in self.lines.items():
                    if line.from_id == 'C' or line.to_id == 'C':
                        line.mode = LineMode.OPEN
                        line.open_reason = f'地震触发 Grid C 孤岛模式，震级{magnitude}，距离{d_to_C:.1f}'
                        line.power = 0
                        line.power_forward = 0
                        line.power_backward = 0
                
                g_C = self.grids['C']
                old_G_actual = g_C.G_actual
                old_L_shed = g_C.L_shed
                
                if g_C.G_actual > g_C.L_actual:
                    g_C.G_actual = g_C.L_actual
                    effects['effects'].append({
                        'grid': 'C',
                        'param': 'G_actual',
                        'old_value': old_G_actual,
                        'new_value': g_C.G_actual,
                        'formula': f"G_actual = min(G_actual, L_actual) = min({old_G_actual:.2f}, {g_C.L_actual:.2f})",
                        'reason': "地震触发孤岛模式，出力调整为自发自用"
                    })
                elif g_C.G_actual < g_C.L_actual:
                    g_C.L_shed = g_C.L_actual - g_C.G_actual
                    effects['effects'].append({
                        'grid': 'C',
                        'param': 'L_shed',
                        'old_value': old_L_shed,
                        'new_value': g_C.L_shed,
                        'formula': f"L_shed = L_actual - G_actual = {g_C.L_actual:.2f} - {g_C.G_actual:.2f}",
                        'reason': "地震触发孤岛模式，出力不足需切负荷"
                    })
                
                # 记录到日志
                if hasattr(self, 'daily_calc_log') and 'event_effects' in self.daily_calc_log:
                    self.daily_calc_log['event_effects'].append(effects)

    def _calculate_default_cost(self):
        """计算系统默认状态下的基准成本
        
        默认状态定义:
        - 频率: 50.0 Hz (额定频率, 无频差)
        - 出力: G_actual = G_base_cap (基础出力)
        - 调频: P_droop = 0, P_res = 0
        - 负荷: L_actual = L_base_cap (基础负荷)
        - 线路: 所有线路并联模式, 因频差为0故潮流为0, 网损为0
        - 状态: 无 CRITICAL, 无 E-Grid 接管
        
        因此默认基准成本 = Σ(G_base_cap_i * 1000 * 24 * price_i)
        """
        default_cost = 0.0
        for g in self.grids.values():
            # 默认出力 = G_base_cap, P_droop = 0, P_res = 0
            if g.grid_id != 'C':
                gen_mw = min([g.G_base_cap, g.L_base_cap])  # 默认出力不超过基础负荷
            else:
                gen_mw = g.G_base_cap
            gen_kwh = gen_mw * 1000.0 * 24.0
            default_cost += gen_kwh * g.price_base
        
        # 默认状态下: 网损=0 (无频差无潮流), 罚单=0, E-Grid=0
        self.base_cost = round(default_cost, 2)

    def _calculate_costs(self):
        """日终经济结算 (system_prompt 公式 6.2)
        
        Cost_total = Σ(G_i * Price_i) + P_loss * Price_waste + Cost_penalty + Cost_E_grid
        """
        day_cost = 0.0
        cost_log = {
            'generation_costs': {},
            'loss_cost': 0.0,
            'penalty_cost': 0.0,
            'e_grid_cost': 0.0
        }
        
        # 1. 发电成本
        for g in self.grids.values():
            if g.status in [GridStatus.COLLAPSE, GridStatus.E_GRID_TAKEOVER]:
                continue
            if g.grid_id == 'B' and g.is_pumping:
                continue  # 抽水状态不产生发电成本
            
            # G_i = max(0, G_actual + P_droop + P_res)
            gen_mw = max(0, g.G_actual + g.P_droop + g.P_res)
            gen_kwh = gen_mw * 1000.0 * 24.0
            gen_cost = gen_kwh * g.price
            day_cost += gen_cost
            
            cost_log['generation_costs'][g.grid_id] = {
                'gen_mw': gen_mw,
                'price': g.price,
                'cost': gen_cost
            }
            
        # 2. 网损成本 (公式 11)
        # 公式: P_loss_ij = k_ij × (P_ij / 1000)^2 × √d_ij
        # 其中 d_ij 为线路最小加权阻力距离（Dijkstra算法计算）
        # 注意: 串联模式下，两个方向的传输都会产生损耗，需要分别计算
        total_loss_mw = 0.0
        line_loss_details = {}  # 记录各线路网损详情
        
        for line in self.lines.values():
            is_line_open = (line.mode == LineMode.OPEN)
            
            if line.mode == LineMode.SERIES and not is_line_open:
                # 串联模式: 两个方向分别计算损耗
                sqrt_dist = math.sqrt(line.distance)
                loss_forward = 0.0
                loss_backward = 0.0
                
                if abs(line.power_forward) > 1e-3:
                    power_pu_forward = line.power_forward / 1000.0
                    loss_forward = line.loss_coeff * (power_pu_forward ** 2) * sqrt_dist
                
                if abs(line.power_backward) > 1e-3:
                    power_pu_backward = line.power_backward / 1000.0
                    loss_backward = line.loss_coeff * (power_pu_backward ** 2) * sqrt_dist
                
                loss_mw_raw = loss_forward + loss_backward
                loss_mw = precise_round(loss_mw_raw, 4)
                total_loss_mw += loss_mw
                
                line_loss_details[line.line_id] = {
                    'from_id': line.from_id,
                    'to_id': line.to_id,
                    'mode': 'Series',
                    'power_forward': line.power_forward,
                    'power_backward': line.power_backward,
                    'power': line.power,
                    'loss_coeff': line.loss_coeff,
                    'distance': line.distance,
                    'sqrt_distance': sqrt_dist,
                    'loss_forward': loss_forward,
                    'loss_backward': loss_backward,
                    'loss_mw_raw': loss_mw_raw,
                    'loss_mw': loss_mw,
                    'is_open': False,
                    'no_power': abs(line.power_forward) < 1e-3 and abs(line.power_backward) < 1e-3
                }
            elif abs(line.power) > 1e-3 and not is_line_open:
                # 并联模式或其他模式: 原有逻辑
                power_pu = abs(line.power) / 1000.0  # 使用绝对值
                sqrt_dist = math.sqrt(line.distance)
                loss_mw_raw = line.loss_coeff * (power_pu ** 2) * sqrt_dist
                loss_mw = precise_round(loss_mw_raw, 4)
                total_loss_mw += loss_mw
                
                line_loss_details[line.line_id] = {
                    'from_id': line.from_id,
                    'to_id': line.to_id,
                    'mode': line.mode.value if hasattr(line.mode, 'value') else str(line.mode),
                    'power': line.power,
                    'loss_coeff': line.loss_coeff,
                    'distance': line.distance,
                    'sqrt_distance': sqrt_dist,
                    'loss_mw_raw': loss_mw_raw,
                    'loss_mw': loss_mw,
                    'is_open': False,
                    'no_power': False
                }
            else:
                line_loss_details[line.line_id] = {
                    'from_id': line.from_id,
                    'to_id': line.to_id,
                    'mode': line.mode.value if hasattr(line.mode, 'value') else str(line.mode),
                    'power': line.power,
                    'loss_coeff': line.loss_coeff,
                    'distance': line.distance,
                    'sqrt_distance': math.sqrt(line.distance),
                    'loss_mw': 0.0,
                    'is_open': is_line_open,
                    'no_power': not is_line_open  # 非断开状态下功率为0，则为无功率流动
                }
        
        total_loss_mw = precise_round(total_loss_mw, 4)
        total_loss_kwh = total_loss_mw * 24.0 * 1000.0
        loss_cost = total_loss_kwh * PRICE_WASTE
        day_cost += loss_cost
        cost_log['loss_cost'] = loss_cost
        cost_log['total_loss_mw'] = total_loss_mw
        cost_log['line_loss_details'] = line_loss_details
        
        # 3. Critical状态罚单 (每个电网100万/天)
        crit_count = sum(1 for g in self.grids.values() if g.status == GridStatus.CRITICAL)
        self.cost_penalty = crit_count * PENALTY_PER_GRID
        day_cost += self.cost_penalty
        cost_log['penalty_cost'] = self.cost_penalty
        
        # 4. E-Grid介入费用
        self.cost_e_grid = 0.0
        for g in self.grids.values():
            if g.status == GridStatus.E_GRID_TAKEOVER:
                deficit_kwh = g.L_base_cap * 24.0 * 1000.0
                cost = deficit_kwh * E_GRID_PRICE
                self.cost_e_grid += cost
                day_cost += cost
        cost_log['e_grid_cost'] = self.cost_e_grid
        
        # 记录成本计算过程
        if hasattr(self, 'daily_calc_log'):
            self.daily_calc_log['cost_breakdown'] = cost_log
        
        # 两位精度
        self.daily_cost = round(day_cost, 2)
        self.total_cost = round(self.total_cost + self.daily_cost, 2)
        self.cost_penalty = round(self.cost_penalty, 2)
        self.cost_e_grid = round(self.cost_e_grid, 2)

    def _check_line_overload(self):
        """检查线路过载并执行物理熔断 (system_prompt 5.2)
        
        物理熔断: 若 P_ij(t) >= P_max 持续 2 天，线路强制 Open
        """
        for lid, line in self.lines.items():
            if line.mode == LineMode.OPEN:
                continue
            
            # 对于串联模式，检查两个方向的功率
            if line.mode == LineMode.SERIES:
                max_power = max(line.power_forward, line.power_backward)
            else:
                max_power = abs(line.power)
            
            if max_power >= line.capacity:
                self.line_overload_days[lid] += 1
                if self.line_overload_days[lid] >= 2:
                    line.mode = LineMode.OPEN
                    line.open_reason = f'线路过载熔断，功率{max_power:.2f}MW>=容量{line.capacity:.2f}MW持续2天'
                    line.power = 0
                    line.power_forward = 0
                    line.power_backward = 0
            else:
                self.line_overload_days[lid] = 0

    def _check_cost_out_of_control(self):
        """成本失控判定 (公式 11 注释)
        
        判定条件:
        1. 当日成本高于第0天成本的15%
        2. 或 E-Grid费用超过1000万
        """
        if self.base_cost is not None:
            if self.daily_cost > self.base_cost * 1.15:
                self.cost_out_of_control = True
        
        if self.cost_e_grid > 10000000:  # 1000万
            self.cost_out_of_control = True

    def step(self, actions: List[Dict]):
        """执行推演 (支持多天推进)
        
        该方法处理动作列表并推进时间：
        1. OBS动作：提取温度更新和时间推进天数
        2. CFG动作：调用统一的 process_config_action 处理
        """
        days_to_advance = 0
        for act in actions:
            if act.get('type') == 'OBS':
                if 'time_advance' in act:
                    days_to_advance = act['time_advance']
                if 'temperature' in act:
                    self.global_temp = act['temperature']
                if 'temperature_update' in act:
                    self.global_temp = act['temperature_update']
            elif act.get('type') == 'CFG':
                self.process_config_action(act)
        
        if days_to_advance <= 0:
            return
        
        for _ in range(days_to_advance):
            self.t += 1
            self._step_one_day()
    
    def apply_config_actions(self, actions: List[Dict]):
        """应用配置类动作（不包含时间推进）
        
        该方法是对 process_config_action 的批量包装，保持向后兼容。
        
        Args:
            actions: 配置动作列表，仅处理 type='CFG' 的动作
        """
        for act in actions:
            self.process_config_action(act)
    
    # ==================== 统一的政策/事件管理方法 ====================
    
    def register_policy(self, policy_id: str, trigger_day: int, params: Dict = None, 
                       active: bool = False, stopped: bool = False) -> bool:
        """统一的政策注册入口
        
        Args:
            policy_id: 政策ID (如 'P-101', 'P-205', 'P-301')
            trigger_day: 触发生效的天数
            params: 政策参数
            active: 是否已激活（用于快照模式恢复历史状态）
            stopped: 是否已停止
        
        Returns:
            True: 注册成功; False: 已存在相同ID的政策（P-205和P-301除外）
        
        P-205 特殊处理：
            - 允许多次注册，新政策的 trigger_day 覆盖旧的
            - 旧政策在新政策生效前的累计触发次数保留到全局变量
            - 历史触发对 L_base_cap 和 Grid D 坐标的影响保留
        """
        # P-301: 同类政策重复下达时，最新版本替代历史版本（同一天的多条共存）
        # P-205: 允许覆盖注册，但保留历史累计
        # 其他政策: 不允许重复注册
        if policy_id == 'P-301':
            for p in self.policies:
                if p.id == 'P-301' and p.trigger_day < trigger_day:
                    p.active = False
                    p.stopped = True
        elif policy_id == 'P-205':
            existing = [p for p in self.policies if p.id == policy_id]
            if existing:
                for p in existing:
                    if p.active and not p.stopped:
                        delta_days = trigger_day - p.trigger_day
                        if delta_days > 0:
                            old_policy_total_level = delta_days // 5
                            old_accumulated = getattr(p, 'accumulated_level', 0)
                            remaining_increment = old_policy_total_level - old_accumulated
                            if remaining_increment > 0:
                                self.p205_global_accumulated_level += remaining_increment
                                for i in range(old_accumulated + 1, old_policy_total_level + 1):
                                    trigger_day_for_level = p.trigger_day + i * 5
                                    if trigger_day_for_level < trigger_day:
                                        self.p205_trigger_history.append((trigger_day_for_level, 1))
                    p.active = False
                    p.stopped = True
        else:
            existing = [p for p in self.policies if p.id == policy_id]
            if existing:
                return False
        
        self.policies.append(Policy(
            id=policy_id,
            trigger_day=trigger_day,
            params=params or {},
            active=active,
            stopped=stopped
        ))
        return True
    
    def register_event(self, event_type: str, trigger_day: int, params: Dict = None,
                      active: bool = False) -> bool:
        """统一的事件注册入口
        
        Args:
            event_type: 事件类型 (如 'E-TYPHOON', 'E-HEATWAVE', 'E-EARTHQUAKE')
            trigger_day: 触发生效的天数
            params: 事件参数
            active: 是否已激活（用于快照模式恢复历史状态）
        
        Returns:
            True: 注册成功; False: 已存在相同类型和触发日的事件
        """
        # 检查是否已存在相同类型和触发日的事件
        existing = [e for e in self.events 
                   if e.type == event_type and e.trigger_day == trigger_day]
        if existing:
            return False
        
        self.events.append(Event(
            type=event_type,
            trigger_day=trigger_day,
            params=params or {},
            active=active
        ))
        return True
    
    def stop_policy(self, policy_id: str) -> bool:
        """停止指定政策
        
        Args:
            policy_id: 政策ID
        
        Returns:
            True: 停止成功; False: 未找到对应政策
        """
        found = False
        for p in self.policies:
            if p.id == policy_id:
                p.active = False
                p.stopped = True
                found = True
        return found
    
    def process_config_action(self, action: Dict):
        """处理单个配置动作（统一入口）
        
        该方法统一处理所有CFG类型的动作，包括：
        - 政策注册/停止
        - 事件注册
        - 线路模式变更
        - 电网状态变更
        - 地形变更
        
        Args:
            action: 配置动作字典
        """
        if action.get('type') != 'CFG':
            return
        
        if 'policy' in action:
            policy_data = action['policy']
            policy_id = policy_data.get('id')
            
            if policy_data.get('stop', False):
                # 政策停止指令
                self.stop_policy(policy_id)
            else:
                # 注册新政策
                self.register_policy(
                    policy_id=policy_id,
                    trigger_day=policy_data.get('trigger_day', self.t + 1),
                    params=policy_data.get('params', {})
                )
        
        elif 'event' in action:
            event_data = action['event']
            self.register_event(
                event_type=event_data['type'],
                trigger_day=event_data.get('trigger_day', self.t + 1),
                params=event_data.get('params', {})
            )
        
        elif 'line_mode' in action:
            line_data = action['line_mode']
            line_id = line_data['line_id']
            if line_id in self.lines:
                self.lines[line_id].mode = LineMode[line_data['mode']]
                # 如果设置为OPEN，记录原因为用户手动设置
                if line_data['mode'] == 'OPEN':
                    self.lines[line_id].open_reason = '用户手动设置断开'
                else:
                    self.lines[line_id].open_reason = ''  # 清除断开原因
        
        elif 'grid_pumping' in action:
            pump_data = action['grid_pumping']
            grid_id = pump_data.get('grid_id', 'B')
            if grid_id in self.grids:
                entering_pump = pump_data.get('is_pumping', False)
                was_pumping = self.grids[grid_id].is_pumping
                self.grids[grid_id].is_pumping = entering_pump
                # 若用户显式设定抽水功率，记录该值（pump_load为正值，仅用于经济结算和日志）
                if 'pump_load' in pump_data:
                    self.grids[grid_id].pump_load = pump_data['pump_load']
                
                # 进入抽水状态：拓扑隔离——断开与Grid B相连的所有联络线
                # 只断开当前非Open的线路，避免覆盖已有其他原因断开的线路的 open_reason
                if entering_pump and not was_pumping:
                    for lid, line in self.lines.items():
                        if line.from_id == grid_id or line.to_id == grid_id:
                            if line.mode != LineMode.OPEN:
                                line.mode_before_pump = line.mode
                                line.mode = LineMode.OPEN
                                line.power = 0.0
                                line.power_forward = 0.0
                                line.power_backward = 0.0
                                line.open_reason = f'Grid {grid_id} 抽水状态，拓扑隔离'
                
                # 退出抽水状态：恢复联络线、负荷、出力等
                if not entering_pump and was_pumping:
                    for lid, line in self.lines.items():
                        if line.from_id == grid_id or line.to_id == grid_id:
                            if line.open_reason == f'Grid {grid_id} 抽水状态，拓扑隔离':
                                line.mode = line.mode_before_pump if line.mode_before_pump is not None else LineMode.PARALLEL
                                line.mode_before_pump = None
                                line.open_reason = ''
                    # 恢复负荷为基础负荷
                    self.grids[grid_id].L_actual = self.grids[grid_id].L_base_cap
                    # 恢复出力为基础出力
                    self.grids[grid_id].G_actual = self.grids[grid_id].G_base_cap
                    # 清零抽水功率记录，避免旧值影响下次抽水周期的日志
                    self.grids[grid_id].pump_load = 0.0
        
        elif 'grid_island' in action:
            grid_data = action['grid_island']
            grid_id = grid_data['grid_id']
            if grid_id in self.grids:
                self.grids[grid_id].is_island = grid_data.get('is_island', False)
        
        elif 'terrain_change' in action:
            terrain_data = action['terrain_change']
            zone_id = terrain_data.get('zone_id')
            resistance = terrain_data.get('resistance')
            if zone_id and resistance:
                self.update_terrain_resistance(zone_id, resistance)
    
    def restore_historical_state(self, previous_events: List[Dict], snapshot_day: int):
        """恢复历史状态（用于快照模式）
        
        从previous_events中提取所有政策/事件/配置变更，并根据snapshot_day
        判断其激活状态。
        
        P-205 特殊处理：
        - 收集所有 P-205 注册记录，按时间顺序处理
        - 计算每个 P-205 在其有效期内（到下一个 P-205 或 snapshot_day）的累计触发次数
        - 将累计效果应用到 L_base_cap 和触发历史记录
        
        Args:
            previous_events: 历史事件列表
            snapshot_day: 快照时间点，trigger_day <= snapshot_day 的政策/事件标记为已生效
        """
        # 首先收集所有 P-205 注册记录，用于计算历史累计
        p205_registrations = []  # [(registration_day, trigger_day, params), ...]
        
        for day_event in previous_events:
            day_t = day_event.get('t', 0)
            for action in day_event.get('actions', []):
                if action.get('type') == 'CFG' and 'policy' in action:
                    policy_data = action['policy']
                    if policy_data.get('id') == 'P-205' and not policy_data.get('stop', False):
                        trigger_day = policy_data.get('trigger_day', day_t)
                        p205_registrations.append((day_t, trigger_day, policy_data.get('params', {})))
        
        # 处理 P-205 历史累计
        if p205_registrations:
            self._restore_p205_historical_state(p205_registrations, snapshot_day)
        
        # 然后处理其他政策和事件
        for day_event in previous_events:
            day_t = day_event.get('t', 0)
            for action in day_event.get('actions', []):
                if action.get('type') == 'CFG':
                    if 'policy' in action:
                        policy_data = action['policy']
                        policy_id = policy_data.get('id')
                        
                        # P-205 已经在上面特殊处理过了，这里跳过
                        if policy_id == 'P-205':
                            continue
                        
                        if policy_data.get('stop', False):
                            # 政策停止指令
                            self.stop_policy(policy_id)
                        else:
                            trigger_day = policy_data.get('trigger_day', day_t)
                            is_active = trigger_day <= snapshot_day
                            self.register_policy(
                                policy_id=policy_id,
                                trigger_day=trigger_day,
                                params=policy_data.get('params', {}),
                                active=is_active
                            )
                    
                    elif 'event' in action:
                        event_data = action['event']
                        trigger_day = event_data.get('trigger_day', day_t)
                        is_active = trigger_day <= snapshot_day
                        self.register_event(
                            event_type=event_data['type'],
                            trigger_day=trigger_day,
                            params=event_data.get('params', {}),
                            active=is_active
                        )
                    
                    elif 'line_mode' in action:
                        if day_t <= snapshot_day:
                            line_data = action['line_mode']
                            line_id = line_data['line_id']
                            if line_id in self.lines:
                                self.lines[line_id].mode = LineMode[line_data['mode']]
                                if line_data['mode'] == 'OPEN':
                                    self.lines[line_id].open_reason = '用户手动设置断开'
                                else:
                                    self.lines[line_id].open_reason = ''
                    
                    elif 'grid_island' in action:
                        if day_t <= snapshot_day:
                            grid_data = action['grid_island']
                            grid_id = grid_data['grid_id']
                            if grid_id in self.grids:
                                self.grids[grid_id].is_island = grid_data.get('is_island', False)
                    
                    elif 'terrain_change' in action:
                        if day_t <= snapshot_day:
                            terrain_data = action['terrain_change']
                            zone_id = terrain_data.get('zone_id')
                            resistance = terrain_data.get('resistance')
                            if zone_id and resistance:
                                self.update_terrain_resistance(zone_id, resistance)
                
                elif action.get('type') == 'OBS':
                    # OBS 类型中的温度只用于设置 global_temp，不追加到 temp_history
                    # temp_history 由 _apply_environment() 在每天推演时自动追加
                    # 这里只记录最后一个温度值作为 global_temp 的初始值
                    if 'temperature_update' in action:
                        self.global_temp = action['temperature_update']
                    elif 'temperature' in action:
                        self.global_temp = action['temperature']
    
    def _restore_p205_historical_state(self, p205_registrations: List[Tuple], snapshot_day: int):
        """恢复 P-205 政策的历史累计状态
        
        处理多个 P-205 注册的情况，计算每个政策在其有效期内的累计触发次数，
        并将效果应用到 L_base_cap 和触发历史记录。
        
        Args:
            p205_registrations: P-205 注册记录列表 [(registration_day, trigger_day, params), ...]
            snapshot_day: 快照时间点
        """
        if not p205_registrations:
            return
        
        # 按注册日期排序
        p205_registrations = sorted(p205_registrations, key=lambda x: x[0])
        
        total_l_base_increment = 0
        
        for i, (reg_day, trigger_day, params) in enumerate(p205_registrations):
            # 确定该政策的有效期结束时间
            # 如果有下一个 P-205 注册，则有效期到下一个注册的 trigger_day
            # 否则有效期到 snapshot_day
            if i + 1 < len(p205_registrations):
                next_trigger_day = p205_registrations[i + 1][1]
                effective_end = next_trigger_day
            else:
                effective_end = snapshot_day + 1  # +1 是因为我们要计算到 snapshot_day 为止
            
            # 计算该政策在有效期内的累计触发次数
            # 触发日为 trigger_day + 5, trigger_day + 10, ...
            accumulated_level = 0
            for day in range(trigger_day + 5, effective_end, 5):
                if day <= snapshot_day:
                    accumulated_level += 1
                    # 记录触发历史（用于坐标计算）
                    self.p205_trigger_history.append((day, 1))
            
            if accumulated_level > 0:
                total_l_base_increment += accumulated_level * 200.0
                self.p205_global_accumulated_level += accumulated_level
        
        # 应用累计效果到 L_base_cap
        if total_l_base_increment > 0:
            self.grids['D'].L_base_cap += total_l_base_increment
        
        # 注册最后一个（当前有效的）P-205 政策
        if p205_registrations:
            last_reg_day, last_trigger_day, last_params = p205_registrations[-1]
            is_active = last_trigger_day <= snapshot_day
            
            # 直接添加政策，不通过 register_policy（避免重复处理）
            new_policy = Policy(
                id='P-205',
                trigger_day=last_trigger_day,
                params=last_params,
                active=is_active,
                stopped=False
            )
            # 设置已累计的 level（从 trigger_day 到 snapshot_day）
            if is_active:
                delta_days = snapshot_day - last_trigger_day
                new_policy.accumulated_level = delta_days // 5
            else:
                new_policy.accumulated_level = 0
            
            self.policies.append(new_policy)
    
    # ==================== 统一的政策/事件管理方法 END ====================
    
    def advance_days(self, days: int):
        """推演指定天数
        
        Args:
            days: 要推演的天数
        """
        if days <= 0:
            return
        
        for _ in range(days):
            self.t += 1
            self._step_one_day()
    
    def update_terrain_resistance(self, zone_id: str, resistance: float):
        """更新地形区域的阻力系数
        
        Args:
            zone_id: 地形区域ID (如 'T-SC1')
            resistance: 新的阻力系数
        """
        for zone in self.zones:
            if zone.name == zone_id:
                zone.resistance = resistance
                # 重新计算所有线路路径（阻力变化可能影响最优路径）
                self._calculate_all_paths()
                return
        
        # 如果区域不存在，可以考虑添加到 terrain_override
        # 这里简单处理，不做额外操作
    
    def _step_one_day(self):
        """执行单天推演 (内部方法)"""
        # 初始化当日计算日志
        self.daily_calc_log = {
            'day': self.t,
            'pre_event_state': {},  # 事件影响前的状态
            'initial_state': {},     # 事件影响后的状态（用于后续计算）
            'economic_dispatch': {},
            'power_flow': {},
            'frequency_evolution': {},
            'reserve_activation': {},
            'load_shedding': {},
            'status_assessment': {},
            'cost_breakdown': {}
        }
        
        # 0. 保存上一时刻的频率 (用于公式2, 3, 7)
        freq_prev = {gid: g.frequency for gid, g in self.grids.items()}
        
        # 2. 环境更新 (重置参数，应用事件/政策)
        self._reset_grid_params()
        
        # 记录事件影响前的状态 (在_reset_grid_params后，_apply_environment前)
        for gid, g in self.grids.items():
            self.daily_calc_log['pre_event_state'][gid] = {
                'frequency': g.frequency,
                'G_actual': g.G_actual,
                'G_max': g.G_max,
                'L_actual': g.L_actual,
                'P_droop': g.P_droop,
                'P_res': g.P_res,
                'status': g.status.value,
                'coord': g.coord
            }
        
        # 1. 环境更新 Phase1 (政策 + 温度事件，不依赖坐标/路径)
        self._apply_environment()

        # 2. 更新所有电站坐标 + 计算线路路径
        # Grid D 依赖温度/政策结果，所以必须在 phase1 之后
        self._update_grid_coordinates()

        # 3. 环境更新 Phase2 (地震 + 台风事件，依赖当日坐标和路径)
        # 地震需要当日 Grid C 坐标计算加权距离
        # 台风需要当日联络线路径判断是否断开
        self._apply_environment_phase2()
        
        # 记录事件影响后的状态 (在环境更新后，计算前)
        # 注意：此时 G_actual, L_actual 已被事件/政策修改
        for gid, g in self.grids.items():
            self.daily_calc_log['initial_state'][gid] = {
                'frequency': g.frequency,
                'G_actual': g.G_actual,
                'G_max': g.G_max,
                'L_actual': g.L_actual,
                'P_droop': g.P_droop,
                'P_res': g.P_res,
                'status': g.status.value,
                'coord': g.coord
            }
        
        # 3. 设置出力 (不是经济调度，出力是设定好的)
        self._set_generation_output()
        
        # 4. 物理计算 (使用 t-1 时刻的频率)
        self._calculate_power_flow(freq_prev)
        self._update_dynamics(freq_prev)
        
        # 5. 检查线路过载
        self._check_line_overload()
        
        # 6. 状态判定
        self._assess_status()
        
        # 7. 检查刚性负荷红线 (P-301)
        self._check_rigid_load_violation()
        
        # 8. 结算
        self._calculate_costs()
        
        # 9. 成本失控判定 (base_cost 已在初始化时由默认状态计算得出)
        self._check_cost_out_of_control()
        
        # 11. 记录快照
        self._record_snapshot()

        # 12. 寒潮/高温事件失效
        self.events = [e for e in self.events 
                           if e.type not in ["E-COLDWAVE", "E-HEATWAVE"] ]
    
    def _check_rigid_load_violation(self):
        """检查刚性负荷红线违规 (P-301)
        
        P-301 支持不同保障等级:
        - 基础保障: 10% 刚性负荷
        - 强化保障: 20% 刚性负荷
        - 最高保障: 30% 刚性负荷
        
        覆盖判定规则:
        1) 若存在点名电网的 P-301，采用最高保障等级
        2) 若存在全网适用的 P-301，采用最高保障等级
        3) 若都不存在，不启用刚性负荷保护
        """
        for gid, g in self.grids.items():
            # Grid B 抽水状态：不参与刚性负荷红线判定
            if gid == 'B' and g.is_pumping:
                continue
            
            # 计算该电网的刚性负荷比例
            rigid_ratio = self._get_rigid_load_ratio(gid)
            
            if rigid_ratio <= 0:
                # 不启用刚性负荷保护
                continue
            
            # 计算刚性负荷（基于L_base_cap计算的最低保障负荷）
            rigid_load = g.L_base_cap * rigid_ratio
            
            # 使用写回值（公式6+公式13: round(L_actual - L_shed, 2)）作为剩余负荷
            remaining_load = g.L_writeback
            
            # 验证是否触及刚性负荷红线：
            # 比较切负荷后的剩余负荷与刚性负荷，如果剩余负荷 < 刚性负荷，需要标记"负荷侧运行限制"
            # 即使切负荷为0，如果实际负荷本身就小于刚性负荷阈值，也需要标记
            if remaining_load < rigid_load:
                g.limit_tags.add("负荷侧运行限制")
    
    def _get_rigid_load_ratio(self, grid_id: str, policies=None) -> float:
        """获取电网的刚性负荷比例 (P-301)
        
        刚性负荷统一口径：
        - 若由 P-301 覆盖，则取对应保障等级
        - 若电网为 Grid D 且未被 P-301 覆盖，则默认 0.30
        - 其他电网在无 P-301 时为 0
        
        Args:
            grid_id: 电网ID
            policies: 可选的策略列表（用于报告生成时传入快照策略，
                      避免使用最终状态的 self.policies）
        """
        policy_list = policies if policies is not None else self.policies
        
        specific_ratio = 0.0
        global_ratio = 0.0
        
        for p in policy_list:
            if p.id == 'P-301' and p.active:
                target = p.params.get('target', 'Global')
                level = p.params.get('level', '最高保障')
                ratio = RIGID_LOAD_LEVELS.get(level, 0.0)
                
                if target == 'Global':
                    global_ratio = max(global_ratio, ratio)
                elif grid_id in target:
                    specific_ratio = max(specific_ratio, ratio)
        
        if specific_ratio > 0:
            return specific_ratio
        if global_ratio > 0:
            return global_ratio
        
        if grid_id == 'D':
            return 0.30
        return 0.0

    def _record_snapshot(self):
        snapshot = {
            'day': self.t,
            'grids': {gid: deepcopy(g) for gid, g in self.grids.items()},
            'lines': {lid: deepcopy(l) for lid, l in self.lines.items()},
            'cost': self.daily_cost,
            'events': [deepcopy(e) for e in self.events if e.active],
            'policies': [deepcopy(p) for p in self.policies if p.active],
            'calc_log': deepcopy(self.daily_calc_log) if hasattr(self, 'daily_calc_log') else {}
        }
        self.daily_snapshots.append(snapshot)

    # --- 报告生成 ---
    
    def generate_daily_report(self) -> str:
        """生成逐天推演过程报告（包含详细计算过程）"""
        report = "【逐天推演过程（含计算过程）】\n\n"
        for snap_idx, snap in enumerate(self.daily_snapshots):
            report += f"{'='*80}\n"
            report += f"Day {snap['day']} 状态演化详情\n"
            report += f"{'='*80}\n\n"
            
            calc_log = snap.get('calc_log', {})
            
            # 0. 激活的事件/政策
            if snap['events'] or snap['policies']:
                report += "**[Step 0] 激活事件/政策：**\n"
                for p in snap['policies']: 
                    report += f"  - 政策 {p.id}\n"
                for e in snap['events']: 
                    p_str = ', '.join([f"{k}:{v}" for k,v in e.params.items()])
                    note = ''
                    if e.type == 'E-TYPHOON' and self._is_typhoon_dissipated(e, snap['day']):
                        note = '（消散标记，本身不产生影响）' if e.params.get('radius', 10) <= 0 else '（已消散，不再生效）'
                    report += f"  - 事件 {e.type} [{p_str}]{note}\n"
                report += "\n"
            
            # 1. 事件影响前的状态 (使用 pre_event_state)
            pre_event = calc_log.get('pre_event_state', {})
            if pre_event:
                report += "**[Step 1] 日初状态 (事件影响前)：**\n"
                report += "```\n"
                report += f"{'电网':<8}{'频率(Hz)':<14}{'出力(MW)':<14}{'负荷(MW)':<14}{'P_droop(MW)':<14}{'P_res(MW)':<14}{'状态':<10}\n"
                report += "-" * 90 + "\n"
                for gid in ['A', 'B', 'C', 'D']:
                    if gid in pre_event:
                        s = pre_event[gid]
                        report += f"{gid:<8}{s['frequency']:<14.4f}{s['G_actual']:<14.2f}{s['L_actual']:<14.2f}{s['P_droop']:<14.2f}{s['P_res']:<14.2f}{s['status']:<10}\n"
                report += "```\n\n"
            
            # 2. 事件影响和出力设定
            event_effects = calc_log.get('event_effects', [])
            go = calc_log.get('generation_output', {})
            initial = calc_log.get('initial_state', {})  # 事件影响后的状态
            
            # 2.1 事件对 G_actual 和 L_actual 的影响
            if event_effects:
                report += "**[Step 2] 事件影响（对 G_actual / L_actual 的修改）：**\n"
                for evt in event_effects:
                    event_type = evt.get('event_type', 'UNKNOWN')
                    if event_type in ['E-HEATWAVE', 'E-COLDWAVE']:
                        temp = evt.get('temperature', 0)
                        report += f"\n  ▶ {event_type} (温度: {temp}°C)\n"
                    elif event_type == 'E-EARTHQUAKE':
                        magnitude = evt.get('magnitude', 0)
                        epicenter = evt.get('epicenter', (0, 0))
                        dist = evt.get('distance_to_C', 0)
                        report += f"\n  ▶ {event_type} (震级: {magnitude}, 震心: {epicenter}, 距Grid C: {dist:.2f}km)\n"
                    else:
                        report += f"\n  ▶ {event_type}\n"
                    
                    # 按电网分组显示影响
                    for eff in evt.get('effects', []):
                        grid = eff.get('grid', '')
                        param = eff.get('param', '')
                        old_val = eff.get('old_value', 0)
                        new_val = eff.get('new_value', 0)
                        formula = eff.get('formula', '')
                        reason = eff.get('reason', '')
                        
                        report += f"    Grid {grid}: {param}\n"
                        report += f"      原始值: {_pr(old_val):.2f} → 新值: {_pr(new_val):.2f}\n"
                        report += f"      计算: {formula}\n"
                        report += f"      原因: {reason}\n"
                report += "\n"
                
                # 输出事件修改后的 G_actual 和 L_actual 汇总表
                report += "  **事件影响后的参数值（后续公式使用这些值）：**\n"
                report += "  ```\n"
                report += f"  {'电网':<8}{'G_actual(MW)':<16}{'L_actual(MW)':<16}{'G_max(MW)':<16}\n"
                report += "  " + "-" * 56 + "\n"
                for gid in ['A', 'B', 'C', 'D']:
                    if gid in initial:
                        s = initial[gid]
                        G_max = s.get('G_max', 0)
                        report += f"  {gid:<8}{s['G_actual']:<16.2f}{s['L_actual']:<16.2f}{G_max:<16.2f}\n"
                report += "  ```\n\n"
            
            # 2.2 出力设定
            if go:
                report += "**[Step 2 续] 出力设定 (G_actual = G_base)：**\n"
                for gid in ['A', 'B', 'C', 'D']:
                    if gid in go:
                        info = go[gid]
                        report += f"  Grid {gid}: G_actual = {_pr(info.get('G_actual', 0)):.2f} MW"
                        if 'reason' in info:
                            report += f" ({info['reason']})"
                        report += "\n"
                report += "\n"
            
            # 3. 功率流计算过程
            pf = calc_log.get('power_flow', {})
            if pf:
                report += "**[Step 3] 功率流计算 (公式3)：**\n"
                report += "  并联模式公式: P_ij(t) = clip(γ × (f_i(t-1) - f_j(t-1)), -P_max, P_max)\n"
                report += "  串联模式公式: P_ij(t) = clip(γ × max(0, f_i(t-1) - f_j(t-1)), 0, P_max)\n"
                report += "                P_ji(t) = clip(γ × max(0, f_j(t-1) - f_i(t-1)), 0, P_max)\n"
                report += "                注意: 串联模式下两个方向独立计算\n"
                report += f"  同步刚性系数 γ = {GAMMA}\n\n"
                for lid, pf_data in pf.items():
                    mode = pf_data.get('mode', 'UNKNOWN')
                    if mode == 'Open':
                        open_reason = pf_data.get('open_reason', '')
                        if open_reason:
                            report += f"  {lid} [断开]: P = 0 MW (原因: {open_reason})\n"
                        else:
                            report += f"  {lid} [断开]: P = 0 MW\n"
                    elif mode == 'Parallel':
                        f_from = pf_data.get('f_from', F_NOM)
                        f_to = pf_data.get('f_to', F_NOM)
                        delta_f = pf_data.get('delta_f', 0)
                        raw_power = pf_data.get('raw_power', 0)
                        final_power = pf_data.get('final_power', 0)
                        report += f"  {lid} [并联]:\n"
                        report += f"    f_from = {_pr(f_from,4):.4f} Hz, f_to = {_pr(f_to,4):.4f} Hz\n"
                        report += f"    Δf = f_from - f_to = {_pr(delta_f,4):.4f} Hz\n"
                        report += f"    原始功率 = γ × Δf = {GAMMA} × {_pr(delta_f,4):.4f} = {_pr(raw_power):.2f} MW\n"
                        report += f"    截断后 P = clip({_pr(raw_power):.2f}, -P_max, P_max) = {_pr(final_power):.2f} MW\n"
                    elif mode == 'Series':
                        f_from = pf_data.get('f_from', F_NOM)
                        f_to = pf_data.get('f_to', F_NOM)
                        delta_f_forward = pf_data.get('delta_f_forward', f_from - f_to)
                        delta_f_backward = pf_data.get('delta_f_backward', f_to - f_from)
                        raw_power_forward = pf_data.get('raw_power_forward', 0)
                        raw_power_backward = pf_data.get('raw_power_backward', 0)
                        power_forward = pf_data.get('power_forward', 0)
                        power_backward = pf_data.get('power_backward', 0)
                        net_power = pf_data.get('net_power', power_forward - power_backward)
                        
                        line = self.lines.get(lid)
                        from_id = line.from_id if line else '?'
                        to_id = line.to_id if line else '?'
                        
                        report += f"  {lid} [串联]:\n"
                        report += f"    f_{from_id} = {_pr(f_from,4):.4f} Hz, f_{to_id} = {_pr(f_to,4):.4f} Hz\n"
                        report += f"    --- {from_id}→{to_id} 方向 (P_{from_id}{to_id}) ---\n"
                        report += f"      Δf = f_{from_id} - f_{to_id} = {_pr(delta_f_forward,4):.4f} Hz\n"
                        report += f"      max(0, Δf) = max(0, {_pr(delta_f_forward,4):.4f}) = {_pr(max(0, delta_f_forward),4):.4f}\n"
                        report += f"      原始功率 = γ × max(0, Δf) = {GAMMA} × {_pr(max(0, delta_f_forward),4):.4f} = {_pr(raw_power_forward):.2f} MW\n"
                        report += f"      截断后 P_{from_id}{to_id} = clip({_pr(raw_power_forward):.2f}, 0, P_max) = {_pr(power_forward):.2f} MW\n"
                        report += f"    --- {to_id}→{from_id} 方向 (P_{to_id}{from_id}) ---\n"
                        report += f"      Δf = f_{to_id} - f_{from_id} = {_pr(delta_f_backward,4):.4f} Hz\n"
                        report += f"      max(0, Δf) = max(0, {_pr(delta_f_backward,4):.4f}) = {_pr(max(0, delta_f_backward),4):.4f}\n"
                        report += f"      原始功率 = γ × max(0, Δf) = {GAMMA} × {_pr(max(0, delta_f_backward),4):.4f} = {_pr(raw_power_backward):.2f} MW\n"
                        report += f"      截断后 P_{to_id}{from_id} = clip({_pr(raw_power_backward):.2f}, 0, P_max) = {_pr(power_backward):.2f} MW\n"
                        report += f"    --- 净功率流 ---\n"
                        report += f"      净功率 = P_{from_id}{to_id} - P_{to_id}{from_id} = {_pr(power_forward):.2f} - {_pr(power_backward):.2f} = {_pr(net_power):.2f} MW\n"
                    else:
                        delta_f = pf_data.get('delta_f', 0)
                        raw_power = pf_data.get('raw_power', 0)
                        final_power = pf_data.get('final_power', 0)
                        report += f"  {lid} [{mode}]: Δf = {_pr(delta_f,4):.4f} Hz → 原始功率 = {_pr(raw_power):.2f} MW → 截断后 P = {_pr(final_power):.2f} MW\n"
                report += "\n"
            
            # 3.5 P_droop更新计算
            p_droop_update = calc_log.get('p_droop_update', {})
            if p_droop_update:
                report += "**[Step 3.5] 一次调频出力更新 (公式2)：**\n"
                report += f"  公式: P_droop(t) = clip(P_droop(t-1) + K_droop × ({F_NOM} - f(t-1)), P_droop_min, P_droop_max)\n\n"
                for gid in ['A', 'B', 'C', 'D']:
                    pd = p_droop_update.get(gid, {})
                    if pd:
                        reason = pd.get('reason', '')
                        report += f"  Grid {gid}:\n"
                        # 抽水状态下不输出P_droop计算过程
                        if reason == '抽水状态，禁止调频':
                            report += f"    抽水状态，禁止调频，P_droop = 0.00 MW\n\n"
                            continue
                        P_droop_prev = pd.get('P_droop_prev', 0)
                        f_prev = pd.get('f_prev', F_NOM)
                        K_droop = pd.get('K_droop', 0)
                        P_droop_raw = pd.get('P_droop_raw', 0)
                        P_droop_min = pd.get('P_droop_min', 0)
                        P_droop_max = pd.get('P_droop_max', 0)
                        P_droop_new = pd.get('P_droop_new', 0)
                        report += f"    P_droop({snap['day']-1}) = {_pr(P_droop_prev):.2f} MW, f({snap['day']-1}) = {_pr(f_prev,4):.4f} Hz, K_droop = {K_droop}\n"
                        report += f"    → P_droop_raw = {_pr(P_droop_prev):.2f} + {K_droop} × ({F_NOM} - {_pr(f_prev,4):.4f}) = {_pr(P_droop_raw):.2f} MW\n"
                        report += f"    → clip({_pr(P_droop_raw):.2f}, {_pr(P_droop_min):.2f}, {_pr(P_droop_max):.2f}) = {_pr(P_droop_new):.2f} MW"
                        if reason == '截断':
                            report += " (触发截断)"
                        report += "\n"
                        report += f"    → P_droop({snap['day']}) = {_pr(P_droop_new):.2f} MW\n\n"
            
            # 4. 备用出力与负荷切除
            reserve = calc_log.get('reserve_activation', {})
            shed = calc_log.get('load_shedding', {})
            if reserve or shed:
                report += "**[Step 4] 功率平衡与备用出力 (公式4-6)：**\n"
                report += "  公式4: ΔP_i(t) = G_actual + P_droop + ΣP_ji - L_i\n"
                report += "  公式5: P_available = max(0, G_max - G_actual - P_droop); P_res = min(|ΔP|, P_available)\n"
                report += "  公式6: L_shed = max(0, -ΔP_post)，其中 ΔP_post = ΔP + P_res\n\n"
                for gid in ['A', 'B', 'C', 'D']:
                    res = reserve.get(gid, {})
                    sh = shed.get(gid, {})
                    if res or sh:
                        # 抽水状态下跳过详细计算
                        g_obj = snap['grids'][gid]
                        if gid == 'B' and g_obj.is_pumping:
                            report += f"  Grid {gid}: 抽水状态，拓扑隔离，ΔP=0, P_res=0, L_shed=0\n\n"
                            continue
                        delta_P = res.get('delta_P', 0)
                        P_in = res.get('P_in', 0)
                        P_avail = res.get('P_available', 0)
                        P_res_val = res.get('P_res', 0)
                        L_shed_val = sh.get('L_shed', 0)
                        reason = res.get('reason', '')
                        G_actual = res.get('G_actual', 0)
                        L_actual = res.get('L_actual', 0)
                        P_droop = res.get('P_droop', 0)
                        G_max = res.get('G_max', 0)
                        report += f"  Grid {gid}:\n"
                        # 公式4详细计算过程
                        report += f"    [公式4] ΔP = G_actual + P_droop + ΣP_ji - L_actual\n"
                        report += f"           = {_pr(G_actual):.2f} + {_pr(P_droop):.2f} + ({_pr(P_in):.2f}) - {_pr(L_actual):.2f}\n"
                        report += f"           = {_pr(delta_P):.2f} MW"
                        if delta_P < 0:
                            report += " (缺口)\n"
                        elif delta_P > 0:
                            report += " (富余)\n"
                        else:
                            report += " (平衡)\n"
                        # 公式5详细计算过程
                        report += f"    [公式5] P_available = max(0, G_max - G_actual - P_droop) = max(0, {_pr(G_max):.2f} - {_pr(G_actual):.2f} - {_pr(P_droop):.2f}) = {_pr(P_avail):.2f} MW\n"
                        if delta_P < 0:
                            report += f"           P_cand_res = |ΔP| = {_pr(abs(delta_P)):.2f} MW\n"
                            report += f"           P_res = min(P_cand_res, P_available) = min({_pr(abs(delta_P)):.2f}, {_pr(P_avail):.2f}) = {_pr(P_res_val):.2f} MW\n"
                        elif delta_P > 0:
                            P_avail_down = res.get('P_available_down', max(0, G_actual + P_droop))
                            report += f"           P_res = {_pr(P_res_val):.2f} MW ({reason})\n"
                            report += f"           [下调备用计算] P_available_down = max(0, G_actual + P_droop) = max(0, {_pr(G_actual):.2f} + {_pr(P_droop):.2f}) = {_pr(P_avail_down):.2f} MW\n"
                            report += f"                          P_res = -min(ΔP, P_available_down) = -min({_pr(delta_P):.2f}, {_pr(P_avail_down):.2f}) = {_pr(P_res_val):.2f} MW\n"
                        else:
                            report += f"           P_res = {_pr(P_res_val):.2f} MW (平衡无需备用)\n"
                        # 公式6详细计算过程
                        if delta_P < 0:
                            report += f"    [公式6] L_shed = max(0, |ΔP| - P_res) = max(0, {_pr(abs(delta_P)):.2f} - {_pr(P_res_val):.2f}) = {_pr(L_shed_val):.2f} MW\n"
                        else:
                            report += f"    [公式6] L_shed = 0 MW (ΔP >= 0，无需切负荷)\n"
                        if L_shed_val > 0:
                            report += f"    **需切负荷 L_shed = {_pr(L_shed_val):.2f} MW**\n"
                        rigid_ratio = self._get_rigid_load_ratio(gid, policies=snap.get('policies', []))
                        if rigid_ratio > 0:
                            L_base = snap['grids'][gid].L_base_cap
                            rigid_load = L_base * rigid_ratio
                            remaining_load = L_actual - L_shed_val
                            report += f"    [刚性负荷检查] 刚性负荷比例 = {rigid_ratio*100:.0f}%, 刚性负荷 = L_base × {rigid_ratio*100:.0f}% = {_pr(L_base):.2f} × {rigid_ratio*100:.0f}% = {_pr(rigid_load):.2f} MW\n"
                            report += f"                   剩余负荷 = L_actual - L_shed = {_pr(L_actual):.2f} - {_pr(L_shed_val):.2f} = {_pr(remaining_load):.2f} MW\n"
                            if remaining_load < rigid_load:
                                report += f"    **⚠ 负荷侧运行限制: 剩余负荷 {_pr(remaining_load):.2f} MW < 刚性负荷 {_pr(rigid_load):.2f} MW（触及刚性负荷红线）**\n"
                        report += "\n"
            
            # 5. 频率演化计算
            freq_evo = calc_log.get('frequency_evolution', {})
            if freq_evo:
                report += "**[Step 5] 频率演化 (公式7)：**\n"
                report += f"  公式: f(t) = f(t-1) + α×ΔP_post - β×(f(t-1) - {F_NOM})\n"
                report += f"  参数: α = {ALPHA}, β = {BETA}\n\n"
                for gid in ['A', 'B', 'C', 'D']:
                    fe = freq_evo.get(gid, {})
                    if fe:
                        # 抽水状态下跳过频率演化计算
                        g_obj = snap['grids'][gid]
                        if gid == 'B' and g_obj.is_pumping:
                            f_frozen = fe.get('f_next', fe.get('f_prev', F_NOM))
                            report += f"  Grid {gid}: 抽水状态，频率冻结，f = {f_frozen:.4f} Hz\n\n"
                            continue
                        f_prev = fe.get('f_prev', F_NOM)
                        delta_P_post = fe.get('delta_P_post', 0)
                        f_next = fe.get('f_next', F_NOM)
                        report += f"  Grid {gid}: f({snap['day']-1}) = {_pr(f_prev,4):.4f} Hz\n"
                        report += f"    → f({snap['day']}) = {_pr(f_prev,4):.4f} + {ALPHA}×{_pr(delta_P_post):.2f} - {BETA}×({_pr(f_prev,4):.4f} - {F_NOM})\n"
                        report += f"    → f({snap['day']}) = {_pr(f_next,4):.4f} Hz\n\n"
            
            # 6. 状态评估
            status_assess = calc_log.get('status_assessment', {})
            if status_assess:
                report += "**[Step 6] 状态评估 (公式8-9)：**\n"
                report += "  公式9: U_fallback = w1×(P_droop/P_droop_max) + w2×(P_res/P_available) + w3×(L_shed/L)\n"
                report += f"  权重: w1={W1}, w2={W2}, w3={W3}\n\n"
                for gid in ['A', 'B', 'C', 'D']:
                    sa = status_assess.get(gid, {})
                    if sa:
                        # 抽水状态下跳过状态评估详细计算
                        g_obj = snap['grids'][gid]
                        if gid == 'B' and g_obj.is_pumping:
                            frozen_status = sa.get('new_status', sa.get('old_status', 'Normal'))
                            report += f"  Grid {gid}: 抽水状态，状态冻结，维持 {frozen_status}\n\n"
                            continue
                        u_fb = sa.get('u_fallback', 0)
                        freq_dev = sa.get('freq_deviation', 0)
                        old_status = sa.get('old_status', '')
                        new_status = sa.get('new_status', '')
                        reason = sa.get('reason', '')
                        report += f"  Grid {gid}:\n"
                        report += f"    兜底占用率 U_fallback = {u_fb:.4f}\n"
                        report += f"    频率偏离 |f - 50| = {freq_dev:.4f} Hz\n"
                        if old_status != new_status:
                            report += f"    状态变化: {old_status} → {new_status}"
                        else:
                            report += f"    状态维持: {new_status}"
                        if reason:
                            report += f" ({reason})"
                        report += "\n\n"
            
            # 7. 成本计算
            cost_bd = calc_log.get('cost_breakdown', {})
            if cost_bd:
                report += "**[Step 7] 成本结算：**\n"
                gen_costs = cost_bd.get('generation_costs', {})
                if gen_costs:
                    report += "  发电成本:\n"
                    for gid, gc in gen_costs.items():
                        gen_mw = gc.get('gen_mw', 0)
                        price = gc.get('price', 0)
                        cost = gc.get('cost', 0)
                        g_coord = snap['grids'][gid].coord
                        g_obj = snap['grids'][gid]
                        if gid == 'B' and g_obj.is_pumping:
                            report += f"    Grid {gid} (位置{g_coord}): 抽水状态，发电出力 = 0 MW，发电成本 = 0 元\n"
                        else:
                            report += f"    Grid {gid} (位置{g_coord}): {_pr(gen_mw):.2f} MW × {price} 元/kWh × 24h × 1000 = {_pr(cost):.2f} 元\n"
                loss_cost = cost_bd.get('loss_cost', 0)
                line_loss_details = cost_bd.get('line_loss_details', {})
                total_loss_mw = cost_bd.get('total_loss_mw', 0)
                if loss_cost > 0 or line_loss_details:
                    report += f"  网损成本计算 (公式11: P_loss = k × (P/1000)² × √d):\n"
                    report += f"    网损电量单价: {PRICE_WASTE} 元/kWh\n"
                    for i, lid in enumerate(['L_AB', 'L_AC', 'L_BD', 'L_CD']):
                        if lid in line_loss_details:
                            ld = line_loss_details[lid]
                            line = snap['lines'].get(lid)
                            line_mode = ld.get('mode', 'Parallel')
                            report += f"    ({i+1}){lid} ({ld['from_id']}→{ld['to_id']}) [{line_mode}]:\n"
                            # 显示路径信息
                            if line and line.path:
                                path_str = self.format_path_segments(line.path)
                                report += f"      •路径: {path_str}\n"
                            report += f"      •最小加权距离 d={_pr(ld['distance']):.2f}, "
                            report += f"√d={_pr(ld['sqrt_distance'],4):.4f}, "
                            report += f"损耗系数 k={ld['loss_coeff']}\n"
                            
                            if line_mode == 'Series':
                                power_forward = ld.get('power_forward', 0)
                                power_backward = ld.get('power_backward', 0)
                                loss_forward = ld.get('loss_forward', 0)
                                loss_backward = ld.get('loss_backward', 0)
                                loss_mw_raw = ld.get('loss_mw_raw', loss_forward + loss_backward)
                                report += f"      •{ld['from_id']}→{ld['to_id']} 方向功率: P_forward = {_pr(power_forward):.2f} MW\n"
                                report += f"      •{ld['to_id']}→{ld['from_id']} 方向功率: P_backward = {_pr(power_backward):.2f} MW\n"
                                if ld['loss_mw'] > 0 or loss_mw_raw > 1e-10:
                                    if loss_forward > 0:
                                        report += f"      → P_loss_forward = {ld['loss_coeff']} × ({_pr(power_forward):.2f}/1000)² × {_pr(ld['sqrt_distance'],4):.4f} = {_pr(loss_forward,6):.6f} MW\n"
                                    if loss_backward > 0:
                                        report += f"      → P_loss_backward = {ld['loss_coeff']} × ({_pr(power_backward):.2f}/1000)² × {_pr(ld['sqrt_distance'],4):.4f} = {_pr(loss_backward,6):.6f} MW\n"
                                    report += f"      → P_loss_raw = {_pr(loss_forward,6):.6f} + {_pr(loss_backward,6):.6f} = {_pr(loss_mw_raw,6):.6f} MW\n"
                                    report += f"      → P_loss = round({_pr(loss_mw_raw,6):.6f}, 4) = {_pr(ld['loss_mw'],4):.4f} MW (四舍五入至4位小数)\n\n"
                                elif ld.get('is_open', False):
                                    report += f"      → P_loss = 0 MW (线路断开)\n\n"
                                else:
                                    report += f"      → P_loss = 0 MW (无功率流动)\n\n"
                            else:
                                report += f"      •功率 P={_pr(ld['power']):.2f} MW\n"
                                loss_mw_raw = ld.get('loss_mw_raw', ld['loss_mw'])
                                if ld['loss_mw'] > 0 or loss_mw_raw > 1e-10:
                                    report += f"      → P_loss_raw = {ld['loss_coeff']} × ({_pr(abs(ld['power'])):.2f}/1000)² × {_pr(ld['sqrt_distance'],4):.4f} = {_pr(loss_mw_raw,6):.6f} MW\n"
                                    report += f"      → P_loss = round({_pr(loss_mw_raw,6):.6f}, 4) = {_pr(ld['loss_mw'],4):.4f} MW (四舍五入至4位小数)\n\n"
                                elif ld.get('is_open', False):
                                    report += f"      → P_loss = 0 MW (线路断开)\n\n"
                                else:
                                    report += f"      → P_loss = 0 MW (无功率流动)\n\n"
                    per_line_losses = []
                    for lid_sum in ['L_AB', 'L_AC', 'L_BD', 'L_CD']:
                        if lid_sum in line_loss_details:
                            per_line_losses.append(f"{_pr(line_loss_details[lid_sum]['loss_mw'],4):.4f}")
                    report += f"    总网损 P_loss_total = {' + '.join(per_line_losses)} = {_pr(total_loss_mw,4):.4f} MW (各线路四舍五入后加总)\n"
                    report += f"    网损成本: {_pr(total_loss_mw,4):.4f} MW × 24h × 1000 × {PRICE_WASTE} 元/kWh = {_pr(loss_cost):.2f} 元\n"
                    report += "    **说明**：路径由 Dijkstra 算法基于地形阻力矩阵计算，表示最小加权阻力路径。\n"
                    report += "    路径格式：(起点) -> (移动方向, 地形名, w=权重) -> (终点)，同方向同地形的连续移动已合并。\n"
                penalty_cost = cost_bd.get('penalty_cost', 0)
                if penalty_cost > 0:
                    report += f"  状态罚单: {penalty_cost:,.2f} 元 (Critical状态×100万/天)\n"
                e_grid_cost = cost_bd.get('e_grid_cost', 0)
                if e_grid_cost > 0:
                    report += f"  国网托管费: {e_grid_cost:,.2f} 元\n"
                report += f"  **当日总成本: {snap['cost']:,.2f} 元**\n\n"
            
            # 7.5 Grid D 坐标推演逻辑
            grid_d_log = calc_log.get('grid_d_coord_evolution', {})
            if grid_d_log:
                report += "**[Step 7.5] Grid D 坐标推演 (公式10.5)：**\n"
                report += "  公式: (x_D(t), y_D(t)) = legalize(x_D(t-1) + dx, y_D(t-1) + dy)\n"
                report += "  其中: dx = dx_f + dx_p, dy 由温度事件决定\n\n"
                
                prev_coord = grid_d_log.get('prev_coord', (0, 0))
                new_coord = grid_d_log.get('new_coord', (0, 0))
                
                report += f"  **上一日坐标**: ({prev_coord[0]}, {prev_coord[1]})\n\n"
                
                # 温度项
                dy = grid_d_log.get('dy', 0)
                dy_reason = grid_d_log.get('dy_reason', '')
                is_heatwave = grid_d_log.get('is_heatwave', False)
                is_coldwave = grid_d_log.get('is_coldwave', False)
                report += f"  **温度项 dy**:\n"
                if is_heatwave:
                    report += f"    高温触发: dy = -1\n"
                elif is_coldwave:
                    report += f"    寒潮触发: dy = +1\n"
                else:
                    report += f"    无温度事件: dy = 0\n"
                report += f"    → dy = {dy} ({dy_reason})\n\n"
                
                # 频率项
                dx_f = grid_d_log.get('dx_f', 0)
                dx_f_reason = grid_d_log.get('dx_f_reason', '')
                frequency = grid_d_log.get('frequency', 50.0)
                report += f"  **频率项 dx_f**:\n"
                report += f"    当前频率: f_D = {frequency:.4f} Hz\n"
                if frequency < 49.8:
                    report += f"    f_D < 49.8 → dx_f = -1\n"
                elif frequency > 50.2:
                    report += f"    f_D > 50.2 → dx_f = +1\n"
                else:
                    report += f"    49.8 ≤ f_D ≤ 50.2 → dx_f = 0\n"
                report += f"    → dx_f = {dx_f} ({dx_f_reason})\n\n"
                
                # 政策项
                dx_p = grid_d_log.get('dx_p', 0)
                dx_p_reason = grid_d_log.get('dx_p_reason', '')
                p205_trigger_today = grid_d_log.get('p205_trigger_today', False)
                p205_trigger_source = grid_d_log.get('p205_trigger_source', None)
                p101_active = grid_d_log.get('p101_active', False)
                p205_global_level = grid_d_log.get('p205_global_accumulated_level', 0)
                p205_history = grid_d_log.get('p205_trigger_history', [])
                l_base_cap = grid_d_log.get('l_base_cap', 0)
                
                report += f"  **政策项 dx_p**:\n"
                report += f"    P-205 全局累计触发次数: {p205_global_level}\n"
                report += f"    P-205 触发历史: {p205_history if p205_history else '无'}\n"
                report += f"    Grid D 当前 L_base_cap: {l_base_cap:.2f} MW\n"
                if p205_trigger_today:
                    report += f"    P-205 今日触发: 是 ({p205_trigger_source})\n"
                else:
                    report += f"    P-205 今日触发: 否\n"
                report += f"    P-101 当前生效: {'是' if p101_active else '否'}\n"
                
                if p205_trigger_today and p101_active:
                    report += f"    P-205 与 P-101 同时生效 → dx_p = 0\n"
                elif p205_trigger_today:
                    report += f"    P-205 触发 → dx_p = +1\n"
                elif p101_active:
                    report += f"    P-101 生效 → dx_p = -1\n"
                else:
                    report += f"    无政策影响 → dx_p = 0\n"
                report += f"    → dx_p = {dx_p} ({dx_p_reason})\n\n"
                
                # 合成位移
                dx = grid_d_log.get('dx', 0)
                x_tilde = grid_d_log.get('x_tilde', 0)
                y_tilde = grid_d_log.get('y_tilde', 0)
                report += f"  **合成位移**:\n"
                report += f"    dx = dx_f + dx_p = {dx_f} + {dx_p} = {dx}\n"
                report += f"    候选坐标: (x̃, ỹ) = ({prev_coord[0]} + {dx}, {prev_coord[1]} + {dy}) = ({x_tilde}, {y_tilde})\n"
                report += f"    合法化后: (x_D, y_D) = ({new_coord[0]}, {new_coord[1]})\n\n"
                
                report += f"  **当日坐标**: ({new_coord[0]}, {new_coord[1]})\n\n"
            
            # 8. 电网限制状态判断
            report += "**[Step 8] 电网限制状态判断：**\n"
            report += "限制状态类型说明：\n"
            report += "  - **结构运行限制**：线路Open且假设并联时|P_ij|≥0.1×P_max\n"
            report += "  - **出力上限限制**：G_actual+P_droop+P_res=G_max 且存在切负荷(L_shed>0)\n"
            report += "  - **状态触发运行限制**：U_fallback≥0.2 或频率偏离>0.5Hz触发Pre-warning/Critical\n"
            report += "  - **负荷侧运行限制**：切负荷后剩余负荷<刚性负荷阈值(P-301政策)\n\n"
            
            # 获取结构运行限制判断日志
            structure_limit_log = calc_log.get('structure_limit_check', {})
            
            for gid in ['A', 'B', 'C', 'D']:
                g = snap['grids'][gid]
                # 抽水状态下跳过限制状态详细判断
                if gid == 'B' and g.is_pumping:
                    report += f"  Grid {gid}: 抽水状态，拓扑隔离，不参与限制状态判断\n"
                    continue
                limit_str = "、".join(canonical_limit_tags(g.limit_tags)) if g.limit_tags else "无"
                report += f"  Grid {gid}: {limit_str}\n"
                
                # 详细判断过程
                if g.limit_tags:
                    for tag in canonical_limit_tags(g.limit_tags):
                        if tag == "结构运行限制":
                            # 结构运行限制唯一条件：线路Open且假设并联功率流>=0.1×P_max
                            for lid in ['L_AB', 'L_AC', 'L_BD', 'L_CD']:
                                if lid in structure_limit_log:
                                    sl_info = structure_limit_log[lid]
                                    line = snap['lines'].get(lid)
                                    if line and line.mode == LineMode.OPEN and gid in [line.from_id, line.to_id]:
                                        if sl_info.get('triggered', False):
                                            hypo_power = sl_info.get('hypothetical_power', 0)
                                            threshold = sl_info.get('threshold', 0)
                                            f_from = sl_info.get('f_from', 0)
                                            f_to = sl_info.get('f_to', 0)
                                            report += f"    → {lid}为Open，假设并联计算: P=γ×(f_{line.from_id}-f_{line.to_id})=500×({f_from:.4f}-{f_to:.4f})={hypo_power:.2f}MW\n"
                                            report += f"      |P|={abs(hypo_power):.2f}MW ≥ 0.1×P_max={threshold:.2f}MW，触发结构运行限制\n"
                        elif tag == "出力上限限制":
                            total_out = g.G_actual + g.P_droop + g.P_res
                            report += f"    → 出力上限限制原因: 总出力{total_out:.2f}MW = G_max({g.G_max:.2f}MW)，且L_shed={g.L_shed:.2f}MW>0\n"
                        elif tag == "状态触发运行限制":
                            status_log = calc_log.get('status_assessment', {}).get(gid, {})
                            u_fallback = status_log.get('u_fallback', 0)
                            freq_dev = status_log.get('freq_deviation', 0)
                            if u_fallback >= 0.5:
                                report += f"    → 状态触发运行限制原因: U_fallback={u_fallback:.4f}≥0.5，触发Critical\n"
                            elif u_fallback >= 0.2:
                                report += f"    → 状态触发运行限制原因: U_fallback={u_fallback:.4f}∈[0.2,0.5)，触发Pre-warning\n"
                            elif freq_dev > 0.5:
                                report += f"    → 状态触发运行限制原因: 频率偏离{freq_dev:.4f}Hz>0.5，触发Critical\n"
                        elif tag == "负荷侧运行限制":
                            remaining_load = g.L_writeback
                            report += f"    → 负荷侧运行限制原因: 切负荷后剩余负荷{remaining_load:.2f}MW < 刚性负荷阈值\n"
            report += "\n"
            
            # 9. 风险综合评估
            report += "**[Step 9] 风险综合评估：**\n"
            report += "风险类型说明：\n"
            report += "  - **成本失控**：当日成本 > 基础成本×1.15 或 国网托管费 > 1000万元\n"
            report += "  - **结构脆弱**：存在Open线路 且 当天与前一天均存在供需失衡\n"
            report += "  - **供需失衡**：(ΔP≠0 且 |f-50|≥0.2Hz) 或 存在Critical/Collapse状态\n\n"
            
            risk_flags = []
            
            # --- 成本失控判断 ---
            report += "  【成本失控判断】\n"
            # 基础成本计算过程
            report += "    基础成本计算（系统默认状态：f=50Hz, 默认出力, 无频差无潮流无网损）:\n"
            report += "    默认出力规则: Grid C = G_base_cap; 其他Grid = min(G_base_cap, L_base_cap)\n"
            base_cost_parts = []
            base_cost_total = 0.0
            for gid in ['A', 'B', 'C', 'D']:
                g = snap['grids'][gid]
                init_price = self.initial_prices[gid]
                if gid != 'C':
                    gen_mw = min(g.G_base_cap, g.L_base_cap)
                    gen_src = f"min(G_base_cap={g.G_base_cap:.2f}, L_base_cap={g.L_base_cap:.2f})"
                else:
                    gen_mw = g.G_base_cap
                    gen_src = f"G_base_cap={g.G_base_cap:.2f}"
                gen_kwh = gen_mw * 1000.0 * 24.0
                part_cost = gen_kwh * init_price
                base_cost_total += part_cost
                g_coord = g.coord
                report += f"      Grid {gid} (位置({g_coord[0]},{g_coord[1]})): 默认出力={gen_src}={gen_mw:.2f} MW, {gen_mw:.2f}×1000×24h×{init_price}元/kWh = {part_cost:,.2f} 元\n"
                base_cost_parts.append(part_cost)
            base_cost_total = round(base_cost_total, 2)
            report += f"      基础成本合计 = {' + '.join(f'{c:,.2f}' for c in base_cost_parts)} = {base_cost_total:,.2f} 元\n"
            
            # 当日成本与阈值比较
            day_cost = snap['cost']
            threshold_cost = base_cost_total * 1.15
            cost_ratio = day_cost / base_cost_total if base_cost_total > 0 else 0
            cost_over = day_cost > threshold_cost
            e_grid_cost = cost_bd.get('e_grid_cost', 0) if cost_bd else 0
            e_grid_over = e_grid_cost > 10000000
            
            report += f"    当日成本: {day_cost:,.2f} 元，基础成本×1.15阈值: {threshold_cost:,.2f} 元\n"
            report += f"    当日成本/基础成本 = {cost_ratio:.4f} ({'>1.15' if cost_over else '≤1.15'})\n"
            if e_grid_cost > 0:
                report += f"    国网托管费: {e_grid_cost:,.2f} 元 ({'>1000万' if e_grid_over else '≤1000万'})\n"
            
            if cost_over or e_grid_over:
                reasons = []
                if cost_over:
                    reasons.append(f"当日成本{day_cost:,.2f}元 > 阈值{threshold_cost:,.2f}元")
                if e_grid_over:
                    reasons.append(f"国网托管费{e_grid_cost:,.2f}元 > 1000万元")
                report += f"    → **触发成本失控**（{'；'.join(reasons)}）\n"
                risk_flags.append("成本失控")
            else:
                report += f"    → 未触发成本失控\n"
            
            # --- 供需失衡判断 ---
            report += "  【供需失衡判断】\n"
            reserve_log = snap.get('calc_log', {}).get('reserve_activation', {})
            imbalance_cond_a = False
            imbalance_cond_b = False
            for gid in ['A', 'B', 'C', 'D']:
                g = snap['grids'][gid]
                delta_p = reserve_log.get(gid, {}).get('delta_P', 0)
                freq_dev = abs(g.frequency - F_NOM)
                if abs(delta_p) > 1e-6 and freq_dev >= 0.2:
                    imbalance_cond_a = True
                    report += f"    Grid {gid}: ΔP={delta_p:.4f}MW≠0 且 |f-50|={freq_dev:.4f}Hz≥0.2 → 条件A满足\n"
            for gid in ['A', 'B', 'C', 'D']:
                g = snap['grids'][gid]
                if g.status in [GridStatus.CRITICAL, GridStatus.COLLAPSE]:
                    imbalance_cond_b = True
                    report += f"    Grid {gid}: 状态为{g.status.value} → 条件B满足\n"
            
            if imbalance_cond_a or imbalance_cond_b:
                report += f"    → **触发供需失衡**（条件A{'满足' if imbalance_cond_a else '不满足'}，条件B{'满足' if imbalance_cond_b else '不满足'}）\n"
                risk_flags.append("供需失衡")
            else:
                report += f"    → 未触发供需失衡（条件A、B均不满足）\n"
            
            # --- 结构脆弱判断 ---
            report += "  【结构脆弱判断】\n"
            has_open_line = any(
                l.mode == LineMode.OPEN and l.open_reason != 'Grid B 抽水状态，拓扑隔离'
                for l in snap['lines'].values()
            )
            open_lines_str = [lid for lid, l in snap['lines'].items() 
                            if l.mode == LineMode.OPEN and l.open_reason != 'Grid B 抽水状态，拓扑隔离']
            
            current_imbalance = imbalance_cond_a or imbalance_cond_b
            prev_imbalance = False
            if snap_idx >= 1:
                prev_snap = self.daily_snapshots[snap_idx - 1]
                prev_reserve_log = prev_snap.get('calc_log', {}).get('reserve_activation', {})
                prev_cond_a = any(
                    abs(prev_reserve_log.get(gid, {}).get('delta_P', 0)) > 1e-6
                    and abs(g.frequency - F_NOM) >= 0.2
                    for gid, g in prev_snap['grids'].items()
                )
                prev_cond_b = any(g.status in [GridStatus.CRITICAL, GridStatus.COLLAPSE] for g in prev_snap['grids'].values())
                prev_imbalance = prev_cond_a or prev_cond_b
            
            report += f"    Open线路: {', '.join(open_lines_str) if open_lines_str else '无'}\n"
            report += f"    当天供需失衡: {'是' if current_imbalance else '否'}\n"
            report += f"    前一天供需失衡: {'是' if prev_imbalance else '否'}\n"
            
            if has_open_line and current_imbalance and prev_imbalance:
                report += f"    → **触发结构脆弱**（存在Open线路 且 连续两天供需失衡）\n"
                risk_flags.append("结构脆弱")
            else:
                miss = []
                if not has_open_line:
                    miss.append("无Open线路")
                if not current_imbalance:
                    miss.append("当天无供需失衡")
                if not prev_imbalance:
                    miss.append("前一天无供需失衡")
                report += f"    → 未触发结构脆弱（{'、'.join(miss)}）\n"
            
            report += f"\n  **风险综合评估结果: {', '.join(risk_flags) if risk_flags else '无重大风险'}**\n\n"
            
            # 10. 最终状态 (After)
            report += "**[Step 10] 日末状态 (After)：**\n"
            report += "```\n"
            report += f"{'电网':<8}{'位置':<14}{'频率(Hz)':<14}{'出力(MW)':<14}{'负荷(MW)':<14}{'P_droop(MW)':<14}{'P_res(MW)':<14}{'L_shed(MW)':<14}{'状态':<10}{'限制状态':<20}\n"
            report += "-" * 138 + "\n"
            for gid in ['A', 'B', 'C', 'D']:
                g = snap['grids'][gid]
                total_out = g.G_actual + g.P_droop + g.P_res
                # 获取限制状态
                limit_str = "、".join(canonical_limit_tags(g.limit_tags)) if g.limit_tags else "无"
                coord_str = f"({g.coord[0]},{g.coord[1]})"
                # Grid B 抽水状态特殊展示
                if gid == 'B' and g.is_pumping:
                    report += f"{gid:<8}{coord_str:<14}{g.frequency:<14.4f}{'无':<14}{0:<14.2f}{0:<14.2f}{0:<14.2f}{0:<14.2f}{'抽水中':<10}{limit_str:<20}\n"
                else:
                    report += f"{gid:<8}{coord_str:<14}{g.frequency:<14.4f}{total_out:<14.2f}{g.L_actual:<14.2f}{g.P_droop:<14.2f}{g.P_res:<14.2f}{g.L_shed:<14.2f}{g.status.value:<10}{limit_str:<20}\n"
            report += "```\n\n"
            
            # 10. 联络线功率流
            report += "**联络线功率流：**\n"
            for lid in ['L_AB', 'L_AC', 'L_BD', 'L_CD']:
                l = snap['lines'][lid]
                direction = ""
                if abs(l.power) > 1e-3:
                    if l.power > 0:
                        direction = f" ({l.from_id}→{l.to_id})"
                    else:
                        direction = f" ({l.to_id}→{l.from_id})"
                report += f"  - **{lid}**: {abs(l.power):.2f} MW{direction} (Mode: {l.mode.value})\n"
            
            report += "\n"
        return report

    def generate_final_report(self) -> str:
        """生成运行评估报告 (system_prompt 第九章)"""
        snap = self.daily_snapshots[-1]
        report = f"【运行评估报告｜Day {snap['day']}】\n\n"
        
        # 一、全网运行概况
        report += "一、全网运行概况\n\n"
        
        structures = []
        # 判断是否有OPEN的线路时，排除因Grid B抽水而断开的联络线
        has_open = any(
            l.mode == LineMode.OPEN and l.open_reason != 'Grid B 抽水状态，拓扑隔离'
            for l in snap['lines'].values()
        )
        has_series = any(l.mode == LineMode.SERIES for l in snap['lines'].values())
        has_takeover = any(g.status == GridStatus.E_GRID_TAKEOVER for g in snap['grids'].values())
        
        if has_takeover:
            structures.append("托管")
        if has_open:
            l_ac = snap['lines'].get('L_AC')
            l_bd = snap['lines'].get('L_BD')
            if l_ac and l_bd and l_ac.mode == LineMode.OPEN and l_bd.mode == LineMode.OPEN:
                structures.append("解列")
            else:
                structures.append("部分断开")
        if has_series:
            structures.append("串联")
        if not structures:
            structures.append("并联")
            
        report += f"当前运行结构：{' / '.join(structures)}\n"
        report += f"累计运行天数：{snap['day']}\n\n"
        
        # 二、电网状态汇总
        report += "二、电网状态汇总\n\n"
        
        for gid in ['A', 'B', 'C', 'D']:
            g = snap['grids'][gid]
            report += f"**Grid {gid}**：\n"
            report += f"- 当前坐标：{g.coord}\n"
            report += f"- 当前运行频率：{g.frequency:.4f} Hz\n"
            
            if g.status == GridStatus.COLLAPSE:
                report += "- 当前出力水平：0 MW (已瘫痪)\n"
            elif g.status == GridStatus.E_GRID_TAKEOVER:
                report += f"- 当前负荷水平：{g.L_base_cap:.2f} MW (国家电网托管)\n"
            elif gid == 'B' and g.is_pumping:
                report += f"- 当前出力水平：无\n"
                report += f"- 当前负荷水平：0 MW\n"
            else:
                # 出力水平 = G_actual + P_droop + P_res (公式12)
                total = g.G_actual + g.P_droop + g.P_res
                report += f"- 当前出力水平：{total:.2f} MW\n"
            
            # 状态等级中文名
            status_map = {
                GridStatus.SAFE: "安全",
                GridStatus.PRE_WARNING: "隐患",
                GridStatus.CRITICAL: "警告",
                GridStatus.COLLAPSE: "瘫痪",
                GridStatus.E_GRID_TAKEOVER: "托管"
            }
            # 抽水状态下状态显示为"抽水中"
            if gid == 'B' and g.is_pumping:
                report += f"- 当前运行状态等级：抽水中\n"
            else:
                report += f"- 当前运行状态等级：{status_map.get(g.status, g.status.value)}\n"
            
            limits = []
            # if g.decay < 1.0:
            #     limits.append("健康衰减")
            # if g.status == GridStatus.E_GRID_TAKEOVER:
            #     limits.append("托管状态")
            if g.limit_tags:
                limits.extend(canonical_limit_tags(g.limit_tags))
            if not limits:
                limits.append("无")
            report += f"- 当前限制状态：{', '.join(limits)}\n\n"
            
        # 三、风险与后果评估
        report += "三、风险与后果评估\n\n"
        
        risks = []
        # 供需失衡判定
        # 条件A: ΔP_i(t) ≠ 0 且 |f_i(t) - 50.0| >= 0.2 Hz
        reserve_log = snap.get('calc_log', {}).get('reserve_activation', {})
        cond_a = any(
            abs(reserve_log.get(gid, {}).get('delta_P', 0)) > 1e-6
            and abs(g.frequency - F_NOM) >= 0.2
            for gid, g in snap['grids'].items()
        )
        # 条件B: FSM 判定为警告或瘫痪
        cond_b = any(g.status in [GridStatus.CRITICAL, GridStatus.COLLAPSE] for g in snap['grids'].values())
        if cond_a or cond_b:
            risks.append("供需失衡")
            
        # 结构脆弱判定：存在 open 且上一天和当天均存在系统失衡
        def check_imbalance(snap_to_check: Dict) -> bool:
            """检查指定快照是否存在供需失衡"""
            check_reserve_log = snap_to_check.get('calc_log', {}).get('reserve_activation', {})
            check_cond_a = any(
                abs(check_reserve_log.get(gid, {}).get('delta_P', 0)) > 1e-6
                and abs(g.frequency - F_NOM) >= 0.2
                for gid, g in snap_to_check['grids'].items()
            )
            check_cond_b = any(g.status in [GridStatus.CRITICAL, GridStatus.COLLAPSE] for g in snap_to_check['grids'].values())
            return check_cond_a or check_cond_b
        
        current_imbalance = cond_a or cond_b  # 当天是否失衡
        prev_imbalance = False
        if len(self.daily_snapshots) >= 2:
            prev_snap = self.daily_snapshots[-2]
            prev_imbalance = check_imbalance(prev_snap)
        
        if has_open and current_imbalance and prev_imbalance:
            risks.append("结构脆弱")
            
        # 成本失控判定：基于最终日快照数据重新计算，与每日报告 Step 9 逻辑一致
        cost_bd_final = snap.get('calc_log', {}).get('cost_breakdown', {})
        day_cost_final = snap['cost']
        base_cost_final = 0.0
        for gid_fc in ['A', 'B', 'C', 'D']:
            g_fc = snap['grids'][gid_fc]
            ip = self.initial_prices[gid_fc]
            gen_fc = g_fc.G_base_cap if gid_fc == 'C' else min(g_fc.G_base_cap, g_fc.L_base_cap)
            base_cost_final += gen_fc * 1000.0 * 24.0 * ip
        base_cost_final = round(base_cost_final, 2)
        e_grid_cost_final = cost_bd_final.get('e_grid_cost', 0)
        if (base_cost_final > 0 and day_cost_final > base_cost_final * 1.15) or e_grid_cost_final > 10000000:
            risks.append("成本失控")
            
        report += f"当前系统面临的主要风险类型：{', '.join(risks) if risks else '无重大风险'}\n"
        report += f"当日运行成本总计：{snap['cost']:,.2f} 元\n\n"
        
        # 生成 Checklist（评估要点）
        checklist = self._generate_checklist(snap, structures, risks)
        report += checklist
        
        return report

    def _generate_checklist(self, snap: Dict, structures: List[str], risks: List[str]) -> str:
        """根据报告数据动态生成 Checklist（评估要点）"""
        checklist = f"\n{'='*80}\n"
        checklist += "【Checklist】\n"
        checklist += f"{'='*80}\n\n"
        
        day = snap['day']
        cost = snap['cost']
        
        # 状态等级中文名映射
        status_map = {
            GridStatus.SAFE: "安全",
            GridStatus.PRE_WARNING: "隐患",
            GridStatus.CRITICAL: "警告",
            GridStatus.COLLAPSE: "瘫痪",
            GridStatus.E_GRID_TAKEOVER: "托管"
        }
        
        item_num = 1
        
        # 1. 报告结构检查
        # checklist += f'{item_num}. 模型回复是否为一份标题是"【运行评估报告｜Day {day}】"的报告，且包含"全网运行概况"、"电网状态汇总"、"风险与后果评估"这三个部分？\n'
        # item_num += 1
        
        # 2. 全网运行概况检查
        # structure_str = '、'.join(structures) if structures else '并联'
        # checklist += f'{item_num}. 模型回复的"全网运行概况"是否包含目前的累计运行天数为{day}天，且包含"{structure_str}"？\n'
        # item_num += 1
        
        # 3. 电网状态汇总通用检查
        # checklist += f'{item_num}. 模型回复的"电网状态汇总"是否包含"Grid A、Grid B、Grid C、Grid D"四个电网"运行频率；出力或负荷水平；运行状态等级；限制状态"这四项的内容（或类似含义）？\n'
        # item_num += 1
        
        # 4-7. 每个电网的详细检查
        for gid in ['A', 'B', 'C', 'D']:
            g = snap['grids'][gid]
            
            # 计算出力/负荷水平
            if g.status == GridStatus.COLLAPSE:
                power_str = "0"
                power_type = "出力水平"
            # elif g.status == GridStatus.E_GRID_TAKEOVER:
            #     power_str = f"{g.L_base_cap:.2f}"
            #     power_type = "负荷水平"
            elif gid == 'B' and g.is_pumping:
                # 抽水状态下不出力，出力为0，checklist显示"无"
                power_str = "无"
                power_type = "出力水平"
            # elif g.grid_type == GridType.LOAD_CENTER:
            #     actual_load = g.L_actual - g.L_shed
            #     power_str = f"{actual_load:.2f}"
            #     power_type = "负荷水平"
            else:
                total = g.G_actual + g.P_droop + g.P_res
                power_str = f"{total:.2f}"
                power_type = "出力水平"
            
            # 获取状态等级
            # 抽水状态下状态显示为"抽水中"
            if gid == 'B' and g.is_pumping:
                status_str = "抽水中"
            else:
                status_str = status_map.get(g.status, g.status.value)
            
            # 获取限制状态
            limits = []
            if g.limit_tags:
                limits.extend(canonical_limit_tags(g.limit_tags))
            limit_str = "、".join(limits) if limits else "无"
            
            # 坐标
            coord_str = f"（{g.coord[0]},{g.coord[1]}）"
            
            if power_str != "无":
                checklist += f'{item_num}. 模型回复的Grid {gid}的运行频率是否为"{g.frequency:.4f}"Hz；{power_type}是否为"{power_str}"MW；运行状态等级是否为"{status_str}"；限制状态是否为"{limit_str}"；坐标是否为{coord_str}？（注：运行状态等级须写中文名称，如“安全”；写英文如“Safe”不满足。）\n'
            else:
                checklist += f'{item_num}. 模型回复的Grid {gid}的运行频率是否为"{g.frequency:.4f}"Hz；{power_type}是否为"{power_str}"；运行状态等级是否为"{status_str}"；限制状态是否为"{limit_str}"；坐标是否为{coord_str}？（注：运行状态等级须写中文名称，如“安全”；写英文如“Safe”不满足。）\n'
            item_num += 1
        
        # 8. 风险类型检查
        risk_count = len(risks)
        risk_str = '、'.join(risks) if risks else '无重大风险'
        if risks:
            checklist += f'{item_num}. 模型回复的"风险与后果评估"是否包含"{risk_str}"这{risk_count}个主要风险类型？\n'
        else:
            checklist += f'{item_num}. 模型回复的"风险与后果评估"是否标明"{risk_str}"？\n'
        item_num += 1
        
        # 9. 成本检查
        checklist += (f'{item_num}. 模型回复的"风险与后果评估"是否包含"{cost:,.2f}"元的当日运行成本总计？'
                      f'（注：金额数值等价即可，千位分隔符有无不影响判定，即“{cost:,.2f}”与“{cost:.2f}”视为相同。）\n')
        
        checklist += f"\n{'='*80}\n"
        
        return checklist

    def load_state(self, state: Dict, previous_events: List[Dict] = None):
        """加载状态快照
        
        如果快照中没有提供 coord 或 velocity，会自动预计算到快照日的坐标。
        这确保了 Grid C 和 Grid D 的坐标在从快照恢复后是正确的。
        
        Args:
            state: 状态快照字典
            previous_events: 历史事件列表，用于预计算 Grid D 坐标时获取温度、频率、政策等状态
        """
        snapshot_day = state.get('t', 0)
        self.t = snapshot_day
        
        # 检查是否需要预计算坐标
        # 如果快照中没有提供 Grid C 的 coord 或 velocity，需要预计算
        grids_state = state.get('grids', {})
        need_precompute_coords = False
        
        if snapshot_day > 0:
            # 检查 Grid C 的坐标和速度是否在快照中提供
            # 也检查其他 Grid 的坐标
            for gid in ['A', 'B', 'C', 'D']:
                grid_state = grids_state.get(gid, {})
                if 'coord' not in grid_state:
                    need_precompute_coords = True
                    break
        
        # 如果需要预计算坐标，先执行预计算
        if need_precompute_coords:
            self.precompute_coordinates_to_day(snapshot_day, previous_events)
        
        # 加载快照中提供的状态（会覆盖预计算的值）
        for gid, gstate in grids_state.items():
            if gid in self.grids:
                g = self.grids[gid]
                if 'frequency' in gstate:
                    g.frequency = gstate['frequency']
        
        # 重新计算线路路径（坐标可能已更新）
        self._calculate_all_paths()
