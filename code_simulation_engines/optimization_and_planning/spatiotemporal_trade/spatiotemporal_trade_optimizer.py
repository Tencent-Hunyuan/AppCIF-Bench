import math
import heapq  # 用于优先队列搜索
from itertools import product

class PsychedelicCity:
    def __init__(self, current_k, current_pos, events, initial_assets=1000, max_time_leap=30, specific_speed_limit=None, item_limit=None, jump_type_limit=None):
        self.k = current_k
        self.pos = current_pos
        self.assets = initial_assets
        self.events = events
        self.t = 0
        self.map_size = 500
        self.max_time_leap = max_time_leap
        self.continue_time = 10
        self.max_wait_time = 2 * max_time_leap
        self.specific_speed_limit = specific_speed_limit
        self.item_limit = item_limit  # 限定交易商品范围，为None时搜索全部商品
        self.jump_type_limit = jump_type_limit  # 限定穿越类型，如['SW']或['KW']或['SW','KW']，为None时搜索全部类型
        # Coordinates
        self.destinations = {
            'SM': (120, 360, 80),
            'CB': (400, 300, 300),
            'NL': (240, 240, 300),
            'HL': (260, 90, 420),
        }
        
        self.base_prices = {'SM': 10, 'CB': 12, 'NL': 11, 'HL': 13}
        self.price_params = {
            'SM': {'a': 1, 'b': 0},
            'CB': {'a': 2, 'b': 1},
            'NL': {'a': 3, 'b': 2},
            'HL': {'a': 4, 'b': 3}
        }
        
        self.sw_config = {
            1: {'pos': (50, 450, 50), 'dk': -30},
            2: {'pos': (450, 450, 100), 'dk': -90},
            3: {'pos': (50, 50, 450), 'dk': 30},
            4: {'pos': (450, 100, 450), 'dk': 90}
        }
        
        self.kw_config = {
            1: {'base': 8, 'vec': (1, 1, 1)},
            2: {'base': 6, 'vec': (2, 1, 3)},
            3: {'base': 10, 'vec': (3, 2, 1)},
            4: {'base': 7, 'vec': (5, 1, 4)}
        }
        
        # 基础地形配置
        self.base_terrains = [
            {'x': (150, 170), 'y': (330, 350), 'z': (60, 120), 'name': 'Maryvia'},
            {'x': (220, 230), 'y': (200, 260), 'z': (120, 249), 'name': 'BlackHole'},
            {'x': (250, 290), 'y': (70, 120), 'z': (450, 499), 'name': 'ControlZone'}
        ]
        self.terrains = self.base_terrains  # 保持兼容性
        
        # === 缓存初始化 ===
        self.max_cache_before = min(0, self.k - self.max_time_leap)
        self.max_cache_after = self.k + self.max_time_leap #+ 200  # 预留足够长的缓存
        # print(self.max_cache_before, self.max_cache_after)
        self.price_cache = {}  # {item: {k: level}}
        self.ik_cache = {}     # {k: ik_value}
        self.kw_pos_cache = {1: {}, 2: {}, 3: {}, 4: {}}  # {kw_id: {k: (x,y,z)}}
        
        # 路径缓存
        self.path_cache = {}  # {(p1, p2, terrain_key): (dist, path)}
        
        # 执行预计算
        self._precompute_all()

    def _precompute_all(self):
        """一次性计算未来状态，消除冗余"""
        print("正在预计算世界线状态...")
        
        # 1. 预计算物价 & I(k)
        for k in range(self.max_cache_before, self.max_cache_after):
            # 计算各商品价格
            ik_raw = 0
            for item in self.destinations:
                lvl = self._calculate_price_level_logic(item, k) 
                if item not in self.price_cache: self.price_cache[item] = {}
                self.price_cache[item][k] = lvl
                
                # 累加 I(k) 权重
                weight = {'SM': 3, 'CB': 2, 'NL': 3, 'HL': 2}[item]
                ik_raw += weight * lvl
            
            self.ik_cache[k] = math.floor(ik_raw / 4)
        # 2. 预计算 KW 轨迹
        for kw_id in self.kw_config:
            curr_x, curr_y, curr_z = 0, 0, 0 # KW 初始坐标
            cfg = self.kw_config[kw_id]
            vec = cfg['vec']
            base_speed = cfg['base']
            
            for k in range(0, self.max_cache_after):
                self.kw_pos_cache[kw_id][k] = (curr_x, curr_y, curr_z)
                
                # 计算下一旬的位移
                
                ik = self.get_ik(k)
                speed = base_speed + ik
                # 检查是否有速度覆盖规则
                if self.specific_speed_limit is not None:
                    # 支持两种格式：
                    # 1. 单个规则: [kw_id, (start, end), speed]
                    # 2. 多个规则: [[kw_id, (start, end), speed], ...]
                    limits = self.specific_speed_limit
                    # 判断是单个规则还是多个规则
                    if isinstance(limits[0], list):
                        # 多个规则的列表
                        for limit in limits:
                            limit_kw_id, (start_k, end_k), override_speed = limit
                            if kw_id == limit_kw_id and start_k <= k <= end_k:
                                speed = override_speed
                                break
                    else:
                        # 单个规则
                        limit_kw_id, (start_k, end_k), override_speed = limits[0], limits[1], limits[2]
                        if kw_id == limit_kw_id and start_k <= k <= end_k:
                            speed = override_speed
                
                # 事件修正 (KW Speed)
                # speed_add = 0
                # speed_mul = 1.0
                events_speed = []
                for e in self.events:
                    for key in ['kw_speed_add', 'kw_speed_mul']:
                        if key not in e: 
                            continue
                        events_speed.append(e)
                events_speed = sorted(events_speed, key=lambda x: x["tier"], reverse=False)

                for e in events_speed:
                    for key in ['kw_speed_add', 'kw_speed_mul']:
                        if key not in e:
                            continue
                        if isinstance(e[key], dict):
                            val = e[key]['value']
                            continue_time = e[key]['continue']
                        else:
                            val = e[key]
                            continue_time = 1

                        if e['start_k'] <= k < e['start_k'] + continue_time:
                            if key == 'kw_speed_add':
                                speed += val
                            elif key == 'kw_speed_mul':
                                speed = math.floor(speed*val)
                            
                current_speed = speed
                # current_speed = speed + speed_add
                # if speed_mul != 1.0:
                #     current_speed = math.floor(current_speed * speed_mul)
                
                curr_x = (curr_x + current_speed * vec[0]) % 500
                curr_y = (curr_y + current_speed * vec[1]) % 500
                curr_z = (curr_z + current_speed * vec[2]) % 500

    def get_price_level(self, item, k):
        if k in self.price_cache.get(item, {}):
            return self.price_cache[item][k]
        return self._calculate_price_level_logic(item, k)

    def get_ik(self, k):
        if k in self.ik_cache: return self.ik_cache[k]
        return 0 

    def get_kw_pos(self, kw_id, k):
        if k in self.kw_pos_cache[kw_id]:
            return self.kw_pos_cache[kw_id][k]
        return (0,0,0)

    def _calculate_price_level_logic(self, item, k):
        # 1. Base Wave
        k_pos = 2 * k if k >= 0 else 2 * abs(k) - 1
        params = self.price_params[item]
        wave = ((params['a'] * k_pos + params['b']) % 7) - 3
        base_level = max(0, min(9, 4 + wave))
        
        # 2. Events (Tier System)
        active_events = []
        for e in self.events:
            if e['start_k'] <= k < e['start_k'] + self.continue_time and e['item'] == item:
                active_events.append(e)

        event_adj = 0
        if active_events:
            tiers = [e.get('tier', 3) for e in active_events]
            min_tier = min(tiers)
            for e in active_events:
                if e.get('tier', 3) == min_tier:
                    event_adj += e.get('delta', 0)
        
        final_level = base_level + event_adj
        final_level = max(0, min(9, final_level))
        if item == 'CB':
            final_level = max(2, min(7, final_level))
        return final_level

    # ========== 枚举法路径计算 ==========
    
    def get_terrains_at_k(self, k):
        """
        获取时间点 k 时的地形配置（考虑事件影响）
        返回地形列表，每个地形包含实际的边界范围
        """
        maryvia_exp = 0
        general_exp = 0
        cbd_block = False
        disable_terrain_ext = False
        
        # 首先检查是否有 disable_terrain_ext 事件生效
        for e in self.events:
            if 'disable_terrain_ext' not in e:
                continue
            if isinstance(e['disable_terrain_ext'], dict):
                val = e['disable_terrain_ext']['value']
                continue_time = e['disable_terrain_ext']['continue']
            else:
                val = e['disable_terrain_ext']
                continue_time = 1
            if e['start_k'] <= k < e['start_k'] + continue_time:
                if val:
                    disable_terrain_ext = True
                    break
        
        for e in self.events:
            for key in ['terrain_expand_all', 'terrain_expand_maryvia', 'cbd_blockade']:
                if key not in e:
                    continue
                if isinstance(e[key], dict):
                    val = e[key]['value']
                    continue_time = e[key]['continue']
                else:
                    val = e[key]
                    continue_time = 1
                if e['start_k'] <= k < e['start_k'] + continue_time:
                    if key == 'terrain_expand_all':
                        # 如果 disable_terrain_ext 生效，则地形扩张效果不生效
                        if not disable_terrain_ext:
                            general_exp += val
                    elif key == 'terrain_expand_maryvia':
                        # 如果 disable_terrain_ext 生效，则地形扩张效果不生效
                        if not disable_terrain_ext:
                            maryvia_exp += val
                    elif key == 'cbd_blockade':
                        cbd_block = True
        
        terrains = []
        for t in self.base_terrains:
            exp = general_exp
            if t['name'] == 'Maryvia':
                exp += maryvia_exp
            terrain = {
                'name': t['name'],
                'x': (t['x'][0] - exp, t['x'][1] + exp),
                'y': (t['y'][0] - exp, t['y'][1] + exp),
                'z': (t['z'][0] - exp, t['z'][1] + exp)
            }
            terrains.append(terrain)
        
        # CBD 封锁区（半径10的立方体）
        if cbd_block:
            cbd_center = (240, 240, 300)
            terrains.append({
                'name': 'CBD_Blockade',
                'x': (cbd_center[0] - 10, cbd_center[0] + 10),
                'y': (cbd_center[1] - 10, cbd_center[1] + 10),
                'z': (cbd_center[2] - 10, cbd_center[2] + 10)
            })
        
        return terrains
    
    def manhattan_distance(self, p1, p2):
        """计算回卷曼哈顿距离"""
        dist = 0
        for i in range(3):
            diff = abs(p1[i] - p2[i])
            dist += min(diff, 500 - diff)
        return dist
    
    def point_in_terrain(self, point, terrain):
        """检查点是否在地形内部（边界也算在内）"""
        x, y, z = point
        return (terrain['x'][0] <= x <= terrain['x'][1] and
                terrain['y'][0] <= y <= terrain['y'][1] and
                terrain['z'][0] <= z <= terrain['z'][1])
    
    def segment_intersects_terrain(self, p1, p2, terrain):
        """
        检查从 p1 到 p2 的曼哈顿路径是否与地形相交
        曼哈顿路径按 X -> Y -> Z 顺序移动（实际上任意顺序距离相同）
        使用精确的 AABB 线段相交检测
        """
        # 路径分解：p1 -> (p2[0], p1[1], p1[2]) -> (p2[0], p2[1], p1[2]) -> p2
        waypoints = [
            p1,
            (p2[0], p1[1], p1[2]),
            (p2[0], p2[1], p1[2]),
            p2
        ]
        
        for i in range(len(waypoints) - 1):
            start = waypoints[i]
            end = waypoints[i + 1]
            if self._axis_aligned_segment_intersects_box(start, end, terrain):
                return True
        return False
    
    def _axis_aligned_segment_intersects_box(self, p1, p2, terrain):
        """
        检查轴对齐线段是否与 AABB 相交
        假设 p1 和 p2 只在一个轴上有差异（曼哈顿路径）
        """
        # 找出变化的轴
        axis = -1
        for i in range(3):
            if p1[i] != p2[i]:
                axis = i
                break
        
        if axis == -1:
            # p1 == p2，检查点是否在地形内
            return self.point_in_terrain(p1, terrain)
        
        # 线段在其他两个轴上的固定值
        fixed_axes = [i for i in range(3) if i != axis]
        
        # 检查固定轴是否在地形范围内
        bounds = [terrain['x'], terrain['y'], terrain['z']]
        for ax in fixed_axes:
            if not (bounds[ax][0] <= p1[ax] <= bounds[ax][1]):
                return False  # 线段不在地形的投影范围内
        
        # 检查变化轴上的线段是否与地形范围重叠
        seg_min = min(p1[axis], p2[axis])
        seg_max = max(p1[axis], p2[axis])
        terrain_min = bounds[axis][0]
        terrain_max = bounds[axis][1]
        
        return seg_max >= terrain_min and seg_min <= terrain_max
    
    def path_intersects_any_terrain(self, p1, p2, terrains):
        """检查路径是否与任何地形相交"""
        for terrain in terrains:
            if self.segment_intersects_terrain(p1, p2, terrain):
                return True
        return False
    
    
    def _simplify_path(self, path, terrains):
        """
        简化路径：如果 path[i] 可以直达 path[j]，则移除中间点
        """
        if len(path) <= 2:
            return path
        
        simplified = [path[0]]
        i = 0
        
        while i < len(path) - 1:
            # 尝试找到最远可直达的点
            farthest = i + 1
            for j in range(i + 2, len(path)):
                if not self.path_intersects_any_terrain(path[i], path[j], terrains):
                    farthest = j
            
            simplified.append(path[farthest])
            i = farthest
        
        return simplified
    
    
    def _get_wrapped_point(self, start, end):
        """
        寻找终点相对于起点的最近虚拟坐标（处理回卷）。
        例如：如果世界大小500，Start=490, End=10 -> NewEnd=510
        """
        new_end = list(end)
        for i in range(3):
            diff = end[i] - start[i]
            # 如果直接距离 > 半个世界，说明跨越边界更近
            if diff > self.map_size / 2:
                new_end[i] -= self.map_size
            elif diff < -self.map_size / 2:
                new_end[i] += self.map_size
        return tuple(new_end)

    def _intersect_aabb(self, p1, p2, box_min, box_max):
        """
        Slab Method 检测线段 p1->p2 是否与 AABB [min, max] 相交。
        返回 True 表示碰撞（穿过内部）。
        """
        t_min = 0.0
        t_max = 1.0
        
        d = [p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2]]
        
        for i in range(3):
            # 稍微缩小障碍物判定，允许贴着表面走 (Grazing)
            # 只有深深切入内部才算碰撞
            b_min = box_min[i] + 1e-3
            b_max = box_max[i] - 1e-3
            
            if abs(d[i]) < 1e-9:
                # 平行于轴，如果起点不在范围内，则平行且无交集
                if p1[i] < b_min or p1[i] > b_max:
                    return False
            else:
                t1 = (b_min - p1[i]) / d[i]
                t2 = (b_max - p1[i]) / d[i]
                
                if t1 > t2: t1, t2 = t2, t1
                
                t_min = max(t_min, t1)
                t_max = min(t_max, t2)
                
                if t_min > t_max:
                    return False
        
        return True

    def _check_segment_collision(self, p1, p2, obstacle):
        """
        检测线段是否碰撞，考虑到 p2 可能是回卷后的虚拟坐标。
        """
        # 1. 基础障碍物检测
        ox_min, ox_max = obstacle['x']
        oy_min, oy_max = obstacle['y']
        oz_min, oz_max = obstacle['z']
        
        if self._intersect_aabb(p1, p2, (ox_min, oy_min, oz_min), (ox_max, oy_max, oz_max)):
            return True
            
        # 2. 幻影障碍物检测 (处理回卷碰撞)
        # 如果 p2 在 [0, 500] 范围外，说明这条线穿过了世界边界。
        # 我们需要检查障碍物是否出现在"下一个世界"的路径上。
        
        shifts = [0, 0, 0]
        check_phantom = False
        
        for i in range(3):
            if p2[i] < 0:
                shifts[i] = -self.map_size
                check_phantom = True
            elif p2[i] > self.map_size:
                shifts[i] = self.map_size
                check_phantom = True
        
        if check_phantom:
            # 移动障碍物到虚拟位置进行检测
            # 例如线段去往 x=550, 我们检测位于 x+500 处的障碍物副本
            p_ox_min, p_ox_max = ox_min + shifts[0], ox_max + shifts[0]
            p_oy_min, p_oy_max = oy_min + shifts[1], oy_max + shifts[1]
            p_oz_min, p_oz_max = oz_min + shifts[2], oz_max + shifts[2]
            
            if self._intersect_aabb(p1, p2, (p_ox_min, p_oy_min, p_oz_min), (p_ox_max, p_oy_max, p_oz_max)):
                return True
                
        return False

    def _generate_critical_nodes(self, p1, p2, terrains):
        """
        生成关键导航点，包含：
        1. 起点和终点
        2. 障碍物的安全角点（Corner Points）
        3. 起终点在障碍物边缘的"贴边投影点"（Grazing Points）-> 核心优化
        """
        nodes = set([p1, p2])
        
        # 定义需要关注的坐标集合
        # 我们不仅关心障碍物的边界，还关心起点终点的坐标值
        # 这样可以生成如 (p1.x, obstacle.y_min-1, p1.z) 这样的投影点
        xs = {p1[0], p2[0]}
        ys = {p1[1], p2[1]}
        zs = {p1[2], p2[2]}
        
        # 提取所有地形的安全边界
        safe_boundaries = []
        for t in terrains:
            # 安全边界：障碍物范围外扩1格
            # 注意处理回卷 (0-1 -> 499)
            safe_x = [(t['x'][0] - 1) % self.map_size, (t['x'][1] + 1) % self.map_size]
            safe_y = [(t['y'][0] - 1) % self.map_size, (t['y'][1] + 1) % self.map_size]
            safe_z = [(t['z'][0] - 1) % self.map_size, (t['z'][1] + 1) % self.map_size]

            # safe_x = [t['x'][0], t['x'][1]]
            # safe_y = [t['y'][0], t['y'][1]]
            # safe_z = [t['z'][0], t['z'][1]]
            
            safe_boundaries.append((safe_x, safe_y, safe_z))
            
            # 将安全边界加入坐标池
            xs.update(safe_x)
            ys.update(safe_y)
            zs.update(safe_z)

        # === 核心优化：仅生成有意义的组合 ===
        # 暴力组合所有坐标点太多(N^3)，我们需要精简。
        # 策略：只保留 "障碍物角点" 和 "起终点投影到障碍物面的点"
        
        candidate_points = set()
        candidate_points.add(p1)
        candidate_points.add(p2)
        
        for sx, sy, sz in safe_boundaries:
            # 1. 障碍物角点 (Corner Points) - 用于大范围绕行
            for x in sx:
                for y in sy:
                    for z in sz:
                        candidate_points.add((x, y, z))
            
            # 2. 投影贴边点 (Grazing Points) - 您的Case最需要的
            # 逻辑：保持两个坐标不变（对齐起点或终点），只改变一个坐标以绕过障碍
            
            # 针对起点 p1 的投影
            for x in sx: candidate_points.add((x, p1[1], p1[2])) # 沿X轴贴边
            for y in sy: candidate_points.add((p1[0], y, p1[2])) # 沿Y轴贴边
            for z in sz: candidate_points.add((p1[0], p1[1], z)) # 沿Z轴贴边
            
            # 针对终点 p2 的投影
            for x in sx: candidate_points.add((x, p2[1], p2[2]))
            for y in sy: candidate_points.add((p2[0], y, p2[2]))
            for z in sz: candidate_points.add((p2[0], p2[1], z))

        # 过滤无效点（在地形内）并加入最终节点集
        for p in candidate_points:
            # 过滤掉虽然是边界但其实撞到了其他地形的点
            if not self.is_collision(p, self.k): # 注意这里用当前k即可，地形大体不变，或者传入具体k
                nodes.add(p)
                
        return list(nodes)

    def get_distance_with_detour(self, p1, p2, k=None):
        if k is None: k = self.k
        terrains = self.get_terrains_at_k(k)
        
        # 缓存键
        terrain_key = tuple(sorted((t['name'], t['x'], t['y'], t['z']) for t in terrains))
        cache_key = (p1, p2, terrain_key)
        if cache_key in self.path_cache:
            return self.path_cache[cache_key]

        # 1. 尝试直连 (快速检查)
        # 获取最佳虚拟连线（处理回卷）
        p2_prime = self._get_wrapped_point(p1, p2)
        blocked = False
        for t in terrains:
            if self._check_segment_collision(p1, p2_prime, t):
                blocked = True
                break
        
        if not blocked:
            dist = self.manhattan_distance(p1, p2)
            self.path_cache[cache_key] = (dist, None) # None 表示无 detour
            return dist, None

        # 2. 直连失败，构建稀疏图进行搜索
        # 使用优化后的节点生成逻辑
        nodes = self._generate_critical_nodes(p1, p2, terrains)
        
        # 确保 p1, p2 在列表中的准确位置
        if p1 not in nodes: nodes.append(p1)
        if p2 not in nodes: nodes.append(p2)
        
        # 构建邻接表 (只连接视线可见的点)
        # 优化：不构建全图，改用 A* 动态展开 (On-the-fly A*) 以提升性能
        
        target = p2
        start_node = p1
        
        # A* 算法
        # heap: (f_score, g_score, current_node, path_list)
        pq = [(self.manhattan_distance(start_node, target), 0, start_node, [])]
        visited = {} # node -> min_g_score
        
        final_dist = float('inf')
        final_path = None
        
        while pq:
            f, g, u, path = heapq.heappop(pq)
            
            if u in visited and visited[u] <= g:
                continue
            visited[u] = g
            
            if u == target:
                final_dist = g
                final_path = path + [u]
                break
            
            # 尝试连接其他关键点
            for v in nodes:
                if u == v: continue
                
                # 启发式剪枝：如果 直线距离 + 当前消耗 已经超过已知最优，跳过
                h = self.manhattan_distance(v, target)
                if final_dist != float('inf') and g + self.manhattan_distance(u, v) + h >= final_dist:
                    continue

                # 碰撞检测
                v_prime = self._get_wrapped_point(u, v)
                seg_blocked = False
                for t in terrains:
                    if self._check_segment_collision(u, v_prime, t):
                        seg_blocked = True
                        break
                
                if not seg_blocked:
                    dist_uv = self.manhattan_distance(u, v)
                    new_g = g + dist_uv
                    
                    if v not in visited or new_g < visited[v]:
                        heapq.heappush(pq, (new_g + h, new_g, v, path + [u]))

        if final_dist == float('inf'):
            return float('inf'), None
            
        # 缓存结果
        detour = final_path[1:-1] if final_path and len(final_path) > 2 else None
        self.path_cache[cache_key] = (final_dist, detour)
        return final_dist, detour
    
    
    def get_distance(self, p1, p2, k=None):
        """获取距离（兼容旧接口）"""
        return self.get_distance_with_detour(p1, p2, k)[0]
    
    def get_full_path(self, p1, p2, k=None):
        """
        获取完整路径（包括起点和终点）
        返回: (距离, 完整路径点列表)
        """
        if k is None:
            k = self.k
        
        terrains = self.get_terrains_at_k(k)
        return self.find_optimal_path_enum(p1, p2, terrains)
    
    def format_path_for_output(self, p1, p2, k=None, include_jumps=None):
        """
        生成符合 System.md 格式要求的路径字符串
        
        格式示例:
        - 直达: (0,0,0,t) → (100,100,100,t)
        - 绕行: (0,0,0,t) → (50,60,70,t) → (100,100,100,t)
        - 含穿越: (0,0,0,t) → 穿越SW1(50,450,50,t) → (50,450,50,t-30)
        
        Args:
            p1: 起点坐标
            p2: 终点坐标
            k: 时间参数
            include_jumps: 可选，包含的跳跃信息 {'type': 'SW'/'KW', 'id': int, 'pos': tuple}
        
        Returns:
            格式化的路径字符串
        """
        if k is None:
            k = self.k
        
        dist, path = self.get_full_path(p1, p2, k)
        
        # 基础路径格式化
        parts = []
        for i, point in enumerate(path):
            coord_str = f"({point[0]},{point[1]},{point[2]})"
            parts.append(coord_str)
        
        result = " → ".join(parts)
        
        return result, dist, path
    
    def explain_detour(self, p1, p2, k=None):
        """
        解释为什么需要绕行
        
        Returns:
            说明字符串，如果不需要绕行返回 None
        """
        if k is None:
            k = self.k
        
        terrains = self.get_terrains_at_k(k)
        
        # 检查直达路径
        if not self.path_intersects_any_terrain(p1, p2, terrains):
            return None
        
        # 找出阻挡的地形
        blocking = []
        for terrain in terrains:
            if self.segment_intersects_terrain(p1, p2, terrain):
                blocking.append(terrain['name'])
        
        if blocking:
            terrain_names = {
                'Maryvia': '玛丽维亚岩脊',
                'BlackHole': '空间黑洞',
                'ControlZone': '高空管制区',
                'CBD_Blockade': 'CBD封锁区'
            }
            names = [terrain_names.get(t, t) for t in blocking]
            return f"直达路径被阻挡: {', '.join(names)}"
        
        return "路径被未知地形阻挡"

    def is_collision(self, p, k):
        """检查点 p 在时间 k 是否与任何地形碰撞"""
        terrains = self.get_terrains_at_k(k)
        for terrain in terrains:
            if self.point_in_terrain(p, terrain):
                return True
        return False

    def get_tax(self, k, jump_idx, is_sw, used_first_free_ks=None):
        """
        计算穿越税
        used_first_free_ks: 已使用过首次免税的事件start_k集合，用于追踪每个first_free事件是否已被使用
        返回: (税额, 是否使用了首次免税, 使用的事件start_k)
        """
        if used_first_free_ks is None:
            used_first_free_ks = set()
        
        count = 1
        first_free = False
        first_free_k = None
        for e in self.events:
            continue_time = 1
            if e['start_k'] <= k < e['start_k'] + continue_time:
                # 检查是否有first_free事件，且该事件的首次免税尚未被使用
                if 'first_free' in e and e['start_k'] not in used_first_free_ks:
                    first_free = True
                    first_free_k = e['start_k']
        
        final_tax = 5 * count
        
        # 收集所有在当前时间生效的税费事件
        active_tax_events = []
        for e in self.events:
            for key in ['tax_mul_all', 'tax_mul_kw', 'tax_mul_sw']:
                if key not in e:
                    continue
                    
                # 提取事件参数
                if isinstance(e[key], dict):
                    continue_time = e[key].get('continue', 1)
                    val = e[key].get('value', 1)
                else:
                    continue_time = 1
                    val = e[key]
                
                # 检查时间是否在事件生效范围内
                if not (e['start_k'] <= k < e['start_k'] + continue_time):
                    continue
                
                # 检查是否对当前穿越类型生效
                if key == 'tax_mul_all':
                    active_tax_events.append({'tier': e.get('tier', 3), 'val': val})
                elif key == 'tax_mul_kw' and not is_sw:
                    active_tax_events.append({'tier': e.get('tier', 3), 'val': val})
                elif key == 'tax_mul_sw' and is_sw:
                    active_tax_events.append({'tier': e.get('tier', 3), 'val': val})
        
        # 按tier排序（tier1 -> tier2 -> tier3）
        active_tax_events.sort(key=lambda x: x['tier'])
        
        # 依次累乘，每次取整
        for tax_event in active_tax_events:
            final_tax = math.floor(final_tax * tax_event['val'])
        if first_free: final_tax = 0
        return int(final_tax), first_free, first_free_k

    def analyze_market_trends(self, k_min, k_max):
        trends = {}
        for item in self.destinations:
            prices = []
            # safe_min = max(0, k_min) 
            safe_min = k_min
            for k in range(safe_min, k_max + 1):
                lvl = self.get_price_level(item, k)
                prices.append((k, lvl))
            
            if not prices: continue

            min_price = min(p[1] for p in prices)
            best_buys = [p for p in prices if p[1] == min_price]
            max_price = max(p[1] for p in prices)
            best_sells = [p for p in prices if p[1] == max_price]
            
            trends[item] = {
                'min_lvl': min_price,
                'max_lvl': max_price,
                'buy_windows': best_buys, 
                'sell_windows': best_sells
            }
        return trends

    def get_kw_transform(self, kw_id, pos):
        x, y, z = pos
        if kw_id == 1: nx, ny, nz = x+50, y+50, z+50
        elif kw_id == 2: nx, ny, nz = 2*x, 2*y, 2*z
        elif kw_id == 3: nx, ny, nz = 500-x, 500-y, 500-z
        elif kw_id == 4: nx, ny, nz = int(x*0.5), int(y*0.5), int(z*0.5)
        else: return pos
        return (nx % 500, ny % 500, nz % 500)
    
    def optimize(self, max_time_leap=30, max_jumps=4):
        """
        树形搜索优化算法（支持多次穿越）：
        修正版：买入时间必须在第一次穿越后，且仅能在静止（停靠/等待）时进行，不可在列车运行途中买入。
        """
        trend_min_k = self.k - max_time_leap
        trend_max_k = self.k + max_time_leap
        trends = self.analyze_market_trends(trend_min_k, trend_max_k)
        
        # 确定搜索的商品范围：如果指定了item_limit，则只搜索限定范围内的商品
        search_items = self.item_limit if self.item_limit else list(self.destinations.keys())
        
        best_plan_per_item = {i: {'profit': 0} for i in self.destinations}
        
        # 诊断信息收集
        search_stats = {'nodes_visited': 0, 'pruned': 0, 'solutions_found': 0}
        trade_analysis = {i: [] for i in self.destinations}
        
        # 预计算各商品的最大可能差价（用于剪枝）
        max_price_diff = {}
        for item in search_items:
            if trends[item]['buy_windows'] and trends[item]['sell_windows']:
                min_buy_lvl = trends[item]['buy_windows'][0][1]
                max_sell_lvl = trends[item]['sell_windows'][0][1]
                max_price_diff[item] = 10 * self.base_prices[item] * (max_sell_lvl - min_buy_lvl)
            else:
                max_price_diff[item] = 0
        
        
        
        def dfs(pos, k, jumps, fuel, tax, path, valid_buy_ranges, used_first_free_ks=None):
            """
            valid_buy_ranges: 列表，存储 [(start_k, end_k), ...] 
            代表历史路径中所有处于静止状态且满足"第一次穿越后"条件的时间段。
            used_first_free_ks: 已使用过首次免税的事件start_k集合
            """
            if used_first_free_ks is None:
                used_first_free_ks = set()
            search_stats['nodes_visited'] += 1
            # print(jumps, path)
            # 剪枝：时间超出范围
            if k < trend_min_k or k > trend_max_k:
                search_stats['pruned'] += 1
                return
            
            # === 分支1：如果已穿越>=1次，尝试到各卖出点 ===
            if jumps >= 1:
                for item in search_items:
                    dest = self.destinations[item]
                    # 剪枝：预估最大利润
                    max_possible_profit = max_price_diff[item] - fuel - tax
                    if max_possible_profit <= best_plan_per_item[item].get('profit', 0):
                        continue
                    
                    # 枚举出发前的等待时间（穿越后可以等待若干旬再出发去卖出点）
                    for wait_before_move in range(self.max_wait_time):
                        start_move_k = k + wait_before_move
                        if start_move_k > trend_max_k:
                            break
                        
                        # 构建买入时间范围：包含历史窗口 + 当前等待期间
                        current_buy_ranges = valid_buy_ranges + [(k, start_move_k)]
                        
                        # 计算到卖出点的距离（使用出发时的k计算地形）
                        dist_to_dest, detour = self.get_distance_with_detour(pos, dest, start_move_k)
                        if dist_to_dest == float('inf'):
                            continue
                            
                        fuel_to_dest = 10 + dist_to_dest
                        travel_time = math.ceil(fuel_to_dest / 10)
                        arrival_k = start_move_k + travel_time
                        
                        if arrival_k > trend_max_k:
                            # 记录诊断信息
                            if len(trade_analysis[item]) < 5:
                                trade_analysis[item].append({
                                    'path': path.copy(),
                                    'reason': f"到达卖出点k={arrival_k} > 上限{trend_max_k}"
                                })
                            continue
                        
                        # CBD封锁检查
                        if item == 'NL' and self.is_collision(dest, arrival_k):
                            continue
                        
                        # 枚举卖出等待时间
                        for sell_wait in range(self.max_time_leap):
                            sell_k = arrival_k + sell_wait
                            if sell_k > trend_max_k:
                                break
                            
                            # 在有效窗口中寻找最佳买入点（包括到达卖出点后的等待期间）
                            extended_buy_ranges = current_buy_ranges + [(arrival_k, sell_k)]
                            best_buy_lvl = 99
                            best_buy_k = None  # k=-1 是合法时刻，不能用作"未找到"哨兵
                            
                            for (bk_start, bk_end) in extended_buy_ranges:
                                for t in range(bk_start, bk_end + 1):
                                    lvl = self.get_price_level(item, t)
                                    if lvl < best_buy_lvl:
                                        best_buy_lvl = lvl
                                        best_buy_k = t
                                        
                            if best_buy_k is None:
                                continue

                            buy_lvl = best_buy_lvl
                            sell_lvl = self.get_price_level(item, sell_k)
                            
                            buy_cost = 10 * self.base_prices[item] * buy_lvl
                            sell_price = 10 * self.base_prices[item] * sell_lvl
                            total_fuel = fuel + fuel_to_dest
                            profit = sell_price - buy_cost - total_fuel - tax
                            
                            # 检查资产限制
                            if total_fuel + tax + buy_cost > self.assets:
                                continue
                            
                            # 比较条件：利润更高，或利润相同但结束时间更早
                            current_profit = best_plan_per_item[item].get('profit', 0)
                            current_sell_k = best_plan_per_item[item].get('sell_k', float('inf'))
                            is_better = (profit > current_profit) or (profit == current_profit and sell_k < current_sell_k)
                            
                            if is_better:
                                search_stats['solutions_found'] += 1
                                
                                # 构建完整路径
                                full_path = path.copy()
                                buy_at_dest = best_buy_k >= arrival_k
                                
                                if buy_at_dest:
                                    # 先移动至卖出点，到达后等待买入再卖出
                                    full_path.append({
                                        'action': 'MoveToSell',
                                        'fuel': fuel_to_dest,
                                        'k_start': start_move_k,
                                        'k_end': sell_k,
                                        'wait': sell_k - arrival_k,
                                        'detour': detour,
                                        'buy_at_dest': True,
                                        'buy_k': best_buy_k,
                                        'arrival_k': arrival_k
                                    })
                                else:
                                    # 先买入再移动至卖出点（原有逻辑）
                                    full_path.append({
                                        'action': 'Buy',
                                        'wait_before': best_buy_k - k,
                                        'k': best_buy_k
                                    })
                                    full_path.append({
                                        'action': 'MoveToSell',
                                        'fuel': fuel_to_dest,
                                        'k_start': start_move_k,
                                        'k_end': sell_k,
                                        'wait': sell_wait,
                                        'detour': detour
                                    })
                                
                                best_plan_per_item[item] = {
                                    'profit': profit,
                                    'item': item,
                                    'path': full_path,
                                    'buy_lvl': buy_lvl,
                                    'sell_lvl': sell_lvl,
                                    'buy_k': best_buy_k,
                                    'sell_k': sell_k,
                                    'fuel': total_fuel,
                                    'tax': tax,
                                    'jump_count': jumps
                                }
            
            # === 分支2：如果穿越次数<max_jumps，继续搜索穿越点 ===
            if jumps < max_jumps:
                # 确定允许的穿越类型
                allowed_jump_types = self.jump_type_limit if self.jump_type_limit else ['SW', 'KW']
                
                # 搜索 SW（如果允许）
                if 'SW' in allowed_jump_types:
                  for sw_id, conf in self.sw_config.items():
                    for wait in range(self.max_wait_time):  
                        start_k = k + wait
                        if start_k > trend_max_k: continue
                        
                        if conf['pos'] != pos:
                            dist, detour = self.get_distance_with_detour(pos, conf['pos'], start_k)
                            if dist == float('inf'): continue

                            fuel_to_sw = 10 + dist
                        else:
                            dist = 0
                            detour = None
                            fuel_to_sw = 0
                        travel_time = math.ceil(fuel_to_sw / 10)
                        arrival_k = start_k + travel_time
                        
                        if arrival_k > trend_max_k or arrival_k < trend_min_k: continue
                        if self.is_collision(conf['pos'], arrival_k): continue
                        
                        after_jump_k = arrival_k + conf['dk']
                        if after_jump_k > trend_max_k or after_jump_k < trend_min_k: continue
                        
                        sw_tax, used_free, free_k = self.get_tax(arrival_k, jumps, True, used_first_free_ks)
                        new_fuel = fuel + fuel_to_sw
                        new_tax = tax + sw_tax
                        
                        # 剪枝
                        best_current = max(p.get('profit', 0) for p in best_plan_per_item.values())
                        max_possible = max(max_price_diff.values()) - new_fuel - new_tax
                        if max_possible <= best_current:
                            search_stats['pruned'] += 1
                            continue
                        
                        # 更新 Valid Buy Ranges
                        # 当前位置 pos，等待了 wait 旬。
                        # 如果当前 jumps >= 1，那么这段等待时间 (k, k+wait) 是有效的买入时间
                        next_buy_ranges = list(valid_buy_ranges)
                        if jumps >= 1:
                            next_buy_ranges.append((k, k + wait))
                        # 穿越后到达的新时间点 after_jump_k 也可以买入（因为 jumps + 1 >= 1）
                        next_buy_ranges.append((after_jump_k, after_jump_k))
                        
                        # 更新已使用的首次免税事件
                        new_used_first_free_ks = set(used_first_free_ks)
                        if used_free and free_k is not None:
                            new_used_first_free_ks.add(free_k)
                        
                        # 构建新路径
                        new_path = path.copy()
                        new_path.append({
                            'action': 'SW',
                            'id': sw_id,
                            'fuel': fuel_to_sw,
                            'tax': sw_tax,
                            'k_arrive': arrival_k,
                            'dk': conf['dk'],
                            'wait_before': wait,
                            'detour': detour
                        })
                        
                        dfs(conf['pos'], after_jump_k, jumps + 1, new_fuel, new_tax, new_path, next_buy_ranges, new_used_first_free_ks)
                
                # 搜索 KW（如果允许）
                if 'KW' in allowed_jump_types:
                  for kw_id in self.kw_config:
                    searched_arrivals = set()
                    
                    for wait in range(self.max_wait_time):
                        start_k = k + wait
                        if start_k > trend_max_k: continue
                        
                        for dt in range(0, self.max_wait_time):
                            arrival_k = start_k + dt
                            if arrival_k > trend_max_k: break
                            if arrival_k in searched_arrivals: continue
                            
                            kw_pos = self.get_kw_pos(kw_id, arrival_k)
                            dist, detour = self.get_distance_with_detour(pos, kw_pos, start_k)
                            
                            if dist == float('inf'): continue
                            
                            fuel_to_kw = 10 + dist if dist != 0 else 0
                            required_dt = math.ceil(fuel_to_kw / 10)
                            
                            if required_dt == dt:
                                searched_arrivals.add(arrival_k)
                                if self.is_collision(kw_pos, arrival_k): continue
                                
                                pos_after = self.get_kw_transform(kw_id, kw_pos)
                                kw_tax, used_free, free_k = self.get_tax(arrival_k, jumps, False, used_first_free_ks)
                                new_fuel = fuel + fuel_to_kw
                                new_tax = tax + kw_tax
                                
                                # 剪枝
                                best_current = max(p.get('profit', 0) for p in best_plan_per_item.values())
                                max_possible = max(max_price_diff.values()) - new_fuel - new_tax
                                if max_possible <= best_current:
                                    search_stats['pruned'] += 1
                                    continue
                                
                                # 更新 Valid Buy Ranges
                                next_buy_ranges = list(valid_buy_ranges)
                                if jumps >= 1:
                                    next_buy_ranges.append((k, k + wait))
                                # 穿越后到达的新时间点 arrival_k 也可以买入（因为 jumps + 1 >= 1）
                                next_buy_ranges.append((arrival_k, arrival_k))

                                # 更新已使用的首次免税事件
                                new_used_first_free_ks = set(used_first_free_ks)
                                if used_free and free_k is not None:
                                    new_used_first_free_ks.add(free_k)

                                # 构建新路径
                                new_path = path.copy()
                                new_path.append({
                                    'action': 'KW',
                                    'id': kw_id,
                                    'fuel': fuel_to_kw,
                                    'tax': kw_tax,
                                    'k_arrive': arrival_k,
                                    'dk': 0,
                                    'wait_before': wait,
                                    'pos_before': kw_pos,
                                    'detour': detour
                                })
                                
                                dfs(pos_after, arrival_k, jumps + 1, new_fuel, new_tax, new_path, next_buy_ranges, new_used_first_free_ks)
        
        # 开始搜索（初始 valid_buy_ranges 为空）
        dfs(self.pos, self.k, 0, 0, 0, [], [])
        
        # 整理结果：利润优先，利润相同时选择结束时间更早的
        final_best = None
        global_max_profit = 0
        global_best_sell_k = float('inf')
        for item, plan in best_plan_per_item.items():
            plan_profit = plan.get('profit', 0)
            plan_sell_k = plan.get('sell_k', float('inf'))
            is_better = (plan_profit > global_max_profit) or (plan_profit == global_max_profit and plan_sell_k < global_best_sell_k)
            if is_better:
                global_max_profit = plan_profit
                global_best_sell_k = plan_sell_k
                final_best = plan
                
        # 诊断信息
        for item in best_plan_per_item:
            if best_plan_per_item[item].get('profit', 0) <= 0:
                reachable_from_start = self._collect_reachable_jumps(
                    self.pos, self.k, trend_min_k, trend_max_k
                )
                best_plan_per_item[item] = {
                    'profit': -float('inf'),
                    'diagnostics': {
                        'reachable_jumps': reachable_from_start['reachable'][:5],
                        'unreachable_jumps': reachable_from_start['unreachable'][:3],
                        'trade_issues': trade_analysis[item][:5],
                        'search_stats': search_stats
                    }
                }
                
        return final_best, best_plan_per_item, trends

    def _collect_reachable_jumps(self, pos, k, trend_min_k, trend_max_k):
        """收集从指定位置可达的穿越点（用于诊断）"""
        reachable = []
        unreachable = []
        
        # SW
        for sw_id, conf in self.sw_config.items():
            dist = self.manhattan_distance(pos, conf['pos'])
            travel_time = math.ceil((10 + dist) / 10)
            arrival_k = k + travel_time
            after_jump_k = arrival_k + conf['dk']
            
            arrival_ok = trend_min_k <= arrival_k <= trend_max_k
            after_ok = trend_min_k <= after_jump_k <= trend_max_k
            
            if arrival_ok and after_ok:
                reachable.append(f"SW{sw_id}(到达k={arrival_k},跳跃后k={after_jump_k})")
            else:
                if not arrival_ok:
                    unreachable.append(f"SW{sw_id}(到达k={arrival_k}超出范围)")
                else:
                    unreachable.append(f"SW{sw_id}(跳跃后k={after_jump_k}超出范围)")
        
        # KW
        for kw_id in self.kw_config:
            found = False
            for dt in range(0, 1):
                arrival_k = k + dt
                if arrival_k > trend_max_k:
                    break
                kw_pos = self.get_kw_pos(kw_id, arrival_k)
                dist = self.manhattan_distance(pos, kw_pos)
                if dist != 0:
                    travel_time = math.ceil((10 + dist) / 10)
                else:
                    travel_time = 0
                # print(travel_time, dt)
                if travel_time == dt:
                    reachable.append(f"KW{kw_id}(行驶{dt}旬,k={arrival_k})")
                    found = True
                    break
            if not found:
                unreachable.append(f"KW{kw_id}(无法拦截)")
        
        return {'reachable': reachable, 'unreachable': unreachable}

    # def optimize_multi_trade(self, max_time_leap=30, max_jumps=4, trade_times_limit=1):
    #     """
    #     连续N次交易的动态规划优化算法
        
    #     规则：
    #     1. 每次交易必须先完成至少一次穿越，然后才能买入和卖出
    #     2. 上一次交易卖出后，需要再次穿越才能进行下一次交易
    #     3. 总穿越次数不超过 max_jumps
    #     4. 时间范围限制在 [k - max_time_leap, k + max_time_leap]
        
    #     动态规划状态设计：
    #     - 状态: (pos, k, remaining_jumps, trades_done)
    #     - 值: (max_profit, best_plan_sequence)
        
    #     Args:
    #         max_time_leap: 最大时间跨度
    #         max_jumps: 最大穿越次数
    #         trade_times_limit: 最大交易次数，默认为1（等同于单次optimize）
        
    #     Returns:
    #         result: 包含最优交易序列和统计信息的字典
    #     """
    #     trend_min_k = self.k - max_time_leap
    #     trend_max_k = self.k + max_time_leap
        
    #     # 预计算市场趋势
    #     trends = self.analyze_market_trends(trend_min_k, trend_max_k)
        
    #     # 商品范围
    #     search_items = self.item_limit if self.item_limit else list(self.destinations.keys())
        
    #     # ========== 中间结果缓存 ==========
    #     # 单次交易方案缓存: {(start_pos, start_k, max_jumps_for_trade): [trade_plans]}
    #     single_trade_cache = {}
        
    #     # DP记忆化缓存: {(pos, k, remaining_jumps, trades_done): (max_profit, best_sequence)}
    #     dp_memo = {}
        
    #     # 统计信息
    #     stats = {
    #         'single_trade_searches': 0,
    #         'single_trade_cache_hits': 0,
    #         'dp_calls': 0,
    #         'dp_cache_hits': 0
    #     }
        
    #     def generate_single_trades(start_pos, start_k, available_jumps):
    #         """
    #         从指定状态生成所有可能的单次交易方案（带缓存）
            
    #         返回列表，每个元素为完整的交易方案字典
    #         """
    #         # 检查缓存
    #         cache_key = (start_pos, start_k, available_jumps)
    #         if cache_key in single_trade_cache:
    #             stats['single_trade_cache_hits'] += 1
    #             return single_trade_cache[cache_key]
            
    #         stats['single_trade_searches'] += 1
    #         trade_plans = []
            
    #         # 使用DFS搜索所有可能的交易路径
    #         def dfs_trade(pos, k, jumps, fuel, tax, path, valid_buy_ranges):
    #             """DFS搜索单次交易的所有可能路径"""
    #             # 边界检查
    #             if k < trend_min_k or k > trend_max_k:
    #                 return
    #             if jumps > available_jumps:
    #                 return
                
    #             # === 尝试完成交易（需要至少1次穿越） ===
    #             if jumps >= 1:
    #                 current_buy_ranges = valid_buy_ranges + [(k, k)]
                    
    #                 for item in search_items:
    #                     dest = self.destinations[item]
                        
    #                     # 计算到卖出点的距离
    #                     dist_to_dest, detour = self.get_distance_with_detour(pos, dest, k)
    #                     if dist_to_dest == float('inf'):
    #                         continue
                        
    #                     fuel_to_dest = 10 + dist_to_dest
    #                     travel_time = math.ceil(fuel_to_dest / 10)
    #                     arrival_k = k + travel_time
                        
    #                     if arrival_k > trend_max_k:
    #                         continue
                        
    #                     # CBD封锁检查
    #                     if item == 'NL' and self.is_collision(dest, arrival_k):
    #                         continue
                        
    #                     # 枚举卖出等待时间（限制搜索范围以提高效率）
    #                     for sell_wait in range(min(self.max_time_leap, trend_max_k - arrival_k + 1)):
    #                         sell_k = arrival_k + sell_wait
    #                         if sell_k > trend_max_k:
    #                             break
                            
    #                         # 在有效窗口中寻找最佳买入点
    #                         best_buy_lvl = 99
    #                         best_buy_k = -1
                            
    #                         for (bk_start, bk_end) in current_buy_ranges:
    #                             for t in range(bk_start, bk_end + 1):
    #                                 lvl = self.get_price_level(item, t)
    #                                 if lvl < best_buy_lvl:
    #                                     best_buy_lvl = lvl
    #                                     best_buy_k = t
                            
    #                         if best_buy_k == -1:
    #                             continue
                            
    #                         buy_lvl = best_buy_lvl
    #                         sell_lvl = self.get_price_level(item, sell_k)
                            
    #                         buy_cost = 10 * self.base_prices[item] * buy_lvl
    #                         sell_price = 10 * self.base_prices[item] * sell_lvl
    #                         total_fuel = fuel + fuel_to_dest
    #                         profit = sell_price - buy_cost - total_fuel - tax
                            
    #                         # 检查资产限制（简化：假设初始资产足够）
    #                         if total_fuel + tax + buy_cost > self.assets:
    #                             continue
                            
    #                         # 只保存正利润的方案
    #                         if profit <= 0:
    #                             continue
                            
    #                         # 构建完整路径
    #                         full_path = path.copy()
    #                         full_path.append({
    #                             'action': 'Buy',
    #                             'wait_before': 0,
    #                             'k': best_buy_k
    #                         })
    #                         full_path.append({
    #                             'action': 'MoveToSell',
    #                             'fuel': fuel_to_dest,
    #                             'k_start': k,
    #                             'k_end': sell_k,
    #                             'wait': sell_wait,
    #                             'detour': detour
    #                         })
                            
    #                         trade_plans.append({
    #                             'start_pos': start_pos,
    #                             'start_k': start_k,
    #                             'end_pos': dest,
    #                             'end_k': sell_k,
    #                             'profit': profit,
    #                             'jumps_used': jumps,
    #                             'path': full_path,
    #                             'item': item,
    #                             'buy_k': best_buy_k,
    #                             'sell_k': sell_k,
    #                             'buy_lvl': buy_lvl,
    #                             'sell_lvl': sell_lvl,
    #                             'fuel': total_fuel,
    #                             'tax': tax
    #                         })
                
    #             # === 继续搜索穿越点 ===
    #             if jumps < available_jumps:
    #                 allowed_jump_types = self.jump_type_limit if self.jump_type_limit else ['SW', 'KW']
                    
    #                 # 搜索 SW
    #                 if 'SW' in allowed_jump_types:
    #                     for sw_id, conf in self.sw_config.items():
    #                         # 限制等待时间以提高效率
    #                         max_wait = min(self.max_wait_time, trend_max_k - k + 1)
    #                         for wait in range(max_wait):
    #                             start_k_move = k + wait
    #                             if start_k_move > trend_max_k:
    #                                 continue
                                
    #                             if conf['pos'] != pos:
    #                                 dist, detour = self.get_distance_with_detour(pos, conf['pos'], start_k_move)
    #                                 if dist == float('inf'):
    #                                     continue
    #                                 fuel_to_sw = 10 + dist
    #                             else:
    #                                 dist = 0
    #                                 detour = None
    #                                 fuel_to_sw = 0
                                
    #                             travel_time = math.ceil(fuel_to_sw / 10)
    #                             arrival_k = start_k_move + travel_time
                                
    #                             if arrival_k > trend_max_k or arrival_k < trend_min_k:
    #                                 continue
    #                             if self.is_collision(conf['pos'], arrival_k):
    #                                 continue
                                
    #                             after_jump_k = arrival_k + conf['dk']
    #                             if after_jump_k > trend_max_k or after_jump_k < trend_min_k:
    #                                 continue
                                
    #                             sw_tax = self.get_tax(arrival_k, jumps, True)
    #                             new_fuel = fuel + fuel_to_sw
    #                             new_tax = tax + sw_tax
                                
    #                             # 更新买入时间范围
    #                             next_buy_ranges = list(valid_buy_ranges)
    #                             if jumps >= 1:
    #                                 next_buy_ranges.append((k, k + wait))
    #                             next_buy_ranges.append((after_jump_k, after_jump_k))
                                
    #                             new_path = path.copy()
    #                             new_path.append({
    #                                 'action': 'SW',
    #                                 'id': sw_id,
    #                                 'fuel': fuel_to_sw,
    #                                 'tax': sw_tax,
    #                                 'k_arrive': arrival_k,
    #                                 'dk': conf['dk'],
    #                                 'wait_before': wait,
    #                                 'detour': detour
    #                             })
                                
    #                             dfs_trade(conf['pos'], after_jump_k, jumps + 1, new_fuel, new_tax, new_path, next_buy_ranges)
                    
    #                 # 搜索 KW
    #                 if 'KW' in allowed_jump_types:
    #                     for kw_id in self.kw_config:
    #                         searched_arrivals = set()
                            
    #                         max_wait = min(self.max_wait_time, trend_max_k - k + 1)
    #                         for wait in range(max_wait):
    #                             start_k_move = k + wait
    #                             if start_k_move > trend_max_k:
    #                                 continue
                                
    #                             for dt in range(0, self.max_wait_time):
    #                                 arrival_k = start_k_move + dt
    #                                 if arrival_k > trend_max_k:
    #                                     break
    #                                 if arrival_k in searched_arrivals:
    #                                     continue
                                    
    #                                 kw_pos = self.get_kw_pos(kw_id, arrival_k)
    #                                 dist, detour = self.get_distance_with_detour(pos, kw_pos, start_k_move)
                                    
    #                                 if dist == float('inf'):
    #                                     continue
                                    
    #                                 fuel_to_kw = 10 + dist if dist != 0 else 0
    #                                 required_dt = math.ceil(fuel_to_kw / 10)
                                    
    #                                 if required_dt == dt:
    #                                     searched_arrivals.add(arrival_k)
    #                                     if self.is_collision(kw_pos, arrival_k):
    #                                         continue
                                        
    #                                     pos_after = self.get_kw_transform(kw_id, kw_pos)
    #                                     kw_tax = self.get_tax(arrival_k, jumps, False)
    #                                     new_fuel = fuel + fuel_to_kw
    #                                     new_tax = tax + kw_tax
                                        
    #                                     # 更新买入时间范围
    #                                     next_buy_ranges = list(valid_buy_ranges)
    #                                     if jumps >= 1:
    #                                         next_buy_ranges.append((k, k + wait))
    #                                     next_buy_ranges.append((arrival_k, arrival_k))
                                        
    #                                     new_path = path.copy()
    #                                     new_path.append({
    #                                         'action': 'KW',
    #                                         'id': kw_id,
    #                                         'fuel': fuel_to_kw,
    #                                         'tax': kw_tax,
    #                                         'k_arrive': arrival_k,
    #                                         'dk': 0,
    #                                         'wait_before': wait,
    #                                         'pos_before': kw_pos,
    #                                         'detour': detour
    #                                     })
                                        
    #                                     dfs_trade(pos_after, arrival_k, jumps + 1, new_fuel, new_tax, new_path, next_buy_ranges)
            
    #         # 开始DFS搜索
    #         dfs_trade(start_pos, start_k, 0, 0, 0, [], [])
            
    #         # 保存到缓存
    #         single_trade_cache[cache_key] = trade_plans
            
    #         return trade_plans
        
    #     def dp(pos, k, remaining_jumps, trades_done):
    #         """
    #         动态规划递归函数（带记忆化）
            
    #         Args:
    #             pos: 当前位置
    #             k: 当前时间
    #             remaining_jumps: 剩余可用穿越次数
    #             trades_done: 已完成的交易次数
            
    #         Returns:
    #             (max_profit, best_sequence): 从当前状态开始能获得的最大利润和最优交易序列
    #         """
    #         stats['dp_calls'] += 1
            
    #         # 边界条件
    #         if remaining_jumps < 1:  # 无法再进行穿越，无法完成新交易
    #             return (0, [])
    #         if trades_done >= trade_times_limit:  # 达到最大交易次数
    #             return (0, [])
    #         if k > trend_max_k:  # 超出时间范围
    #             return (0, [])
            
    #         # 检查缓存
    #         state_key = (pos, k, remaining_jumps, trades_done)
    #         if state_key in dp_memo:
    #             stats['dp_cache_hits'] += 1
    #             return dp_memo[state_key]
            
    #         # 生成从当前状态可能的所有单次交易
    #         possible_trades = generate_single_trades(pos, k, remaining_jumps)
            
    #         # 如果没有可行的交易，返回0
    #         if not possible_trades:
    #             dp_memo[state_key] = (0, [])
    #             return (0, [])
            
    #         best_total_profit = 0
    #         best_sequence = []
            
    #         # 枚举每个可能的单次交易
    #         for trade in possible_trades:
    #             # 当前交易的利润
    #             current_profit = trade['profit']
                
    #             # 交易后的状态
    #             next_pos = trade['end_pos']
    #             next_k = trade['end_k']
    #             next_remaining_jumps = remaining_jumps - trade['jumps_used']
                
    #             # 递归计算后续最优收益
    #             future_profit, future_sequence = dp(next_pos, next_k, next_remaining_jumps, trades_done + 1)
                
    #             total_profit = current_profit + future_profit
                
    #             if total_profit > best_total_profit:
    #                 best_total_profit = total_profit
    #                 best_sequence = [trade] + future_sequence
            
    #         dp_memo[state_key] = (best_total_profit, best_sequence)
    #         return (best_total_profit, best_sequence)
        
    #     # ========== 执行DP求解 ==========
    #     print(f"开始多次交易优化: max_jumps={max_jumps}, trade_times_limit={trade_times_limit}")
        
    #     total_profit, best_sequence = dp(self.pos, self.k, max_jumps, 0)
        
    #     # ========== 整理输出结果 ==========
    #     result = {
    #         'total_profit': total_profit,
    #         'trade_count': len(best_sequence),
    #         'trades': best_sequence,
    #         'trends': trends,
    #         'cache': {
    #             'single_trade_cache': single_trade_cache,  # 保存中间结果以便复用
    #             'dp_memo': dp_memo
    #         },
    #         'stats': {
    #             **stats,
    #             'memo_size': len(dp_memo),
    #             'single_trade_cache_size': len(single_trade_cache),
    #             'max_jumps': max_jumps,
    #             'trade_times_limit': trade_times_limit,
    #             'time_range': (trend_min_k, trend_max_k)
    #         }
    #     }
        
    #     print(f"优化完成: 总利润={total_profit}, 交易次数={len(best_sequence)}")
    #     print(f"统计: DP调用={stats['dp_calls']}, DP缓存命中={stats['dp_cache_hits']}, "
    #           f"单次交易搜索={stats['single_trade_searches']}, 单次交易缓存命中={stats['single_trade_cache_hits']}")
        
    #     return result

    # def optimize_flexible_trade(self, max_time_leap=30, max_jumps=4, trade_times_limit=1):
    #     """
    #     灵活多次交易的动态规划优化算法（支持同时持有多个商品）
        
    #     规则（与optimize_multi_trade的区别）：
    #     1. 第一次穿越后，可以任意进行买入/卖出/穿越操作
    #     2. 买卖和穿越可以交织进行（不要求每次交易前必须穿越）
    #     3. **同一时间可以持有多个商品**（可同时持有SM、CB、NL、HL）
    #     4. 最后一次卖出标志交易结束（卖出次数 = 交易次数）
    #     5. 总穿越次数不超过 max_jumps
    #     6. 总交易次数（卖出次数）不超过 trade_times_limit
        
    #     动态规划状态设计：
    #     - 状态: (pos, k, remaining_jumps, has_jumped, holdings_tuple, trades_done)
    #     - has_jumped: 是否已经完成过至少一次穿越
    #     - holdings_tuple: 当前持仓的元组表示 ((item1, buy_k1, buy_lvl1), (item2, buy_k2, buy_lvl2), ...)
        
    #     Args:
    #         max_time_leap: 最大时间跨度
    #         max_jumps: 最大穿越次数
    #         trade_times_limit: 最大交易次数（卖出次数）
        
    #     Returns:
    #         result: 包含最优交易序列和统计信息的字典
    #     """
    #     trend_min_k = self.k - max_time_leap
    #     trend_max_k = self.k + max_time_leap
        
    #     # 预计算市场趋势
    #     trends = self.analyze_market_trends(trend_min_k, trend_max_k)
        
    #     # 商品范围
    #     search_items = self.item_limit if self.item_limit else list(self.destinations.keys())
        
    #     # 允许的穿越类型
    #     allowed_jump_types = self.jump_type_limit if self.jump_type_limit else ['SW', 'KW']
        
    #     # ========== 记忆化缓存 ==========
    #     # 状态: (pos, k, remaining_jumps, has_jumped, holdings_tuple, trades_done)
    #     dp_memo = {}
        
    #     # 统计信息
    #     stats = {
    #         'dp_calls': 0,
    #         'dp_cache_hits': 0,
    #         'buy_attempts': 0,
    #         'sell_attempts': 0,
    #         'jump_attempts': 0
    #     }
        
    #     def holdings_to_tuple(holdings_dict):
    #         """将持仓字典转为可哈希的元组"""
    #         if not holdings_dict:
    #             return ()
    #         return tuple(sorted((item, info['buy_k'], info['buy_lvl']) for item, info in holdings_dict.items()))
        
    #     def tuple_to_holdings(holdings_tuple):
    #         """将元组转回持仓字典"""
    #         if not holdings_tuple:
    #             return {}
    #         return {item: {'buy_k': buy_k, 'buy_lvl': buy_lvl} for item, buy_k, buy_lvl in holdings_tuple}
        
    #     def dfs(pos, k, remaining_jumps, has_jumped, holdings, trades_done, total_fuel, total_tax, path):
    #         """
    #         DFS搜索最优交易路径（支持多商品持仓）
            
    #         Args:
    #             pos: 当前位置
    #             k: 当前时间
    #             remaining_jumps: 剩余穿越次数
    #             has_jumped: 是否已完成过至少一次穿越
    #             holdings: 当前持仓字典 {item: {'buy_k': k, 'buy_lvl': lvl}}
    #             trades_done: 已完成的交易次数（卖出次数）
    #             total_fuel: 累计燃料消耗
    #             total_tax: 累计穿越税
    #             path: 行动路径
            
    #         Returns:
    #             (max_profit, best_path): 最大利润和最优路径
    #         """
    #         stats['dp_calls'] += 1
            
    #         # 边界条件
    #         if k > trend_max_k or k < trend_min_k:
    #             return (0, [])
    #         if trades_done >= trade_times_limit:
    #             return (0, [])
            
    #         # 检查缓存
    #         holdings_tuple = holdings_to_tuple(holdings)
    #         state_key = (pos, k, remaining_jumps, has_jumped, holdings_tuple, trades_done)
    #         if state_key in dp_memo:
    #             stats['dp_cache_hits'] += 1
    #             return dp_memo[state_key]
            
    #         best_profit = 0
    #         best_path = []
            
    #         # ========== 动作1: 卖出（如果持有商品且已穿越） ==========
    #         if holdings and has_jumped:
    #             stats['sell_attempts'] += 1
                
    #             # 可以选择卖出任意一个持有的商品
    #             for item, buy_info in holdings.items():
    #                 dest = self.destinations[item]
    #                 buy_k = buy_info['buy_k']
    #                 buy_lvl = buy_info['buy_lvl']
                    
    #                 # 计算到卸货点的距离
    #                 dist_to_dest, detour = self.get_distance_with_detour(pos, dest, k)
                    
    #                 if dist_to_dest == float('inf'):
    #                     continue
                    
    #                 fuel_to_dest = 10 + dist_to_dest if dist_to_dest > 0 else 0
    #                 travel_time = math.ceil(fuel_to_dest / 10) if fuel_to_dest > 0 else 0
    #                 arrival_k = k + travel_time
                    
    #                 # 枚举卖出等待时间
    #                 for sell_wait in range(min(self.max_time_leap // 2, trend_max_k - arrival_k + 1)):
    #                     sell_k = arrival_k + sell_wait
    #                     if sell_k > trend_max_k:
    #                         break
                        
    #                     # CBD封锁检查
    #                     if item == 'NL' and self.is_collision(dest, sell_k):
    #                         continue
                        
    #                     sell_lvl = self.get_price_level(item, sell_k)
                        
    #                     # 计算本次交易利润
    #                     buy_cost = 10 * self.base_prices[item] * buy_lvl
    #                     sell_price = 10 * self.base_prices[item] * sell_lvl
    #                     trade_profit = sell_price - buy_cost
                        
    #                     if trade_profit <= 0:
    #                         continue  # 跳过亏损交易
                        
    #                     # 构建卖出动作
    #                     sell_action = {
    #                         'action': 'Sell',
    #                         'item': item,
    #                         'fuel': fuel_to_dest,
    #                         'k_start': k,
    #                         'k_end': sell_k,
    #                         'wait': sell_wait,
    #                         'detour': detour,
    #                         'buy_k': buy_k,
    #                         'buy_lvl': buy_lvl,
    #                         'sell_k': sell_k,
    #                         'sell_lvl': sell_lvl,
    #                         'trade_profit': trade_profit
    #                     }
                        
    #                     new_path = path + [sell_action]
                        
    #                     # 卖出后从持仓中移除该商品
    #                     new_holdings = {k_item: v for k_item, v in holdings.items() if k_item != item}
                        
    #                     # 递归：卖出后该商品从持仓移除
    #                     future_profit, future_path = dfs(
    #                         dest, sell_k, remaining_jumps, has_jumped,
    #                         new_holdings, trades_done + 1,
    #                         total_fuel + fuel_to_dest, total_tax, new_path
    #                     )
                        
    #                     total_profit = trade_profit + future_profit
    #                     if total_profit > best_profit:
    #                         best_profit = total_profit
    #                         best_path = new_path + future_path
            
    #         # ========== 动作2: 买入（如果已穿越，且该商品未持有） ==========
    #         if has_jumped:
    #             stats['buy_attempts'] += 1
                
    #             for item in search_items:
    #                 # 跳过已持有的商品
    #                 if item in holdings:
    #                     continue
                    
    #                 # 枚举等待时间寻找更好的买入点
    #                 for wait in range(min(self.max_time_leap // 4, trend_max_k - k + 1)):
    #                     buy_time = k + wait
    #                     if buy_time > trend_max_k:
    #                         break
                        
    #                     lvl = self.get_price_level(item, buy_time)
                        
    #                     # 只有价格足够低才考虑买入（简单剪枝）
    #                     if lvl > 5:  # 价格等级太高，跳过
    #                         continue
                        
    #                     buy_action = {
    #                         'action': 'Buy',
    #                         'item': item,
    #                         'k': buy_time,
    #                         'lvl': lvl,
    #                         'wait_before': wait
    #                     }
                        
    #                     new_path = path + [buy_action]
                        
    #                     # 买入后添加到持仓
    #                     new_holdings = dict(holdings)
    #                     new_holdings[item] = {'buy_k': buy_time, 'buy_lvl': lvl}
                        
    #                     # 递归：买入后该商品加入持仓
    #                     future_profit, future_path = dfs(
    #                         pos, buy_time, remaining_jumps, has_jumped,
    #                         new_holdings, trades_done,
    #                         total_fuel, total_tax, new_path
    #                     )
                        
    #                     if future_profit > best_profit:
    #                         best_profit = future_profit
    #                         best_path = new_path + future_path
            
    #         # ========== 动作3: 穿越（如果还有穿越次数） ==========
    #         if remaining_jumps > 0:
    #             stats['jump_attempts'] += 1
                
    #             # 搜索 SW
    #             if 'SW' in allowed_jump_types:
    #                 for sw_id, conf in self.sw_config.items():
    #                     sw_pos = conf['pos']
    #                     dk = conf['dk']
                        
    #                     # 枚举等待时间
    #                     for wait in range(min(self.max_wait_time // 2, trend_max_k - k + 1)):
    #                         start_k_move = k + wait
    #                         if start_k_move > trend_max_k:
    #                             continue
                            
    #                         # 计算到SW的距离
    #                         if sw_pos != pos:
    #                             dist, detour = self.get_distance_with_detour(pos, sw_pos, start_k_move)
    #                             if dist == float('inf'):
    #                                 continue
    #                             fuel_to_sw = 10 + dist
    #                         else:
    #                             dist = 0
    #                             detour = None
    #                             fuel_to_sw = 0
                            
    #                         travel_time = math.ceil(fuel_to_sw / 10) if fuel_to_sw > 0 else 0
    #                         arrival_k = start_k_move + travel_time
                            
    #                         if arrival_k > trend_max_k or arrival_k < trend_min_k:
    #                             continue
    #                         if self.is_collision(sw_pos, arrival_k):
    #                             continue
                            
    #                         after_jump_k = arrival_k + dk
    #                         if after_jump_k > trend_max_k or after_jump_k < trend_min_k:
    #                             continue
                            
    #                         # 计算当前穿越次数（用于税率计算）
    #                         current_jump_count = max_jumps - remaining_jumps
    #                         sw_tax = self.get_tax(arrival_k, current_jump_count, True)
                            
    #                         sw_action = {
    #                             'action': 'SW',
    #                             'id': sw_id,
    #                             'fuel': fuel_to_sw,
    #                             'tax': sw_tax,
    #                             'k_arrive': arrival_k,
    #                             'dk': dk,
    #                             'wait_before': wait,
    #                             'detour': detour
    #                         }
                            
    #                         new_path = path + [sw_action]
                            
    #                         # 递归：穿越后位置不变，时间跳跃
    #                         future_profit, future_path = dfs(
    #                             sw_pos, after_jump_k, remaining_jumps - 1, True,
    #                             holdings, trades_done,
    #                             total_fuel + fuel_to_sw, total_tax + sw_tax, new_path
    #                         )
                            
    #                         # 扣除穿越成本后的净利润
    #                         net_profit = future_profit - sw_tax - fuel_to_sw
    #                         if net_profit > best_profit:
    #                             best_profit = net_profit
    #                             best_path = new_path + future_path
                
    #             # 搜索 KW
    #             if 'KW' in allowed_jump_types:
    #                 for kw_id in self.kw_config:
    #                     searched_arrivals = set()
                        
    #                     for wait in range(min(self.max_wait_time // 2, trend_max_k - k + 1)):
    #                         start_k_move = k + wait
    #                         if start_k_move > trend_max_k:
    #                             continue
                            
    #                         for dt in range(0, self.max_wait_time // 2):
    #                             arrival_k = start_k_move + dt
    #                             if arrival_k > trend_max_k:
    #                                 break
    #                             if arrival_k in searched_arrivals:
    #                                 continue
                                
    #                             kw_pos = self.get_kw_pos(kw_id, arrival_k)
    #                             dist, detour = self.get_distance_with_detour(pos, kw_pos, start_k_move)
                                
    #                             if dist == float('inf'):
    #                                 continue
                                
    #                             fuel_to_kw = 10 + dist if dist != 0 else 0
    #                             required_dt = math.ceil(fuel_to_kw / 10) if fuel_to_kw > 0 else 0
                                
    #                             if required_dt == dt:
    #                                 searched_arrivals.add(arrival_k)
    #                                 if self.is_collision(kw_pos, arrival_k):
    #                                     continue
                                    
    #                                 pos_after = self.get_kw_transform(kw_id, kw_pos)
                                    
    #                                 current_jump_count = max_jumps - remaining_jumps
    #                                 kw_tax = self.get_tax(arrival_k, current_jump_count, False)
                                    
    #                                 kw_action = {
    #                                     'action': 'KW',
    #                                     'id': kw_id,
    #                                     'fuel': fuel_to_kw,
    #                                     'tax': kw_tax,
    #                                     'k_arrive': arrival_k,
    #                                     'dk': 0,
    #                                     'wait_before': wait,
    #                                     'pos_before': kw_pos,
    #                                     'detour': detour
    #                                 }
                                    
    #                                 new_path = path + [kw_action]
                                    
    #                                 # 递归：KW后位置变换，时间不变
    #                                 future_profit, future_path = dfs(
    #                                     pos_after, arrival_k, remaining_jumps - 1, True,
    #                                     holdings, trades_done,
    #                                     total_fuel + fuel_to_kw, total_tax + kw_tax, new_path
    #                                 )
                                    
    #                                 net_profit = future_profit - kw_tax - fuel_to_kw
    #                                 if net_profit > best_profit:
    #                                     best_profit = net_profit
    #                                     best_path = new_path + future_path
            
    #         # 保存到缓存
    #         dp_memo[state_key] = (best_profit, best_path)
    #         return (best_profit, best_path)
        
    #     # ========== 执行DFS求解 ==========
    #     print(f"开始灵活多次交易优化(多商品持仓): max_jumps={max_jumps}, trade_times_limit={trade_times_limit}")
        
    #     total_profit, best_path = dfs(
    #         self.pos, self.k, max_jumps, False,
    #         {}, 0,  # 初始空仓
    #         0, 0, []
    #     )
        
    #     # ========== 整理输出结果 ==========
    #     # 从path中提取交易信息
    #     trades = []
    #     current_trades = {}  # 记录每个商品的买入信息 {item: buy_action}
    #     total_fuel = 0
    #     total_tax = 0
    #     total_jumps = 0
        
    #     for action in best_path:
    #         if action['action'] == 'Buy':
    #             item = action['item']
    #             current_trades[item] = {
    #                 'item': item,
    #                 'buy_k': action['k'],
    #                 'buy_lvl': action['lvl'],
    #                 'path_from_buy': [action],
    #                 'fuel': 0,
    #                 'tax': 0,
    #                 'jumps_after_buy': 0
    #             }
    #         elif action['action'] == 'Sell':
    #             item = action['item']
    #             if item in current_trades:
    #                 trade_info = current_trades[item]
    #                 trade_info['sell_k'] = action['sell_k']
    #                 trade_info['sell_lvl'] = action['sell_lvl']
    #                 trade_info['profit'] = action['trade_profit']
    #                 trade_info['end_pos'] = self.destinations[item]
    #                 trade_info['end_k'] = action['k_end']
    #                 trade_info['path_from_buy'].append(action)
    #                 trade_info['fuel'] += action.get('fuel', 0)
    #                 trades.append(trade_info)
    #                 del current_trades[item]
    #         elif action['action'] in ['SW', 'KW']:
    #             total_jumps += 1
    #             # 将穿越动作添加到所有当前持仓商品的路径中
    #             for item, trade_info in current_trades.items():
    #                 trade_info['path_from_buy'].append(action)
    #                 trade_info['fuel'] += action.get('fuel', 0)
    #                 trade_info['tax'] += action.get('tax', 0)
    #                 trade_info['jumps_after_buy'] += 1
    #             # 如果没有持仓，记录到总消耗中
    #             if not current_trades:
    #                 total_fuel += action.get('fuel', 0)
    #                 total_tax += action.get('tax', 0)
        
    #     # 计算总和
    #     for t in trades:
    #         total_fuel += t.get('fuel', 0)
    #         total_tax += t.get('tax', 0)
        
    #     result = {
    #         'total_profit': total_profit,
    #         'trade_count': len(trades),
    #         'trades': trades,
    #         'full_path': best_path,
    #         'trends': trends,
    #         'stats': {
    #             **stats,
    #             'memo_size': len(dp_memo),
    #             'max_jumps': max_jumps,
    #             'trade_times_limit': trade_times_limit,
    #             'total_jumps_used': total_jumps,
    #             'total_fuel': total_fuel,
    #             'total_tax': total_tax,
    #             'time_range': (trend_min_k, trend_max_k)
    #         }
    #     }
        
    #     print(f"灵活交易优化完成(多商品持仓): 总利润={total_profit}, 交易次数={len(trades)}")
    #     print(f"统计: DFS调用={stats['dp_calls']}, 缓存命中={stats['dp_cache_hits']}")
        
    #     return result
