"""
古墓探险物理系统实现
基于 system_prompt.md 中的规则实现完整的物理判定系统
"""
import math
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations
from decimal import Decimal, ROUND_HALF_UP


def math_round(value: float, decimals: int = 1) -> float:
    """
    使用Decimal实现严格的数学四舍五入
    解决Python内置round()的银行家舍入问题（如9.95应进位为10.0而非9.9）
    """
    d = Decimal(str(value))
    if decimals == 0:
        rounded = d.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    else:
        quantize_str = '0.' + '0' * decimals
        rounded = d.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)
    return float(rounded)


class Direction(Enum):
    """移动方向"""
    NORTH = "north"  # Y+1
    SOUTH = "south"  # Y-1
    EAST = "east"   # X+1
    WEST = "west"   # X-1
    STAY = "stay"   # 原地停留
    JUMP_UP = "jump_up"  # 向上层跳跃
    JUMP_DOWN = "jump_down"  # 向下层跳跃


@dataclass
class GridPoint:
    """格点物理参数"""
    S: bool = False  # 墙体标记：否=畅通，是=封死
    V: bool = False  # 真空标记：否=实地，是=真空
    L: float = 5.0   # 承重上限
    D: float = 10.0  # 耐受度
    F: int = 0       # 疲劳度
    shadow: bool = False  # 黑影标记
    original_D: float = 10.0  # 原始耐受度（用于跳跃落地后恢复）
    
    def __repr__(self):
        return f"Grid(S={self.S}, V={self.V}, L={self.L}, D={self.D}, F={self.F}, shadow={self.shadow})"


@dataclass
class ExplorerState:
    """探险者状态"""
    H: int = 1  # 层级
    X: int = 1  # 横向坐标
    Y: int = 1  # 纵向坐标
    W: float = 2.0  # 负重
    M: Direction = Direction.NORTH  # 面朝方向
    last_move_success: bool = True  # 上一轮是否成功移动
    jump_landing_round: bool = False  # 是否处于跳跃落地回合
    on_vacuum: bool = False  # 是否处于真空点上（用于真空延迟处决判定）
    
    def get_coord(self) -> Tuple[int, int, int]:
        return (self.H, self.X, self.Y)


class TombSystem:
    """古墓物理系统"""
    
    def __init__(self, initial_state):
        # 初始化3层5x5网格
        self.grids: Dict[Tuple[int, int, int], GridPoint] = {}
        for h in [1, 2, 3]:
            for x in range(1, 6):
                for y in range(1, 6):
                    self.grids[(h, x, y)] = GridPoint()
        
        self.explorer = ExplorerState()
        self.shadow_count_by_layer: Dict[int, int] = {1: 0, 2: 0, 3: 0}
        self.last_shadow_count_by_layer: Dict[int, int] = {1: 0, 2: 0, 3: 0}  # 上一轮各层黑影数（用于状态维持判定）
        self.last_axis: Optional[str] = None  # 上一次移动的轴向
        self.axis_count: int = 0  # 连续相同轴向计数
        self.query_count: int = 0  # 本轮查询次数
        self.path_history: List[Tuple[int, int, int]] = [[initial_state["H"], initial_state["X"], initial_state["Y"]]]  # 路径历史（用于拓扑回路判定）
        self.affected_coords: Set[Tuple[int, int, int]] = set()  # 本轮受影响的坐标
        self.natural_f_growth_coords: Set[Tuple[int, int, int]] = set()  # 本轮已执行自然增长F+1的格点（用于自然增长上限=1约束）
        self.landing_halved_this_round: bool = False  # 本轮Tier3是否已对落脚点执行过D减半（规则四-4-(3)：仅执行一次）
        self.topology_inner_coords: Set[Tuple[int, int, int]] = set()  # 记录所有曾经是拓扑回路内部的格点（用于观测反噬判定）
        self.w_change_history: List[Dict] = []  # W值变化历史：每轮记录[{"reason": "原因", "change": 变化值, "before": 变化前值, "after": 变化后值}]
        self.l_change_history: List[Dict] = []  # L值变化历史：每轮记录[{"coord": 坐标, "reason": "原因", "change": 变化值, "before": 变化前值, "after": 变化后值}]
        self.d_change_history: List[Dict] = []  # D值变化历史：每轮记录[{"coord": 坐标, "reason": "原因", "change": 变化值, "before": 变化前值, "after": 变化后值}]
        self.f_change_history: List[Dict] = []  # F值变化历史：每轮记录[{"coord": 坐标, "reason": "原因", "change": 变化值, "before": 变化前值, "after": 变化后值}]
        self.initial_w_this_round: float = 2.0  # 本轮移动开始时的W值
        self.initial_grid_params: Dict[Tuple[int, int, int], Dict] = {}  # 本轮移动开始时各格点的L/D/F初始值
        
        # 全局状态数组：存储所有坐标的参数历史 [H][X][Y] = GridPoint
        self.global_state: Dict[int, Dict[int, Dict[int, Dict]]] = {}
        self._initialize_global_state()
        
    def _initialize_global_state(self):
        """初始化全局状态数组"""
        for h in [1, 2, 3]:
            self.global_state[h] = {}
            for x in range(1, 6):
                self.global_state[h][x] = {}
                for y in range(1, 6):
                    grid = self.get_grid(h, x, y)
                    self.global_state[h][x][y] = {
                        "S": grid.S,
                        "V": grid.V,
                        "L": grid.L,
                        "D": grid.D,
                        "F": grid.F,
                        "shadow": grid.shadow
                    }
    
    def update_global_state(self):
        """更新全局状态数组：将所有格点的当前参数同步到全局状态"""
        for h in [1, 2, 3]:
            for x in range(1, 6):
                for y in range(1, 6):
                    grid = self.get_grid(h, x, y)
                    self.global_state[h][x][y] = {
                        "S": grid.S,
                        "V": grid.V,
                        "L": grid.L if grid.L != float('inf') else "∞",
                        "D": grid.D if grid.D != float('inf') else "∞",
                        "F": grid.F,
                        "shadow": grid.shadow
                    }
    
    def get_global_state_snapshot(self) -> Dict:
        """获取全局状态快照"""
        snapshot = {}
        for h in [1, 2, 3]:
            snapshot[h] = {}
            for x in range(1, 6):
                snapshot[h][x] = {}
                for y in range(1, 6):
                    snapshot[h][x][y] = self.global_state[h][x][y].copy()
        return snapshot
    
    def format_global_state(self, layer: Optional[int] = None) -> str:
        """格式化全局状态输出"""
        result = "[全局状态数组]：\n"
        layers = [layer] if layer else [1, 2, 3]
        
        for h in layers:
            result += f"\n层级 {h}（H={h}）：\n"
            result += "     X=1    X=2    X=3    X=4    X=5\n"
            for y in range(5, 0, -1):  # 从北到南（Y从大到小）
                result += f"Y={y} "
                for x in range(1, 6):  # 从西到东（X从小到大）
                    state = self.global_state[h][x][y]
                    shadow_str = "影" if state["shadow"] else "·"
                    s_str = "墙" if state["S"] else "·"
                    v_str = "空" if state["V"] else "·"
                    l_val = state['L'] if isinstance(state['L'], (int, float)) else state['L']
                    d_val = state['D'] if isinstance(state['D'], (int, float)) else state['D']
                    result += f"[{shadow_str}{s_str}{v_str}]L{l_val}-D{d_val}-F{state['F']} "
                result += "\n"
        
        return result
    
    def mark_affected(self, h: int, x: int, y: int):
        """标记受影响的坐标"""
        if self.is_valid_coord(h, x, y):
            self.affected_coords.add((h, x, y))
    
    def record_w_change(self, reason: str, change: float):
        """记录W值变化"""
        before = self.explorer.W
        # 使用math_round避免浮点数精度问题（如17.95应为18.0而非17.9）
        self.explorer.W = math_round(self.explorer.W + change, 1)
        after = self.explorer.W
        if after < 2.0:
            after = 2.0
            self.explorer.W = 2.0
            self.w_change_history.append({
            "reason": reason + "，W值低于2.0，启动下限保护，已修正为2.0",
            "change": change,
            "before": before,
            "after": after
        })
        else:
            self.w_change_history.append({
                "reason": reason,
                "change": change,
                "before": before,
                "after": after
            })
    
    def record_l_change(self, h: int, x: int, y: int, reason: str, new_value: float = None, change: float = None):
        """记录L值变化"""
        grid = self.get_grid(h, x, y)
        before = grid.L
        if new_value is not None:
            grid.L = new_value
        elif change is not None:
            grid.L = max(0, grid.L + change)
        after = grid.L
        # if before != after:
        self.l_change_history.append({
            "coord": (h, x, y),
            "reason": reason,
            "before": before if before != float('inf') else "∞",
            "after": after if after != float('inf') else "∞"
        })
        # 检查L归零导致真空化，并触发连锁坍塌和垂直贯穿坍塌
        if grid.L <= 0:
            if not grid.V:  # V之前不是True，现在因为L归零变为True
                grid.V = True
                # 连锁坍塌：通知四个共边相邻格点L下降1
                adjacent_points = [
                    (h, x, y + 1),
                    (h, x, y - 1),
                    (h, x + 1, y),
                    (h, x - 1, y),
                ]
                for ah, ax, ay in adjacent_points:
                    if self.is_valid_coord(ah, ax, ay):
                        self.mark_affected(ah, ax, ay)
                        self.record_l_change(ah, ax, ay, f"连锁坍塌（来自({h},{x},{y})）L下降", change=-1)
                # 垂直贯穿坍塌（H1→H2）：底层L归零坍塌，正上方中层F+1
                if h == 1:
                    self.mark_affected(2, x, y)
                    self.record_f_change(2, x, y, f"垂直贯穿坍塌（H1→H2，来自({h},{x},{y})）F增加", change=1)
            else:
                grid.V = True
    
    def record_d_change(self, h: int, x: int, y: int, reason: str, new_value: float = None, halve: bool = False):
        """记录D值变化"""
        grid = self.get_grid(h, x, y)
        before = grid.D
        if new_value is not None:
            grid.D = new_value
        elif halve:
            grid.D = math.floor(grid.D / 2)
        after = grid.D
        if before != after:
            self.d_change_history.append({
                "coord": (h, x, y),
                "reason": reason,
                "before": before if before != float('inf') else "∞",
                "after": after if after != float('inf') else "∞"
            })
    
    def record_f_change(self, h: int, x: int, y: int, reason: str, change: int = 1):
        """记录F值变化"""
        grid = self.get_grid(h, x, y)
        before = grid.F
        grid.F += change
        after = grid.F
        if before != after:
            self.f_change_history.append({
                "coord": (h, x, y),
                "reason": reason,
                "change": change,
                "before": before,
                "after": after
            })
    
    def record_natural_f_growth(self, h: int, x: int, y: int, reason: str) -> bool:
        """
        记录自然增长F+1（受自然增长上限=1约束）
        适用于：重复踏入、滑行残留、黑影生成
        返回：是否成功执行了F+1（如果该格点本轮已执行过自然增长，则返回False）
        """
        coord = (h, x, y)
        # 检查该格点本轮是否已执行过自然增长F+1
        if coord in self.natural_f_growth_coords:
            # 自然增长上限=1，跳过
            return False
        
        # 标记该格点已执行自然增长
        self.natural_f_growth_coords.add(coord)
        # 执行F+1
        self.record_f_change(h, x, y, reason, change=1)
        return True
    
    def get_grid(self, h: int, x: int, y: int) -> GridPoint:
        """获取格点"""
        return self.grids.get((h, x, y), GridPoint())
    
    def is_valid_coord(self, h: int, x: int, y: int) -> bool:
        """检查坐标是否合法"""
        return 1 <= h <= 3 and 1 <= x <= 5 and 1 <= y <= 5
    
    def parse_direction(self, direction_str: str) -> Direction:
        """解析方向字符串"""
        direction_str = direction_str.lower().strip()
        
        # 非法指令检测：检测到以下词汇时解析为原地停留
        # 1. 逻辑撤回/修正词汇
        retraction_keywords = ["撤回", "返回上一步", "改为", "刚才说错了"]
        # 2. 模糊意图指令
        ambiguous_keywords = ["随便走", "哪边安全走哪边"]
        # 3. 指令过载关键词
        overload_keywords = ["连跳", "东北", "东南", "西北", "西南", "斜向", "同时向", 
                            "右前方", "看情况", "两格", "两次", "三步", "连续", "一直", "到底"]
        
        # 检查是否包含非法指令关键词
        all_invalid_keywords = retraction_keywords + ambiguous_keywords + overload_keywords
        for keyword in all_invalid_keywords:
            if keyword in direction_str:
                return Direction.STAY
        
        # 优先检查跳跃/跨越关键词
        if "跳跃" in direction_str or "跨越" in direction_str or "jump" in direction_str:
            if "上" in direction_str or "up" in direction_str or "向上" in direction_str:
                return Direction.JUMP_UP
            elif "下" in direction_str or "down" in direction_str or "向下" in direction_str:
                return Direction.JUMP_DOWN
            else:
                return Direction.JUMP_DOWN  # 默认向下
        elif "停留" in direction_str or "stay" in direction_str or "原地" in direction_str:
            return Direction.STAY
        elif "北" in direction_str or direction_str in ["north", "n"]:
            return Direction.NORTH
        elif "南" in direction_str or direction_str in ["south", "s"]:
            return Direction.SOUTH
        elif "东" in direction_str or "右" in direction_str or direction_str in ["east", "e", "right"]:
            return Direction.EAST
        elif "西" in direction_str or "左" in direction_str or direction_str in ["west", "w", "left"]:
            return Direction.WEST
        else:
            return Direction.STAY
    
    def calculate_target_coord(self, direction: Direction) -> Tuple[int, int, int]:
        """计算目标坐标"""
        h, x, y = self.explorer.H, self.explorer.X, self.explorer.Y
        
        if direction == Direction.NORTH:
            return (h, x, y + 1)
        elif direction == Direction.SOUTH:
            return (h, x, y - 1)
        elif direction == Direction.EAST:
            return (h, x + 1, y)
        elif direction == Direction.WEST:
            return (h, x - 1, y)
        elif direction == Direction.JUMP_UP:
            return (h + 1, x, y)
        elif direction == Direction.JUMP_DOWN:
            return (h - 1, x, y)
        else:
            return (h, x, y)
    
    def tier_0_space_topology(self, target_h: int, target_x: int, target_y: int) -> bool:
        """
        Tier 0: 空间拓扑与前置干扰
        返回是否应该终止（断路）
        """
        current_grid = self.get_grid(self.explorer.H, self.explorer.X, self.explorer.Y)
        
        # 观测代偿：超额查询扣除
        # 规则：若查询项数量超过1项，立足点耐受度D执行独立减半损耗
        if self.query_count > 1:
            excess = self.query_count - 1
            self.mark_affected(self.explorer.H, self.explorer.X, self.explorer.Y)
            for i in range(excess):
                self.record_d_change(self.explorer.H, self.explorer.X, self.explorer.Y, f"观测代偿超额查询第{i+1}次减半", halve=True)
                if current_grid.D <= 0:
                    return True  # 断路
        
        # 拓扑回路判定在落脚点执行，这里不处理
        return False
    
    def get_axis(self, direction: Direction) -> Optional[str]:
        """获取移动轴向"""
        if direction in [Direction.NORTH, Direction.SOUTH]:
            return "Y"
        elif direction in [Direction.EAST, Direction.WEST]:
            return "X"
        return None
    
    def tier_1_kinetic_conversion(self, direction: Direction) -> Tuple[int, int, int]:
        """
        Tier 1: 动能转换与位移指令修正
        返回修正后的目标坐标
        注意：动能断裂重置（W+2）不在此处执行，而是在确认有效位移发生的起步瞬间执行
        """
        # 检查是否为跨层跳跃（跳跃不受层级特性影响）
        is_jump = (direction == Direction.JUMP_UP or direction == Direction.JUMP_DOWN)
        
        # 计算基础目标坐标
        target_h, target_x, target_y = self.calculate_target_coord(direction)
        
        # 跨层跳跃直接返回，不受层级特性影响
        if is_jump:
            return (target_h, target_x, target_y)
        
        # H2层镜像反转（仅对水平移动有效）
        if self.explorer.H == 2:
            if direction == Direction.WEST:
                target_x = self.explorer.X + 1  # 实际向右
            elif direction == Direction.EAST:
                target_x = self.explorer.X - 1  # 实际向左
        
        # H3层双格位移（仅对同层移动有效）
        if self.explorer.H == 3 and direction in [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]:
            if direction == Direction.NORTH:
                target_y = self.explorer.Y + 2
            elif direction == Direction.SOUTH:
                target_y = self.explorer.Y - 2
            elif direction == Direction.EAST:
                target_x = self.explorer.X + 2
            elif direction == Direction.WEST:
                target_x = self.explorer.X - 2
        
        return (target_h, target_x, target_y)
    
    def check_h2_fatigue_inertia(self, direction: Direction, target_h: int, target_x: int, target_y: int) -> Tuple[int, int, int]:
        """
        H2层疲劳失控惯性检查
        如果F>=3且是横向（X轴）位移，追加一格外向位移（实际移动方向）
        注意：H2层存在镜像反转，指令向东实际向西，指令向西实际向东
        追加位移的方向应该是本轮实际执行位移后的最新矢量方向
        """
        if target_h != 2:
            return (target_h, target_x, target_y)
        
        # 只对横向（X轴）位移触发
        if direction not in [Direction.EAST, Direction.WEST]:
            return (target_h, target_x, target_y)
        
        # 根据规则：判定基准是"落脚点"（目标格子）的F值，而非出发点
        target_grid = self.get_grid(target_h, target_x, target_y)
        if target_grid.F >= 3:
            # 追加位移之前，先检查基础位移目标（第一格）是否合法
            # 如果第一格本身就不合法，不追加位移，由后续tier_2_path_collision统一处理第一格撞墙
            if not self.is_valid_coord(target_h, target_x, target_y):
                return (target_h, target_x, target_y)
            
            # 检查第一格是否有墙体，如果有墙体也不追加位移
            first_grid = self.get_grid(target_h, target_x, target_y)
            if first_grid.S:
                return (target_h, target_x, target_y)
            
            # 保存第一格坐标，用于追加位移撞墙时回退
            first_target_x = target_x
            
            # 强制追加一格外向位移（实际移动方向）
            # H2层存在镜像反转：指令向东实际向西，指令向西实际向东
            # 因此追加位移的方向应该与指令方向相反
            if direction == Direction.EAST:
                # 指令向东，实际向西，追加位移向西
                actual_move_direction = Direction.WEST
                target_x -= 1
            elif direction == Direction.WEST:
                # 指令向西，实际向东，追加位移向东
                actual_move_direction = Direction.EAST
                target_x += 1
            
            # 检查追加位移后的目标是否合法（包括边界和墙体）
            inertia_collision = False
            if not self.is_valid_coord(target_h, target_x, target_y):
                inertia_collision = True
            else:
                second_grid = self.get_grid(target_h, target_x, target_y)
                if second_grid.S:
                    inertia_collision = True
            
            if inertia_collision:
                # 追加位移撞墙：回退到第一格
                target_x = first_target_x
                
                self.record_w_change("H2层疲劳失控惯性追加位移撞墙", 2.0)
                # 底层投影L下降
                self.mark_affected(1, target_x, target_y)
                self.record_l_change(1, target_x, target_y, "H2层疲劳失控惯性追加位移撞墙底层投影L下降", change=-1)
        
        return (target_h, target_x, target_y)
    
    def check_command_resonance(self, direction: Direction, target_h: int, target_x: int, target_y: int):
        """
        指令共振检查：连续3次相同轴向
        """
        if direction in [Direction.JUMP_UP, Direction.JUMP_DOWN]:
            # 跨层跳跃重置计数
            self.last_axis = None
            self.axis_count = 0
            return
        
        current_axis = self.get_axis(direction)
        if current_axis:
            if current_axis == self.last_axis:
                self.axis_count += 1
            else:
                self.last_axis = current_axis
                self.axis_count = 1
            
            # 连续3次相同轴向
            if self.axis_count >= 3:
                self.mark_affected(target_h, target_x, target_y)
                self.record_l_change(target_h, target_x, target_y, "指令共振（连续3次相同轴向）L下降", change=-1)
                
                # 底层投影L下降
                if target_h != 1:
                    self.mark_affected(1, target_x, target_y)
                    self.record_l_change(1, target_x, target_y, "指令共振底层投影L下降", change=-1)
    
    def tier_2_path_collision(self, target_h: int, target_x: int, target_y: int, 
                              is_jump: bool = False) -> Tuple[bool, Optional[Tuple[int, int, int]], bool, bool]:
        """
        Tier 2: 路径冲突与硬碰撞确认
        返回 (是否成功, 实际落脚/出事坐标, 是否触发了物理爆破, 是否坠亡)
        - 是否坠亡: True表示坠亡（如超载即坠、失速坠亡等），False表示非法失败（如撞墙、边界溢出等）
        - H3层采用分段裁决：先判定过渡点，再判定落脚点
        """
        def resolve_shadow_rejection(coord: Tuple[int, int, int], grid: GridPoint, reason_prefix: str) -> Optional[Tuple[bool, Optional[Tuple[int, int, int]], bool, bool]]:
            self.record_w_change(f"{reason_prefix}影迹排斥", 2.0)
            # 结构脆化：D执行减半（若超载则连续执行两次减半）
            # 注意：这里先执行一次减半，如果W>L，在tier_3中会再执行一次减半
            self.record_d_change(coord[0], coord[1], coord[2], f"{reason_prefix}影迹排斥脆化D减半", halve=True)
            # 真空化相变：V永久转为"是"
            grid.V = True
            # 硬性约束（超载即坠）：若W>=10，踏入真空点瞬间直接判定坠亡
            # 注意：若为跳跃动作，跳跃重力惩罚(+2.0)尚未结算，需预先纳入判断
            effective_w = self.explorer.W + (2.0 if is_jump else 0.0)
            if effective_w >= 10:
                return (False, coord, False, True)
            # H3层过渡点/落脚点影迹排斥：若脆化导致D归零，判定失速坠亡
            if self.explorer.H == 3 and grid.D <= 0:
                return (False, coord, False, True)
            return None

        triggered_blast = False

        # H3层滑行路径检查：必须先检查过渡点，再检查落脚点
        # 不能像其他层一样先对最终target做一次统一S/V判定，否则会错误拦截“第二格受阻但可停留在第一格”的情况
        if self.explorer.H == 3 and not is_jump:
            mid_coord = None
            if self.explorer.Y != target_y:
                mid_coord = (self.explorer.H, self.explorer.X, (self.explorer.Y + target_y) // 2)
            elif self.explorer.X != target_x:
                mid_coord = (self.explorer.H, (self.explorer.X + target_x) // 2, self.explorer.Y)

            if not mid_coord:
                return (False, None, False, False)

            mid_is_valid = self.is_valid_coord(mid_coord[0], mid_coord[1], mid_coord[2])
            if not mid_is_valid:
                self.record_w_change("H3层过渡点碰撞", 2.0)
                self.mark_affected(1, self.explorer.X, self.explorer.Y)
                self.record_l_change(1, self.explorer.X, self.explorer.Y, "H3层过渡点碰撞路径弱化起点底层L下降", change=-1)
                return (False, None, False, False)

            mid_grid = self.get_grid(mid_coord[0], mid_coord[1], mid_coord[2])
            if mid_grid.S:
                self.record_w_change("H3层过渡点碰撞", 2.0)
                self.mark_affected(1, self.explorer.X, self.explorer.Y)
                self.record_l_change(1, self.explorer.X, self.explorer.Y, "H3层过渡点碰撞路径弱化起点底层L下降", change=-1)
                self.mark_affected(1, mid_coord[1], mid_coord[2])
                self.record_l_change(1, mid_coord[1], mid_coord[2], "H3层过渡点碰撞路径弱化撞墙点底层L下降", change=-1)
                self.record_l_change(1, mid_coord[1], mid_coord[2], "H3层过渡点碰撞撞墙点底层L额外下降", change=-1)
                return (False, None, False, False)

            # 滑行重合逻辑：如果第一格是真空，直接在第一格坠落
            if mid_grid.V and not self.explorer.jump_landing_round:
                return (False, mid_coord, False, True)

            shadow_result = None
            if mid_grid.shadow:
                shadow_result = resolve_shadow_rejection(mid_coord, mid_grid, "H3层过渡点")
            if shadow_result:
                return shadow_result

            # 第一格合法后，第二格非法/撞墙时允许停留在第一格
            target_is_valid = self.is_valid_coord(target_h, target_x, target_y)
            if not target_is_valid:
                self.record_w_change("H3层落脚点碰撞", 1.0)
                return (True, mid_coord, False, False)

            target_grid = self.get_grid(target_h, target_x, target_y)
            if target_grid.S:
                self.record_w_change("H3层落脚点碰撞", 1.0)
                self.mark_affected(1, target_x, target_y)
                self.record_l_change(1, target_x, target_y, "H3层落脚点碰撞路径弱化撞墙点底层L下降", change=-1)
                self.record_l_change(1, target_x, target_y, "H3层落脚点碰撞撞墙点底层L额外下降", change=-1)
                return (True, mid_coord, False, False)

            if target_grid.V and not self.explorer.jump_landing_round:
                return (False, (target_h, target_x, target_y), False, True)

            shadow_result = None
            if target_grid.shadow:
                shadow_result = resolve_shadow_rejection((target_h, target_x, target_y), target_grid, "H3层落脚点")
            if shadow_result:
                return shadow_result

            return (True, (target_h, target_x, target_y), False, False)

        # 非H3层/跨层跳跃：按普通目标点裁决
        if not self.is_valid_coord(target_h, target_x, target_y):
            return (False, None, False, False)  # 非法失败，非坠亡

        target_grid = self.get_grid(target_h, target_x, target_y)

        # 物理爆破特权（跨层跳跃）
        if is_jump and target_grid.S:
            # 检查是否为坍塌废墟（非原始岩壁）
            # 这里简化处理：如果S=是，允许爆破
            triggered_blast = True
            target_grid.S = False
            self.record_f_change(target_h, target_x, target_y, "物理爆破特权F增加", change=1)

        # 检查墙体
        if target_grid.S:
            return (False, None, False, False)  # 非法失败（撞墙），非坠亡

        # 检查真空（跳跃落地回合有特权）
        # 规则四-1-(2)和规则七-3：跨层跳跃落地时，即使V=是，探险者也可安全立足
        if target_grid.V and not self.explorer.jump_landing_round and not is_jump:
            return (False, (target_h, target_x, target_y), False, True)  # 坠亡（踏入真空）

        shadow_result = None
        if target_grid.shadow:
            shadow_result = resolve_shadow_rejection((target_h, target_x, target_y), target_grid, "")
        if shadow_result:
            return shadow_result

        return (True, (target_h, target_x, target_y), triggered_blast, False)  # 成功，非坠亡
    
    def tier_3_mass_settlement(self, start_h: int, start_x: int, start_y: int, target_h: int, target_x: int, target_y: int):
        """
        Tier 3: 质量对碰与质量结算
        """
        target_grid = self.get_grid(target_h, target_x, target_y)
        self.mark_affected(target_h, target_x, target_y)
        
        # 底层位移损耗（成功完成坐标更新）
        if start_h == 1 and target_h == 1:
            self.record_w_change("底层位移损耗", 1.0)
        
        # 底层粘滞步进（离开起始点时检查）
        if start_h == 1:
            start_grid = self.get_grid(start_h, start_x, start_y)
            self.mark_affected(start_h, start_x, start_y)
            if start_grid.D <= 2:
                self.record_w_change("底层粘滞步进", 1.0)

        # 稳态检查（跳跃落地回合）
        if self.explorer.jump_landing_round:
            self.record_d_change(target_h, target_x, target_y, "跳跃落地稳态检查D设为无限", new_value=float('inf'))
            return
        
        # 疲劳先行
        if target_grid.F >= 3:
            self.record_d_change(target_h, target_x, target_y, "疲劳先行（F>=3）D减半", halve=True)
            self.landing_halved_this_round = True
        
        # 超载结算
        # 规则：W值在进行W > L逻辑对比前，一律向上取整
        w_for_comparison = math.ceil(self.explorer.W)
        if w_for_comparison > target_grid.L:
            if target_grid.F < 3:
                self.record_d_change(target_h, target_x, target_y, f"超载结算（W={w_for_comparison}>L={int(target_grid.L)}）D减半", halve=True)
            self.landing_halved_this_round = True
            self.record_f_change(target_h, target_x, target_y, "超载结算F增加", change=1)
            
            # 高疲劳超载双重减半（但如果是黑影排斥+超载，不触发高疲劳双重减半）
            # 规则：结构脆化：格点耐受度 D 执行减半（若超载则连续执行两次减半）
            # 黑影排斥时已经减半了一次，超载时又减半了一次，总共两次，不再触发高疲劳双重减半
            # if target_grid.F >= 3 and not target_grid.shadow:
            #     self.record_d_change(target_h, target_x, target_y, "高疲劳超载双重减半D减半", halve=True)
        
        # 检查坍塌：如果D归零或L归零，标记V为是
        # 记录是否因为L或D归零导致V变为True（用于连锁坍塌判断）
        v_became_true_due_to_collapse = False
        if target_grid.D <= 0 or target_grid.L <= 0:
            if not target_grid.V:  # 如果V之前不是True，现在因为L或D归零变为True
                v_became_true_due_to_collapse = True
            target_grid.V = True
            if target_grid.D <= 0:
                target_grid.S = True  # 坍塌形成废墟
        
        # 连锁坍塌：只有当V因为L或D归零变为"是"时，才触发连锁坍塌
        # 规则：连锁坍塌只发生在由于L或D归零导致V变成"是"的情况
        if v_became_true_due_to_collapse:
            adjacent_points = [
                (target_h, target_x, target_y + 1),
                (target_h, target_x, target_y - 1),
                (target_h, target_x + 1, target_y),
                (target_h, target_x - 1, target_y),
            ]
            for h, x, y in adjacent_points:
                if self.is_valid_coord(h, x, y):
                    self.mark_affected(h, x, y)
                    self.record_l_change(h, x, y, f"连锁坍塌（来自({target_h},{target_x},{target_y})）L下降", change=-1)
        
        # 垂直贯穿坍塌（H1→H2）
        if target_h == 1 and target_grid.V:
            self.mark_affected(2, target_x, target_y)
            self.record_f_change(2, target_x, target_y, "垂直贯穿坍塌（H1→H2）F增加", change=1)
    
    def tier_4_stress_conduction(self, start_h: int, start_x: int, start_y: int,
                                 target_h: int, target_x: int, target_y: int,
                                 is_jump: bool = False):
        """
        Tier 4: 应力传导与区域重组
        """
        # H3层滑行弱化
        if start_h == 3 and start_h == target_h:
            # 计算实际移动距离，H3层正常滑行应该移动2格
            move_distance = abs(start_x - target_x) + abs(start_y - target_y)
            is_normal_slide = (move_distance == 2)  # 正常滑行移动2格
            
            # 动能残留（轨道磨损）：起始点、过渡点、落脚点的疲劳度F均增加1
            # 注意：起始点的F+1会在生成黑影时执行，这里不需要重复增加
            # 正常滑行时，过渡点的F+1也在生成黑影时执行
            # 落脚点碰撞时（只移动1格），落脚点就是原来的过渡点，不生成黑影，需要在这里单独增加F
            self.mark_affected(start_h, start_x, start_y)
            # 起始点的F+1在生成黑影时执行，这里不重复
            
            # 过渡点
            if is_normal_slide:
                # 正常滑行：过渡点的F+1在生成黑影时执行，这里不重复
                if start_x != target_x:
                    mid_x = (start_x + target_x) // 2
                    self.mark_affected(start_h, mid_x, start_y)
                elif start_y != target_y:
                    mid_y = (start_y + target_y) // 2
                    self.mark_affected(start_h, start_x, mid_y)
            # 落脚点碰撞时（只移动1格），落脚点就是原来的过渡点，不生成黑影
            # 落脚点的F+1在下面统一处理
            
            # 落脚点：因为轨道磨损F+1（落脚点不生成黑影，所以需要在这里单独增加）
            # 使用自然增长方法，受自然增长上限=1约束
            self.mark_affected(target_h, target_x, target_y)
            self.record_natural_f_growth(target_h, target_x, target_y, "H3层滑行轨道磨损落脚点F增加")
            
            # 路径弱化底层：起点、过渡点、落脚点正下方的底层坐标L下降1
            path_points = []
            if start_x != target_x:
                for x in range(min(start_x, target_x), max(start_x, target_x) + 1):
                    path_points.append((1, x, start_y))
            elif start_y != target_y:
                for y in range(min(start_y, target_y), max(start_y, target_y) + 1):
                    path_points.append((1, start_x, y))
            
            # 震动吸收失败（H1→H3）：在L下降前检查底层L≤2的点，W额外+1
            for h, x, y in path_points:
                if self.is_valid_coord(h, x, y):
                    bottom_grid = self.get_grid(h, x, y)
                    if bottom_grid.L <= 2:
                        self.record_w_change(f"震动吸收失败（底层({h},{x},{y})L={bottom_grid.L}≤2）", 1.0)
            
            # 执行路径弱化底层L下降
            for h, x, y in path_points:
                if self.is_valid_coord(h, x, y):
                    self.mark_affected(h, x, y)
                    self.record_l_change(h, x, y, "H3层滑行路径弱化底层L下降", change=-1)
        
        # H2层撞墙应力下传
        # （在碰撞处理中已处理）
        
        
        
        # 生成黑影
        # 规则：只要探险者成功离开坐标A进入坐标B，坐标A立即生成一个"黑影"
        # 这适用于所有移动（同层移动和跨层跳跃）
        start_grid = self.get_grid(start_h, start_x, start_y)
        self.mark_affected(start_h, start_x, start_y)
        if not start_grid.shadow:
            start_grid.shadow = True
            # 使用自然增长方法，受自然增长上限=1约束
            self.record_natural_f_growth(start_h, start_x, start_y, "生成黑影F增加")
            self.shadow_count_by_layer[start_h] += 1
        else:
            # 如果已经有黑影，F仍然要+1（疲劳度累积）
            # 使用自然增长方法，受自然增长上限=1约束
            self.record_natural_f_growth(start_h, start_x, start_y, "已有黑影疲劳累积F增加")
        
        # H3层滑行：过渡点也生成黑影（仅对同层移动有效）
        # 注意：如果发生了H3层落脚点碰撞，探险者只移动了1格（停在过渡点），
        # 此时target就是过渡点，不应该再生成黑影（落脚点不生成黑影）
        if start_h == target_h and start_h == 3:
            # 计算实际移动距离，H3层正常滑行应该移动2格
            move_distance = abs(start_x - target_x) + abs(start_y - target_y)
            # 只有移动了2格（正常滑行）才在过渡点生成黑影
            if move_distance == 2:
                if start_x != target_x:
                    mid_x = (start_x + target_x) // 2
                    mid_grid = self.get_grid(start_h, mid_x, start_y)
                    self.mark_affected(start_h, mid_x, start_y)
                    if not mid_grid.shadow:
                        mid_grid.shadow = True
                        # 使用自然增长方法，受自然增长上限=1约束
                        self.record_natural_f_growth(start_h, mid_x, start_y, "H3层滑行过渡点生成黑影F增加")
                        self.shadow_count_by_layer[start_h] += 1
                    else:
                        # 使用自然增长方法，受自然增长上限=1约束
                        self.record_natural_f_growth(start_h, mid_x, start_y, "H3层滑行过渡点已有黑影F增加")
                    # 过渡点超载结算
                    w_for_comparison = math.ceil(self.explorer.W)
                    if w_for_comparison > mid_grid.L:
                        self.record_d_change(start_h, mid_x, start_y, f"H3层过渡点超载结算（W={w_for_comparison}>L={int(mid_grid.L)}）D减半", halve=True)
                        self.record_f_change(start_h, mid_x, start_y, "H3层过渡点超载结算F增加", change=1)
                elif start_y != target_y:
                    mid_y = (start_y + target_y) // 2
                    mid_grid = self.get_grid(start_h, start_x, mid_y)
                    self.mark_affected(start_h, start_x, mid_y)
                    if not mid_grid.shadow:
                        mid_grid.shadow = True
                        # 使用自然增长方法，受自然增长上限=1约束
                        self.record_natural_f_growth(start_h, start_x, mid_y, "H3层滑行过渡点生成黑影F增加")
                        self.shadow_count_by_layer[start_h] += 1
                    else:
                        # 使用自然增长方法，受自然增长上限=1约束
                        self.record_natural_f_growth(start_h, start_x, mid_y, "H3层滑行过渡点已有黑影F增加")
                    # 过渡点超载结算
                    w_for_comparison = math.ceil(self.explorer.W)
                    if w_for_comparison > mid_grid.L:
                        self.record_d_change(start_h, start_x, mid_y, f"H3层过渡点超载结算（W={w_for_comparison}>L={int(mid_grid.L)}）D减半", halve=True)
                        self.record_f_change(start_h, start_x, mid_y, "H3层过渡点超载结算F增加", change=1)
        
        # H3层落点崩塌
        if start_h == 3 and start_h == target_h:
            mid_h = 2
            mid_grid = self.get_grid(mid_h, target_x, target_y)
            self.mark_affected(mid_h, target_x, target_y)
            mid_grid.S = True
        
        # 重复踏入疲劳
        target_grid = self.get_grid(target_h, target_x, target_y)
        self.mark_affected(target_h, target_x, target_y)
        if target_grid.shadow:  # 已经踏过
            # 使用自然增长方法，受自然增长上限=1约束
            self.record_natural_f_growth(target_h, target_x, target_y, "重复踏入疲劳F增加")
    
    def tier_5_global_resonance(self):
        """
        Tier 5: 全局共振与稳态终审
        
        每次位移结束后，对所有三层都检查材质老化和结构性塌缩的触发条件。
        
        触发条件精度说明（规则六-3-(3)）：
        1. 精确命中判定：仅在本轮结算终点的黑影总数精确处于对应倍数（5/9 的倍数）时触发。
           若通过单次位移产生的黑影增量使总数跳过了阈值，则视为动能跨越，本轮不触发。
        2. 状态维持判定：若本轮未产生新黑影，但上一轮已达成的黑影总数仍维持在阈值点位上，
           系统判定应力共振持续生效，本轮将重复执行对应的材质老化或结构塌缩判定。
        """
        # 对每一层都进行检查
        for layer in [1, 2, 3]:
            shadow_count = self.shadow_count_by_layer[layer]
            last_shadow_count = self.last_shadow_count_by_layer[layer]
            
            # 判断该层是否产生了新黑影
            new_shadows_generated = (shadow_count != last_shadow_count)
            
            # 材质老化判定（5的倍数）
            should_trigger_aging = False
            if shadow_count > 0 and shadow_count % 5 == 0:
                if new_shadows_generated:
                    # 精确命中判定：检查是否跳过了某个5的倍数阈值
                    skipped_threshold = False
                    if last_shadow_count < shadow_count:
                        for threshold in range(last_shadow_count + 1, shadow_count):
                            if threshold % 5 == 0:
                                skipped_threshold = True
                                break
                    if not skipped_threshold:
                        should_trigger_aging = True
                else:
                    # 状态维持判定：本轮未产生新黑影，但黑影数仍在5的倍数上
                    should_trigger_aging = True
            
            if should_trigger_aging:
                reason_suffix = "状态维持" if not new_shadows_generated else "精确命中"
                for x in range(1, 6):
                    for y in range(1, 6):
                        grid = self.get_grid(layer, x, y)
                        if not grid.shadow:
                            self.mark_affected(layer, x, y)
                            self.record_f_change(layer, x, y, f"材质老化（H{layer}层黑影数{shadow_count}为5倍数，{reason_suffix}）F增加", change=1)
            
            # 结构性塌缩判定（9的倍数）
            should_trigger_collapse = False
            if shadow_count > 0 and shadow_count % 9 == 0:
                if new_shadows_generated:
                    # 精确命中判定：检查是否跳过了某个9的倍数阈值
                    skipped_threshold = False
                    if last_shadow_count < shadow_count:
                        for threshold in range(last_shadow_count + 1, shadow_count):
                            if threshold % 9 == 0:
                                skipped_threshold = True
                                break
                    if not skipped_threshold:
                        should_trigger_collapse = True
                else:
                    # 状态维持判定：本轮未产生新黑影，但黑影数仍在9的倍数上
                    should_trigger_collapse = True
            
            if should_trigger_collapse:
                reason_suffix = "状态维持" if not new_shadows_generated else "精确命中"
                for x in range(1, 6):
                    for y in range(1, 6):
                        self.mark_affected(layer, x, y)
                        self.record_l_change(layer, x, y, f"结构性塌缩（H{layer}层黑影数{shadow_count}为9倍数，{reason_suffix}）L下降", change=-1)
    
    def check_topology_loop(self, target_h: int, target_x: int, target_y: int) -> Optional[Dict]:
        """
        检查是否构成拓扑回路
        返回回路信息或None
        
        规则：
        1. 回路是所有走过的路径相连可以围成一个正方形或者长方形（如 1->2->3->1）
        2. 中间至少有一个内部格点
        3. 边界集合P包括路径围成的矩形区域的所有边界点（不仅仅是路径经过的点）
        """
        # 只检查同层的路径
        # print(self.path_history)
        points = [(h, x, y) for h, x, y in self.path_history if h == target_h]
        # print(points)
        points = list(set(points))  # 去重
        
        # --- 1. 基础校验 ---
        if not points or len(points) < 4:
            # print("错误: 点数不足")
            return None

        # --- 2. 降维处理 (共面性检查) ---
        h_set = set(p[0] for p in points)
        x_set = set(p[1] for p in points)
        y_set = set(p[2] for p in points)

        fixed_dim = None # 记录被固定的维度值
        fixed_axis = -1  # 0:h固定, 1:x固定, 2:y固定
        plane_coords = [] # 降维后的 2D 坐标 (u, v)

        if len(h_set) == 1:
            fixed_dim = list(h_set)[0]
            fixed_axis = 0
            plane_coords = [(p[1], p[2]) for p in points] # (x, y)
        # elif len(x_set) == 1:
        #     fixed_dim = list(x_set)[0]
        #     fixed_axis = 1
        #     plane_coords = [(p[0], p[2]) for p in points] # (h, y)
        # elif len(y_set) == 1:
        #     fixed_dim = list(y_set)[0]
        #     fixed_axis = 2
        #     plane_coords = [(p[0], p[1]) for p in points] # (h, x)
        else:
            # print("错误: 坐标不在同一平面内")
            return None
        
        # 遍历所有的点组合，去除重复点
        def get_combinations_descending(points):
            """
            生成所有长度 >= 4 的点组合，并按组合长度从大到小排序。
            """
            # 1. 确保输入没有重复点 (如果输入已经是唯一的，可以去掉这一步)
            unique_points = list(set(points))
            n = len(unique_points)
            
            # 如果点数少于4个，直接返回空
            if n < 4:
                return []
            
            result = []
            
            # 2. 倒序循环：从 n (所有点) 开始，递减直到 4
            # range(start, stop, step) -> range(n, 3, -1) 会生成 n, n-1, ..., 4
            for r in range(n, 3, -1):
                # combinations(iterable, r) 返回长度为 r 的所有子序列
                for combo in combinations(unique_points, r):
                    # 只保留包含当前落脚点的组合
                    if (target_x, target_y) in combo:
                        result.append(combo)            
                
            return result
        
        all_combinations = get_combinations_descending(plane_coords)
        
        # 收集所有有效的回路（去重）
        valid_loops = []
        seen_loops = set()  # 用于去重，存储 (boundary_tuple, inner_tuple)
        
        for combo in all_combinations:
            result = self._check_loop(combo, target_h, fixed_axis, fixed_dim)
            if result:
                # 生成回路的唯一标识（边界和内部格点的frozenset）
                boundary_key = frozenset(tuple(pt) for pt in result["boundary"])
                inner_key = frozenset(tuple(pt) for pt in result["inner"])
                loop_key = (boundary_key, inner_key)
                
                # 只添加未见过的回路
                if loop_key not in seen_loops:
                    seen_loops.add(loop_key)
                    valid_loops.append(result)
        
        # 如果没有有效回路，返回None
        if not valid_loops:
            return None
        
        # 如果只有一个回路，直接返回
        if len(valid_loops) == 1:
            return valid_loops[0]
        
        # 多重回路共振判定
        return self._resolve_multiple_loops(valid_loops)
    
    def _resolve_multiple_loops(self, valid_loops: List[Dict]) -> Optional[Dict]:
        """
        多重回路共振判定：当同时闭合多个回路时，按以下顺序锁定唯一生效的拓扑结构
        
        优先级规则：
        1. 最大面积准则 (A_max)：优先结算内部格点数 A 最大的回路
        2. 坐标轴轴向定标（若A值相等）：
           - Y_min (极小值优先)：最南者胜
           - X_min (极小值优先)：最西者胜
           - Y_max (极大值优先)：最北者胜
           - X_max (极大值优先)：最东者胜
        3. 时间戳总和准则：边界点 P 的 ID 编号之和，数值越大（动能越新鲜）的回路胜出
        4. 谐振失效判定：若所有判定均完全相等，所有回路判定为无效
        """
        def get_loop_metrics(loop: Dict) -> Dict:
            """计算回路的各项指标"""
            boundary = loop["boundary"]
            inner = loop["inner"]
            
            # 1. 内部格点数 A
            A = len(inner)
            
            # 2. 提取边界点的坐标边界值
            xs = [pt[1] for pt in boundary]  # X坐标
            ys = [pt[2] for pt in boundary]  # Y坐标
            
            y_min = min(ys)
            x_min = min(xs)
            y_max = max(ys)
            x_max = max(xs)
            
            # 3. 时间戳总和：边界点在 path_history 中的 ID 编号之和
            timestamp_sum = 0
            for pt in boundary:
                for idx, hist_pt in enumerate(self.path_history):
                    if (hist_pt[0], hist_pt[1], hist_pt[2]) == pt:
                        timestamp_sum += (idx + 1)  # ID 从 1 开始
            
            return {
                "A": A,
                "Y_min": y_min,
                "X_min": x_min,
                "Y_max": y_max,
                "X_max": x_max,
                "timestamp_sum": timestamp_sum
            }
        
        def get_priority_key(metrics: Dict) -> Tuple:
            """根据指标计算排序键"""
            # - A 取负值（越大越优先）
            # - y_min, x_min 正常（越小越优先）
            # - y_max, x_max 取负值（越大越优先）
            # - timestamp_sum 取负值（越大越优先）
            return (
                -metrics["A"],
                metrics["Y_min"],
                metrics["X_min"],
                -metrics["Y_max"],
                -metrics["X_max"],
                -metrics["timestamp_sum"]
            )
        
        # 计算所有回路的指标和排序键
        loops_with_info = []
        for i, loop in enumerate(valid_loops):
            metrics = get_loop_metrics(loop)
            key = get_priority_key(metrics)
            loops_with_info.append({
                "loop": loop,
                "metrics": metrics,
                "key": key,
                "index": i + 1  # 回路编号从1开始
            })
        
        # 按优先级排序
        loops_with_info.sort(key=lambda x: x["key"])
        
        # 生成判别过程记录
        resolution_process = []
        resolution_process.append(f"检测到 {len(valid_loops)} 个潜在拓扑回路，启动多重回路共振判定：")
        
        # 列出所有候选回路
        for info in loops_with_info:
            m = info["metrics"]
            loop = info["loop"]
            boundary_str = str(loop["boundary"])
            inner_str = str(loop["inner"])
            resolution_process.append(
                f"  回路{info['index']}：边界={boundary_str}，内部格点={inner_str}，"
                f"A={m['A']}，Y_min={m['Y_min']}，X_min={m['X_min']}，"
                f"Y_max={m['Y_max']}，X_max={m['X_max']}，时间戳总和={m['timestamp_sum']}"
            )
        
        # 检查是否存在谐振失效
        if len(loops_with_info) >= 2:
            if loops_with_info[0]["key"] == loops_with_info[1]["key"]:
                resolution_process.append("判定结果：所有指标完全相等，触发谐振失效，所有回路判定为无效")
                # 返回谐振失效信息，包含判别过程但标记为无效
                return {
                    "resonance_failure": True,
                    "resolution_process": resolution_process,
                    "candidate_count": len(valid_loops)
                }
        
        # 确定胜出原因
        winner = loops_with_info[0]
        winner_metrics = winner["metrics"]
        
        # 找出决定性因素
        if len(loops_with_info) >= 2:
            second = loops_with_info[1]
            second_metrics = second["metrics"]
            
            deciding_factor = None
            if winner_metrics["A"] != second_metrics["A"]:
                deciding_factor = f"最大面积准则（A={winner_metrics['A']} > {second_metrics['A']}）"
            elif winner_metrics["Y_min"] != second_metrics["Y_min"]:
                deciding_factor = f"Y_min极小值优先（{winner_metrics['Y_min']} < {second_metrics['Y_min']}）"
            elif winner_metrics["X_min"] != second_metrics["X_min"]:
                deciding_factor = f"X_min极小值优先（{winner_metrics['X_min']} < {second_metrics['X_min']}）"
            elif winner_metrics["Y_max"] != second_metrics["Y_max"]:
                deciding_factor = f"Y_max极大值优先（{winner_metrics['Y_max']} > {second_metrics['Y_max']}）"
            elif winner_metrics["X_max"] != second_metrics["X_max"]:
                deciding_factor = f"X_max极大值优先（{winner_metrics['X_max']} > {second_metrics['X_max']}）"
            elif winner_metrics["timestamp_sum"] != second_metrics["timestamp_sum"]:
                deciding_factor = f"时间戳总和准则（{winner_metrics['timestamp_sum']} > {second_metrics['timestamp_sum']}）"
            
            resolution_process.append(f"判定结果：回路{winner['index']}胜出，决定性因素：{deciding_factor}")
        else:
            resolution_process.append(f"判定结果：仅有一个有效回路，回路{winner['index']}生效")
        
        # 将判别过程添加到胜出回路的信息中
        result_loop = winner["loop"].copy()
        result_loop["resolution_process"] = resolution_process
        result_loop["candidate_count"] = len(valid_loops)
        
        return result_loop

        
    def _check_loop(self, plane_coords, target_h, fixed_axis, fixed_dim):
        # 1. 预处理：去重并转为集合 (消除顺序影响)
        input_set = set(plane_coords)
        
        # 点数不足4个，绝对构不成矩形
        if len(input_set) < 4:
            # print(f"错误: 点数不足 ({len(input_set)})，无法构成矩形")
            return None

        # 2. 提取边界 (Bounding Box)
        us = [c[0] for c in input_set]
        vs = [c[1] for c in input_set]
        min_u, max_u = min(us), max(us)
        min_v, max_v = min(vs), max(vs)
        
        width = max_u - min_u
        height = max_v - min_v

        # --- 尺寸检查 ---
        if width < 2 or height < 2:
            # print(f"错误: 矩形尺寸太小 ({width}x{height})，中间无空格子")
            return None

        # --- 核心判定逻辑 ---
        
        # 判定 A: 必要的4个角点必须存在于输入中
        # 如果输入了 [(0,0), (0,5), (5,5), (5,0), (0,2)], 它是合法的
        # 但如果输入 [(0,0), (0,5), (5,5), (0,2)], 缺了(5,0)角点，则不是矩形回路
        needed_corners = {
            (min_u, min_v), (min_u, max_v),
            (max_u, min_v), (max_u, max_v)
        }
        
        if not needed_corners.issubset(input_set):
            # print("错误: 输入点集缺失了关键的角点，无法闭合为标准矩形")
            # 找出缺了哪个角，方便调试
            missing = needed_corners - input_set
            # print(f"缺失角点: {missing}")
            return None

        # 判定 B: 所有输入点都必须落在四条边上
        # 不允许有点落在矩形内部，也不允许有点落在边界框之外(计算min/max时已排除外部，所以主要防内部)
        for u, v in input_set:
            on_u_edge = (u == min_u or u == max_u)
            on_v_edge = (v == min_v or v == max_v)
            
            # 一个点只要满足 u在边界 或 v在边界，就在矩形边框上
            # 注意：这里我们只检查是否“在边线上”。如果点是 (min_u+1, min_v+1)，它就在内部 -> 非法
            if not (on_u_edge or on_v_edge):
                # print(f"错误: 发现非法点 ({u}, {v})，它不在矩形的边框上")
                return None

        # --- 5. 生成结果点集 (填充内部) ---
        # boundary只保留历史走过的点（在input_set中的点）
        all_boundary_points = []
        inner_points = []

        for u in range(min_u, max_u + 1):
            for v in range(min_v, max_v + 1):
                
                # 还原为 3D 坐标
                if fixed_axis == 0:   # h 固定
                    pt = (fixed_dim, u, v)
                elif fixed_axis == 1: # x 固定
                    pt = (u, fixed_dim, v)
                else:                 # y 固定
                    pt = (u, v, fixed_dim)

                # 区分边界和内部
                if u == min_u or u == max_u or v == min_v or v == max_v:
                    # 只保留历史走过的点（在input_set中的点）
                    if (u, v) in input_set:
                        all_boundary_points.append(pt)
                else:
                    inner_points.append(pt)

        return {
            "boundary": all_boundary_points,
            "inner": inner_points,
            "layer": target_h
        }
    
    def process_topology_loop(self, loop_info: Dict, is_jump: bool = False):
        """
        处理拓扑回路
        """
        boundary = loop_info["boundary"]
        inner = loop_info["inner"]
        layer = loop_info["layer"]
        
        A = len(inner)  # 内部格点数
        
        # 内部结构湮灭
        for h, x, y in inner:
            grid = self.get_grid(h, x, y)
            self.mark_affected(h, x, y)
            grid.V = True
            grid.S = False
            # 记录该格点为拓扑回路内部格点（用于观测反噬判定）
            self.topology_inner_coords.add((h, x, y))
        
        if is_jump:
            # +2已在jump时处理过
            self.record_w_change("拓扑回路跳跃执行减重奖励", -self.explorer.W/2)
        
        # 能量重组：边界加固
        boundary_sorted = sorted(boundary, key=lambda c: (c[2], c[1]))  # 按Y, X排序
        for i, (h, x, y) in enumerate(boundary_sorted):
            if i < A:
                self.mark_affected(h, x, y)
                self.record_l_change(h, x, y, f"拓扑回路边界加固（第{i+1}个边界点）L增加, {boundary_sorted}", change=1)
        
        # 边界D回满：若圈内包含被粉碎的S=是的格点，所有边界点的耐受度D立即强制回满至10
        has_crushed_s = any(self.get_grid(h, x, y).S for h, x, y in inner)
        if has_crushed_s:
            for h, x, y in boundary:
                self.mark_affected(h, x, y)
                self.record_d_change(h, x, y, "拓扑回路边界D回满（圈内包含被粉碎S=是的格点）", new_value=10.0)
        
        # 减重奖励：圈内每消失一个黑影，W减半
        # cleared_shadows = sum(1 for h, x, y in inner if self.get_grid(h, x, y).shadow)
        # for _ in range(cleared_shadows):
        #     before = self.explorer.W
        #     self.explorer.W = max(2.0, math.floor(self.explorer.W / 2))
        #     change = self.explorer.W - before
        #     if change != 0:
        #         self.w_change_history.append({
        #             "reason": "拓扑回路减重奖励",
        #             "change": change,
        #             "before": before,
        #             "after": self.explorer.W
        #         })
        
        # 负荷代偿
        self.record_w_change(f"拓扑回路负荷代偿（内部格点数A={A}）", A)
        
        # 规则九-7-(4) 碰撞判定：检查因W激增是否导致当前立足点直接超载（W > L）
        # 注意：跳跃落地回合处于稳态（D=∞），豁免超载判定
        # 规则四-4-(3)：若本轮Tier3已因超载/高疲劳对落脚点减半，则不再二次减半
        if not is_jump and not self.landing_halved_this_round:
            landing_grid = self.get_grid(self.explorer.H, self.explorer.X, self.explorer.Y)
            w_for_comparison = math.ceil(self.explorer.W)
            if w_for_comparison > landing_grid.L:
                self.mark_affected(self.explorer.H, self.explorer.X, self.explorer.Y)
                self.record_d_change(self.explorer.H, self.explorer.X, self.explorer.Y, 
                                   f"拓扑回路碰撞判定超载（W={w_for_comparison}>L={int(landing_grid.L)}）D减半", halve=True)
                self.record_f_change(self.explorer.H, self.explorer.X, self.explorer.Y, 
                                   "拓扑回路碰撞判定超载F增加", change=1)
        
        # 疲劳累积
        for h, x, y in boundary:
            self.mark_affected(h, x, y)
            self.record_f_change(h, x, y, "拓扑回路边界疲劳累积F增加", change=2)
        
        # 跨层应力对冲
        if layer != 1:
            # 向下穿透
            for h, x, y in inner:
                if layer == 3:
                    self.mark_affected(2, x, y)
                    self.record_l_change(2, x, y, "拓扑回路跨层应力对冲（H3→H2）L下降", change=-1)
                    bottom_grid = self.get_grid(2, x, y)
                    if not bottom_grid.shadow:
                        self.shadow_count_by_layer[2] += 1
                    bottom_grid.shadow = True
                    self.record_f_change(2, x, y, "拓扑回路跨层应力对冲生成黑影F增加", change=1)
                elif layer == 2:
                    self.mark_affected(1, x, y)
                    self.record_l_change(1, x, y, "拓扑回路跨层应力对冲（H2→H1）L下降", change=-1)
                    bottom_grid = self.get_grid(1, x, y)
                    if not bottom_grid.shadow:
                        self.shadow_count_by_layer[1] += 1
                    bottom_grid.shadow = True
                    self.record_f_change(1, x, y, "拓扑回路跨层应力对冲生成黑影F增加", change=1)
        
        if layer == 1 and A >= 3:
            # 向上支撑
            landing_h, landing_x, landing_y = self.explorer.H, self.explorer.X, self.explorer.Y
            self.mark_affected(2, landing_x, landing_y)
            self.record_d_change(2, landing_x, landing_y, "拓扑回路向上支撑D设为无限", new_value=float('inf'))
    
    def process_jump(self, target_h: int, target_x: int, target_y: int) -> Dict:
        """
        处理跨层跳跃
        """
        # 重力惩罚
        self.record_w_change("跨层跳跃重力惩罚", 2.0)
        
        # 物理爆破
        target_grid = self.get_grid(target_h, target_x, target_y)
        self.mark_affected(target_h, target_x, target_y)
        adjacent_points = [
            (target_h, target_x, target_y + 1),
            (target_h, target_x, target_y - 1),
            (target_h, target_x + 1, target_y),
            (target_h, target_x - 1, target_y),
        ]
        
        for h, x, y in adjacent_points:
            if self.is_valid_coord(h, x, y):
                grid = self.get_grid(h, x, y)
                if grid.S:
                    self.mark_affected(h, x, y)
                    grid.S = False
                    self.record_f_change(target_h, target_x, target_y, f"跨层跳跃物理爆破（清除({h},{x},{y})墙体）F增加", change=1)
        
        # 震动净化：清除当前层所有黑影
        cleared_shadows = 0
        for x in range(1, 6):
            for y in range(1, 6):
                grid = self.get_grid(target_h, x, y)
                if grid.shadow:
                    self.mark_affected(target_h, x, y)
                    grid.shadow = False
                    cleared_shadows += 1
                    self.shadow_count_by_layer[target_h] = max(0, self.shadow_count_by_layer[target_h] - 1)
        
        # 能量反馈
        if cleared_shadows >= 3:
            self.record_d_change(target_h, target_x, target_y, f"跨层跳跃能量反馈（清除{cleared_shadows}个黑影>=3）D恢复", new_value=10.0)
        if cleared_shadows >= 5:
            self.record_l_change(target_h, target_x, target_y, f"跨层跳跃能量反馈（清除{cleared_shadows}个黑影>=5）L增加", change=1)
        
        # 瞬时固化
        self.explorer.jump_landing_round = True
        # 保存原始D值
        if target_grid.D != float('inf'):
            target_grid.original_D = target_grid.D
        self.record_d_change(target_h, target_x, target_y, "跨层跳跃瞬时固化D设为无限", new_value=float('inf'))
    
    def move(self, direction_str: str, query_coords: Optional[List[Tuple[int, int, int]]] = None) -> List[Dict]:
        """
        执行移动指令，返回快照列表（场景A/B/C）
        比对步骤前后坐标，若一致则视为原地停留，触发重复踏入疲劳F+1
        """
        start_h = self.explorer.H
        start_x = self.explorer.X
        start_y = self.explorer.Y
        snapshots = self._move_core(direction_str, query_coords)

        if (self.explorer.H, self.explorer.X, self.explorer.Y) == (start_h, start_x, start_y):
            # 区分"有效位移导致坠亡"与"真正的原地驻留"：
            # _move_core 仅在 is_death=True 时生成 "start" 类型快照，
            # 撞墙/驻留等坐标未更新的场景只生成 "current" 类型。
            is_movement_death = any(s.get("类型") == "start" for s in snapshots)

            if is_movement_death:
                # 规则十三-4"死人无法引起震动"：探险者在 Tier 2 死亡后，
                # 不执行 Tier 4 效果（黑影生成/F+1），也不触发"重复踏入"
                pass
            else:
                self.mark_affected(self.explorer.H, self.explorer.X, self.explorer.Y)
                self.record_natural_f_growth(self.explorer.H, self.explorer.X, self.explorer.Y, "重复踏入疲劳F增加")

            # 重新生成最后一个快照，使其包含黑影/F变化的记录
            if snapshots:
                last = snapshots[-1]
                snapshots[-1] = self.generate_snapshot(
                    self.explorer.H, self.explorer.X, self.explorer.Y,
                    last.get("类型", "current"),
                    last.get("拓扑回路"),
                    last.get("终止", False),
                    last.get("终止原因")
                )
        
        # 本轮结束后，更新上一轮黑影数（用于下一轮的状态维持判定）
        for layer in [1, 2, 3]:
            self.last_shadow_count_by_layer[layer] = self.shadow_count_by_layer[layer]
        
        return snapshots

    def _move_core(self, direction_str: str, query_coords: Optional[List[Tuple[int, int, int]]] = None) -> List[Dict]:
        """
        执行移动指令的核心逻辑，返回快照列表（场景A/B/C）
        """
        snapshots = []
        # 重置受影响坐标集合
        self.affected_coords = set()
        # 重置自然增长F记录（用于自然增长上限=1约束）
        self.natural_f_growth_coords = set()
        self.landing_halved_this_round = False
        # 记录本轮初始W值并清空变化历史
        self.initial_w_this_round = self.explorer.W
        self.w_change_history = []
        self.l_change_history = []
        self.d_change_history = []
        self.f_change_history = []
        # 记录当前坐标的初始L/D/F值
        current_grid = self.get_grid(self.explorer.H, self.explorer.X, self.explorer.Y)
        self.initial_grid_params = {
            (self.explorer.H, self.explorer.X, self.explorer.Y): {
                "L": current_grid.L if current_grid.L != float('inf') else "∞",
                "D": current_grid.D if current_grid.D != float('inf') else "∞",
                "F": current_grid.F
            }
        }
        
        # 场景A：探测快照（在位移前输出）
        # 记录是否因观测反噬导致坠亡
        observation_backlash_death = False
        if query_coords:
            for qh, qx, qy in query_coords:
                if self.is_valid_coord(qh, qx, qy):
                    # 观测反噬检查（规则九-3-(3)）：
                    # 针对拓扑回路内部具备真空性质（即V=是）的格点执行参数查询，
                    # 将导致扫描波全反射，探险者当前立足点耐受度D强制减半
                    query_grid = self.get_grid(qh, qx, qy)
                    if (qh, qx, qy) in self.topology_inner_coords and query_grid.V:
                        # 触发观测反噬：立足点D减半
                        self.mark_affected(self.explorer.H, self.explorer.X, self.explorer.Y)
                        self.record_d_change(self.explorer.H, self.explorer.X, self.explorer.Y, 
                                           f"观测反噬（查询拓扑回路内部真空格点({qh},{qx},{qy})）D减半", halve=True)
                        # 检查立足点D是否归零（类似观测代偿的断路判定）
                        current_grid = self.get_grid(self.explorer.H, self.explorer.X, self.explorer.Y)
                        if current_grid.D <= 0:
                            observation_backlash_death = True
                    # 保存当前状态（探测不影响物理状态）
                    snapshots.append(self.generate_snapshot(qh, qx, qy, "query"))
        
        # 如果观测反噬导致D归零，探险者原地坠亡
        if observation_backlash_death:
            self.update_global_state()
            snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "current", None, True, "观测反噬导致立足点D归零，探险者原地坠亡"))
            return snapshots
        
        # 重置状态
        self.query_count = len(query_coords) if query_coords else 0
        
        # 如果上一回合是跳跃落地回合，恢复D值并检查是否在真空点上
        if self.explorer.jump_landing_round:
            current_grid = self.get_grid(self.explorer.H, self.explorer.X, self.explorer.Y)
            if current_grid.D == float('inf'):
                current_grid.D = current_grid.original_D
            # 跳跃落地到真空点后，下一轮进入真空延迟处决状态
            if current_grid.V:
                self.explorer.on_vacuum = True
        
        self.explorer.jump_landing_round = False
        
        direction = self.parse_direction(direction_str)
        
        # 场景C：原地停留（坐标未更新）
        if direction == Direction.STAY:
            current_grid = self.get_grid(self.explorer.H, self.explorer.X, self.explorer.Y)
            
            # 标记动能断裂（坐标未更新）
            self.explorer.last_move_success = False
            
            # 真空延迟处决：在真空点上执行原地驻留，判定生命终止，在最开始进行结算
            if self.explorer.on_vacuum:
                self.update_global_state()
                snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "current", None, True, "真空延迟处决：在真空点上执行原地驻留"))
                return snapshots
            
            self.record_w_change("原地停留", 1.0)

            # 底层沉降逻辑
            if self.explorer.H == 1:
                self.record_l_change(self.explorer.H, self.explorer.X, self.explorer.Y, "原地停留底层沉降L下降", change=-1)
                if current_grid.L <= 0:
                    self.update_global_state()
                    snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "current", None, True, "底层沉降导致L归零"))
                    return snapshots
            
            # 疲劳先行检查（按照Tier 3的顺序）
            # 规则：W值在进行W > L逻辑对比前，一律向上取整
            w_for_comparison = math.ceil(self.explorer.W)
            if current_grid.F >= 3 or w_for_comparison > current_grid.L:
                if current_grid.F >= 3:
                    note = '高疲劳（F>=3）D减半'
                else:
                    note = f'超载（W={w_for_comparison}>L={int(current_grid.L)}）'
                self.record_d_change(self.explorer.H, self.explorer.X, self.explorer.Y, note, halve=True)
                if w_for_comparison > current_grid.L:
                    # self.record_d_change(self.explorer.H, self.explorer.X, self.explorer.Y, f"原地停留高疲劳超载（W={w_for_comparison}>L={int(current_grid.L)}）D减半", halve=True)
                    self.record_f_change(self.explorer.H, self.explorer.X, self.explorer.Y, "W>L超载F增加1", change=1)
            # else:
            #     # 超载检查：如果W>L，D需要减半，F+1
            #     if w_for_comparison > current_grid.L:
            #         self.record_d_change(self.explorer.H, self.explorer.X, self.explorer.Y, f"原地停留超载（W={w_for_comparison}>L={int(current_grid.L)}）D减半", halve=True)
            #         self.record_f_change(self.explorer.H, self.explorer.X, self.explorer.Y, "W>L超载F增加1", change=1)         
            # 检查坍塌
            if current_grid.D <= 0:
                current_grid.V = True
                current_grid.S = True
                self.update_global_state()
                snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "current", None, True, "原地停留导致D归零坍塌"))
                return snapshots
            
            self.update_global_state()
            snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "current"))
            return snapshots
        
        # Tier 0: 空间拓扑
        target_h, target_x, target_y = self.calculate_target_coord(direction)
        if self.tier_0_space_topology(target_h, target_x, target_y):
            self.update_global_state()
            snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "current", None, True, "空间拓扑约束触发终止"))
            return snapshots
        
        # Tier 1: 动能转换
        target_h, target_x, target_y = self.tier_1_kinetic_conversion(direction)
        
        # H2层疲劳失控惯性（在Tier 1之后，Tier 2之前）
        target_h, target_x, target_y = self.check_h2_fatigue_inertia(direction, target_h, target_x, target_y)
        
        # 检查是否为跨层跳跃
        is_jump = (direction == Direction.JUMP_UP or direction == Direction.JUMP_DOWN)
        
        if is_jump:
            # 检查跳跃合法性
            if abs(target_h - self.explorer.H) != 1:
                self.update_global_state()
                snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "current", None, True, "跳跃层级差不为1，非法跳跃"))
                return snapshots
            if target_x != self.explorer.X or target_y != self.explorer.Y:
                self.update_global_state()
                snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "current", None, True, "跳跃时X/Y坐标发生变化，非法跳跃"))
                return snapshots
        
        # Tier 2: 路径冲突
        # 在执行路径冲突检测前，预先记录目标点的初始L/D/F值
        # H3层滑行允许第二格非法但停留在第一格，因此这里只在目标坐标合法时预记录第二格
        if self.is_valid_coord(target_h, target_x, target_y):
            target_grid_pre = self.get_grid(target_h, target_x, target_y)
            self.initial_grid_params[(target_h, target_x, target_y)] = {
                "L": target_grid_pre.L if target_grid_pre.L != float('inf') else "∞",
                "D": target_grid_pre.D if target_grid_pre.D != float('inf') else "∞",
                "F": target_grid_pre.F
            }
        
        success, actual_coord, triggered_blast, is_death = self.tier_2_path_collision(target_h, target_x, target_y, is_jump)
        if actual_coord and actual_coord not in self.initial_grid_params and self.is_valid_coord(actual_coord[0], actual_coord[1], actual_coord[2]):
            actual_grid_pre = self.get_grid(actual_coord[0], actual_coord[1], actual_coord[2])
            self.initial_grid_params[actual_coord] = {
                "L": actual_grid_pre.L if actual_grid_pre.L != float('inf') else "∞",
                "D": actual_grid_pre.D if actual_grid_pre.D != float('inf') else "∞",
                "F": actual_grid_pre.F
            }
        
        # 场景C：撞墙（坐标未更新）
        if not success:
            # 碰撞处理
            # 规则十三-4"死人无法引起震动"：Tier 2 死亡后不执行 Tier 3+ 效果
            # - 动能断裂重置：规则八-(一)-2 明确要求坐标更新才算有效位移，死亡时坐标未更新
            # - 跳跃重力惩罚：属于 Tier 3 质量结算，死亡后不补录
            # - 碰撞损耗：同理，死亡路径不追加 W 增量
            if is_death:
                pass
            else:
                # 撞墙等未发生有效位移：不加动能断裂重置W+2
                # H3层滑行的碰撞W值已在tier_2_path_collision中处理，这里不再重复
                if not (self.explorer.H == 3 and not is_jump):
                    self.record_w_change("物理碰撞损耗（撞墙）", 1.0)
                # H2层撞墙应力下传（仅限撞墙场景，死亡路径无墙体碰撞）
                if self.explorer.H == 2:
                    self.mark_affected(1, self.explorer.X, self.explorer.Y)
                    self.record_l_change(1, self.explorer.X, self.explorer.Y, "H2层撞墙应力下传L下降", change=-1)
            self.explorer.last_move_success = False
            
            # 判定生命终止：坠亡返回或真空延迟处决（在真空点上位移失败）
            terminated = is_death or self.explorer.on_vacuum
            death_coord = actual_coord if actual_coord else (target_h, target_x, target_y)
            
            # 确定终止原因
            terminate_reason = None
            if is_death:
                # 根据死亡坐标的状态判断死亡原因
                if actual_coord:
                    death_grid = self.get_grid(actual_coord[0], actual_coord[1], actual_coord[2])
                    # 检查W变化历史中是否有影迹排斥
                    has_shadow_rejection = any("影迹排斥" in r.get("reason", "") for r in self.w_change_history)
                    if has_shadow_rejection:
                        # 影迹排斥导致的死亡
                        if self.explorer.W >= 10:
                            terminate_reason = "超载即坠：影迹排斥后W>=10踏入真空点"
                        elif self.explorer.H == 3 and death_grid.D <= 0:
                            terminate_reason = "H3层失速坠亡：影迹排斥导致D归零"
                        else:
                            terminate_reason = "影迹排斥导致真空化后坠亡"
                    elif death_grid.V:
                        terminate_reason = "踏入真空点坠亡"
                    else:
                        terminate_reason = "位移过程中坠亡"
                else:
                    terminate_reason = "位移失败导致坠亡"
            elif self.explorer.on_vacuum:
                terminate_reason = "真空延迟处决：在真空点上位移失败"
            
            self.update_global_state()
            if is_death:
                # 有效位移后坠亡：起始点快照用start类型（中继瞬时，W为位移前初始值，无变化历史）
                snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "start", None, terminated, terminate_reason))
                # 额外生成实际出事坐标快照（如H3层过渡点坠亡时应落在第一格，而不是第二格）
                snapshots.append(self.generate_snapshot(death_coord[0], death_coord[1], death_coord[2], "end", None, terminated, terminate_reason))
            else:
                # 撞墙等未发生有效位移：用current类型（坐标未更新，含变化历史）
                snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "current", None, terminated, terminate_reason))
            return snapshots
        
        # 场景B：位移成功，在起步瞬间补加动能断裂重置W+2
        if not self.explorer.last_move_success:
            self.record_w_change("动能断裂重置", 2.0)
        
        # 场景B：位移成功，但如果是从H2层向上跳跃且触发了物理爆破，也需要执行H2层撞墙应力下传
        # 注意：如果起始点和目标点的X、Y相同，底层投影是同一个点，物理爆破时已经减过了，这里不再重复
        if success and is_jump and triggered_blast and self.explorer.H == 2:
            # 从H2层向上跳跃，触发了物理爆破，需要执行H2层撞墙应力下传
            # 但只有当起始点和目标点的X、Y不同时，才需要额外减（因为底层投影不同）
            start_h, start_x, start_y = self.explorer.H, self.explorer.X, self.explorer.Y
            if start_x != actual_coord[1] or start_y != actual_coord[2]:
                self.mark_affected(1, start_x, start_y)
                self.record_l_change(1, start_x, start_y, "H2层跳跃物理爆破应力下传L下降", change=-1)
        
        # 场景B：位移成功，输出起始点和落脚点快照
        start_h, start_x, start_y = self.explorer.H, self.explorer.X, self.explorer.Y
        
        # 记录落脚点的初始L/D/F值（在更新坐标前）
        target_grid = self.get_grid(actual_coord[0], actual_coord[1], actual_coord[2])
        self.initial_grid_params[actual_coord] = {
            "L": target_grid.L if target_grid.L != float('inf') else "∞",
            "D": target_grid.D if target_grid.D != float('inf') else "∞",
            "F": target_grid.F
        }
        
        # 更新坐标
        self.explorer.H, self.explorer.X, self.explorer.Y = actual_coord
        self.explorer.last_move_success = True
        
        # 更新面朝方向M（根据实际移动方向）
        # 注意：H2层存在镜像反转，指令方向与实际方向相反
        if direction == Direction.NORTH:
            self.explorer.M = Direction.NORTH
        elif direction == Direction.SOUTH:
            self.explorer.M = Direction.SOUTH
        elif direction == Direction.EAST:
            # H2层镜像反转：指令向东，实际向西
            if start_h == 2:
                self.explorer.M = Direction.WEST
            else:
                self.explorer.M = Direction.EAST
        elif direction == Direction.WEST:
            # H2层镜像反转：指令向西，实际向东
            if start_h == 2:
                self.explorer.M = Direction.EAST
            else:
                self.explorer.M = Direction.WEST
        
        # 更新路径历史
        self.path_history.append((self.explorer.H, self.explorer.X, self.explorer.Y))
        
        # 指令共振检查
        self.check_command_resonance(direction, self.explorer.H, self.explorer.X, self.explorer.Y)
        
        # 处理跳跃
        if is_jump:
            self.process_jump(self.explorer.H, self.explorer.X, self.explorer.Y)
        
        # Tier 3: 质量结算
        self.tier_3_mass_settlement(start_h, start_x, start_y, self.explorer.H, self.explorer.X, self.explorer.Y)
        
        # Tier 4: 应力传导（生成黑影等）
        self.tier_4_stress_conduction(start_h, start_x, start_y,
                                      self.explorer.H, self.explorer.X, self.explorer.Y,
                                      is_jump)
        
        # 生成起始点快照（离地瞬间，此时黑影已生成）
        snapshots.append(self.generate_snapshot(start_h, start_x, start_y, "start"))
        
        # 拓扑回路判定（Tier 0级别，但需要在落脚后执行）
        loop_info = self.check_topology_loop(self.explorer.H, self.explorer.X, self.explorer.Y)
        if loop_info and not loop_info.get("resonance_failure"):
            # 只有非谐振失效的有效回路才执行处理
            self.process_topology_loop(loop_info, is_jump)
        
        # Tier 5: 全局共振（对所有三层都检查材质老化和结构性塌缩）
        self.tier_5_global_resonance()
        
        # 更新全局状态数组（所有物理结算完成后）
        self.update_global_state()
        
        # 检查终止条件
        target_grid = self.get_grid(self.explorer.H, self.explorer.X, self.explorer.Y)
        terminated = False
        terminate_reason = None
        if target_grid.D <= 0:
            terminated = True
            terminate_reason = "落脚点D归零坍塌"
        elif target_grid.V and not self.explorer.jump_landing_round:
            # 真空延迟处决检查
            if self.explorer.on_vacuum:
                # 在真空点上再次进入另一个V=是的格点，判定生命终止
                terminated = True
                terminate_reason = "连续踏入真空点，真空延迟处决"
            else:
                # 本轮踏入真空点，设置状态，下一轮必须成功移动到非真空点
                self.explorer.on_vacuum = True
        else:
            # 成功移动到非真空点，清除真空状态
            self.explorer.on_vacuum = False
        
        # 生成落脚点快照（终态瞬间，包含所有物理结算结果）
        snapshots.append(self.generate_snapshot(self.explorer.H, self.explorer.X, self.explorer.Y, "end", loop_info, terminated, terminate_reason))
        
        return snapshots
    
    def generate_snapshot(self, h: int, x: int, y: int, snapshot_type: str = "current", 
                         loop_info: Optional[Dict] = None, terminated: bool = False,
                         terminate_reason: str = None) -> Dict:
        """
        生成物理快照
        snapshot_type: "query" (场景A-探测), "start" (场景B-起始), "end" (场景B-落脚), "current" (场景C-原位)
        """
        grid = self.get_grid(h, x, y)
        
        # 获取当前层的黑影列表
        shadows = []
        for sx in range(1, 6):
            for sy in range(1, 6):
                sgrid = self.get_grid(h, sx, sy)
                if sgrid.shadow:
                    shadows.append((h, sx, sy))
        
        # 获取受影响坐标的参数（仅对落脚点快照）
        # 使用全局状态数组获取参数，确保历史信息完整
        affected_params = {}
        if snapshot_type in ["end", "current"] and self.affected_coords:
            for ah, ax, ay in self.affected_coords:
                if (ah, ax, ay) != (h, x, y):  # 排除落脚点本身
                    # 从全局状态数组获取参数
                    state = self.global_state.get(ah, {}).get(ax, {}).get(ay, {})
                    if state:
                        affected_params[(ah, ax, ay)] = {
                            "S": "是" if state.get("S", False) else "否",
                            "V": "是" if state.get("V", False) else "否",
                            "L": state.get("L", 5.0),
                            "D": state.get("D", 10.0),
                            "F": state.get("F", 0),
                            "shadow": state.get("shadow", False)
                        }
        
        # W值快照规则：
        # - 探测点（query）：使用探测时的最新值（上一轮结算结束后的W值）
        # - 起始点（start）：使用起步瞬间的W值（若本轮发生了动能断裂重置，则为initial_w + 2.0）
        # - 落脚点（end）和原位（current）：使用当前W值（所有结算完成后的值）
        if snapshot_type == "query":
            w_value = math_round(self.initial_w_this_round, 1)  # 探测时使用上一轮结算后的W值
        elif snapshot_type == "start":
            # 起始点使用起步瞬间的W值：若本轮发生了动能断裂重置，则在initial_w基础上加2.0
            # kinetic_reset = any(r["reason"] == "动能断裂重置" for r in self.w_change_history)
            # w_value = math_round(self.initial_w_this_round + (2.0 if kinetic_reset else 0.0), 1)
            w_value = math_round(self.initial_w_this_round, 1)
        else:
            w_value = math_round(self.explorer.W, 1)  # 落脚点和原位使用当前W值
        
        # 获取初始L/D/F值（仅对end和current类型）
        initial_params = None
        if snapshot_type in ["end", "current"]:
            initial_params = self.initial_grid_params.get((h, x, y))
        
        # 拓扑回路受影响坐标参数：在快照生成时刻捕获，确保与基本参数同一时间点
        if loop_info and snapshot_type == "end":
            loop_affected_params = {}
            for coord_list in [loop_info.get("boundary", []), loop_info.get("inner", [])]:
                for ch, cx, cy in coord_list:
                    g = self.get_grid(ch, cx, cy)
                    loop_affected_params[(ch, cx, cy)] = {
                        'S': g.S, 'V': g.V,
                        'L': g.L, 'D': g.D, 'F': g.F
                    }
            layer = loop_info.get("layer", h)
            if layer != 1 and loop_info.get("inner"):
                target_layer = 2 if layer == 3 else 1
                for ih, ix, iy in loop_info["inner"]:
                    g = self.get_grid(target_layer, ix, iy)
                    loop_affected_params[(target_layer, ix, iy)] = {
                        'S': g.S, 'V': g.V,
                        'L': g.L, 'D': g.D, 'F': g.F
                    }
            # 规则九-6-(2) 向上支撑：H1回路A>=3时，落脚点正上方H2格点同样属于拓扑回路影响坐标
            if layer == 1 and len(loop_info.get("inner", [])) >= 3:
                g = self.get_grid(2, x, y)
                loop_affected_params[(2, x, y)] = {
                    'S': g.S, 'V': g.V,
                    'L': g.L, 'D': g.D, 'F': g.F
                }
            loop_info['affected_params'] = loop_affected_params

        snapshot = {
            "坐标": (h, x, y),
            "类型": snapshot_type,
            "状态": {
                "W": w_value,
                "L": grid.L if grid.L != float('inf') else "∞",
                "D": grid.D if grid.D != float('inf') else "∞",
                "F": grid.F
            },
            "W变化历史": self.w_change_history.copy() if snapshot_type in ["end", "current"] else [],
            "L变化历史": self.l_change_history.copy() if snapshot_type in ["end", "current"] else [],
            "D变化历史": self.d_change_history.copy() if snapshot_type in ["end", "current"] else [],
            "F变化历史": self.f_change_history.copy() if snapshot_type in ["end", "current"] else [],
            "初始W值": self.initial_w_this_round if snapshot_type in ["end", "current", "start"] else None,
            "初始LDF": initial_params,
            "黑影列表": shadows if shadows else "无",
            "拓扑回路": loop_info,
            "受影响坐标": affected_params if affected_params else None,
            "终止": terminated,
            "终止原因": terminate_reason
        }
        
        return snapshot
    
    def format_snapshot(self, snapshot: Dict) -> str:
        """
        格式化快照输出（按照规则十四格式）
        """
        h, x, y = snapshot["坐标"]
        state = snapshot["状态"]
        shadows = snapshot["黑影列表"]
        loop_info = snapshot.get("拓扑回路")
        
        result = f"【坐标（{h}, {x}, {y}）物理快照】\n\n"
        result += f"[坐标（{h}, {x}, {y}）基本参数]\n"
        result += f"- 坐标： ({h}, {x}, {y})\n"
        
        # 输出状态和变化逻辑（仅在有变化时显示）
        snapshot_type = snapshot.get("类型", "")
        w_history = snapshot.get("W变化历史", [])
        l_history = snapshot.get("L变化历史", [])
        d_history = snapshot.get("D变化历史", [])
        f_history = snapshot.get("F变化历史", [])
        initial_w = snapshot.get("初始W值")
        initial_ldf = snapshot.get("初始LDF")
        
        l_str = '∞' if state['L'] == float('inf') or state['L'] == '∞' else int(state['L'])
        d_str = '∞' if state['D'] == float('inf') or state['D'] == '∞' else int(state['D'])
        result += f"- 状态： W = {state['W']:.1f} | 目标点 L = {l_str}，D = {d_str}，F = {int(state['F'])}\n"
        
        # 检查是否有任何变化
        has_w_change = initial_w is not None and snapshot_type in ["end", "current"] and w_history
        has_ldf_change = False
        if initial_ldf and snapshot_type in ["end", "current"]:
            has_ldf_change = (
                initial_ldf.get("L") != state['L'] or
                initial_ldf.get("D") != state['D'] or
                initial_ldf.get("F") != state['F']
            )
        
        # 如果有变化，显示变化逻辑
        if has_w_change or has_ldf_change:
            change_lines = []
            
            # W值变化逻辑
            if has_w_change:
                w_line = f"W值变化逻辑：初始W = {initial_w:.1f}"
                for change_record in w_history:
                    change_val = change_record["change"]
                    change_str = f"+{change_val:.1f}" if change_val >= 0 else f"{change_val:.1f}"
                    w_line += f" → {change_record['reason']} {change_str} ({change_record['before']:.1f} → {change_record['after']:.1f})"
                w_line += f" = 最终W = {state['W']:.1f}"
                change_lines.append(w_line)
            
            # L/D/F值变化逻辑
            if has_ldf_change:
                ldf_changes = []
                if initial_ldf.get("L") != state['L']:
                    init_l_val = initial_ldf.get('L')
                    init_l = '∞' if init_l_val == float('inf') or init_l_val == '∞' else int(init_l_val)
                    final_l_val = state['L']
                    final_l = '∞' if final_l_val == float('inf') or final_l_val == '∞' else int(final_l_val)
                    ldf_changes.append(f"L: {init_l} → {final_l}")
                if initial_ldf.get("D") != state['D']:
                    init_d_val = initial_ldf.get('D')
                    init_d = '∞' if init_d_val == float('inf') or init_d_val == '∞' else int(init_d_val)
                    final_d_val = state['D']
                    final_d = '∞' if final_d_val == float('inf') or final_d_val == '∞' else int(final_d_val)
                    ldf_changes.append(f"D: {init_d} → {final_d}")
                if initial_ldf.get("F") != state['F']:
                    ldf_changes.append(f"F: {int(initial_ldf.get('F'))} → {int(state['F'])}")
                if ldf_changes:
                    change_lines.append(f"目标点参数变化：{', '.join(ldf_changes)}")
            
            if change_lines:
                for line in change_lines:
                    result += f"- {line}\n"
        
        result += "\n"
        
        # 输出L/D/F变化历史（详细过程）
        # 场景C（current）：坐标未更新（坠亡/撞墙），只输出当前快照坐标自身的变化，过滤掉目标点的变化
        # 场景B（end）：输出所有坐标的变化（包括落脚点及受影响坐标）
        def _coord_filter(record):
            # if snapshot_type == "current":
            #     return tuple(record["coord"]) == (h, x, y)
            return True

        filtered_l = [r for r in l_history if _coord_filter(r)]
        filtered_d = [r for r in d_history if _coord_filter(r)]
        filtered_f = [r for r in f_history if _coord_filter(r)]

        if snapshot_type in ["end", "current"] and (filtered_l or filtered_d or filtered_f):
            result += "[L/D/F参数变化过程]\n"
            
            if filtered_l:
                result += "L值变化：\n"
                for record in filtered_l:
                    coord = record["coord"]
                    before_l = int(record['before']) if record['before'] != '∞' else '∞'
                    after_l = int(record['after']) if record['after'] != '∞' else '∞'
                    result += f"  - ({coord[0]},{coord[1]},{coord[2]}) {record['reason']}: {before_l} → {after_l}\n"
            
            if filtered_d:
                result += "D值变化：\n"
                for record in filtered_d:
                    coord = record["coord"]
                    before_d = int(record['before']) if record['before'] != '∞' else '∞'
                    after_d = int(record['after']) if record['after'] != '∞' else '∞'
                    result += f"  - ({coord[0]},{coord[1]},{coord[2]}) {record['reason']}: {before_d} → {after_d}\n"
            
            if filtered_f:
                result += "F值变化：\n"
                for record in filtered_f:
                    coord = record["coord"]
                    change_str = f"+{record['change']}" if record['change'] >= 0 else str(record['change'])
                    result += f"  - ({coord[0]},{coord[1]},{coord[2]}) {record['reason']}: {record['before']} → {record['after']} ({change_str})\n"
            
            result += "\n"
        
        # 拓扑回路判定（仅在该坐标点使回路闭合时输出）
        if loop_info:
            result += "[拓扑回路判定]\n"
            
            # 如果存在多重回路共振判定过程，先输出判定过程
            resolution_process = loop_info.get("resolution_process")
            candidate_count = loop_info.get("candidate_count", 1)
            if resolution_process and candidate_count > 1:
                result += "多重回路共振判定：\n"
                for line in resolution_process:
                    result += f"{line}\n"
                result += "\n"
            
            # 检查是否为谐振失效
            if loop_info.get("resonance_failure"):
                result += "回路状态： 谐振失效（所有潜在回路判定为无效，不触发任何重构奖励）\n"
                result += "\n"
            else:
                result += "回路状态： 已构成\n"
                result += "回路参数：\n"
                result += f"- 回路边界集合：{loop_info.get('boundary', [])}\n"
                result += f"- 内部格点：{loop_info.get('inner', [])}\n"
                # result += f"- 净化影迹： N = {len([p for p in loop_info.get('inner', []) if self.get_grid(*p).shadow])}\n"
                result += "- 拓扑回路影响的所有坐标点及参数：\n"
                
                # 输出边界点参数
                for bh, bx, by in loop_info.get('boundary', []):
                    bg = self.get_grid(bh, bx, by)
                    result += f"({bh}, {bx}, {by})：S:{'是' if bg.S else '否'}, V:{'是' if bg.V else '否'}, L:{int(bg.L) if bg.L != float('inf') else '∞'}, D:{int(bg.D) if bg.D != float('inf') else '∞'}, F:{int(bg.F)}\n"
                
                # 输出内部点参数
                for ih, ix, iy in loop_info.get('inner', []):
                    ig = self.get_grid(ih, ix, iy)
                    result += f"({ih}, {ix}, {iy})：S:{'是' if ig.S else '否'}, V:{'是' if ig.V else '否'}, L:{int(ig.L) if ig.L != float('inf') else '∞'}, D:{int(ig.D) if ig.D != float('inf') else '∞'}, F:{int(ig.F)}\n"
                
                # 输出跨层应力对冲影响的坐标参数
                layer = loop_info.get('layer', h)
                inner = loop_info.get('inner', [])
                if layer != 1 and inner:
                    target_layer = 2 if layer == 3 else 1
                    result += f"- 跨层应力对冲影响的H{target_layer}层坐标：\n"
                    for ih, ix, iy in inner:
                        cross_grid = self.get_grid(target_layer, ix, iy)
                        result += f"({target_layer}, {ix}, {iy})：S:{'是' if cross_grid.S else '否'}, V:{'是' if cross_grid.V else '否'}, L:{int(cross_grid.L) if cross_grid.L != float('inf') else '∞'}, D:{int(cross_grid.D) if cross_grid.D != float('inf') else '∞'}, F:{int(cross_grid.F)}\n"
                
                # 输出向上支撑影响的坐标参数（H1层且A>=3时）
                if layer == 1 and len(inner) >= 3:
                    landing_x, landing_y = self.explorer.X, self.explorer.Y
                    support_grid = self.get_grid(2, landing_x, landing_y)
                    result += f"- 向上支撑影响的H2层坐标：\n"
                    result += f"(2, {landing_x}, {landing_y})：S:{'是' if support_grid.S else '否'}, V:{'是' if support_grid.V else '否'}, L:{int(support_grid.L) if support_grid.L != float('inf') else '∞'}, D:{int(support_grid.D) if support_grid.D != float('inf') else '∞'}, F:{int(support_grid.F)}\n"
                
                result += "\n"
        
        result += "[黑影列表]：\n"
        if shadows == "无":
            result += "无\n"
        else:
            for sh, sx, sy in shadows:
                result += f"({sh}, {sx}, {sy})\n"
        
        # 输出受影响坐标的参数（仅对落脚点快照）
        affected_params = snapshot.get("受影响坐标")
        if affected_params:
            result += "\n[受影响坐标参数变化]：\n"
            for (ah, ax, ay), params in sorted(affected_params.items()):
                shadow_str = "（黑影）" if params["shadow"] else ""
                l_str = '∞' if params['L'] == float('inf') or params['L'] == '∞' else int(params['L'])
                d_str = '∞' if params['D'] == float('inf') or params['D'] == '∞' else int(params['D'])
                result += f"({ah}, {ax}, {ay}){shadow_str}：S:{params['S']}, V:{params['V']}, L:{l_str}, D:{d_str}, F:{int(params['F'])}\n"
        
        return result


def merge_snapshots_by_coord(snapshots: List[Dict]) -> List[Dict]:
    """
    规则十五-3：快照冗余与坐标合并逻辑。
    若同一回合内同一坐标点承担了多重逻辑角色（探测点、起始点、落脚点），
    只保留该回合结算最终完成时的状态（即最后一个出现的快照），
    并按首次出现的顺序输出。
    """
    # 记录每个坐标首次出现的顺序索引
    coord_first_index: Dict[tuple, int] = {}
    # 记录每个坐标最后一个快照
    coord_last_snapshot: Dict[tuple, Dict] = {}

    for i, snapshot in enumerate(snapshots):
        coord = tuple(snapshot["坐标"])
        if coord not in coord_first_index:
            coord_first_index[coord] = i
        coord_last_snapshot[coord] = snapshot

    # 按首次出现顺序排序，每个坐标只保留最后一个快照
    sorted_coords = sorted(coord_first_index.keys(), key=lambda c: coord_first_index[c])
    return [coord_last_snapshot[coord] for coord in sorted_coords]


def _format_param_value(val, is_int=True):
    """格式化参数值，处理无穷大"""
    if val == float('inf') or val == '∞':
        return '∞'
    return int(val) if is_int else val


def generate_checklist(snapshots: List[Dict], system: TombSystem = None) -> str:
    """
    生成最后一轮的checklist，格式参照ground_truth。
    所有数据均从 snapshot 字典中提取，不依赖 system 实时状态。
    """
    checklist_items = []
    item_num = 1
    
    # 为每个快照生成checklist条目
    for snapshot in snapshots:
        h, x, y = snapshot["坐标"]
        state = snapshot["状态"]
        shadows = snapshot["黑影列表"]
        loop_info = snapshot.get("拓扑回路")
        
        # 格式化状态值
        w_val = f"{state['W']:.1f}"
        l_val = _format_param_value(state['L'])
        d_val = _format_param_value(state['D'])
        f_val = int(state['F'])
        
        # 基本参数检查
        checklist_items.append(
            f'{item_num}. 模型回复是否包含 "【坐标（{h}, {x}, {y}）物理快照】"，'
            f'"【坐标（{h}, {x}, {y}）物理快照】" 中包含 "[坐标（{h}, {x}, {y}）基本参数]"，'
            f'且 "[坐标（{h}, {x}, {y}）基本参数]" 中坐标为 "({h}, {x}, {y})"，'
            f'状态为 "W = {w_val} | 目标点 L = {l_val}，D = {d_val}，F = {f_val}"？（注：括号全角/半角、空格差异不影响判定；状态行额外列出 S、V 等字段不影响判定，以 W、L、D、F 数值为准。）'
        )
        item_num += 1
        
        # 拓扑回路判定检查（如果有）
        if loop_info:
            boundary = loop_info.get('boundary', [])
            inner = loop_info.get('inner', [])
            affected_params = loop_info.get('affected_params', {})
            
            boundary_str = ', '.join([f'({bh}, {bx}, {by})' for bh, bx, by in boundary])
            inner_str = ', '.join([f'({ih}, {ix}, {iy})' for ih, ix, iy in inner]) if inner else "无"
            
            all_coords_params = []
            for ch, cx, cy in boundary + inner:
                params = affected_params.get((ch, cx, cy))
                if params:
                    pl = _format_param_value(params['L'])
                    pd = _format_param_value(params['D'])
                    all_coords_params.append(
                        f'({ch}, {cx}, {cy})：S:{"是" if params["S"] else "否"}, V:{"是" if params["V"] else "否"}, '
                        f'L:{pl}, D:{pd}, F:{int(params["F"])}'
                    )
            
            # 跨层应力对冲坐标
            layer = loop_info.get('layer', h)
            if layer != 1 and inner:
                target_layer = 2 if layer == 3 else 1
                for ih, ix, iy in inner:
                    params = affected_params.get((target_layer, ix, iy))
                    if params:
                        cl = _format_param_value(params['L'])
                        cd = _format_param_value(params['D'])
                        all_coords_params.append(
                            f'({target_layer}, {ix}, {iy})：S:{"是" if params["S"] else "否"}, V:{"是" if params["V"] else "否"}, '
                            f'L:{cl}, D:{cd}, F:{int(params["F"])}'
                        )
            # 向上支撑坐标（H1回路A>=3）
            if layer == 1 and len(inner) >= 3:
                params = affected_params.get((2, x, y))
                if params:
                    sl = _format_param_value(params['L'])
                    sd = _format_param_value(params['D'])
                    all_coords_params.append(
                        f'(2, {x}, {y})：S:{"是" if params["S"] else "否"}, V:{"是" if params["V"] else "否"}, '
                        f'L:{sl}, D:{sd}, F:{int(params["F"])}'
                    )
            
            all_coords_str = '；'.join(all_coords_params)
            
            checklist_items.append(
                f'{item_num}. 模型回复的 "【坐标（{h}, {x}, {y}）物理快照】" 是否包含 "[拓扑回路判定]"，'
                f'且判定回路状态为 "已构成"，包含 "回路参数" 且内容如下：'
                f'回路边界集合：{boundary_str}，；'
                f'内部格点：{inner_str}；'
                f'拓扑回路影响的所有坐标点及参数：{all_coords_str}？（注：括号全角/半角、空格差异不影响判定。）'
            )
            item_num += 1
        
        # 黑影列表检查
        if shadows == "无":
            checklist_items.append(
                f'{item_num}. 模型回复的 "【坐标（{h}, {x}, {y}）物理快照】" 是否包含 "[黑影列表]"，'
                f'且 "[黑影列表]" 内容为 "无"？（注：括号全角/半角、空格差异不影响判定。）'
            )
        else:
            shadow_coords = ', '.join([f'({sh}, {sx}, {sy})' for sh, sx, sy in shadows])
            checklist_items.append(
                f'{item_num}. 模型回复的 "【坐标（{h}, {x}, {y}）物理快照】" 是否包含 "[黑影列表]"，'
                f'且 "[黑影列表]" 中仅包含坐标 {shadow_coords}？（注：括号全角/半角、空格差异不影响判定。）'
            )
        item_num += 1
    
    return '\n'.join(checklist_items)


def verified_gumu(test_case, show_global_state=False) -> List[str]:
    """
    模拟完整场景
    show_global_state: 是否在每轮结束后输出全局状态数组
    query_coords: 探查坐标列表，格式为 [时机, [h1, x1, y1], [h2, x2, y2], ...]
                  时机：-1表示最后一步，-2表示最后一步后还要执行最后一个操作，正数表示第几步
    """
    initial_state = test_case["initial_state"]
    initial_h = initial_state["H"]
    initial_x = initial_state["X"]
    initial_y = initial_state["Y"]
    moves = test_case["moves"]
    system = TombSystem(initial_state)
    query_coords = test_case.get("query_coords", None)
    
    system.explorer.H = initial_h
    system.explorer.X = initial_x
    system.explorer.Y = initial_y
    
    results = []
    last_round_snapshots = []  # 保存最后一轮的快照
    is_terminated = False  # 标记是否终止
    
    # 解析query_coords格式
    query_timing = None
    actual_query_coords = None
    if query_coords and len(query_coords) > 0:
        # 检查第一个元素是否是时机标识
        query_timing = query_coords[0]
        actual_query_coords = query_coords[1:]  # 提取实际的查询坐标
    if query_timing == -1:
        moves.append("原地停留")
    
    for i, move in enumerate(moves, 1):
        # 判断是否在本轮执行探查
        should_query = False
        if query_timing is not None and actual_query_coords:
            should_query = (i == len(moves))
        
        # 执行移动，如果应该探查则传入查询坐标
        current_query_coords = actual_query_coords if should_query else None
        snapshots = system.move(move, current_query_coords)
        result_text = f"第 {i} 轮：{move}\n"

        # 规则十五-3：快照冗余与坐标合并，同一坐标只输出最终状态的快照
        merged_snapshots = merge_snapshots_by_coord(snapshots)

        terminate_reason = None
        for snapshot in merged_snapshots:
            formatted = system.format_snapshot(snapshot)
            result_text += formatted + "\n"
            if snapshot["终止"]:
                is_terminated = True
                if snapshot.get("终止原因"):
                    terminate_reason = snapshot["终止原因"]
        # 注意：不在此处break，确保所有快照（包括坠亡目标点快照）都能输出
        # 终止提示统一在所有快照输出完毕后加一次
        if is_terminated:
            if terminate_reason:
                result_text += f"\n探险者当前生命周期已终止。终止原因：{terminate_reason}\n"
            else:
                result_text += "\n探险者当前生命周期已终止。\n"
        
        # 如果需要，输出全局状态数组
        if show_global_state:
            result_text += system.format_global_state() + "\n"
        
        results.append(result_text)
        last_round_snapshots = merged_snapshots  # 更新最后一轮的快照（已合并）
        
        # 检查是否终止
        if any(s["终止"] for s in snapshots):
            break

    gap_str = '-' * 80 + '\n'
    output = gap_str.join(results)
    
    # 在最后添加checklist
    if last_round_snapshots:
        checklist = generate_checklist(last_round_snapshots, system)
        output += "\n" + "=" * 80 + "\n"
        output += "【Checklist】\n"
        output += checklist    
        if is_terminated:
            item_num = len(checklist.splitlines()) + 1
            output += f"\n{item_num}. 模型回复的结尾是否包含“探险者当前生命周期已终止”？"
    return output


if __name__ == "__main__":
    # usage: python -m code_simulation_engines.spatial_multi_rule.tomb_exploration.tomb_exploration_engine [question id], e.g. tomb_1
    import ast
    import json
    import sys
    from pathlib import Path

    qid = sys.argv[1] if len(sys.argv) > 1 else "tomb_1"
    with open(Path(__file__).resolve().parents[2] / "structured_inputs.jsonl", encoding="utf-8") as f:
        rows = {r["id"]: r for r in map(json.loads, f)}
    raw = rows[qid]["structured_input"]
    try:
        case = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        case = json.loads(raw)
    print(verified_gumu(case))
