"""
演唱会审计系统实现
基于 system_prompt.md 中的规则实现完整的审计判定系统
"""
import re
from typing import Dict, List, Tuple, Optional, Any, final
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class SecurityLevel(Enum):
    """场馆安保等级"""
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


class VenueGrade(Enum):
    """场次定级"""
    S_PLUS = "S+"
    S = "S"
    A = "A"
    C = "C"


class HotelTier(Enum):
    """酒店等级"""
    T1 = "T1"  # 豪华级
    T2 = "T2"  # 标准级
    T3 = "T3"  # 经济级


@dataclass
class Equipment:
    """拍摄器材"""
    code: str  # 器材代码
    name: str  # 器材名称
    focal_range: Tuple[int, int]  # 焦距范围（等效）
    rent: float  # 日租金
    deposit: float  # 押金
    weight: float  # 重量（kg）
    length: float  # 最大伸缩长度（mm）
    # structure: str  # 结构类型
    # min_focus_distance: float = 0.0  # 最近对焦距离（米）
    removable: bool   # 是否可拆卸
    is_white: bool    # 是否白色镜身 (高安保可能敏感)
    
    def is_heavy(self) -> bool:
        """是否为重型器材（SP 四.四.2：重量 > 1.5kg 或伸缩长度 > 150mm）"""
        return self.weight > 1.5 or self.length > 150
    
    def is_extreme_long_focal(self) -> bool:
        """
        是否为极限长焦器材（600mm - 3000mm）
        SP 定义：极限长焦是指焦段范围可达到 600-3000mm 的器材
        判定标准：最大焦段 > 600mm（超过600mm才算极限长焦）
        例如：WC-03 (24-3000mm) 是极限长焦，ZC-02 (24-600mm) 不是
        """
        return self.focal_range[1] > 600


# 器材库
# 对焦距离说明：
# - 短焦器材：对焦距离很近，可以很近拍摄（0.1-0.5米）
# - 中长焦器材：对焦距离中等（1-3米）
# - 超长焦器材：对焦距离较远（3-5米）
# - 极限长焦器材：对焦距离很远（5-10米以上）

equipments = [
            Equipment("MT-01", "移动终端", (13, 230), 100, 3000, 0.2, 0, False, False),
            Equipment("ZC-02", "一体化长焦", (24, 600), 200, 5000, 1.1, 120, False, False),
            Equipment("WC-03", "物理超长焦", (24, 3000), 150, 8000, 1.4, 180, False, False),
            Equipment("PQ-04", "专业画质", (70, 200), 400, 12000, 1.8, 200, True, False),
            Equipment("TQ-05", "旗舰特写", (100, 500), 500, 15000, 2.1, 300, True, True),
        ]

# 创建器材字典以便快速查找
EQUIPMENT_LIB = {eq.code: eq for eq in equipments}
class VisualTier(Enum):
    PANORAMA = "环境与全景"       # 短焦 13-50mm
    PORTRAIT = "全身与半身"       # 中长焦 70-200mm
    CLOSEUP = "表情特写"         # 超长焦 300-600mm
    EXTREME = "面部识别/远程"     # 极限长焦 600-3000mm

# 场馆安保等级映射
VENUE_SECURITY_MAP = {
    "高": [
        "国家体育场（鸟巢）", "国家体育馆（冰之帆）", "凯迪拉克中心（原五棵松体育馆）",
        "上海梅赛德斯-奔驰文化中心", "红磡香港体育馆", "澳门银河综艺馆"
    ],
    "中": [
        "上海体育场（八万人）", "广州奥体中心", "杭州奥体中心体育场（大莲花）",
        "国家网球中心（钻石球场）", "中国进出口商品交易会展馆（广交会展馆）", "曼谷 Impact Arena"
    ],
    "低": [
        "MAO Livehouse", "糖果TANGO", "保利剧院"
    ]
}

# 酒店品牌映射
HOTEL_BRANDS = {
    "T1": ["希尔顿", "喜来登", "威斯汀", "君悦", "瑞吉", "半岛", "柏悦", "丽思卡尔顿", "洲际", "华尔道夫", "香格里拉", "悦榕庄"],
    "T2": ["全季", "亚朵", "橘子", "欢漫", "智选假日", "维也纳", "美豪", "和颐", "丽枫", "假日酒店"],
    "T3": ["汉庭", "如家", "7天", "布丁", "速8", "格林豪泰", "锦江之星", "海友"]
}

# 各级别默认酒店配置（名称和基准价格）
DEFAULT_HOTELS = {
    "T1": {"name": "希尔顿酒店", "cost": 1000.0},
    "T2": {"name": "全季酒店", "cost": 500.0},
    "T3": {"name": "汉庭酒店", "cost": 300.0},
}


def get_hotel_tier_by_name(hotel_name: str) -> "HotelTier":
    """根据酒店名称确定酒店等级
    
    通过匹配酒店品牌库确定酒店等级，支持双向模糊匹配（品牌名包含在酒店名中，或酒店名包含在品牌名中）
    
    Args:
        hotel_name: 酒店名称
        
    Returns:
        HotelTier: 酒店等级（T1豪华级/T2标准级/T3经济级），未匹配到时默认返回T3
    """
    for tier, brands in HOTEL_BRANDS.items():
        for brand in brands:
            if brand in hotel_name or hotel_name in brand:
                return HotelTier(tier)
    return HotelTier.T3

# 声学巅峰场馆（加3分）
ACOUSTIC_PEAK_VENUES = ["红磡香港体育馆", "保利剧院", "国家体育场"]

# 标准室内感场馆（加1分）
INDOOR_VENUES = [
    "国家体育馆（冰之帆）", "凯迪拉克中心（五棵松）", "上海梅赛德斯-奔驰文化中心",
    "澳门银河综艺馆", "MAO Livehouse", "糖果TANGO", "曼谷 Impact Arena"
]

# 情感维度关键词 - 高价值（触发+5分：神仙场/必看本命）
EMOTION_HIGH_VALUE_KEYWORDS = ["唯一本命", "精神支柱", "非他不看", "梦中情演", "此生必看", "久违归来"]

# 情感维度关键词 - 告别类高价值（触发+5分：终场告别/收官等）
EMOTION_FAREWELL_KEYWORDS = ["终场告别", "收官", "解散", "封麦", "最后一站"]

# 情感维度关键词 - 中等价值（触发+3分：值得一去/阶段首秀）
EMOTION_MEDIUM_VALUE_KEYWORDS = ["换了新名字", "单飞后首场", "新巡演首站", "跨界尝试", "新歌首演", "作品热度", "中期回归"]

# 情感维度关键词 - 扣分（触发-5分：凑热闹场/资源浪费）
# (1) 识别关键词：每个关键词各触发-5分
EMOTION_NEGATIVE_KEYWORDS = ["群星", "音乐节", "拼盘演出", "商业站台", "路演"]
# (2) 硬性条件关键词：整组只触发一次-5分
EMOTION_NEGATIVE_HARD_KEYWORDS = ["假唱争议", "嗓子哑了", "倒嗓", "体力滑坡", "现场划水", "全场大合唱太多"]

# 场馆负面评价关键词（触发-3分）
VENUE_NEGATIVE_SCORE_KEYWORDS = ["音响烂", "回声大", "炸麦", "听不清", "吃字"]

# 市场维度 - 特殊节点关键词（触发+3分）
SPECIAL_EVENT_KEYWORDS = ["生日会", "周年庆典", "跨年场", "情人节专场", "出道周年纪念日", "歌手生日"]

# 市场维度 - 唯一性关键词（触发+3分）
UNIQUE_EVENT_KEYWORDS = ["全球首场", "全球最终场"]


@dataclass
class HotelOption:
    """酒店选项"""
    name: str  # 酒店名称
    cost: float  # 酒店费用

@dataclass
class TransportOption:
    """交通选项"""
    transport: str  # 交通方式
    cost: float  # 交通费用
    duration: float  # 交通时长（小时）
    duration_from_input: bool = False  # 时长是否从原始输入中解析

@dataclass
class ConcertInfo:
    """演唱会信息"""
    name: str  # 场次名称
    date: str  # 日期
    venue: str  # 场馆
    seat_row: int  # 座位排数
    seat_area: str  # 座位区域（内场/看台）
    visual_keyword: str  # 视觉产出层级关键句
    transport: str  # 交通方式（单一选项时使用）
    transport_cost: float  # 交通费用（单一选项时使用）
    transport_duration: float  # 交通时长（小时）（单一选项时使用）
    emotion_keywords: List[str]  # 核心情感维度关键词
    special_keywords: List[str]  # 特殊节点维度关键词
    ticket_original: float  # 票面原价
    ticket_actual: float  # 实付金额
    hotel_name: str  # 酒店名称（单一选项时使用）
    hotel_cost: float  # 酒店费用（单一选项时使用）
    transport_duration_from_input: bool = False  # 时长是否从原始输入中解析
    venue_negative_keywords: List[str] = field(default_factory=list)  # 场馆负面评价关键词
    want_view_count: float = 0.0  # 想看人数（单位：万人）
    special_note: str = ""  # 特殊说明
    # 多种选择支持（用于最终审计场）
    hotel_options: List[HotelOption] = field(default_factory=list)  # 多个酒店选项
    transport_options: List[TransportOption] = field(default_factory=list)  # 多个交通选项
    is_final_audit: bool = False  # 是否为最终审计场（最后一场）
    requested_equipment_codes: List[str] = field(default_factory=list)


@dataclass
class AuditResult:
    """审计结果"""
    # 实时现金流穿透审计
    nominal_balance: float  # 名义余额
    deposit_occupied: float  # 未退押金占用额
    actual_available_balance: float  # 实际可用余额
    hotel_selection: str  # 酒店选择
    transport_selection: str  # 交通方式选择
    ticket_selection: str  # 门票选择
    
    # 物理准入权与光学冲突判定
    security_level: str  # 场馆安保等级
    
    # 生理资产 BE 动态结算
    initial_be: float = 100.0  # 初始体力值
    recovery_rate: float = 10.0  # 恢复率
    total_loss: float = 0.0  # 本场总损耗
    final_be: float = 100.0  # 离场残值
    previous_be: float = 100.0  # 上场残余BE
    days_since_last: int = 0  # 休整天数
    # 损耗详情
    loss_details: Dict[str, float] = field(default_factory=dict)  # 损耗组成明细
    
    # 演出价值分定格与定级
    score: int = 0  # 演出价值分
    grade: str = ""  # 定级（S+/S/A/C）
    is_cancelled: bool = False  # 是否被熔断
    score_details: Dict[str, Any] = field(default_factory=dict)  # 得分明细
    
    # 可选字段（有默认值）
    risk_buffer: Optional[float] = None  # 风险缓冲金
    buffer_indicator_a: Optional[bool] = None  # 缓冲金指标A：演出价值分≥13
    buffer_indicator_b: Optional[bool] = None  # 缓冲金指标B：想看人数≥100万 或 实付≥票面原价3倍
    rr_collapsed_this_session: bool = False  # 本场触发了RR永久坍塌（10%→8%）
    rr_collapse_reason: Optional[str] = None  # RR坍塌原因说明
    equipment: Optional[str] = None  # 拍摄器材
    equipment_selection_logic: Optional[str] = None  # 拍摄器材选择逻辑说明
    equipment_rent: Optional[float] = None  # 器材租金
    equipment_deposit: Optional[float] = None  # 器材押金
    ticket_cost: Optional[float] = None  # 本场门票实付金额
    transport_cost: Optional[float] = None  # 本场交通费用
    hotel_cost: Optional[float] = None  # 本场酒店费用


class ConcertAuditSystem:
    """演唱会审计系统"""
    
    def __init__(self, initial_balance: float = 20000.0, initial_be: float = 100.0):
        self.initial_balance = initial_balance
        self.risk_buffer_total = 1000.0
        self.risk_buffer_used = 0.0
        self.current_be = initial_be
        self.recovery_rate = 10.0  # 基准恢复率
        self.concerts: List[ConcertInfo] = []
        self.audit_results: List[AuditResult] = []
        self.total_spent = 0.0
        self.deposits: List[Dict] = []  # 存储押金信息 {equipment_code, deposit, return_date}

    @staticmethod
    def _transport_kind(text: str) -> str:
        if any(
            token in text
            for token in ("飞机", "航班", "航空", "飞航", "飞往", "直飞")
        ):
            return "航空"
        if "高铁" in text:
            return "高铁"
        return "其他"

    @staticmethod
    def _amounts(text: str) -> List[float]:
        return [
            float(value.replace(",", ""))
            for value in re.findall(r"([\d,]+(?:\.\d+)?)\s*元", text)
        ]

    def _fill_authoritative_source_fields(
        self, concert: ConcertInfo, concert_text: str, only_missing: bool = True
    ) -> None:
        """Fill fields from the authored Chinese source without rewriting it."""
        structured = bool(
            re.search(r"(?m)^\s*-?\s*(?:日期|场馆|座位要求)\s*[：:]", concert_text)
        )
        if "场次信息如下：" in concert_text:
            body_text = concert_text.split("场次信息如下：", 1)[1]
        else:
            head, _, rest = concert_text.strip().partition("\n")
            body_text = (
                rest if re.search(r"第[一二三四五六七八九十\d]+场", head) else concert_text
            )
        kept = {
            "date": concert.date,
            "venue": concert.venue,
            "seat": (concert.seat_area, concert.seat_row),
            "visual": concert.visual_keyword,
            "ticket": (concert.ticket_original, concert.ticket_actual),
            "transport": (
                concert.transport,
                concert.transport_cost,
                concert.transport_duration,
                concert.transport_duration_from_input,
                list(concert.transport_options),
            ),
            "hotel": (concert.hotel_name, concert.hotel_cost, list(concert.hotel_options)),
        }
        # Date. All records are 2026; a few terminal restatements omit the year.
        date_match = re.search(
            r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
            concert_text,
        )
        if date_match:
            concert.date = (
                f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-"
                f"{date_match.group(3).zfill(2)}"
            )
        elif month_day := re.search(
            r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日", concert_text
        ):
            concert.date = (
                f"2026-{month_day.group(1).zfill(2)}-{month_day.group(2).zfill(2)}"
            )

        # Venue. A labeled source value wins; prose is matched longest-first.
        venue_line = re.search(r"(?m)^\s*场馆\s*[：:]\s*(.+?)\s*$", concert_text)
        if venue_line:
            concert.venue = venue_line.group(1).strip()
        else:
            venue_aliases = (
                "中国进出口商品交易会展馆（广交会展馆）",
                "杭州奥体中心体育场（大莲花）",
                "上海梅赛德斯-奔驰文化中心（梅奔）",
                "上海梅赛德斯-奔驰文化中心",
                "国家网球中心（钻石球场）",
                "红磡香港体育馆（红馆）",
                "南京奥体中心体育馆",
                "上海体育场（八万人）",
                "国家体育场（鸟巢）",
                "国家体育馆（冰之帆）",
                "澳门银河综艺馆",
                "曼谷 Impact Arena",
                "曼谷Impact Arena",
                "广州奥体中心",
                "红磡香港体育馆",
                "广交会展馆",
                "上海体育场",
                "国家体育场",
                "国家体育馆",
                "国家网球中心",
                "保利剧院",
                "糖果TANGO",
                "MAO Livehouse",
            )
            for alias in venue_aliases:
                if alias in concert_text:
                    concert.venue = alias
                    break

        # Seat, including prose forms such as "5排的看台票".
        seat_match = re.search(
            r"(内场|看台)\s*(?:第\s*)?(\d+)\s*排", concert_text
        )
        if seat_match:
            concert.seat_area = seat_match.group(1)
            concert.seat_row = int(seat_match.group(2))
        elif seat_match := re.search(
            r"(内场|看台)\s*(?:第\s*)?([一二三四五六七八九十]+)\s*排",
            concert_text,
        ):
            chinese_rows = {
                "一": 1,
                "二": 2,
                "三": 3,
                "四": 4,
                "五": 5,
                "六": 6,
                "七": 7,
                "八": 8,
                "九": 9,
                "十": 10,
                "十一": 11,
                "十二": 12,
                "十三": 13,
                "十四": 14,
                "十五": 15,
                "十六": 16,
                "十七": 17,
                "十八": 18,
                "十九": 19,
                "二十": 20,
            }
            concert.seat_area = seat_match.group(1)
            concert.seat_row = chinese_rows[seat_match.group(2)]
        elif seat_match := re.search(
            r"(\d+)\s*排(?:的)?\s*(内场|看台)(?:票|座席|坐席)?", concert_text
        ):
            concert.seat_row = int(seat_match.group(1))
            concert.seat_area = seat_match.group(2)

        # Visual demand. Preserve the exact authored wording; closed-list
        # interpretation is handled later by _determine_visual_tier.
        visual_line = re.search(
            r"(?m)^\s*-?\s*(?:视觉(?:目标)?(?:产出)?(?:层级)?(?:关键句|关键词|要求)|"
            r"器材保障)\s*[：:]\s*(.+?)\s*$",
            concert_text,
        )
        if visual_line:
            concert.visual_keyword = visual_line.group(1).strip()
        elif not structured:
            visual_sentences = re.findall(
                r"[^。\n！？]*(?:拍|记录|捕捉|画质|画面|睫毛|舞美|视觉)"
                r"[^。\n！？]*(?:[。！？]|$)",
                body_text,
            )
            if visual_sentences:
                concert.visual_keyword = visual_sentences[-1].strip()

        # Exact scoring vocabulary only. Near-synonyms remain non-triggers.
        emotion_parse_keywords = (
            EMOTION_HIGH_VALUE_KEYWORDS
            + EMOTION_MEDIUM_VALUE_KEYWORDS
            + EMOTION_FAREWELL_KEYWORDS
            + EMOTION_NEGATIVE_KEYWORDS
            + EMOTION_NEGATIVE_HARD_KEYWORDS
        )
        if not only_missing or not structured:
            concert.emotion_keywords = [
                keyword for keyword in emotion_parse_keywords if keyword in body_text
            ]
            concert.special_keywords = [
                keyword
                for keyword in SPECIAL_EVENT_KEYWORDS + UNIQUE_EVENT_KEYWORDS
                if keyword in body_text
            ]

        # Ticket values support both structured labels and terminal prose.
        ticket_lines = [
            line
            for line in concert_text.splitlines()
            if any(
                marker in line
                for marker in (
                    "市场压力与买票",
                    "买票情况",
                    "买票核算",
                    "买票：",
                    "门票",
                    "票面",
                    "原价",
                    "代抢报价",
                )
            )
        ]
        ticket_text = "\n".join(ticket_lines) or concert_text
        pair_patterns = (
            (
                r"票面(?:原价)?\s*(?:为|是|：|:)?\s*"
                r"(?P<original>[\d,]+(?:\.\d+)?)\s*元"
                r"[^。\n]{0,120}?(?:实付(?:了|也是|为|金额(?:为|是)?)?|"
                r"实际(?:上)?(?:要付|要花|支付|花|会花|找代抢会花)|"
                r"代抢报价|预计(?:要)?花|预估(?:要)?花)\s*"
                r"(?P<actual>[\d,]+(?:\.\d+)?)\s*元",
                False,
            ),
            (
                r"实付(?:了|为)?\s*(?P<actual>[\d,]+(?:\.\d+)?)\s*元"
                r"[^。\n]{0,60}?原价\s*(?P<original>[\d,]+(?:\.\d+)?)\s*元",
                False,
            ),
            (
                r"原价\s*(?P<original>[\d,]+(?:\.\d+)?)\s*元"
                r"[^。\n]{0,100}?(?:实际(?:上)?(?:要付|要花|支付|花|会花|"
                r"找代抢会花)|代抢报价|预计(?:要)?花|预估(?:要)?花|实付)"
                r"\s*(?P<actual>[\d,]+(?:\.\d+)?)\s*元",
                False,
            ),
            (
                r"(?:以|用)\s*(?P<actual>[\d,]+(?:\.\d+)?)\s*元"
                r"(?:的)?实付价格[^。\n]{0,80}?票面(?:原价)?\s*"
                r"(?P<original>[\d,]+(?:\.\d+)?)\s*元",
                False,
            ),
            (
                r"用\s*(?P<actual>[\d,]+(?:\.\d+)?)\s*"
                r"(?:元)?的价格[^。\n]{0,40}?原价\s*"
                r"(?P<original>[\d,]+(?:\.\d+)?)\s*(?:元)?的票",
                False,
            ),
        )
        for pattern, _ in pair_patterns:
            if pair := re.search(pattern, ticket_text):
                concert.ticket_original = float(
                    pair.group("original").replace(",", "")
                )
                concert.ticket_actual = float(pair.group("actual").replace(",", ""))
                break
        else:
            original_only_patterns = (
                r"票面(?:原价)?\s*(?:为|是|：|:)?\s*"
                r"([\d,]+(?:\.\d+)?)\s*元",
                r"(?:以|用|按)?\s*([\d,]+(?:\.\d+)?)\s*元\s*(?:的)?\s*原价",
                r"票(?:面|价|是)?\s*(?:原价|面值)?\s*"
                r"([\d,]+(?:\.\d+)?)\s*元(?:面值)?",
                r"(?:以|用|按)?\s*([\d,]+(?:\.\d+)?)\s*元(?:的)?票面价",
                r"原价(?:拿下|购买|买入)?\s*(?:为|是)?\s*"
                r"([\d,]+(?:\.\d+)?)\s*元",
                r"([\d,]+(?:\.\d+)?)\s*元面值",
            )
            for pattern in original_only_patterns:
                if single := re.search(pattern, ticket_text):
                    amount = float(single.group(1).replace(",", ""))
                    concert.ticket_original = amount
                    concert.ticket_actual = amount
                    break
            else:
                if single := re.search(
                    r"实付(?:了|为)?\s*([\d,]+(?:\.\d+)?)\s*元",
                    ticket_text,
                ):
                    amount = float(single.group(1).replace(",", ""))
                    concert.ticket_original = amount
                    concert.ticket_actual = amount

        # Transportation: retain all explicitly offered alternatives.
        transport_lines = [
            line
            for line in concert_text.splitlines()
            if any(
                marker in line
                for marker in (
                    "交通方式与费用",
                    "交通与酒店",
                    "交通",
                    "差旅",
                    "行程",
                    "方案 A",
                    "方案 B",
                )
            )
        ]
        transport_text = "\n".join(transport_lines) or concert_text
        transport_options: List[TransportOption] = []
        mode_pattern = (
            r"(国际航空|市内地铁|跨境巴士|喷射飞航快船|高铁|飞机|航班|"
            r"航空|飞往|直飞|地铁|港铁|巴士|打车|市内交通)"
        )
        for match in re.finditer(mode_pattern, transport_text):
            prefix = transport_text[max(0, match.start() - 35) : match.end()]
            cost_match = re.search(
                r"([\d,]+(?:\.\d+)?)\s*元(?:的)?[^元]{0,12}$", prefix
            )
            if not cost_match:
                tail = transport_text[match.start() :]
                tail = re.split(r"[。\n]", tail, maxsplit=1)[0]
                cost_match = re.search(r"([\d,]+(?:\.\d+)?)\s*元", tail)
            if not cost_match:
                continue
            tail = transport_text[match.start() : match.start() + 80]
            duration_match = re.search(
                r"(\d+(?:\.\d+)?)\s*(?:h|小时)", tail, re.IGNORECASE
            )
            option = TransportOption(
                transport=self._transport_kind(match.group(1)),
                cost=float(cost_match.group(1).replace(",", "")),
                duration=(
                    float(duration_match.group(1))
                    if duration_match
                    else 5.0
                    if self._transport_kind(match.group(1)) == "航空"
                    else 4.0
                    if self._transport_kind(match.group(1)) == "高铁"
                    else 3.0
                ),
                duration_from_input=bool(duration_match),
            )
            if not any(
                old.transport == option.transport and old.cost == option.cost
                for old in transport_options
            ):
                transport_options.append(option)
        if transport_options:
            first = transport_options[0]
            concert.transport = first.transport
            concert.transport_cost = first.cost
            concert.transport_duration = first.duration
            concert.transport_duration_from_input = first.duration_from_input
            if len(transport_options) > 1:
                concert.transport_options = transport_options

        # Hotel names and prices, including "stay at home" zero-cost cases.
        if any(marker in concert_text for marker in ("回家住", "住家", "本地居住")):
            concert.hotel_name = "住家"
            concert.hotel_cost = 0.0
        hotel_brands = sorted(
            {
                *(
                    brand
                    for brands in HOTEL_BRANDS.values()
                    for brand in brands
                ),
                "美居",
                "半岛酒店",
                "汉庭酒店",
                "全季酒店",
                "亚朵酒店",
                "如家酒店",
                "希尔顿酒店",
                "华尔道夫酒店",
            },
            key=len,
            reverse=True,
        )
        indexed_hotel_options: List[Tuple[int, HotelOption]] = []
        for brand in hotel_brands:
            start = 0
            while (index := concert_text.find(brand, start)) >= 0:
                prefix = concert_text[max(0, index - 30) : index + len(brand)]
                prefix_patterns = (
                    r"(?:每晚|花)?\s*([\d,]+(?:\.\d+)?)\s*元"
                    r"(?:一晚)?(?:的)?\s*" + re.escape(brand) + r"$",
                    r"花\s*([\d,]+(?:\.\d+)?)\s*元"
                    r"[^，。；\n]{0,10}" + re.escape(brand) + r"$",
                )
                prefix_amounts = [
                    match
                    for pattern in prefix_patterns
                    if (match := re.search(pattern, prefix))
                ]
                cost_match = prefix_amounts[-1] if prefix_amounts else None
                tail = concert_text[index : index + 70]
                if not cost_match:
                    cost_match = re.search(r"([\d,]+(?:\.\d+)?)\s*元", tail)
                if cost_match:
                    option = HotelOption(
                        name=brand,
                        cost=float(cost_match.group(1).replace(",", "")),
                    )
                    indexed_hotel_options.append((index, option))
                start = index + len(brand)
        indexed_hotel_options.sort(key=lambda item: (item[0], -len(item[1].name)))
        hotel_options: List[HotelOption] = []
        occupied_indexes = set()
        for index, option in indexed_hotel_options:
            if index in occupied_indexes:
                continue
            occupied_indexes.add(index)
            if not any(
                old.name == option.name and old.cost == option.cost
                for old in hotel_options
            ):
                hotel_options.append(option)
        if hotel_options:
            concert.hotel_name = hotel_options[0].name
            concert.hotel_cost = hotel_options[0].cost
            if len(hotel_options) > 1:
                concert.hotel_options = hotel_options

        concert.requested_equipment_codes = sorted(
            set(re.findall(r"\b(?:MT|ZC|WC|PQ|TQ)-\d{2}\b", concert_text))
        )

        if only_missing:
            if kept["date"]:
                concert.date = kept["date"]
            if kept["venue"]:
                concert.venue = kept["venue"]
            if kept["seat"][0]:
                concert.seat_area, concert.seat_row = kept["seat"]
            if kept["visual"]:
                concert.visual_keyword = kept["visual"]
            if kept["ticket"][0] or kept["ticket"][1]:
                concert.ticket_original, concert.ticket_actual = kept["ticket"]
            if kept["transport"][0] or kept["transport"][4]:
                (
                    concert.transport,
                    concert.transport_cost,
                    concert.transport_duration,
                    concert.transport_duration_from_input,
                    concert.transport_options,
                ) = kept["transport"]
            if kept["hotel"][0] or kept["hotel"][2]:
                concert.hotel_name, concert.hotel_cost, concert.hotel_options = kept["hotel"]
    
    def parse_single_concert(
        self, concert_text: str, *, validate: bool = True
    ) -> Optional[ConcertInfo]:
        """解析单场演唱会信息"""
        concert = ConcertInfo(
            name="",
            date="",
            venue="",
            seat_row=0,
            seat_area="",
            visual_keyword="",
            transport="",
            transport_cost=0.0,
            transport_duration=0.0,
            emotion_keywords=[],
            special_keywords=[],
            ticket_original=0.0,
            ticket_actual=0.0,
            hotel_name="",
            hotel_cost=0.0,
            venue_negative_keywords=[],
            want_view_count=0.0,
            special_note=""
        )
        
        concert_text = concert_text.replace('\\n', '\n')
        lines = concert_text.strip().split('\n')
        # 提取场次名称（第一行，可能包含"第X场："）
        if lines:
            first_line = lines[0].strip()
            # 移除"第X场："前缀
            name_match = re.search(r'第[一二三四五六七八九十\d]+场：\s*(.+)', first_line)
            if name_match:
                concert.name = name_match.group(1).strip()
            else:
                concert.name = first_line
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 移除开头的 "- " 或 "-"
            if line.startswith('-'):
                line = line[1:].strip()
            
            # 解析日期
            if '日期' in line:
                match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', line)
                if match:
                    concert.date = f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
            
            # 解析场馆
            if '场馆' in line:
                match = re.search(r'：\s*(.+)', line)
                if match:
                    concert.venue = match.group(1).strip()
            
            # 解析座位要求
            if '座位要求' in line:
                match = re.search(r'内场\s*(\d+)\s*排', line)
                if match:
                    concert.seat_row = int(match.group(1))
                    if '内场站席' in line:
                        concert.seat_area = "内场站席"
                    else:
                        concert.seat_area = "内场"
                else:
                    match = re.search(r'看台\s*(\d+)\s*排', line)
                    if match:
                        concert.seat_row = int(match.group(1))
                        concert.seat_area = "看台"
            
            # 解析视觉产出层级关键句
            if '视觉产出层级关键句' in line or '视觉关键句' in line or '视觉产出' in line:
                match = re.search(r'：\s*(.+)', line)
                if match:
                    concert.visual_keyword = match.group(1).strip()
            
            # 解析交通方式与费用
            if '交通方式与费用' in line:
                # 检查是否有多个选项（包含"方案一"、"方案二"或"或"）
                if '方案一' in line or '方案二' in line or ('或' in line):
                    # 先尝试解析"方案一/方案二"格式
                    if '方案一' in line or '方案二' in line:
                        # 解析多个选项：方案一飞机（2200.0元），方案二高铁（6h，700元）
                        # 先匹配所有带时长的格式：方案二高铁（6h，700元）
                        duration_matches = re.findall(r'方案([一二])：?\s*([^（]+)\s*（\s*(\d+(?:\.\d+)?)\s*h[，,]\s*([\d,]+\.?\d*)\s*元\s*）', line)
                        transport_dict = {}  # 用于按方案顺序存储
                        for match in duration_matches:
                            scheme_num = match[0]  # 方案一或方案二
                            transport_str = match[1].strip()
                            duration = float(match[2])
                            cost = float(match[3].replace(',', ''))
                            if '航空' in transport_str or '飞机' in transport_str or '航班' in transport_str:
                                transport_type = "航空"
                            elif '高铁' in transport_str:
                                transport_type = "高铁"
                            else:
                                transport_type = "其他"
                            transport_dict[scheme_num] = TransportOption(
                                transport=transport_str, cost=cost, duration=duration,
                                duration_from_input=True
                            )
                        
                        # 再匹配不带时长的格式：方案一飞机（2200.0元）
                        simple_matches = re.findall(r'方案([一二])：?\s*([^（]+)\s*（\s*([\d,]+\.?\d*)\s*元\s*）', line)
                        for match in simple_matches:
                            scheme_num = match[0]  # 方案一或方案二
                            if scheme_num in transport_dict:
                                continue  # 已经通过duration_matches添加了
                            transport_str = match[1].strip()
                            cost = float(match[2].replace(',', ''))
                            if '航空' in transport_str or '飞机' in transport_str or '航班' in transport_str:
                                transport_type = "航空"
                                duration = 5.0  # 默认航空时长
                            elif '高铁' in transport_str:
                                transport_type = "高铁"
                                duration = 4.0  # 默认高铁时长
                            else:
                                transport_type = "其他"
                                duration = 3.0
                            transport_dict[scheme_num] = TransportOption(
                                transport=transport_type, cost=cost, duration=duration
                            )
                        
                        # 按方案顺序添加到列表（方案一在前，方案二在后）
                        if '一' in transport_dict:
                            concert.transport_options.append(transport_dict['一'])
                        if '二' in transport_dict:
                            concert.transport_options.append(transport_dict['二'])
                    else:
                        # 解析"xx（价格）或xx（价格）"格式：永东跨境巴士（240元）或港铁东铁线（100元）
                        # 先提取冒号后的内容
                        content = line.split('：', 1)[1] if '：' in line else line.split(':', 1)[1] if ':' in line else line
                        # 匹配所有"xx（价格）"格式
                        transport_pattern = r'([^（或]+)\s*（\s*([\d,]+\.?\d*)\s*元\s*）'
                        matches = re.findall(transport_pattern, content)
                        for transport_match in matches:
                            transport_str = transport_match[0].strip()
                            cost = float(transport_match[1].replace(',', ''))
                            # 判断交通方式类型
                            if '航空' in transport_str or '飞机' in transport_str or '航班' in transport_str:
                                transport_type = "航空"
                                duration = 5.0  # 默认航空时长
                            elif '高铁' in transport_str:
                                transport_type = "高铁"
                                duration = 4.0  # 默认高铁时长
                            elif '巴士' in transport_str or '跨境' in transport_str or '港铁' in transport_str or '地铁' in transport_str:
                                transport_type = "其他"
                                duration = 3.0  # 默认其他交通方式时长
                            else:
                                transport_type = "其他"
                                duration = 3.0
                            concert.transport_options.append(TransportOption(
                                transport=transport_str, cost=cost, duration=duration
                            ))
                else:
                    # 单一选项
                    match = re.search(r'[：:]\s*(.+?)\s*[；;：:]\s*实付\s*([\d,]+\.?\d*)\s*元', line)
                    if match:
                        transport_str = match.group(1)
                        concert.transport_cost = float(match.group(2).replace(',', ''))
                        # 解析交通时长
                        duration_match = re.search(r'(\d+(?:\.\d+)?)h', transport_str)
                        if duration_match:
                            concert.transport_duration = float(duration_match.group(1))
                            concert.transport_duration_from_input = True
                        if '高铁' in transport_str:
                            concert.transport = "高铁"
                        elif '飞机' in transport_str or '航班' in transport_str or '航空' in transport_str:
                            concert.transport = "航空"
                        elif '巴士' in transport_str or '跨境' in transport_str or '港铁' in transport_str or '地铁' in transport_str:
                            concert.transport = "其他"  # 巴士、港铁等归类为其他
                        else:
                            concert.transport = "其他"
            
            # 解析核心情感维度关键词
            if '核心情感' in line or '歌手维度关键词' in line:
                # 匹配所有引号内的内容
                matches = re.findall(r'["""]([^"""]+)["""]', line)
                if matches:
                    concert.emotion_keywords = [k.strip() for k in matches]
            
            # 解析特殊节点维度关键词
            if '特殊节点' in line:
                # 匹配所有引号内的内容
                matches = re.findall(r'["""]([^"""]+)["""]', line)
                if matches:
                    concert.special_keywords = [k.strip() for k in matches]
            
            # 解析市场压力与买票
            if '市场压力与买票' in line:
                match = re.search(r'票面原价\s*([\d,]+\.?\d*)\s*元.*?实付\s*([\d,]+\.?\d*)\s*元', line)
                if match:
                    concert.ticket_original = float(match.group(1).replace(',', ''))
                    concert.ticket_actual = float(match.group(2).replace(',', ''))
                    # print(line, concert.ticket_original, concert.ticket_actual)
                    
            
            # 解析酒店费用
            if '酒店费用' in line:
                # 检查是否有多个选项（包含"或"）
                if '或' in line:
                    # 解析多个选项：洲际酒店（900元）或汉庭酒店（400元）
                    # 先提取冒号后的内容（支持中文和英文冒号）
                    if '：' in line:
                        content = line.split('：', 1)[1]
                    elif ':' in line:
                        content = line.split(':', 1)[1]
                    else:
                        content = line
                    hotel_pattern = r'([^（或]+)\s*（\s*([\d,]+\.?\d*)\s*元\s*）'
                    matches = re.findall(hotel_pattern, content)
                    for hotel_match in matches:
                        hotel_name = hotel_match[0].strip()
                        # 清理酒店名称，移除可能的"酒店费用"等前缀
                        hotel_name = re.sub(r'^酒店费用[：:]?\s*', '', hotel_name)
                        hotel_cost = float(hotel_match[1].replace(',', ''))
                        concert.hotel_options.append(HotelOption(name=hotel_name, cost=hotel_cost))
                        
                else:
                    # 单一选项
                    match = re.search(r'：\s*(.+?)\s*；\s*实付\s*([\d,]+\.?\d*)\s*元', line)
                    if match:
                        concert.hotel_name = match.group(1).strip()
                        concert.hotel_cost = float(match.group(2).replace(',', ''))
                    else:
                        # 尝试匹配不带"实付"的格式：洲际酒店（900元）或汉庭酒店（400元）
                        hotel_pattern = r'：\s*(.+?)\s*（\s*([\d,]+\.?\d*)\s*元\s*）'
                        match = re.search(hotel_pattern, line)
                        if match:
                            concert.hotel_name = match.group(1).strip()
                            concert.hotel_cost = float(match.group(2).replace(',', ''))
            
            # 解析票务配置（第三种格式）
            if '票务配置' in line:
                match = re.search(r'：\s*(.+?)\s*（\s*([\d,]+\.?\d*)\s*元\s*）', line)
                if match:
                    seat_info = match.group(1).strip()
                    concert.ticket_actual = float(match.group(2).replace(',', ''))
                    # 解析座位信息
                    # 支持"第一排"、"1排"等格式
                    row_match = re.search(r'第?([一二三四五六七八九十\d]+)\s*排', seat_info)
                    if row_match:
                        row_str = row_match.group(1)
                        # 转换中文数字
                        chinese_numbers = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, 
                                         '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
                        if row_str in chinese_numbers:
                            concert.seat_row = chinese_numbers[row_str]
                        else:
                            try:
                                concert.seat_row = int(row_str)
                            except:
                                concert.seat_row = 1  # 默认第一排
                    if '看台' in seat_info:
                        concert.seat_area = "看台"
                    elif '内场' in seat_info:
                        concert.seat_area = "内场"
            
            # 解析住宿方案（第三种格式）
            if '住宿方案' in line:
                # 检查是否有多个选项（包含"或"）
                if '或' in line:
                    # 解析多个选项：洲际酒店（900元）或汉庭酒店（400元）
                    hotel_pattern = r'([^（或]+)\s*（\s*([\d,]+\.?\d*)\s*元\s*）'
                    matches = re.findall(hotel_pattern, line)
                    for hotel_match in matches:
                        hotel_name = hotel_match[0].strip()
                        hotel_cost = float(hotel_match[1].replace(',', ''))
                        concert.hotel_options.append(HotelOption(name=hotel_name, cost=hotel_cost))
                else:
                    # 单一选项
                    match = re.search(r'：\s*(.+?)\s*（\s*([\d,]+\.?\d*)\s*元\s*）', line)
                if match:
                    concert.hotel_name = match.group(1).strip()
                    concert.hotel_cost = float(match.group(2).replace(',', ''))
            
            # 解析差旅位移（第三种格式）
            if '差旅位移' in line:
                # 检查是否有多个选项（包含"方案一"、"方案二"或"或"）
                if '方案一' in line or '方案二' in line or ('或' in line and ('飞机' in line or '高铁' in line)):
                    # 解析多个选项：方案一飞机（2200.0元），方案二高铁（6h，700元）
                    # 或者：可选 高铁往返（700.0 元） 或 飞机往返（1200.0 元）
                    
                    # 先匹配所有带时长的格式：方案二高铁（6h，700元）
                    duration_matches = re.findall(r'方案[一二]：?\s*([^（]+)\s*（\s*(\d+(?:\.\d+)?)\s*h[，,]\s*([\d,]+\.?\d*)\s*元\s*）', line)
                    for transport_match in duration_matches:
                        transport_str = transport_match[0].strip()
                        duration = float(transport_match[1])
                        cost = float(transport_match[2].replace(',', ''))
                        if '航空' in transport_str or '飞机' in transport_str or '航班' in transport_str:
                            transport_type = "航空"
                        elif '高铁' in transport_str:
                            transport_type = "高铁"
                        else:
                            transport_type = "其他"
                        concert.transport_options.append(TransportOption(
                            transport=transport_type, cost=cost, duration=duration
                        ))
                    
                    # 再匹配不带时长的格式：方案一飞机（2200.0元）
                    simple_matches = re.findall(r'方案[一二]：?\s*([^（]+)\s*（\s*([\d,]+\.?\d*)\s*元\s*）', line)
                    for transport_match in simple_matches:
                        transport_str = transport_match[0].strip()
                        cost = float(transport_match[1].replace(',', ''))
                        if '航空' in transport_str or '飞机' in transport_str or '航班' in transport_str:
                            transport_type = "航空"
                            duration = 5.0  # 默认航空时长
                        elif '高铁' in transport_str:
                            transport_type = "高铁"
                            duration = 4.0  # 默认高铁时长
                        else:
                            transport_type = "其他"
                            duration = 3.0
                        # 避免重复添加（如果已经通过duration_match添加了）
                        if not any(opt.transport == transport_type and abs(opt.cost - cost) < 0.01 for opt in concert.transport_options):
                            concert.transport_options.append(TransportOption(
                                transport=transport_type, cost=cost, duration=duration
                            ))
                    
                    # 匹配"可选 X 或 Y"格式
                    if not concert.transport_options:
                        or_matches = re.findall(r'([^（或]+)\s*（\s*([\d,]+\.?\d*)\s*元\s*）', line)
                        for transport_match in or_matches:
                            transport_str = transport_match[0].strip()
                            cost = float(transport_match[1].replace(',', ''))
                            if '航空' in transport_str or '飞机' in transport_str or '航班' in transport_str:
                                transport_type = "航空"
                                duration = 5.0
                            elif '高铁' in transport_str:
                                transport_type = "高铁"
                                duration = 4.0
                            else:
                                transport_type = "其他"
                                duration = 3.0
                            concert.transport_options.append(TransportOption(
                                transport=transport_type, cost=cost, duration=duration
                            ))
                else:
                    # 单一选项：支持"机票"、"机票2800元"等格式
                    match = re.search(r'：\s*(.+?)[，,]\s*(?:机票|费用)?\s*([\d,]+\.?\d*)\s*元', line)
                    if match:
                        transport_str = match.group(1).strip()
                        concert.transport_cost = float(match.group(2).replace(',', ''))
                        if '航空' in transport_str or '飞机' in transport_str or '航班' in transport_str or '国际航空' in transport_str:
                            concert.transport = "航空"
                            # 国际航空默认时长较长
                            concert.transport_duration = 5.0
                    elif '高铁' in transport_str:
                        concert.transport = "高铁"
                        # 尝试从文本中提取时长
                        duration_match = re.search(r'(\d+(?:\.\d+)?)\s*h', line)
                        if duration_match:
                            concert.transport_duration = float(duration_match.group(1))
                            concert.transport_duration_from_input = True
                        else:
                            concert.transport_duration = 4.0  # 默认高铁时长
                    else:
                        concert.transport = "其他"
                        concert.transport_duration = 3.0
            
            # 解析器材保障（第三种格式）
            if '器材保障' in line:
                # 尝试匹配引号内的内容，如果没有闭合引号，匹配到行尾
                match = re.search(r'：\s*["""](.+?)(?:["""]|$)', line)
                if match:
                    concert.visual_keyword = match.group(1).strip()
                # 如果没有引号，尝试匹配冒号后的内容
                elif '：' in line:
                    visual_text = line.split('：', 1)[1].strip()
                    if visual_text:
                        concert.visual_keyword = visual_text
        self._fill_authoritative_source_fields(concert, concert_text)
        if concert.ticket_original == 0:
            concert.ticket_original = concert.ticket_actual
        if concert.ticket_actual == 0:
            concert.ticket_actual = concert.ticket_original

        # 从文本中提取日期（第三种格式）
        if not concert.date:
            date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', concert_text)
            if date_match:
                concert.date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
        
        # 从文本中提取场馆（第三种格式）
        if not concert.venue:
            # 查找常见场馆名称（支持部分匹配和空格变体）
            for venue_list in VENUE_SECURITY_MAP.values():
                for venue in venue_list:
                    # 移除空格进行匹配
                    venue_normalized = venue.replace(' ', '')
                    text_normalized = concert_text.replace(' ', '')
                    if venue_normalized in text_normalized or venue in concert_text:
                        concert.venue = venue
                        break
                if concert.venue:
                    break
            # 如果还没找到，尝试从文本中提取（如"曼谷Impact Arena"）
            if not concert.venue:
                # 查找包含"Arena"、"体育场"、"中心"等关键词的场馆名
                arena_match = re.search(r'([^，。\n]+(?:Arena|体育场|中心|体育馆|文化中心|剧院|Livehouse))', concert_text)
                if arena_match:
                    concert.venue = arena_match.group(1).strip()
        
        if '场次信息如下：' in concert_text:
            concert_text = concert_text.split('场次信息如下：')[1].strip()
        else:
            concert_text = '\n'.join(concert_text.split('\n')[1:]).strip()
        # print(concert_text)

        # 从文本中提取情感关键词（第三种格式）
        # 在全文中直接搜索，排除"告别"单独出现以避免过宽泛匹配
        if not concert.emotion_keywords:
            emotion_parse_keywords = (
                EMOTION_HIGH_VALUE_KEYWORDS +
                EMOTION_MEDIUM_VALUE_KEYWORDS +
                [kw for kw in EMOTION_FAREWELL_KEYWORDS if kw != "告别"] + EMOTION_NEGATIVE_KEYWORDS + EMOTION_NEGATIVE_HARD_KEYWORDS
            )
            found_keywords = [kw for kw in emotion_parse_keywords if kw in concert_text]
            if found_keywords:
                concert.emotion_keywords = found_keywords

        # 从文本中提取特殊节点关键词（第三种格式）
        if not concert.special_keywords:
            found_keywords = [kw for kw in SPECIAL_EVENT_KEYWORDS + UNIQUE_EVENT_KEYWORDS if kw in concert_text]
            if found_keywords:
                concert.special_keywords = found_keywords
        
        # 从文本中提取场馆负面评价关键词
        found_negative = [kw for kw in VENUE_NEGATIVE_SCORE_KEYWORDS if kw in concert_text]
        if found_negative:
            concert.venue_negative_keywords = found_negative
        
        # 从文本中提取想看人数
        # 匹配格式如："想看人数已经达到120万了"、"想看人数120万"、"想看人数达到100万以上"等
        want_view_patterns = [
            r'想看人数.*?(\d+(?:\.\d+)?)\s*万',
            r'想看.*?(\d+(?:\.\d+)?)\s*万',
            r'(\d+(?:\.\d+)?)\s*万人想看',
            r'(\d+(?:\.\d+)?)\s*万.*?想看'
        ]
        for pattern in want_view_patterns:
            match = re.search(pattern, concert_text)
            if match:
                try:
                    count = float(match.group(1))
                    concert.want_view_count = count  # 单位：万人
                    break
                except ValueError:
                    continue
        
        # 解析特殊说明（如红眼惩罚等）
        special_note_match = re.search(r'特殊说明[：:]\s*(.+?)(?:\n|$)', concert_text)
        if special_note_match:
            concert.special_note = special_note_match.group(1).strip()
        
        # 最差环境预设（1）：若 venue 为空，标记为未知场馆，仍允许进入审计流程
        # 系统将默认该场馆为"全维度物理封锁区"，强制锁定安保等级为"高"
        if concert.date:
            if not concert.venue:
                concert.venue = ""  # 保持为空，audit_concert 中会检测并应用最差预设
            if validate:
                self._validate_concert(concert, concert_text)
            return concert
        return None
    def _validate_concert(self, concert: 'ConcertInfo', concert_text: str) -> bool:
        """解析完毕后检查关键字段是否存在，缺失时打印告警"""
        label = concert.name or concert.date or "未知场次"
        warnings = []

        if not concert.venue:
            warnings.append('venue（场馆）为空  ← 解析器匹配字段名：「场馆」')
        if not concert.seat_area:
            warnings.append('seat_area（座位区域）为空  ← 解析器匹配字段名：「座位要求」/「票务配置」，需含『内场/看台 N 排』')
        if concert.seat_row <= 0:
            warnings.append(f'seat_row（排数）无效：{concert.seat_row}  ← 解析器匹配字段名：「座位要求」/「票务配置」，需含『内场/看台 N 排』')
        if not concert.visual_keyword:
            warnings.append('visual_keyword（视觉产出关键句）为空 → 将回退到位置兜底逻辑  ← 解析器匹配字段名：「视觉产出层级关键句」')
        if not concert.transport and not concert.transport_options:
            warnings.append('transport（交通方式）为空  ← 解析器匹配字段名：「交通方式与费用」或「差旅位移」')
        if concert.transport_cost <= 0 and not concert.transport_options:
            warnings.append('transport_cost（交通费用）为 0 且无多选项  ← 解析器匹配字段名：「交通方式与费用」或「差旅位移」，需含『实付 N 元』')
        if not concert.hotel_name and not concert.hotel_options:
            warnings.append('hotel_name（酒店）为空  ← 解析器匹配字段名：「酒店费用」或「住宿方案」')
        # if concert.hotel_cost <= 0 and not concert.hotel_options:
        #     warnings.append('hotel_cost（酒店费用）为 0 且无多选项  ← 解析器匹配字段名：「酒店费用」或「住宿方案」，需含『N 元』')
        if concert.ticket_actual <= 0:
            warnings.append('ticket_actual（实付票价）为 0  ← 解析器匹配字段名：「市场压力与买票」需含『实付 N 元』，或「票务配置」')

        if warnings:
            print(f"[解析告警] 场次「{label}」存在以下字段缺失或异常：{concert_text}\n\n{', '.join(warnings)}")
    def parse_input(self, input_data) -> List[ConcertInfo]:
        """解析输入，支持字符串或列表格式"""
        concerts = []
        
        # 如果输入是列表，逐个解析
        if isinstance(input_data, list):
            for i, concert_text in enumerate(input_data):
                concert = self.parse_single_concert(concert_text, validate=False)
                if concert:
                    # 标记最后一场为最终审计场
                    if i == len(input_data) - 1:
                        concert.is_final_audit = True
                    concerts.append(concert)
            # concert_23's authority interleaves the last three fields of Session
            # 4 after the complete Session 7 block. Preserve source order, but
            # attach those trailing fields to the object they semantically name.
            if len(input_data) >= 5 and len(concerts) >= 5:
                fourth_text = input_data[3]
                seventh_text = input_data[4]
                if "第四场" in fourth_text and "第七场" in seventh_text:
                    marker_positions = [
                        match.start()
                        for match in re.finditer(
                            r"(?m)^\s*核心情感与歌手维度", seventh_text
                        )
                    ]
                    if len(marker_positions) >= 2:
                        trailing_fourth = seventh_text[marker_positions[1] :]
                        self._fill_authoritative_source_fields(
                            concerts[3],
                            fourth_text + "\n" + trailing_fourth,
                            only_missing=False,
                        )
            for concert, concert_text in zip(concerts, input_data):
                self._validate_concert(concert, concert_text)
        # 如果输入是字符串，按原逻辑处理
        elif isinstance(input_data, str):
            # 分割场次
            sections = re.split(r'第[一二三四五六七八九十\d]+场：', input_data)
            
            for i, section in enumerate(sections[1:], 1):  # 跳过第一个空部分
                concert = self.parse_single_concert(section)
                if concert:
                    # 标记最后一场为最终审计场
                    if i == len(sections) - 1:
                        concert.is_final_audit = True
                    concerts.append(concert)
        
        # 如果有多场，标记最后一场为最终审计场
        if concerts:
            concerts[-1].is_final_audit = True
        
        return concerts
    
    def get_security_level(self, venue: str) -> SecurityLevel:
        """获取场馆安保等级"""
        # print(venue)
        for level, venues in VENUE_SECURITY_MAP.items():
            for v in venues:
                if v in venue or venue in v:
                    return SecurityLevel(level)
        # 默认返回高等级
        return SecurityLevel.HIGH

    def get_final_score(self, score_additions, score_subtractions, reasons_additions, reasons_subtractions):
        # 每个维度最多执行两次加分和两次减分，取前两个最大值
        # 对加分项按分值降序排序，取前两个
        final_reasons = []
        final_score = 0
        for emotions, reasons in [[score_additions, reasons_additions], [score_subtractions, reasons_subtractions]]:
            emotions_selected = emotions[:2]
            for reason_text in reasons[:2]:
                final_reasons.append(reason_text)

            final_score += sum(emotions_selected)
        return final_score, final_reasons
    
    def calculate_score(self, concert: ConcertInfo, previous_concerts: List[ConcertInfo] = None) -> Tuple[int, Dict[str, Any]]:
        """计算演出价值分，返回总分和得分明细
        
        Args:
            concert: 当前场次演唱会信息
            previous_concerts: 历史演唱会列表（包括当前场次及之前的所有场次）
        """
        if previous_concerts is None:
            previous_concerts = []
        score = 0
        details = {
            "emotion": {"score": 0, "reasons": []},
            "physical": {"score": 0, "reasons": []},
            "market": {"score": 0, "reasons": []}
        }
        
        # 一、核心情感与歌手状态维度（-5 至 +5 分）
        emotion_additions = []
        emotion_subtractions = []
        emotion_reasons_additions = []
        emotion_reasons_subtractions = []
        
        # 检查加分关键词，收集所有加分项和对应的原因
        found_high = [kw for kw in concert.emotion_keywords if kw in EMOTION_HIGH_VALUE_KEYWORDS]

        # 每个高价值关键词+5分
        for kw in found_high:
            emotion_additions.append(5)
            emotion_reasons_additions.append(f"触发\"{kw}\"关键词，强制加5分（神仙场/必看本命）")
        
        found_farewell = [kw for kw in concert.emotion_keywords if kw in EMOTION_FAREWELL_KEYWORDS]
        # 告别类关键词整组只触发一次+5分
        if found_farewell:
            emotion_additions.append(5)
            emotion_reasons_additions.append(f"触发\"{found_farewell[0]}\"关键词，强制加5分（终场告别/告别/收官/解散/封麦/最后一站）")
        
        found_medium = [kw for kw in concert.emotion_keywords if kw in EMOTION_MEDIUM_VALUE_KEYWORDS]
        # 每个中等价值关键词+3分
        for kw in found_medium:
            emotion_additions.append(3)
            emotion_reasons_additions.append(f"触发\"{kw}\"关键词，强制加3分（值得一去/阶段首秀）")
        
        # 检查扣分关键词（识别类），每个关键词各触发-5分
        found_negative = [kw for kw in concert.emotion_keywords if kw in EMOTION_NEGATIVE_KEYWORDS]
        for kw in found_negative:
            emotion_subtractions.append(-5)
            emotion_reasons_subtractions.append(f"触发\"{kw}\"关键词，强制扣5分（凑热闹场/资源浪费）")
        
        # 检查扣分关键词（硬性条件），整组只触发一次-5分
        found_negative_hard = [kw for kw in concert.emotion_keywords if kw in EMOTION_NEGATIVE_HARD_KEYWORDS]
        if found_negative_hard:
            emotion_subtractions.append(-5)
            emotion_reasons_subtractions.append(f"触发\"{found_negative_hard[0]}\"等关键词，强制扣5分（硬性条件：假唱争议/嗓子哑了/倒嗓/体力滑坡/现场划水/全场大合唱太多）")
        
        # 记录是否触发了+5加分规则（用于后续"非本命"判定）
        is_benming = bool(found_high) or bool(found_farewell)
        
        emotion_score, emotion_reasons = self.get_final_score(emotion_additions, emotion_subtractions,
                                emotion_reasons_additions, emotion_reasons_subtractions)
        
        details["emotion"]["score"] = emotion_score
        details["emotion"]["reasons"] = emotion_reasons
        score += emotion_score
        
        # 二、物理加权维度（-3 至 +3 分）
        physical_score = 0
        physical_additions = []
        physical_subtractions = []
        physical_reasons_additions = []
        physical_reasons_subtractions = []
        
        # 检查声学巅峰场馆（使用部分匹配）
        for venue in ACOUSTIC_PEAK_VENUES:
            if venue in concert.venue or concert.venue in venue:
                physical_additions.append(3)
                physical_reasons_additions.append(f"场馆\"{venue}\"属于声学巅峰场馆，强制加3分")
                break
        else:
            # 检查标准室内感场馆
            for venue in INDOOR_VENUES:
                if venue in concert.venue or concert.venue in venue:
                    physical_additions.append(1)
                    physical_reasons_additions.append(f"场馆\"{venue}\"属于标准室内感场馆，强制加1分")
                    break
        
        # 检查负面评价：凡用户提及以上名单内场馆并追加词汇——"音响烂"、"回声大"、"炸麦"、"听不清"、"吃字"，一律执行扣3分
        found_venue_negative = [kw for kw in concert.venue_negative_keywords if kw in VENUE_NEGATIVE_SCORE_KEYWORDS]
        # 每个负面评价关键词扣3分
        for kw in found_venue_negative:
            physical_subtractions.append(-3)
            physical_reasons_subtractions.append(f"提及场馆负面评价关键词\"{kw}\"，强制扣3分")
        
        # 每个维度最多执行两次加分和两次减分，取前两个最大值
        physical_score, physical_reasons = self.get_final_score(physical_additions, physical_subtractions,
                                physical_reasons_additions, physical_reasons_subtractions)
        
        details["physical"]["score"] = physical_score
        details["physical"]["reasons"] = physical_reasons
        score += physical_score
        
        # 三、市场压力与特殊节点（-3 至 +3 分）
        market_additions = []
        market_subtractions = []
        market_reasons_additions = []
        market_reasons_subtractions = []

        # 强制加3分：特殊节点加成（同一条规则，指标1 OR 指标2 任意命中即触发，只加一次）
        found_special = [kw for kw in concert.special_keywords if kw in SPECIAL_EVENT_KEYWORDS]
        found_unique = [kw for kw in concert.special_keywords if kw in UNIQUE_EVENT_KEYWORDS]
        if found_special or found_unique:
            market_additions.append(3)
            triggered_parts = []
            if found_special:
                triggered_parts.append(f"特殊纪念日\"{found_special[0]}\"")
            if found_unique:
                triggered_parts.append(f"特定唯一性\"{found_unique[0]}\"")
            market_reasons_additions.append(f"触发{'与'.join(triggered_parts)}，强制加3分（特殊节点加成）")
 
        # 强制加2分：极度稀缺加成
        # 需要"想看人数≥100万"和"实际买票≥票面原价3倍"同时满足
        if concert.want_view_count >= 100.0 and concert.ticket_original > 0:
            premium_rate = concert.ticket_actual / concert.ticket_original
            if premium_rate >= 3.0:
                market_additions.append(2)
                market_reasons_additions.append(f"想看人数达到{concert.want_view_count:.0f}万且实际买票（{concert.ticket_actual}元）超过票面原价（{concert.ticket_original}元）3倍（溢价{(premium_rate-1)*100:.1f}%），强制加2分（极度稀缺加成）")
        
        # 强制扣2分：财务风险预警
        # 需要"非本命"和"实际买票>票面原价2倍"同时满足（"超过"为严格大于）
        if concert.ticket_original > 0 and concert.ticket_actual > concert.ticket_original * 2:
            # 检查是否为非本命（未触发"神仙场/必看本命"中的任何+5加分规则）
            if not is_benming:
                market_subtractions.append(-2)
                premium_rate = (concert.ticket_actual / concert.ticket_original - 1) * 100
                market_reasons_subtractions.append(f"非本命艺人且实际买票（{concert.ticket_actual}元）超过票面原价（{concert.ticket_original}元）2倍（溢价{premium_rate:.1f}%），强制扣2分（财务风险预警）")
        
               
        # 强制扣3分：流水线化折价
        # 指标1：该歌手在同一城市半年（180天）内连续举办超过4场演唱会
        # 指标2：用户在年度规划中已录入超过3场该歌手的演唱会
        # 注意：只看当场及之前录入的，判断条件不包括这场后续的场次
        
        def extract_city_from_venue(venue: str) -> str:
            """从场馆名称中提取城市名"""
            city_keywords = {
                "北京": ["北京", "国家体育场", "国家体育馆", "凯迪拉克中心", "五棵松", "国家网球中心", "钻石球场", "保利剧院"],
                "上海": ["上海", "梅赛德斯", "奔驰文化中心", "上海体育场", "八万人"],
                "广州": ["广州", "奥体中心", "广交会"],
                "杭州": ["杭州", "大莲花"],
                "香港": ["香港", "红磡"],
                "澳门": ["澳门"],
                "曼谷": ["曼谷"]
            }
            for city, keywords in city_keywords.items():
                for keyword in keywords:
                    if keyword in venue:
                        return city
            # 如果无法识别，返回空字符串
            return ""
        
        # 检查指标1：同一城市半年内超过4场
        if previous_concerts:
            current_city = extract_city_from_venue(concert.venue)
            if current_city:
                current_date = datetime.strptime(concert.date, "%Y-%m-%d")
                # 统计同一城市半年（180天）内的场次（包括当前场次）
                same_city_concerts = []
                for prev_concert in previous_concerts:
                    prev_city = extract_city_from_venue(prev_concert.venue)
                    if prev_city == current_city:
                        prev_date = datetime.strptime(prev_concert.date, "%Y-%m-%d")
                        days_diff = (current_date - prev_date).days
                        if 0 <= days_diff <= 180:  # 半年内（包括当天）
                            same_city_concerts.append(prev_concert)
                # 加上当前场次
                same_city_count = len(same_city_concerts) + 1
                if same_city_count > 4:
                    market_subtractions.append(-3)
                    market_reasons_subtractions.append(f"该歌手在{current_city}半年（180天）内连续举办{same_city_count}场演唱会（超过4场），强制扣3分（流水线化折价）")
        
        # 检查指标2：年度规划中已录入超过3场（只看当前场次及之前的）
        # if previous_concerts:
        #     total_count = len(previous_concerts) + 1  # 包括当前场次
        #     if total_count > 3:
        #         market_subtractions.append(-3)
        #         market_reasons.append(("sub", -3, f"用户在年度规划中已录入{total_count}场该歌手的演唱会（超过3场），强制扣3分（流水线化折价）"))
        
        # 每个维度最多执行两次加分和两次减分，取前两个最大值
        market_score, market_reasons = self.get_final_score(market_additions, market_subtractions,
                                        market_reasons_additions, market_reasons_subtractions)
        
        details["market"]["score"] = market_score
        details["market"]["reasons"] = market_reasons
        score += market_score
        
        return score, details
    
    def determine_equipment(self, 
                            concert: ConcertInfo, 
                            security_level: SecurityLevel, 
                            available_balance: float, 
                            be: float, grade) -> Tuple[Optional[str], str]:
        """
        根据 SP 规则决定器材。
        Returns: (Equipment_Code, Logic_Trace_Log)
        """
        logs = []
        logs.append(f"=== 启动器材精算审计 ===")
        logs.append(f"环境参数: 安保[{security_level.value}] | 评级[{grade}] | 余额[{available_balance}] | 体力[{be}%]")

        # 0. 初始候选池
        candidates = equipments[:]

        # --- 第一关：C级熔断 (SP 七.4) ---
        # if grade == "C":
        #     return None, "LOGIC MELT: 场次评级为 C，触发逻辑熔断，资产清算。"

        # --- 第二关：安保物理准入 (SP 四.二 & 四.四) ---
        survivors_r1 = []
        for eq in candidates:
            passed = True
            reason = ""
            
            if security_level == SecurityLevel.HIGH:
                # 高安保：长度<=50mm, 不可拆卸, 非白色(SP虽未明确写非白但暗示黑色), 口径限制(简化为不可拆卸)
                if eq.length > 50 or eq.removable or eq.is_white:
                    passed = False
                    reason = "违反高安保长度/结构/外观红线"
            
            elif security_level == SecurityLevel.MEDIUM:
                # 中安保：长度<=150mm
                if eq.length > 150:
                    passed = False
                    reason = "违反中安保长度红线 (>150mm)"
            
            elif security_level == SecurityLevel.LOW:
                # 低安保：长度<=400mm
                if eq.length > 400:
                    passed = False
                    reason = "违反低安保长度红线"

            
            if passed:
                survivors_r1.append(eq)
            else:
                logs.append(f"安保拦截: [{eq.code}] {reason}")

        if not survivors_r1:
            logs.append("结论: 安保规则导致所有器材被拦截（包括手机），无可用器材。")
            return None, "\n".join(logs)
        
        candidates = survivors_r1

        # --- 第三关：场次定级与财务权限 (SP 七) ---
        survivors_r2 = []
        balance_blocked = []
        for eq in candidates:
            passed = True
            reason = ""

            # 评级权限限制
            if grade == "A":
                if eq.code != "MT-01":
                    passed = False
                    reason = "A级场次强制锁定 MT-01"
            
            elif grade == "S":
                # SP原文：押金总额限 5,000 元以下 (严格逻辑 < 5000, 修正逻辑 <= 5000)
                # 这里采用修正逻辑 <= 5000，否则 ZC-02 (5000) 也会被杀
                if eq.deposit > 5000:
                    passed = False
                    reason = "S级场次押金不得超过 5,000"
            
            # S+ 级权限全开，无限制

            # 实时财务流动性限制 (SP 九.一)
            total_cost = eq.rent + eq.deposit
            if total_cost > available_balance:
                if passed:
                    balance_blocked.append(eq)
                passed = False
                reason = f"流动性不足 (需 {total_cost}, 余 {available_balance})"

            if passed:
                survivors_r2.append(eq)
            else:
                logs.append(f"财务拦截: [{eq.code}] {reason}")

        if not survivors_r2:
            logs.append("结论: 账户余额不足以支付任何器材（含MT-01），本场以无器材状态执行。")
            return None, "\n".join(logs)
        
        candidates = survivors_r2

        # --- 第四关：生理机能与风险避让 (SP 四.三.4 & 四.四.2) ---
        survivors_r3 = []
        # 风险避让：BE < 40% 且 安保 != LOW，禁止重型 (>1.5kg 或 >150mm)
        # SP 四.四.2 修正定义：风险避让锁定总重 <= 1.1kg (严格执行)
        force_lightweight = (be < 40 and security_level != SecurityLevel.LOW)
        
        if force_lightweight:
            logs.append("生理预警: BE < 40% 且非低安保，触发风险避让，强制轻量化 (<=1.1kg)。")

        for eq in candidates:
            passed = True
            if force_lightweight:
                if eq.weight > 1.1: 
                    passed = False
                    logs.append(f"机能拦截: [{eq.code}] 过重 ({eq.weight}kg)")
            
            if passed:
                survivors_r3.append(eq)
        
        if not survivors_r3:
            # 理论上 MT-01 (0.2kg) 肯定还在，除非没钱
            logs.append("结论: 生理机能限制导致所有器材被拦截，无可用器材。")
            return None, "\n".join(logs)

        candidates = survivors_r3

        # --- 第五关：排数与视觉需求匹配 (SP 三.二) ---
        # 这一步不是“剔除”，而是“打分/择优”
        # 首先检查物理排数限制 (SP 三.三)
        
        # 预处理：计算当前位置支持的最大焦段需求
        # 如果坐在看台40排(EXTREME)，却想要(PANORAMA)，SP允许向下兼容吗？
        # SP 三.三：若物理无法实现(如看台拍特写?? SP原文例子是反的)，以排数能达到的最高焦段为准。
        # 修正理解：主要是防止“近距离用长焦”或“远距离用短焦无法满足”。
        
        # 识别物理位置限制的有效层级
        location_tier = self._get_location_tier(concert.seat_area, concert.seat_row)
        logs.append(f"位置信息: {concert.seat_area} 第{concert.seat_row}排")
        
        # 处理近距离对焦冲突 (SP 四.四.3)
        # 内场 1-5 排，强制拦截极限长焦器材（可拍摄 600mm-3000mm 焦段的器材）
        # SP 定义：器材归属按其主要定位的焦段区间判定
        close_focus_conflict = False
        if concert.seat_area == '内场' and concert.seat_row <= 5:
            # 移除所有极限长焦器材
            # 根据 SP 定义，极限长焦器材是指焦段范围可达到 600-3000mm 的器材
            # WC-03 (24-3000mm) 属于极限长焦类
            before_count = len(candidates)
            removed_candidates = ','.join([c.code for c in candidates if c.is_extreme_long_focal()])
            candidates = [c for c in candidates if not c.is_extreme_long_focal()]
            if len(candidates) < before_count:
                close_focus_conflict = True
                logs.append(f"物理冲突: 内场前排(1-5排)强制移除极限长焦器材({removed_candidates})，因近距离对焦冲突。")
        front_row = concert.seat_area == '内场' and concert.seat_row <= 5
        requested_tier = (
            self._determine_visual_tier(concert.visual_keyword, location_tier)
            if concert.visual_keyword else None
        )
        conflict_by_request = (front_row and not close_focus_conflict
                               and requested_tier == VisualTier.EXTREME
                               and security_level != SecurityLevel.HIGH)
        finance_backtrack = False
        if requested_tier is not None and balance_blocked:
            _rng = {
                VisualTier.PANORAMA: (13, 50),
                VisualTier.PORTRAIT: (70, 200),
                VisualTier.CLOSEUP: (300, 600),
                VisualTier.EXTREME: (600, 3000),
            }[requested_tier]

            def _covers(eq):
                return eq.focal_range[0] <= _rng[0] and eq.focal_range[1] >= _rng[1]

            if any(_covers(eq) for eq in balance_blocked) and not any(
                _covers(eq) for eq in candidates
            ):
                finance_backtrack = True
        # --- 最终择优逻辑 (SP 三.二 & 四.四.4) ---

        # SP 三.五 视觉关键句缺省协议：未提供视觉产出层级关键句时，强制锁定 MT-01
        if not concert.visual_keyword:
            logs.append("视觉关键句缺省: 用户未提供视觉产出层级关键句，强制锁定 MT-01（SP 三.五）")
            return "MT-01", "\n".join(logs)

        # 1. 确定目标视觉层级 (VisualTier)
        # 根据 visual_keyword 识别用户需求层级
        visual_tier = self._determine_visual_tier(concert.visual_keyword, location_tier)
        logs.append(f"视觉需求: {visual_tier.value if visual_tier else '未识别'} ")
        if conflict_by_request:
            trial_logs = []
            trial = self._select_best_match(candidates, visual_tier, location_tier, grade, trial_logs,
                                            False, conflict_switch=True)
            if trial and trial != "MT-01":
                logs.append("物理冲突: 内场前排(1-5排)请求极限长焦，触发近距离对焦冲突（极限长焦器材已在前序关卡被拦截），切换至短焦/中长焦方案。")
                logs.extend(trial_logs)
                logs.append(f"最终决策: 锁定器材 [{trial}]。")
                return trial, "\n".join(logs)
        if finance_backtrack and not close_focus_conflict:
            trial_logs = []
            trial = self._select_best_match(candidates, visual_tier, location_tier, grade, trial_logs,
                                            False, finance_backtrack=True)
            if trial and trial != "MT-01":
                logs.append("财务校准: 目标层级器材仅因实际可用余额不足被拦截，执行逐级向下回溯（SP 四.(四).4.(3)、九.(一)）。")
                logs.extend(trial_logs)
                logs.append(f"最终决策: 锁定器材 [{trial}]。")
                return trial, "\n".join(logs)
        
        target_eq_code = self._select_best_match(candidates, visual_tier, location_tier, grade, logs, close_focus_conflict)
        
        if target_eq_code:
            logs.append(f"最终决策: 锁定器材 [{target_eq_code}]。")
            return target_eq_code, "\n".join(logs)
        else:
            # 最后的保底：如果所有期望都匹配不上，返回候选池里最基础的 MT-01
            # 只要 MT-01 在候选池里
            for eq in candidates:
                if eq.code == "MT-01":
                    logs.append("降级执行: 目标器材无法匹配，强制降级为 MT-01。")
                    return "MT-01", "\n".join(logs)
            
            logs.append("结论: 无法匹配任何器材，且保底 MT-01 不可用。")
            return None, "\n".join(logs)

    def _get_location_tier(self, seat_area: str, row: int) -> List[VisualTier]:
        """
        判定物理位置适合的层级。
        根据 SP 三.四 和 SP 四.四.3 规则：
        
        物理位置决定了可用的视觉层级范围：
        - 内场1-5排：支持短焦(PANORAMA)、中长焦(PORTRAIT)，但禁止极限长焦(近距离对焦冲突)
        - 内场6-20排：支持中长焦(PORTRAIT)、超长焦(CLOSEUP)
        - 内场21排及以后：支持超长焦(CLOSEUP)
        - 看台第1排：支持短焦(PANORAMA)、中长焦(PORTRAIT)
        - 看台2-10排：支持中长焦(PORTRAIT)、超长焦(CLOSEUP)
        - 看台11-30排：支持超长焦(CLOSEUP)
        - 看台31排及以上：支持极限长焦(EXTREME)
        
        返回值从低层级到高层级排序，用于向上兼并判定。
        """
        is_inner = (seat_area == '内场')
        tiers = []
        
        if is_inner:
            # 内场
            if row <= 5:
                # 前排：适合全景和半身拍摄
                tiers.append(VisualTier.PANORAMA)
                tiers.append(VisualTier.PORTRAIT)
                # 注意：SP 四.四.3 规定内场1-5排禁止极限长焦，因近距离对焦冲突
            elif 6 <= row <= 20:
                # 中排：适合半身和特写
                tiers.append(VisualTier.PORTRAIT)
                tiers.append(VisualTier.CLOSEUP)
            elif row >= 21:
                # 后排：适合特写
                tiers.append(VisualTier.CLOSEUP)
        else:
            # 看台
            if row == 1:
                # 看台第一排
                tiers.append(VisualTier.PANORAMA)
                tiers.append(VisualTier.PORTRAIT)
            elif 2 <= row <= 10:
                # 看台前排
                tiers.append(VisualTier.PORTRAIT)
                tiers.append(VisualTier.CLOSEUP)
            elif 11 <= row <= 30:
                # 看台中排
                tiers.append(VisualTier.CLOSEUP)
            elif row >= 31:
                # 看台远距离（"山顶"位）
                tiers.append(VisualTier.EXTREME)
        
        # 如果没有匹配到任何层级，默认返回全景
        if not tiers:
            tiers.append(VisualTier.PANORAMA)
        
        return tiers

    def _determine_visual_tier(self, visual_keyword: str, location_tiers: List[VisualTier]) -> Optional[VisualTier]:
        """
        根据视觉关键词和物理位置确定目标视觉层级。
        遵循 SP 三.三: 若排数支持更高级，且用户需求多重，取最高。
        """

        if not visual_keyword:
            return None
        
        visual_keyword_lower = visual_keyword.lower()
        
        # 定义四个视觉产出层级的关键词
        # 1. 短焦器材（13mm - 50mm）- PANORAMA
        short_focal_keywords = [
            "我想拍全场的大合唱画面",
            "舞美灯光非常震撼，我想完整录下来",
            "我在前排，想拍那种很有氛围感的全景感",
            "我想记录全场的应援色灯海",
            "舞台设计很有层次，需要广角视角"

        ]
        
        # 2. 中长焦器材（70mm - 200mm）- PORTRAIT
        medium_focal_keywords = [
            "我想拍他跳舞的全身动作，不想只拍脸",
            "看清舞台上的整体编舞，但人要占屏幕一半以上",
            "只要能拍到清晰的半身像就行",
            "不需要特写，只要画面纯净、背景虚化好",
            "想记录艺人和伴舞的互动画面",

        ]
        
        # 3. 超长焦器材（300mm - 600mm）- CLOSEUP
        long_focal_keywords = [
            "我想拍到他在舞台上流汗的细节",
            "能不能拍到睫毛或者妆容的特写",
            "只要艺人的脸，背景全部虚化",
            "我在看台，但我想要像在第一排看一样的清晰度",
            "捕捉他微小的表情变化",

        ]
        
        # 4. 极限长焦器材（600mm - 3000mm）- EXTREME
        extreme_focal_keywords = [
            "我在‘山顶’位，但我还是想拍到艺人的脸",
            "只要能拍到人在哪就行，不需要多高清，只要大",
            "哪怕画质有噪点，我也要拍到大头特写",
            "坐在最后排，求一个能看到人的神器",
            "远距离记录，主要为了存个档",
        ]
        
        # 检测触发的视觉产出层级（按优先级从高到低）
        triggered_tiers = []
        
        if any(kw in visual_keyword_lower for kw in extreme_focal_keywords):
            triggered_tiers.append(VisualTier.EXTREME)
        if any(kw in visual_keyword_lower for kw in long_focal_keywords):
            triggered_tiers.append(VisualTier.CLOSEUP)
        if any(kw in visual_keyword_lower for kw in medium_focal_keywords):
            triggered_tiers.append(VisualTier.PORTRAIT)
        if any(kw in visual_keyword_lower for kw in short_focal_keywords):
            triggered_tiers.append(VisualTier.PANORAMA)
        # 如果触发了多个层级，选择最高的（最接近用户需求）
        if triggered_tiers:
            desired_tier = triggered_tiers[0]  # 最高优先级的需求
            
            
            return desired_tier
        # The authored source sometimes supplies descriptive prose rather than
        # one of the twenty closed sentences, and one session supplies no visual
        # sentence at all. Such wording is deliberately not promoted into a
        # trigger; the SP's physical-position fallback supplies the highest tier
        # supported by the seat.
        if location_tiers:
            return location_tiers[-1]
        return VisualTier.PANORAMA
    
    def _select_best_match(self, candidates: List[Equipment], visual_tier: Optional[VisualTier], 
                          location_tiers: List[VisualTier], grade: str, logs: List[str],
                          close_focus_conflict: bool = False,
                          finance_backtrack: bool = False,
                          conflict_switch: bool = False) -> Optional[str]:
        """
        在清洗后的候选池中，寻找最符合视觉需求的器材。
        遵循 SP 三.(四) 光学区间匹配协议（Priority Matching Protocol），每级执行三步法：
        1. 视觉目标定域 - 锁定焦段需求区间
        2. 器材全集筛选 - 筛选物理参数完全包含目标区间的型号
        3. 多重约束校准 - 代入财务准入配额等限制条件进行二次过滤

        两种降级路径：
        - SP四.四.3 近距离对焦冲突（close_focus_conflict=True）：
          内场1-5排极限长焦被移除后，允许逐级向下匹配适合的短焦/中长焦方案，
          选择对焦距离最远的器材。
        - SP三.(四) 降级兜底规则（close_focus_conflict=False）：
          仅尝试目标视觉层级，无可用器材时强制锁定 MT-01。
        """
        if not visual_tier:
            visual_tier = VisualTier.PANORAMA

        logs.append(f"执行光学区间匹配协议，目标视觉层级: {visual_tier.value}")

        focal_range_map = {
            VisualTier.PANORAMA: (13, 50),
            VisualTier.PORTRAIT: (70, 200),
            VisualTier.CLOSEUP: (300, 600),
            VisualTier.EXTREME: (600, 3000),
        }

        deposit_limit_map = {
            VisualTier.PANORAMA: 3000,
            VisualTier.PORTRAIT: (5000, 12000),
            VisualTier.CLOSEUP: (5000, 8000),
            VisualTier.EXTREME: 15000,
        }

        tier_descending = [VisualTier.EXTREME, VisualTier.CLOSEUP, VisualTier.PORTRAIT, VisualTier.PANORAMA]
        start = tier_descending.index(visual_tier) if visual_tier in tier_descending else len(tier_descending) - 1

        step_label = "SP四.(四).4.(3)(财务逐级回溯)" if finance_backtrack else "SP四.四.3(近距离对焦冲突)"
        if close_focus_conflict or finance_backtrack:
            # SP四.四.3: 近距离对焦冲突，逐级向下匹配适合的短焦/中长焦方案
            tiers_to_try = tier_descending[start:]
        else:
            # SP三.(四): 仅尝试目标层级，无匹配则由降级兜底规则强制锁定MT-01
            tiers_to_try = [visual_tier]
        # SP四.(四).3(2): 请求极限长焦触发的近距离对焦冲突，只能切换至中长焦/短焦方案
        switch_names = {VisualTier.PORTRAIT: "中长焦", VisualTier.PANORAMA: "短焦"}
        if conflict_switch:
            tiers_to_try = [visual_tier] + [t for t in switch_names if t != visual_tier]

        for tier in tiers_to_try:
            target_min, target_max = focal_range_map[tier]
            is_downgrade = (tier != visual_tier)

            if is_downgrade and conflict_switch:
                logs.append(f"{step_label}: 切换至{switch_names[tier]}方案 → {tier.value} (焦段 {target_min}-{target_max}mm)")
            elif is_downgrade:
                logs.append(f"{step_label}: 向下兼容尝试 → {tier.value} (焦段 {target_min}-{target_max}mm)")
            else:
                logs.append(f"第一步-视觉目标定域: 焦段需求区间 {target_min}-{target_max}mm")

            # === 第二步：器材全集筛选 ===
            full_coverage = []
            for eq in candidates:
                eq_min, eq_max = eq.focal_range
                if eq_min <= target_min and eq_max >= target_max:
                    full_coverage.append(eq)
                    logs.append(f"第二步-全集包含: [{eq.code}] ({eq_min}-{eq_max}mm) 完全覆盖{tier.value}区间")
                elif not is_downgrade:
                    logs.append(f"第二步-全集筛除: [{eq.code}] ({eq_min}-{eq_max}mm) 无法完全覆盖 {target_min}-{target_max}mm")

            if not full_coverage:
                continue

            # === 第三步：多重约束校准 ===
            deposit_limit = deposit_limit_map.get(tier)
            final = []
            for eq in full_coverage:
                passed = True
                reason = ""
                if deposit_limit:
                    if isinstance(deposit_limit, tuple):
                        _min_d, max_d = deposit_limit
                        if eq.deposit > max_d:
                            passed = False
                            reason = f"押金超出配额上限 ({eq.deposit} > {max_d})"
                    else:
                        if eq.deposit > deposit_limit:
                            passed = False
                            reason = f"押金超出配额 ({eq.deposit} > {deposit_limit})"
                if passed:
                    final.append(eq)
                else:
                    logs.append(f"第三步-财务配额拦截: [{eq.code}] {reason}")

            if not final:
                continue

            # === 最终择优：选择焦距最远的器材 ===
            selected = max(final, key=lambda x: x.focal_range[1])
            if is_downgrade and conflict_switch:
                logs.append(
                    f"{step_label}: 在{switch_names[tier]}方案中选择焦距最远的器材 "
                    f"[{selected.code}] ({selected.focal_range[0]}-{selected.focal_range[1]}mm)"
                )
            elif is_downgrade:
                logs.append(
                    f"{step_label}: 向下兼容至{tier.value}，选择焦距最远的器材 "
                    f"[{selected.code}] ({selected.focal_range[0]}-{selected.focal_range[1]}mm)"
                )
            else:
                logs.append(
                    f"最终选定: [{selected.code}] {selected.name} "
                    f"(焦段 {selected.focal_range[0]}-{selected.focal_range[1]}mm, 押金 {selected.deposit})"
                )
            return selected.code

        if close_focus_conflict:
            logs.append("SP四.四.3: 近距离对焦冲突，逐级向下兼容后仍无可用器材，兜底至MT-01")
        else:
            logs.append("SP三.(四) 降级兜底规则: 目标视觉层级无可用器材，强制向下兼容至MT-01")
        for eq in candidates:
            if eq.code == "MT-01":
                return "MT-01"
        return None
    
    
    def downgrade_hotel_to_tier(self, concert: ConcertInfo, target_tier: HotelTier) -> Tuple[str, float]:
        """将酒店降级到指定等级
        
        SP 十一「用户备选优先」规则：若用户提供多项跨级备选方案，
        系统将优先从中择取达标的层级（例：降级目标为T2，若用户提供T1与T3，则生效T3）。
        
        Args:
            concert: 演唱会信息（会被原地修改）
            target_tier: 目标酒店等级（T2 或 T3）
        
        Returns:
            Tuple[str, float]: (酒店名称, 酒店费用)
        """
        if target_tier == HotelTier.T2:
            brands = HOTEL_BRANDS["T2"]
            default_name = DEFAULT_HOTELS["T2"]["name"]
            default_cost = DEFAULT_HOTELS["T2"]["cost"]
        elif target_tier == HotelTier.T3:
            brands = HOTEL_BRANDS["T3"]
            default_name = DEFAULT_HOTELS["T3"]["name"]
            default_cost = DEFAULT_HOTELS["T3"]["cost"]
        else:
            return concert.hotel_name, concert.hotel_cost
        
        if concert.hotel_options:
            tier_options = [opt for opt in concert.hotel_options if any(brand in opt.name for brand in brands)]
            if tier_options:
                cheapest = min(tier_options, key=lambda x: x.cost)
                concert.hotel_name = cheapest.name
                concert.hotel_cost = cheapest.cost
            else:
                # SP 七.①/十一「用户备选优先」：目标等级无匹配时，
                # 从用户选项中择取更低等级的达标选项
                lower_tier_selected = False
                if target_tier == HotelTier.T2:
                    t3_brands = HOTEL_BRANDS["T3"]
                    t3_options = [opt for opt in concert.hotel_options
                                 if any(brand in opt.name for brand in t3_brands)]
                    if t3_options:
                        cheapest = min(t3_options, key=lambda x: x.cost)
                        concert.hotel_name = cheapest.name
                        concert.hotel_cost = cheapest.cost
                        lower_tier_selected = True
                if not lower_tier_selected:
                    concert.hotel_name = default_name
                    concert.hotel_cost = default_cost
        else:
            concert.hotel_name = default_name
            concert.hotel_cost = default_cost
        
        return concert.hotel_name, concert.hotel_cost
    
    def _apply_survival_mode(self, concert: ConcertInfo) -> bool:
        """执行极限生存模式：酒店强制T3 + 交通强制最低价。
        器材强制MT-01由调用方处理（器材选择在漏斗之外）。
        
        Returns:
            bool: 是否实际执行了降级动作
        """
        TRANSPORT_FLOOR = 200.0
        modified = False

        if get_hotel_tier_by_name(concert.hotel_name) != HotelTier.T3:
            self.downgrade_hotel_to_tier(concert, HotelTier.T3)
            modified = True

        if concert.transport_options and len(concert.transport_options) > 1:
            cheapest = min(concert.transport_options, key=lambda x: x.cost)
            if cheapest.cost > TRANSPORT_FLOOR:
                concert.transport = cheapest.transport
                concert.transport_duration = cheapest.duration
                concert.transport_duration_from_input = cheapest.duration_from_input
                concert.transport_cost = TRANSPORT_FLOOR
                modified = True
            elif concert.transport_cost > cheapest.cost:
                concert.transport = cheapest.transport
                concert.transport_cost = cheapest.cost
                concert.transport_duration = cheapest.duration
                concert.transport_duration_from_input = cheapest.duration_from_input
                modified = True
        else:
            if concert.transport_cost > TRANSPORT_FLOOR:
                concert.transport_cost = TRANSPORT_FLOOR
                modified = True

        return modified
    
    def determine_hotel_tier(self, concert: ConcertInfo, available_balance: float, 
                           be: float, score: int, skip_financial_check: bool = False) -> Tuple[HotelTier, str, str]:
        """确定酒店等级（基础判定，不含降级漏斗逻辑）
        
        注意：此函数仅做基础等级判定和机能代偿升级。
        降级漏斗逻辑（第一层到第四层）统一在 execute_downgrade_funnel 中处理。
        
        Args:
            concert: 演唱会信息
            available_balance: 可用余额
            be: 当前体力值
            score: 演出价值分
            skip_financial_check: 是否跳过财务检查（由降级漏斗统一处理时设为True）
        
        Returns:
            Tuple[HotelTier, str, str]: (酒店等级, 酒店名称, 降级原因说明)
        """
        hotel_name = concert.hotel_name
        downgrade_reason = ""  # 降级原因，为空表示无强制降级
        
        # 检查品牌库，确定当前酒店等级
        hotel_tier = get_hotel_tier_by_name(hotel_name)
        
        # 机能代偿性判定（生命体征原则）- 这是升级逻辑，不受降级漏斗影响
        # 注意：只有在未被降级漏斗强制降级时才执行升级
        if not skip_financial_check and be <= 25:
            if hotel_tier == HotelTier.T3:
                downgrade_reason = f"初始体力值≤25%（{be:.1f}%），机能代偿性强制升级至T2标准级"
                return HotelTier.T2, hotel_name, downgrade_reason
            elif hotel_tier == HotelTier.T2:
                downgrade_reason = f"初始体力值≤25%（{be:.1f}%），机能代偿性强制升级至T1豪华级"
                return HotelTier.T1, hotel_name, downgrade_reason
        
        return hotel_tier, hotel_name, downgrade_reason
    
    def execute_downgrade_funnel(self, concert: ConcertInfo, pre_audit_available_balance: float,
                                  initial_be: float, score: int, grade: str, 
                                  security_level: SecurityLevel,
                                  pre_audit_nominal_balance: float = None) -> Tuple[Optional[dict], Optional[str]]:
        """统一降级漏斗 - 严格按SP 十一.二执行
        
        执行顺序：
        第一层：合规性与安全性单点降级（A级降级、溢价抵补、安保红线）
        第二层：财务平衡预警与抵补修复（中度财务预警T1→T2）
        第三层：极限生存压榨（余额<4000，全维度降级至生存底线）
        第四层：终极熔断（降级后仍无法覆盖，执行熔断）
        
        Args:
            concert: 演唱会信息（会被原地修改）
            pre_audit_available_balance: 审计前可用余额（已扣除未退押金）
            pre_audit_nominal_balance: 审计前名义余额（未扣除未退押金，用于第三层极限生存判断）
            initial_be: 初始体力值
            score: 演出价值分
            grade: 场次等级
            security_level: 安保等级
        
        Returns:
            Tuple[Optional[dict], Optional[str]]: 
                - 成功时返回 (降级结果dict, None)
                - 熔断时返回 (None, 熔断原因)
        """
        downgrade_logs = []
        TRANSPORT_FLOOR = 200.0
        
        # 记录原始配置
        original_hotel_tier = get_hotel_tier_by_name(concert.hotel_name)
        if concert.hotel_options:
            user_intends_t1 = any(
                get_hotel_tier_by_name(opt.name) == HotelTier.T1 for opt in concert.hotel_options
            )
        else:
            user_intends_t1 = original_hotel_tier == HotelTier.T1
        
        current_hotel_tier = original_hotel_tier
        hotel_name = concert.hotel_name
        
        # ========== 第一层：合规性与安全性单点降级 ==========
        
        # 1.1 A级专属降级（定级边缘化）- SP 七.3
        if grade == VenueGrade.A.value:
            # A级零溢价检查（熔断条件，在audit_concert中已处理，此处仅做酒店降级）
            if current_hotel_tier != HotelTier.T3:
                hotel_name, _ = self.downgrade_hotel_to_tier(concert, HotelTier.T3)
                current_hotel_tier = HotelTier.T3
                downgrade_logs.append(f"第一层-A级专属降级：A级场次（得分{score}分）强制降级至T3经济级（原配置：{original_hotel_tier.value}级）")
        
        # 1.2 溢价抵补（S/S+级）- SP 七.1、七.2
        # 必须在第二层之前执行，确保溢价缺口优先通过差旅压降抵补
        premium_downgrade_executed = False
        
        if grade == VenueGrade.S.value and concert.ticket_original > 0:
            s_premium_amount = concert.ticket_actual - concert.ticket_original
            s_premium_rate = s_premium_amount / concert.ticket_original if concert.ticket_original > 0 else 0
            if s_premium_rate > 0.30:
                # S级溢价超30%，调用通用降级函数执行差旅同步压降
                # 需要抵补的是超过30%的部分：溢价金额 - 原价*30%
                excess_premium = s_premium_amount - concert.ticket_original * 0.30
                premium_downgrade_executed = True
                _, _, current_hotel_tier = self.execute_premium_downgrade(
                    concert, excess_premium, f"S级溢价超30%（溢价率{s_premium_rate*100:.1f}%）", TRANSPORT_FLOOR
                )
                hotel_name = concert.hotel_name
                downgrade_logs.append(f"第一层-溢价抵补：S级溢价超30%（溢价率{s_premium_rate*100:.1f}%），强制执行差旅同步压降")
        
        if grade == VenueGrade.S_PLUS.value and concert.ticket_original > 0:
            splus_premium = concert.ticket_actual - concert.ticket_original
            if splus_premium > 1000:
                # S+级溢价超1000元，调用通用降级函数执行差旅同步压降
                # 需要抵补的是超过1000元的部分：溢价金额 - 1000
                excess_premium = splus_premium - 1000
                premium_downgrade_executed = True
                _, _, current_hotel_tier = self.execute_premium_downgrade(
                    concert, excess_premium, f"S+级溢价超1000元（溢价{splus_premium:.2f}元）", TRANSPORT_FLOOR
                )
                hotel_name = concert.hotel_name
                downgrade_logs.append(f"第一层-溢价抵补：S+级溢价超1000元（溢价{splus_premium:.2f}元），强制执行差旅同步压降")
        
        # ========== 第二层：财务平衡预警与抵补修复 ==========
        # 触发条件：扣除本场门票实付、预选机酒预算及当前所有未退押金后，
        # 实时可用余额在 4,000-8,000元 区间，且原定配置为T1豪华级
        # 注意：如果不存在溢价，那么本层会执行；如果存在溢价，酒店不可能为T1，所以本层不会执行。
        
        layer2_after_premium = premium_downgrade_executed and user_intends_t1
        if (not premium_downgrade_executed or layer2_after_premium) and grade != VenueGrade.A.value:
            post_expense_balance = pre_audit_available_balance - concert.ticket_actual - concert.transport_cost - concert.hotel_cost
            if layer2_after_premium:
                if post_expense_balance < 4000 and current_hotel_tier != HotelTier.T3:
                    hotel_name, _ = self.downgrade_hotel_to_tier(concert, HotelTier.T3)
                    current_hotel_tier = HotelTier.T3
                    downgrade_logs.append(
                        f"第二层-中度财务预警（溢价抵补后复核，用户原定T1）：扣除本场门票实付({concert.ticket_actual:.2f}元)、"
                        f"机酒预算后，实时可用余额为{post_expense_balance:.2f}元，"
                        f"低于4,000元，强制降级为T3"
                    )
            elif 4000 <= post_expense_balance < 8000 and current_hotel_tier == HotelTier.T1:
                hotel_name, _ = self.downgrade_hotel_to_tier(concert, HotelTier.T2)
                current_hotel_tier = HotelTier.T2
                downgrade_logs.append(
                    f"第二层-中度财务预警：扣除本场门票实付({concert.ticket_actual:.2f}元)、"
                    f"机酒预算后，实时可用余额为{post_expense_balance:.2f}元，"
                    f"未达到8,000元的T1准入红线，强制将T1降级为T2"
                )
            elif post_expense_balance < 4000 and current_hotel_tier == HotelTier.T1:
                hotel_name, _ = self.downgrade_hotel_to_tier(concert, HotelTier.T3)
                current_hotel_tier = HotelTier.T3
                downgrade_logs.append(
                    f"第二层-中度财务预警：扣除本场门票实付({concert.ticket_actual:.2f}元)、"
                    f"机酒预算后，实时可用余额为{post_expense_balance:.2f}元，"
                    f"未达到8,000元的T1准入红线，强制将T1降级为T3"
                )
        
        # ========== 第三层：极限生存压榨 ==========
        # 触发条件：年度预算余额 < 4,000元
        # 执行动作：全维度资产同步降级至绝对生存底线（T3经济级酒店 + 最低基准交通 + 最低押金器材）
        
        min_equipment_deposit = EQUIPMENT_LIB["MT-01"].rent
        # 机酒均降级 / 机酒均未降级 / 仅降级酒店（不存在仅下降交通的情况）
        if not downgrade_logs and (concert.hotel_options or concert.transport_options):
            # 机酒均未降级
            min_hotel_cost = min([opt.cost for opt in concert.hotel_options]) if concert.hotel_options else concert.hotel_cost
            min_transport_cost = min([opt.cost for opt in concert.transport_options]) if concert.transport_options else concert.transport_cost
        elif downgrade_logs and (concert.transport_cost != TRANSPORT_FLOOR):
            # 仅降级酒店(A级降级策略)
            min_transport_cost = min([opt.cost for opt in concert.transport_options]) if concert.transport_options else concert.transport_cost
            min_hotel_cost = concert.hotel_cost
        else:
            # 机酒均降级 或不存在多选项
            min_hotel_cost = concert.hotel_cost
            min_transport_cost = concert.transport_cost

        total_cost_estimate = concert.ticket_actual + min_transport_cost + min_hotel_cost + min_equipment_deposit
        # 第三层用名义余额判断：押金终将退还，不应把尚未退回的押金计入"极限生存"触发条件
        balance_for_survival_check = pre_audit_nominal_balance if pre_audit_nominal_balance is not None else pre_audit_available_balance
        remaining_after_cost = balance_for_survival_check - total_cost_estimate
        
        survival_mode_active = False
        if remaining_after_cost < 4000:
            survival_mode_active = True
            actually_modified = self._apply_survival_mode(concert)
            if actually_modified:
                current_hotel_tier = HotelTier.T3
                hotel_name = concert.hotel_name
                downgrade_logs.append(
                    f"第三层-极限生存模式：预估支出后余额({remaining_after_cost:.2f}元)<4000元，"
                    f"全维度资产同步降级至绝对生存底线"
                )
        
        # ========== 第四层：终极熔断检查 ==========
        # 经过前三层降级后，若依然财务崩盘，执行熔断
        base_cost = concert.ticket_actual + concert.transport_cost + concert.hotel_cost
        if base_cost > pre_audit_available_balance and current_hotel_tier == HotelTier.T3:
            meltdown_reason = (
                f"第四层-终极熔断：基础支出（门票{concert.ticket_actual:.2f} + "
                f"交通{concert.transport_cost:.2f} + 酒店{concert.hotel_cost:.2f} = {base_cost:.2f}元）> "
                f"实际可用余额 {pre_audit_available_balance:.2f}元，且已降级至T3，降级挽救失败"
            )
            return None, meltdown_reason
        
        # 返回降级结果
        return {
            "hotel_tier": current_hotel_tier,
            "hotel_name": hotel_name,
            "downgrade_logs": downgrade_logs,
            "premium_downgrade_executed": premium_downgrade_executed,
            "survival_mode_active": survival_mode_active
        }, None
    
    def execute_premium_downgrade(self, concert: ConcertInfo, excess_premium: float,
                                   grade_label: str, transport_floor: float = 200.0) -> Tuple[str, str, HotelTier]:
        """执行溢价触发的机酒降级流程（SP 七.1.(2)）
        
        降级流程：
        ①逐级降级：住宿降一级 + 交通最低价
        ②实时评估：降级后重新计算，若溢价超出部分已抵补则终止
          - S+级：抵补超过1000元的溢价部分
          - S级：抵补超过30%的溢价部分
        ③循环判定：若超出部分仍在，继续降级住宿
        ④终点规则：即使降至最低级别仍有缺口，流程也终止，采用最终方案（不熔断）
        
        Args:
            concert: 演唱会信息（会被原地修改）
            excess_premium: 需要抵补的溢价超出部分
              - S+级：超过1000元的溢价部分（即 溢价金额 - 1000）
              - S级：超过30%的溢价部分（即 溢价金额 - 原价*30%）
            grade_label: 等级标签（用于生成提示文本，如"S级溢价超30%"或"S+级溢价超1000元"）
            transport_floor: 交通最低价基准（默认200元）
        
        Returns:
            Tuple[str, str, HotelTier]: (交通选择文本, 酒店选择文本, 最终酒店等级)
        """
        # 确定当前酒店等级
        current_hotel_tier = get_hotel_tier_by_name(concert.hotel_name)
        
        # 记录降级前的成本，用于计算节省金额
        original_transport_cost = concert.transport_cost
        original_hotel_cost = concert.hotel_cost
        
        # === 第一步：交通降至最低价 + 酒店降一级 同步执行 ===
        concert.transport_cost = min(concert.transport_cost, transport_floor)
        duration_str = f"（{concert.transport_duration}h）" if concert.transport_duration_from_input else ""
        transport_selection = f"{concert.transport}{duration_str}；实付 {concert.transport_cost:.2f} 元（{grade_label}，强制降至最低价交通）"
        
        # 酒店降一级（T1→T2 或 T2→T3）
        # 「用户备选优先」可能使实际等级低于目标等级，需重新检测
        if current_hotel_tier == HotelTier.T1:
            self.downgrade_hotel_to_tier(concert, HotelTier.T2)
            current_hotel_tier = get_hotel_tier_by_name(concert.hotel_name)
        elif current_hotel_tier == HotelTier.T2:
            self.downgrade_hotel_to_tier(concert, HotelTier.T3)
            current_hotel_tier = HotelTier.T3
        
        # === 第二步：实时评估，计算降级节省的金额是否已抵补溢价超出部分 ===
        savings_step1 = (original_transport_cost - concert.transport_cost) + (original_hotel_cost - concert.hotel_cost)
        remaining_excess = excess_premium - savings_step1
        
        # === 第三步：若溢价超出部分仍未抵补完且酒店为T2，继续降级至T3 ===
        if remaining_excess > 0 and current_hotel_tier == HotelTier.T2:
            hotel_cost_before_t3 = concert.hotel_cost
            self.downgrade_hotel_to_tier(concert, HotelTier.T3)
            current_hotel_tier = HotelTier.T3
        
        # === 第四步：终点规则 - 即使降至最低级别仍有缺口，采用最终方案（不熔断）===
        # 生成酒店选择文本
        hotel_selection = f"{current_hotel_tier.value}级 - {concert.hotel_name}；实付 {concert.hotel_cost:.2f} 元（⚠️ {grade_label}，强制降级以抵补票款）"
        
        return transport_selection, hotel_selection, current_hotel_tier
    
    def _extract_city(self, concert: ConcertInfo) -> str:
        """从演唱会名称或场馆提取城市名"""
        known_cities = [
            '上海', '北京', '广州', '深圳', '杭州', '成都', '南京', '武汉',
            '长沙', '西安', '重庆', '天津', '沈阳', '哈尔滨', '香港', '澳门',
            '曼谷', '首尔', '东京', '新加坡', '台北'
        ]
        search_text = (concert.name or '') + ' ' + (concert.venue or '')
        for city in known_cities:
            if city in search_text:
                return city
        return ''

    def _detect_cross_province(self, concert: ConcertInfo, previous_concert: ConcertInfo) -> bool:
        """判断两场演唱会是否涉及跨省位移"""
        city_current = self._extract_city(concert)
        city_previous = self._extract_city(previous_concert)

        if city_current and city_previous:
            if city_current == city_previous:
                return False
            # 香港、澳门与广东省不属于跨省位移
            gd_group = {'香港', '澳门', '广州', '深圳', '东莞', '佛山'}
            if city_current in gd_group and city_previous in gd_group:
                return False
            return True

        # 无法从名称/场馆推断城市时，依赖 special_note 的显式声明
        return '跨省' in (concert.special_note or '')

    def calculate_be_loss(self, concert: ConcertInfo, equipment_code: Optional[str], 
                          days_since_last: int = 0, previous_concert: Optional[ConcertInfo] = None,
                          force_extreme_transport: bool = False) -> Tuple[float, bool, Dict[str, float]]:
        """计算体力损耗
        
        Args:
            concert: 当前场次演唱会信息
            equipment_code: 器材代码
            days_since_last: 距离上一场的天数
            previous_concert: 上一场演唱会信息（用于应急损耗判断）
            force_extreme_transport: 最差环境预设（2）：强制触发极端转场20%损耗
        
        Returns:
            (total_loss, rr_collapsed, loss_details): 总损耗值、本场是否首次触发RR永久坍塌、损耗详情
        """
        total_loss = 0.0
        rr_collapsed = False  # 本场是否首次触发RR坍塌
        loss_details = {}  # 损耗详情
        
        # 1. 空间位能损耗
        space_loss = 0.0
        if concert.seat_area == "内场站席":
            space_loss = 30.0
        elif concert.seat_area == "内场":
            space_loss = 15.0
        elif concert.seat_area == "看台":
            space_loss = 5.0
        if space_loss > 0:
            total_loss += space_loss
            loss_details[f"空间位能({concert.seat_area})"] = space_loss
            
        # 2. 器材载荷损耗
        if equipment_code:
            equipment = EQUIPMENT_LIB[equipment_code]
            if equipment.is_heavy():
                total_loss += 10
                loss_details[f"器材载荷({equipment_code})"] = 10.0
                # 检测是否首次触发永久折旧（不在此处修改self.recovery_rate，由调用方在记录本场RR后再更新）
                if self.recovery_rate == 10.0:
                    rr_collapsed = True
                    
        # 3. 时空移动损耗
        transport_loss = 0.0
        if force_extreme_transport:
            # 最差环境预设（2）：日期跨度未知，强制触发极端转场，直接预扣20%
            transport_loss = 20.0
            loss_details["极端转场"] = transport_loss
        elif concert.transport == "航空" or concert.transport == "飞机":
            transport_loss = 15.0
            loss_details["差旅(航空)"] = transport_loss
        elif concert.transport == "高铁" and concert.transport_duration >= 5:
            transport_loss = 10.0
            loss_details["差旅(长途高铁)"] = transport_loss
        else:
            transport_loss = 5.0
            loss_details["差旅(其他)"] = transport_loss
        total_loss += transport_loss
        
        # 4. 红眼惩罚：检查特殊说明是否包含"红眼"关键词
        if concert.special_note and "红眼" in concert.special_note:
            total_loss += 20
            loss_details["红眼惩罚"] = 20.0
        
        # 5. 应急损耗：两场演出间隔≤24h且涉及跨省位移
        # 优先从演唱会名称/场馆自动推断城市；若无法推断则依赖 special_note 显式声明
        if previous_concert and days_since_last <= 0:
            if self._detect_cross_province(concert, previous_concert) or '跨省' in concert.special_note:
                if concert.venue != previous_concert.venue:
                    total_loss += 10
                    loss_details["应急损耗(跨省)"] = 10.0
        
        return total_loss, rr_collapsed, loss_details
    
    def audit_concert(self, concert: ConcertInfo, previous_be: float = 100.0, 
                     days_since_last: int = 0, previous_concerts: List[ConcertInfo] = None) -> AuditResult:
        """对单场演唱会进行审计
        
        Args:
            concert: 当前场次演唱会信息
            previous_be: 上一场结束后的BE值
            days_since_last: 距离上一场的天数
            previous_concerts: 历史演唱会列表（包括当前场次及之前的所有场次）
        """
        if previous_concerts is None:
            previous_concerts = []
        # 计算演出价值分
        score, score_details = self.calculate_score(concert, previous_concerts)
        
        # 确定定级
        if score > 10:
            grade = VenueGrade.S_PLUS.value
        elif score == 10:
            grade = VenueGrade.S.value
        elif 7 <= score < 10:
            grade = VenueGrade.A.value
        else:
            grade = VenueGrade.C.value
        
        # 获取安保等级
        # 最差环境预设（1）：若场馆名为空，强制锁定为高安保等级（全维度物理封锁区）
        # 后果：仅核准 MT-01（手机）方案，所有长焦/可拆卸器材被拦截
        if not concert.venue:
            security_level = SecurityLevel.HIGH
            venue_unknown = True
        else:
            security_level = self.get_security_level(concert.venue)
            venue_unknown = False
        
        # 计算审计前的可用余额（用于决策）
        # 名义余额 = 初始余额 - 已支出（不包括本场）
        pre_audit_nominal_balance = self.initial_balance - self.total_spent
        
        # 计算审计前的未退押金占用额（不包括本场）
        # 根据当前场次日期，过滤掉已经退回的押金
        # 押金会在"演唱会结束（不算演唱会当天）后的第7天"退回
        # 即：演唱会日期 + 7天（不算演唱会当天，从次日起数第7天）
        # 在退回日期当天押金尚未到账（>=），次日方可用于新场次审计
        current_date = datetime.strptime(concert.date, "%Y-%m-%d")
        # 清理已经退回的押金（退回日期 < 当前日期）
        self.deposits = [d for d in self.deposits if d["return_date"] >= current_date]
        pre_audit_deposit_occupied = sum(d["deposit"] for d in self.deposits)
        
        # 审计前的实际可用余额 = 名义余额 - 未退押金（用于决策）
        pre_audit_available_balance = pre_audit_nominal_balance - pre_audit_deposit_occupied
        
        # 计算初始BE
        # 本场初始 BE = 上场残余 % + 休整天数 × RR
        # 计算结算数值（可能超过100%）
        # days_since_last = -1 为特殊标记（最差环境预设（3）：日期跨度未知），此时不进行BE恢复
        if days_since_last < 0:
            calculated_be = previous_be  # 日期跨度未知，保守处理：不恢复BE
        else:
            calculated_be = previous_be + days_since_last * self.recovery_rate
        # 如果结算数值 > 100%，则强制显示为 100% 封顶
        initial_be = min(100.0, calculated_be)
        
        # C级直接熔断：在计算完余额变量后返回，确保现金流数据正确
        if grade == VenueGrade.C.value:
            return AuditResult(
                nominal_balance=pre_audit_nominal_balance,
                deposit_occupied=pre_audit_deposit_occupied,
                actual_available_balance=pre_audit_available_balance,
                hotel_selection="",
                transport_selection="",
                ticket_selection="",
                security_level=security_level.value,
                initial_be=initial_be,
                previous_be=previous_be,
                days_since_last=days_since_last,
                recovery_rate=self.recovery_rate,
                score=score,
                grade=grade,
                is_cancelled=True,
                equipment_selection_logic="本场次已熔断，无需选择器材",
                score_details=score_details
            )
        
        # 检查体力红线拦截
        if initial_be <= 10:
            # C级熔断时，现金流仍为审计前的值
            return AuditResult(
                nominal_balance=pre_audit_nominal_balance,
                deposit_occupied=pre_audit_deposit_occupied,
                actual_available_balance=pre_audit_available_balance,
                hotel_selection="",
                transport_selection="",
                ticket_selection="",
                security_level=security_level.value,
                initial_be=initial_be,
                recovery_rate=self.recovery_rate,
                previous_be=previous_be,
                days_since_last=days_since_last,
                score=score,
                grade=grade,
                is_cancelled=True,
                equipment_selection_logic="本场次因体力红线拦截已熔断，无需选择器材",
                score_details=score_details
            )
        
        # === A级零溢价熔断检查（SP 七.3）===
        # A级财务红线：硬性零溢价。任何形式的代抢费或溢价均视为财务违规，直接熔断本场次规划。
        if grade == VenueGrade.A.value and concert.ticket_original > 0:
            premium_amount = concert.ticket_actual - concert.ticket_original
            if premium_amount > 0:
                return AuditResult(
                    nominal_balance=pre_audit_nominal_balance,
                    deposit_occupied=pre_audit_deposit_occupied,
                    actual_available_balance=pre_audit_available_balance,
                    hotel_selection="",
                    transport_selection="",
                    ticket_selection=f"{concert.seat_area} {concert.seat_row} 排；票面原价 {concert.ticket_original} 元，实付 {concert.ticket_actual} 元（溢价 {premium_amount} 元）",
                    security_level=security_level.value,
                    initial_be=initial_be,
                    previous_be=previous_be,
                    days_since_last=days_since_last,
                    recovery_rate=self.recovery_rate,
                    score=score,
                    grade=grade,
                    is_cancelled=True,
                    equipment_selection_logic=f"A级场次财务违规熔断（SP 七.3）：A级硬性零溢价红线，实付 {concert.ticket_actual} 元超出票面原价 {concert.ticket_original} 元（溢价 {premium_amount} 元），直接熔断本场次规划，预算原数返回账户。",
                    score_details=score_details
                )
        
        # ========== 统一降级漏斗执行（SP 十一.二）==========
        # 在选择酒店和交通之前，先执行统一降级漏斗
        # 降级漏斗会按顺序执行：第一层（单点降级）→ 第二层（中度财务预警）→ 第三层（极限生存）→ 第四层（熔断）
        downgrade_result, meltdown_reason = self.execute_downgrade_funnel(
            concert, pre_audit_available_balance, initial_be, score, grade, security_level,
            pre_audit_nominal_balance=pre_audit_nominal_balance
        )
        
        # 如果降级漏斗返回熔断，直接返回熔断结果
        if meltdown_reason:
            return AuditResult(
                nominal_balance=pre_audit_nominal_balance,
                deposit_occupied=pre_audit_deposit_occupied,
                actual_available_balance=pre_audit_available_balance,
                hotel_selection="",
                transport_selection="",
                ticket_selection=f"{concert.seat_area} {concert.seat_row} 排；票面原价 {concert.ticket_original} 元，实付 {concert.ticket_actual} 元",
                security_level=security_level.value,
                initial_be=initial_be,
                previous_be=previous_be,
                days_since_last=days_since_last,
                recovery_rate=self.recovery_rate,
                score=score,
                grade=grade,
                is_cancelled=True,
                equipment_selection_logic=f"降级漏斗熔断：{meltdown_reason}",
                score_details=score_details
            )
        
        # 提取降级结果
        funnel_hotel_tier = downgrade_result["hotel_tier"]
        funnel_hotel_name = downgrade_result["hotel_name"]
        funnel_downgrade_logs = downgrade_result["downgrade_logs"]
        premium_downgrade_executed = downgrade_result["premium_downgrade_executed"]
        survival_mode_active = downgrade_result.get("survival_mode_active", False)
        
        # 确定酒店和交通方式
        # 降级漏斗已经处理了降级逻辑，这里使用漏斗返回的结果
        hotel_tier = funnel_hotel_tier
        hotel_name = funnel_hotel_name
        
        # 如果有多个选项，在降级漏斗约束下选择最优方案
        # 根据SP 六.6 多方案合规效用最大化与组合择优逻辑
        if (concert.hotel_options or concert.transport_options) and not funnel_downgrade_logs:
            # 准备选项列表
            hotel_opts = concert.hotel_options if concert.hotel_options else [HotelOption(name=concert.hotel_name, cost=concert.hotel_cost)]
            transport_opts = concert.transport_options if concert.transport_options else [TransportOption(transport=concert.transport, cost=concert.transport_cost, duration=concert.transport_duration, duration_from_input=concert.transport_duration_from_input)]
            
            # 根据降级漏斗的强制降级结果过滤酒店选项
            # 注意：只有当降级漏斗明确执行了降级动作（有降级日志）时，才进行过滤
            # 否则让效用矩阵择优逻辑通过余额准入红线自行控制
            if funnel_downgrade_logs:
                # 如果漏斗强制降级到T3（如A级场次、极限生存模式），只能选择T3酒店
                if hotel_tier == HotelTier.T3:
                    t3_brands = HOTEL_BRANDS["T3"]
                    filtered_hotel_opts = [opt for opt in hotel_opts if any(brand in opt.name for brand in t3_brands)]
                    if filtered_hotel_opts:
                        hotel_opts = filtered_hotel_opts
                elif hotel_tier == HotelTier.T2:
                    # 如果漏斗强制降级到T2（如中度财务预警），排除T1选项
                    t1_brands = HOTEL_BRANDS["T1"]
                    filtered_hotel_opts = [opt for opt in hotel_opts if not any(brand in opt.name for brand in t1_brands)]
                    if filtered_hotel_opts:
                        hotel_opts = filtered_hotel_opts
            
            # === SP 六.6 多方案合规效用最大化与组合择优逻辑 ===
            # 第一步：构建效用降序矩阵（排列组合）
            # 主排序键（优先）：酒店级别（T1 > T2 > T3）
            # 次排序键（从属）：交通金额（高价 > 低价）
            
            # 酒店等级优先级映射（数值越小优先级越高）
            hotel_tier_priority = {HotelTier.T1: 0, HotelTier.T2: 1, HotelTier.T3: 2}
            
            # 酒店等级对应的余额准入红线（SP 六.5 保守避险协议）
            # T1需要余额>8000元，T2需要余额>=4000元，T3无下限
            hotel_tier_balance_threshold = {
                HotelTier.T1: 8000,
                HotelTier.T2: 4000,
                HotelTier.T3: 0
            }
            
            # 构建所有组合并计算效用排序值
            all_combinations = []
            for hotel_opt in hotel_opts:
                opt_hotel_tier = get_hotel_tier_by_name(hotel_opt.name)
                for transport_opt in transport_opts:
                    total_cost = transport_opt.cost + hotel_opt.cost
                    # 排序键：(酒店等级优先级, -酒店费用, -交通费用) - 酒店等级越高越优先，同等级下酒店费用越高越优先，再按交通费用高优先
                    sort_key = (hotel_tier_priority.get(opt_hotel_tier, 2), -hotel_opt.cost, -transport_opt.cost)
                    all_combinations.append((hotel_opt, transport_opt, total_cost, opt_hotel_tier, sort_key))
            
            # 按效用降序排序（酒店等级高优先，同等级下酒店费用高优先，再按交通费用高优先）
            all_combinations.sort(key=lambda x: x[4])
            
            # 第二步：自上向下阈值对撞
            # 从最顶部的组合开始，依次向下代入金额进行核算
            best_combination = None
            combination_selection_logic = None  # 记录选择逻辑
            checked_combinations = []  # 记录检查过的组合
            
            for idx, (hotel_opt, transport_opt, total_cost, opt_hotel_tier, _) in enumerate(all_combinations):
                # 计算选择该组合后的剩余余额
                # 剩余余额 = 审计前可用余额 - 门票实付 - 酒店费用 - 交通费用
                remaining_balance = pre_audit_available_balance - concert.ticket_actual - hotel_opt.cost - transport_opt.cost
                
                # 获取该酒店等级的余额准入红线
                balance_threshold = hotel_tier_balance_threshold.get(opt_hotel_tier, 0)
                
                # 记录检查过程
                checked_combinations.append(f"[{opt_hotel_tier.value}+{transport_opt.transport}({transport_opt.cost}元)]余额{remaining_balance:.0f}元{'≥' if remaining_balance >= balance_threshold else '<'}{balance_threshold}元")
                
                # 检查是否满足余额准入红线
                if remaining_balance >= balance_threshold:
                    # 全合规直接锁定：满足该酒店等级的余额准入要求
                    best_combination = (hotel_opt, transport_opt)
                    if idx == 0:
                        combination_selection_logic = f"效用矩阵择优：首选组合[{opt_hotel_tier.value}+{transport_opt.transport}]满足{opt_hotel_tier.value}准入红线（余额{remaining_balance:.0f}元≥{balance_threshold}元），直接锁定"
                    else:
                        combination_selection_logic = f"效用矩阵择优：经{idx+1}轮阈值对撞，组合[{opt_hotel_tier.value}+{transport_opt.transport}]满足{opt_hotel_tier.value}准入红线（余额{remaining_balance:.0f}元≥{balance_threshold}元）"
                    break
                # 若不满足，继续顺延至下一个组合（第三步：自动抵补与越级回撤）
            
            # 第四步：终局判定
            # 如果遍历完所有组合都不满足，选择最后一个（最低配置）
            if best_combination is None and all_combinations:
                last_combo = all_combinations[-1]
                best_combination = (last_combo[0], last_combo[1])
                last_hotel_tier = last_combo[3]
                combination_selection_logic = f"效用矩阵择优：所有组合均未达标，终局选择最低配置[{last_hotel_tier.value}+{last_combo[1].transport}]"
            
            # 更新concert的信息
            if best_combination:
                selected_hotel = best_combination[0]
                selected_transport_opt = best_combination[1]
                concert.hotel_name = selected_hotel.name
                concert.hotel_cost = selected_hotel.cost
                concert.transport = selected_transport_opt.transport
                concert.transport_cost = selected_transport_opt.cost
                concert.transport_duration = selected_transport_opt.duration
                concert.transport_duration_from_input = selected_transport_opt.duration_from_input
                
                # 重新确定酒店等级
                hotel_tier = get_hotel_tier_by_name(concert.hotel_name)
                hotel_name = concert.hotel_name
        else:
            # 没有多选项或已执行溢价降级，无需效用矩阵择优
            combination_selection_logic = None

        # 多选项交通在漏斗已执行降级时不进入效用矩阵，需在漏斗锁定的酒店下单独择定（SP 六.6 / 七.1）
        transport_resolution_logic = None
        if concert.transport_options and not concert.transport and concert.transport_cost == 0:
            if premium_downgrade_executed:
                chosen = min(concert.transport_options, key=lambda x: x.cost)
                chosen_cost = min(chosen.cost, 200.0)
                transport_resolution_logic = "多选项交通：溢价抵补采用最低价格方案"
            else:
                threshold = {HotelTier.T1: 8000, HotelTier.T2: 4000, HotelTier.T3: 0}.get(hotel_tier, 0)
                ordered = sorted(concert.transport_options, key=lambda x: -x.cost)
                chosen = ordered[-1]
                for opt in ordered:
                    remaining = pre_audit_available_balance - concert.ticket_actual - concert.hotel_cost - opt.cost
                    if remaining >= threshold:
                        chosen = opt
                        break
                chosen_cost = chosen.cost
                transport_resolution_logic = (
                    f"多选项交通：在漏斗锁定的{hotel_tier.value}级酒店下自上而下择定"
                    f"[{chosen.transport}({chosen.cost}元)]"
                )
            concert.transport = chosen.transport
            concert.transport_cost = chosen_cost
            concert.transport_duration = chosen.duration
            concert.transport_duration_from_input = chosen.duration_from_input
        
        # 生成酒店选择文本
        hotel_selection = f"{hotel_tier.value}级 - {hotel_name}；实付 {concert.hotel_cost:.2f} 元"
        if funnel_downgrade_logs:
            hotel_selection += f"（⚠️ 降级漏斗：{'; '.join(funnel_downgrade_logs)}）"
        elif combination_selection_logic:
            hotel_selection += f"（📊 {combination_selection_logic}）"
        
        # 交通方式
        duration_str = f"（{concert.transport_duration}h）" if concert.transport_duration_from_input else ""
        transport_selection = f"{concert.transport}{duration_str}；实付 {concert.transport_cost} 元"
        if premium_downgrade_executed:
            transport_selection += "（⚠️ 溢价抵补强制降级）"
        if transport_resolution_logic:
            transport_selection += f"（📊 {transport_resolution_logic}）"
        
        # 门票选择
        premium = concert.ticket_actual - concert.ticket_original
        if premium > 0:
            ticket_selection = f"{concert.seat_area} {concert.seat_row} 排；票面原价 {concert.ticket_original} 元，实付 {concert.ticket_actual} 元（溢价 {premium} 元）"
        else:
            ticket_selection = f"{concert.seat_area} {concert.seat_row} 排；实付 {concert.ticket_actual} 元"
        
        # 计算基础支出（不含器材）：门票 + 交通 + 酒店
        base_cost = concert.ticket_actual + concert.transport_cost + concert.hotel_cost
        
        # 检查当前酒店是否已经是T3等级（用于后续熔断判断）
        is_t3_hotel = (hotel_tier == HotelTier.T3)
        
        # 缓冲金资格预计算（实际决策在器材选定后统一执行 SP 八.三）
        buffer_indicator_b = (
            concert.want_view_count >= 100.0 or
            (concert.ticket_original > 0 and concert.ticket_actual >= concert.ticket_original * 3)
        )
        original_pre_audit_available_balance = pre_audit_available_balance
        buffer_fund_eligible = (grade == VenueGrade.S_PLUS.value and score >= 13 and buffer_indicator_b)
        
        # 基础支出熔断检查（二次保险，仅对不满足缓冲金资格的场次生效）
        # 满足缓冲金资格的场次由后续 SP 八.三 统一处理（可能通过极限生存模式挽救）
        if base_cost > pre_audit_available_balance and is_t3_hotel and not buffer_fund_eligible:
            result = AuditResult(
                nominal_balance=pre_audit_nominal_balance,
                deposit_occupied=pre_audit_deposit_occupied,
                actual_available_balance=original_pre_audit_available_balance,
                hotel_selection=hotel_selection,
                transport_selection=transport_selection,
                ticket_selection=ticket_selection,
                security_level=security_level.value,
                initial_be=initial_be,
                recovery_rate=self.recovery_rate,
                total_loss=0.0,
                final_be=initial_be,
                previous_be=previous_be,
                days_since_last=days_since_last,
                score=score,
                grade=grade,
                is_cancelled=True,
                score_details=score_details,
                equipment=None,
                equipment_selection_logic=f"财务崩盘熔断（SP 九.一.2）：基础支出（门票{concert.ticket_actual:.2f} + 交通{concert.transport_cost:.2f} + 酒店{concert.hotel_cost:.2f} = {base_cost:.2f}元）> 实际可用余额 {original_pre_audit_available_balance:.2f}元，且酒店已为T3等级，本场不做任何安排，预算原数返回账户",
                ticket_cost=concert.ticket_actual,
                transport_cost=concert.transport_cost,
                hotel_cost=concert.hotel_cost,
            )
            return result
        
        # 确定器材
        available_balance = pre_audit_available_balance - concert.transport_cost - concert.hotel_cost - concert.ticket_actual
        
        if survival_mode_active:
            # 极限生存模式：器材强制锁定 MT-01（SP 十一.二 第三层）
            # 但需校验余额是否足以支付 MT-01（租金+押金=3100元），不足则以无器材状态执行
            mt01 = EQUIPMENT_LIB["MT-01"]
            mt01_total_cost = mt01.rent + mt01.deposit
            if available_balance >= mt01_total_cost:
                equipment_code = "MT-01"
                equipment_logic = "极限生存模式强制锁定MT-01（SP 十一.二 第三层）"
            else:
                equipment_code = None
                equipment_logic = (f"极限生存模式：MT-01亦不可用（需{mt01_total_cost}元，"
                                   f"余{available_balance:.2f}元），以无器材状态执行")
        else:
            # 正常选择（基于实际可用余额，不膨胀缓冲金）
            equipment_code, equipment_logic = self.determine_equipment(concert, security_level, 
                                                      available_balance, initial_be, grade)
        if equipment_code:
            equipment = EQUIPMENT_LIB[equipment_code]
            equipment_name = f"{equipment_code} ({equipment.name})"
        else:
            equipment_name = "无"

        # === SP 六.5 保守避险协议：第二重审计（最终账面检查） ===
        # 在器材确定后，必须减去【当前所有未退回的器材押金】及【本场待付的器材租金】进行再次核算
        # 如果第二重审计后余额不够8000元，强制降级至T2标准级
        if equipment_code and hotel_tier == HotelTier.T1:
            equipment_for_audit = EQUIPMENT_LIB[equipment_code]
            # 第二重审计余额 = 第一重审计余额 - 本场器材押金 - 本场器材租金
            # 注意：pre_audit_available_balance 已经减去了未退回的历史器材押金
            second_audit_balance = (pre_audit_available_balance - concert.ticket_actual - 
                                   concert.transport_cost - concert.hotel_cost 
                                    - equipment_for_audit.rent)
            
            if second_audit_balance < 8000:
                # 第二重审计不通过，强制降级至T2标准级
                old_hotel_tier = hotel_tier
                old_hotel_name = concert.hotel_name
                old_hotel_cost = concert.hotel_cost
                
                # 优先从用户提供的选项中选择T2酒店
                t2_selected = False
                if concert.hotel_options:
                    t2_brands = HOTEL_BRANDS["T2"]
                    t2_options = [opt for opt in concert.hotel_options 
                                 if any(brand in opt.name for brand in t2_brands)]
                    if t2_options:
                        selected_t2 = min(t2_options, key=lambda x: x.cost)
                        concert.hotel_name = selected_t2.name
                        concert.hotel_cost = selected_t2.cost
                        t2_selected = True
                
                if not t2_selected:
                    # 无T2选项，使用T2默认酒店配置
                    concert.hotel_name = DEFAULT_HOTELS["T2"]["name"]
                    concert.hotel_cost = DEFAULT_HOTELS["T2"]["cost"]
                
                hotel_tier = HotelTier.T2
                hotel_name = concert.hotel_name
                hotel_selection = (f"{hotel_tier.value}级 - {hotel_name}；实付 {concert.hotel_cost:.2f} 元"
                                  f"（⚠️ 保守避险协议-第二重审计：扣除器材"
                                  f"租金{equipment_for_audit.rent}元后，余额{second_audit_balance:.0f}元<8000元，"
                                  f"强制由{old_hotel_tier.value}级降至T2级）")
        
        # 计算体力损耗
        # 获取前一场演唱会信息（用于应急损耗判断）
        previous_concert = previous_concerts[-1] if previous_concerts else None
        
        # 最差环境预设（2）：若用户未提供具体排数或座位区域，强制锁定"内场站席 + 极端转场"
        # 后果：单场体力损耗直接按 50%（30%站立 + 20%红眼/位移）进行预扣
        worst_case_be_applied = False
        if not concert.seat_area:
            concert.seat_area = "内场站席"
            worst_case_be_applied = True
        # 若日期跨度无法确定（days_since_last < 0 为特殊标记），强制触发极端转场
        force_extreme_transport = (days_since_last < 0)
        if force_extreme_transport:
            days_since_last = 0  # 恢复为0，极端转场损耗在calculate_be_loss中单独处理
            worst_case_be_applied = True  # 日期跨度未知也触发最差预设
        
        # 记录本场实际使用的RR（坍塌前的值），用于输出展示
        rr_used_this_session = self.recovery_rate
        total_loss, rr_collapsed, loss_details = self.calculate_be_loss(concert, equipment_code, days_since_last, previous_concert, force_extreme_transport)
        # 若本场首次触发RR坍塌，在记录完本场RR后再更新（坍塌从下一场开始生效）
        if rr_collapsed:
            self.recovery_rate = 8.0
        
        # 计算离场BE
        final_be = max(0.0, initial_be - total_loss)
        
        # 最差环境预设（2）后果：若扣除后剩余体力≤25%，强制将机酒预算上调至T1豪华级进行机能代偿
        # 注意：此处用 final_be（扣除后）而非 initial_be 进行判断
        if worst_case_be_applied and final_be <= 25.0:
            # 强制升级酒店至T1豪华级
            t1_brands = HOTEL_BRANDS["T1"]
            is_already_t1 = any(brand in concert.hotel_name for brand in t1_brands)
            if not is_already_t1:
                # 优先从用户提供的选项中选择T1酒店
                if concert.hotel_options:
                    t1_options = [opt for opt in concert.hotel_options if any(brand in opt.name for brand in t1_brands)]
                    if t1_options:
                        selected_t1 = min(t1_options, key=lambda x: x.cost)
                        concert.hotel_name = selected_t1.name
                        concert.hotel_cost = selected_t1.cost
                    else:
                        # 无T1选项，使用T1默认酒店配置
                        concert.hotel_name = DEFAULT_HOTELS["T1"]["name"]
                        concert.hotel_cost = DEFAULT_HOTELS["T1"]["cost"]
                else:
                    concert.hotel_name = DEFAULT_HOTELS["T1"]["name"]
                    concert.hotel_cost = DEFAULT_HOTELS["T1"]["cost"]
                hotel_selection = f"T1级 - {concert.hotel_name}；实付 {concert.hotel_cost:.2f} 元（⚠️ 最差环境预设（2）：座位信息缺失，预设内场站席，离场BE={final_be:.1f}%≤25%，强制机能代偿升级至T1豪华级）"

        # 计算本场总支出
        this_concert_cost = concert.ticket_actual + concert.transport_cost + concert.hotel_cost
        equipment_rent = 0.0
        equipment_deposit = 0.0
        if equipment_code:
            equipment = EQUIPMENT_LIB[equipment_code]
            equipment_rent = equipment.rent
            equipment_deposit = equipment.deposit
            this_concert_cost += equipment_rent
        
        # ===== SP 八.三 风险缓冲金"降级优先"补偿协议（统一检查点）=====
        risk_buffer = None
        total_cost_with_deposit = this_concert_cost + equipment_deposit
        has_funding_gap = total_cost_with_deposit > original_pre_audit_available_balance
        
        if buffer_fund_eligible and has_funding_gap:
            # 满足缓冲金申请条件（得分≥13 + 稀缺度校验）且存在资金缺口
            
            # === 第一步：资产状态前置确认 — 强制极限生存模式 ===
            # SP 十一.二 第三层：在试图申请动用"风险缓冲金"进行补差之前，必须先确认处于极限生存模式
            if not survival_mode_active:
                actually_modified = self._apply_survival_mode(concert)
                survival_mode_active = True
                if actually_modified:
                    hotel_tier = HotelTier.T3
                    hotel_name = concert.hotel_name
                
                # 器材强制至 MT-01
                survival_eq = EQUIPMENT_LIB["MT-01"]
                equipment_code = "MT-01"
                equipment_name = f"MT-01 ({survival_eq.name})"
                equipment_rent = survival_eq.rent
                equipment_deposit = survival_eq.deposit
                equipment_logic = "SP八.三缓冲金降级优先协议：强制极限生存模式，器材锁定MT-01"
                
                # 重算本场总支出
                this_concert_cost = (concert.ticket_actual + concert.transport_cost 
                                    + concert.hotel_cost + equipment_rent)
                total_cost_with_deposit = this_concert_cost + equipment_deposit
                
                # 更新显示文本
                hotel_selection = (f"{hotel_tier.value}级 - {hotel_name}；实付 {concert.hotel_cost:.2f} 元"
                                  f"（⚠️ SP八.三缓冲金降级优先协议：强制极限生存模式）")
                duration_str = f"（{concert.transport_duration}h）" if concert.transport_duration_from_input else ""
                transport_selection = (f"{concert.transport}{duration_str}；"
                                      f"实付 {concert.transport_cost} 元"
                                      f"（⚠️ SP八.三极限生存模式）")
            
            # === 第二步：动态缺口对冲 ===
            survival_gap = total_cost_with_deposit - original_pre_audit_available_balance
            
            if survival_gap <= 0:
                # 场景A：降级后无缺口，取消缓冲金拨付，保留额度供后续场次使用
                risk_buffer = None
            else:
                # 场景B：降级后仍有缺口，启动缓冲金注入
                buffer_remaining = self.risk_buffer_total - self.risk_buffer_used
                if survival_gap <= buffer_remaining:
                    risk_buffer = survival_gap
                    self.risk_buffer_used += survival_gap
                else:
                    # === 第三步：终极熔断判定 ===
                    # T3 + 最低交通 + MT-01 + 全部缓冲金后仍为负 → 财务崩盘
                    return AuditResult(
                        nominal_balance=pre_audit_nominal_balance,
                        deposit_occupied=pre_audit_deposit_occupied,
                        actual_available_balance=original_pre_audit_available_balance,
                        hotel_selection=hotel_selection,
                        transport_selection=transport_selection,
                        ticket_selection=ticket_selection,
                        security_level=security_level.value,
                        initial_be=initial_be,
                        recovery_rate=self.recovery_rate,
                        total_loss=0.0,
                        final_be=initial_be,
                        previous_be=previous_be,
                        days_since_last=days_since_last,
                        score=score,
                        grade=grade,
                        is_cancelled=True,
                        score_details=score_details,
                        equipment=None,
                        equipment_selection_logic=(
                            f"SP八.三终极熔断：极限生存模式（T3+最低交通+MT-01）下总支出"
                            f"{total_cost_with_deposit:.2f}元 > 可用余额"
                            f"{original_pre_audit_available_balance:.2f}元，"
                            f"缺口{survival_gap:.2f}元 > 剩余缓冲金{buffer_remaining:.2f}元，"
                            f"注入全部缓冲金后仍为负数，强制熔断"
                        ),
                        ticket_cost=concert.ticket_actual,
                        transport_cost=concert.transport_cost,
                        hotel_cost=concert.hotel_cost,
                    )
        
        # 实时现金流穿透审计显示的是本场开始前的金额状态
        # 名义余额 = 初始余额 - 已支出（不包括本场）
        # 未退押金占用额 = 本场开始前的未退押金（不包括本场押金）
        # 实际可用余额 = 名义余额 - 未退押金（不包括本场）
        
        # 创建结果对象（使用本场开始前的现金流）
        # 注意：actual_available_balance 使用原始值（不含风险缓冲金），确保报告显示正确的实际可用余额
        result = AuditResult(
            nominal_balance=pre_audit_nominal_balance,
            deposit_occupied=pre_audit_deposit_occupied,
            actual_available_balance=original_pre_audit_available_balance,
            hotel_selection=hotel_selection,
            transport_selection=transport_selection,
            ticket_selection=ticket_selection,
            security_level=security_level.value,
            initial_be=initial_be,
            recovery_rate=rr_used_this_session,
            total_loss=total_loss,
            final_be=final_be,
            previous_be=previous_be,
            days_since_last=days_since_last,
            loss_details=loss_details,
            score=score,
            grade=grade,
            risk_buffer=risk_buffer,
            buffer_indicator_a=(score >= 13) if grade == VenueGrade.S_PLUS.value else None,
            buffer_indicator_b=buffer_indicator_b if grade == VenueGrade.S_PLUS.value else None,
            rr_collapsed_this_session=rr_collapsed,
            rr_collapse_reason=(
                f"本场使用重型器材（{EQUIPMENT_LIB[equipment_code].name} {equipment_code}，"
                f"重量{EQUIPMENT_LIB[equipment_code].weight}kg / 伸缩{EQUIPMENT_LIB[equipment_code].length}mm），"
                f"首次触发RR永久坍塌：10% → 8%，自下一场起生效"
            ) if rr_collapsed else None,
            equipment=equipment_name,
            equipment_selection_logic=equipment_logic,
            equipment_rent=equipment_rent if equipment_code else None,
            equipment_deposit=equipment_deposit if equipment_code else None,
            ticket_cost=concert.ticket_actual,
            transport_cost=concert.transport_cost,
            hotel_cost=concert.hotel_cost,
            score_details=score_details
        )
        
        # 更新总支出和押金
        self.total_spent += this_concert_cost
        if equipment_code:
            equipment = EQUIPMENT_LIB[equipment_code]
            # 押金会在"演唱会结束（不算演唱会当天）后的第7天"退回
            # 即：演唱会日期 + 7天 
            concert_date = datetime.strptime(concert.date, "%Y-%m-%d")
            return_date = concert_date + timedelta(days=7)
            self.deposits.append({
                "equipment_code": equipment_code,
                "deposit": equipment.deposit,
                "return_date": return_date
            })
        
        # 更新当前BE
        self.current_be = result.final_be
        
        return result
    
    def generate_audit_report(self, results: List[AuditResult], is_annual_plan: bool = False) -> str:
        """生成审计报告
        
        Args:
            results: 审计结果列表
            is_annual_plan: 是否为全年规划触发（只有全年规划触发时才输出年度资产总结报告）
        """
        report = []
        report.append("=" * 80)
        report.append("演唱会审计结论报告")
        report.append("=" * 80)
        report.append("")
        
        for i, result in enumerate(results, 1):
            report.append(f"【第{i}场审计结论】")
            report.append("-" * 80)
            
            if result.is_cancelled:
                # 判断熔断类型
                is_financial_meltdown = result.equipment_selection_logic and "财务崩盘熔断" in result.equipment_selection_logic
                is_a_grade_premium_meltdown = result.equipment_selection_logic and "A级场次财务违规熔断" in result.equipment_selection_logic
                is_s_grade_premium_meltdown = result.equipment_selection_logic and "S级溢价超30%熔断" in result.equipment_selection_logic
                is_stamina_meltdown = result.equipment_selection_logic and "体力红线拦截已熔断" in result.equipment_selection_logic
                is_c_grade_meltdown = result.grade == "C"
                
                # 非C级熔断的统一话术
                non_c_meltdown_notice = "本场熔断，该场次关联的所有资金将统一回收。"
                
                if is_financial_meltdown:
                    # 财务崩盘熔断
                    report.append(f"❌ 财务崩盘熔断：本场预期支出超过实际可用余额，且酒店已为T3等级。")
                    report.append(f"   {result.equipment_selection_logic}")
                    report.append("")
                    report.append("1. 实时现金流穿透审计")
                    report.append(f"   （1）名义余额：{result.nominal_balance:.2f} 元")
                    report.append(f"   （2）未退押金占用额：{result.deposit_occupied:.2f} 元")
                    report.append(f"   （3）实际可用余额：{result.actual_available_balance:.2f} 元")
                    report.append(f"   （4）酒店选择：{result.hotel_selection}")
                    report.append(f"   （5）交通方式选择：{result.transport_selection}")
                    report.append(f"   （6）门票选择：{result.ticket_selection}")
                    # 预计支出汇总
                    if result.ticket_cost is not None and result.transport_cost is not None and result.hotel_cost is not None:
                        predicted_spend = result.ticket_cost + result.transport_cost + result.hotel_cost
                        report.append(f"   ──────────────────────────────")
                        report.append(f"   预计本场总支出：{predicted_spend:.2f} 元（门票 {result.ticket_cost:.2f} + 交通 {result.transport_cost:.2f} + 酒店 {result.hotel_cost:.2f}），超出实际可用余额 {result.actual_available_balance:.2f} 元，已熴断")
                    report.append("")
                    report.append(non_c_meltdown_notice)
                elif is_a_grade_premium_meltdown:
                    # A级零溢价熔断
                    report.append(f"❌ A级场次财务违规熔断（SP 七.3）：硬性零溢价红线触发，本场次规划直接熔断。")
                    report.append(f"   {result.equipment_selection_logic}")
                    report.append("")
                    report.append("1. 实时现金流穿透审计")
                    report.append(f"   （1）名义余额：{result.nominal_balance:.2f} 元")
                    report.append(f"   （2）未退押金占用额：{result.deposit_occupied:.2f} 元")
                    report.append(f"   （3）实际可用余额：{result.actual_available_balance:.2f} 元")
                    report.append(f"   （4）门票（违规项）：{result.ticket_selection}")
                    report.append("")
                    report.append("4. 演出价值分定格与定级")
                    report.append(f"   （1）定级判决：{result.score} 分 → {result.grade} 级")
                    report.append("")
                    report.append(non_c_meltdown_notice)
                elif is_s_grade_premium_meltdown:
                    # S级溢价超30%熔断
                    report.append(f"❌ S级溢价超30%熔断（SP 七.2）：机酒降级后余额仍为负，强制熔断本场次规划。")
                    report.append(f"   {result.equipment_selection_logic}")
                    report.append("")
                    report.append("1. 实时现金流穿透审计")
                    report.append(f"   （1）名义余额：{result.nominal_balance:.2f} 元")
                    report.append(f"   （2）未退押金占用额：{result.deposit_occupied:.2f} 元")
                    report.append(f"   （3）实际可用余额：{result.actual_available_balance:.2f} 元")
                    report.append(f"   （4）门票（违规项）：{result.ticket_selection}")
                    report.append("")
                    report.append("4. 演出价值分定格与定级")
                    report.append(f"   （1）定级判决：{result.score} 分 → {result.grade} 级")
                    report.append("")
                    report.append(non_c_meltdown_notice)
                elif is_stamina_meltdown:
                    # 体力红线熔断
                    report.append(f"❌ 体力红线拦截熔断：当前体力值低于执行阈值，无法执行本场次。")
                    report.append(f"   {result.equipment_selection_logic}")
                    report.append("")
                    report.append("1. 实时现金流穿透审计")
                    report.append(f"   （1）名义余额：{result.nominal_balance:.2f} 元")
                    report.append(f"   （2）未退押金占用额：{result.deposit_occupied:.2f} 元")
                    report.append(f"   （3）实际可用余额：{result.actual_available_balance:.2f} 元")
                    report.append("")
                    report.append("2. 体力状态")
                    report.append(f"   （1）初始体力值：{result.initial_be:.2f}")
                    report.append(f"   （2）上场结束体力值：{result.previous_be:.2f}")
                    report.append(f"   （3）距上场天数：{result.days_since_last} 天")
                    report.append("")
                    report.append("4. 演出价值分定格与定级")
                    report.append(f"   （1）定级判决：{result.score} 分 → {result.grade} 级")
                    report.append("")
                    report.append(non_c_meltdown_notice)
                elif is_c_grade_meltdown:
                    # C级逻辑熔断
                    report.append(f"❌ 本场次综合评分为 {result.score} 分，系统已将其标记为\"无效逻辑点\"，执行资产清算。")
                    report.append("本场次不产生任何实际支出与体力损耗，该笔预算已回笼至年度总资金池。")
                    report.append("")
                    report.append("1. 实时现金流穿透审计（熔断前状态）")
                    report.append(f"   （1）名义余额：{result.nominal_balance:.2f} 元")
                    report.append(f"   （2）未退押金占用额：{result.deposit_occupied:.2f} 元")
                    report.append(f"   （3）实际可用余额：{result.actual_available_balance:.2f} 元")
                    report.append("")
                    report.append("   得分明细：")
                    
                    # 输出核心情感维度得分
                    emotion_details = result.score_details.get("emotion", {})
                    emotion_score = emotion_details.get("score", 0)
                    emotion_reasons = emotion_details.get("reasons", [])
                    report.append(f"       一、核心情感与歌手状态维度：{emotion_score:+d} 分")
                    if emotion_reasons:
                        for reason in emotion_reasons:
                            report.append(f"          - {reason}")
                    elif emotion_score == 0:
                        report.append(f"          - 未触发任何加分或扣分项")
                    
                    # 输出物理加权维度得分
                    physical_details = result.score_details.get("physical", {})
                    physical_score = physical_details.get("score", 0)
                    physical_reasons = physical_details.get("reasons", [])
                    report.append(f"       二、物理加权维度：{physical_score:+d} 分")
                    if physical_reasons:
                        for reason in physical_reasons:
                            report.append(f"          - {reason}")
                    elif physical_score == 0:
                        report.append(f"          - 场馆为露天或超大型场地，听感收益中平（0分）")
                    
                    # 输出市场压力与特殊节点得分
                    market_details = result.score_details.get("market", {})
                    market_score = market_details.get("score", 0)
                    market_reasons = market_details.get("reasons", [])
                    report.append(f"       三、市场压力与特殊节点：{market_score:+d} 分")
                    if market_reasons:
                        for reason in market_reasons:
                            report.append(f"          - {reason}")
                    elif market_score == 0:
                        report.append(f"          - 未触发任何加分或扣分项")
                else:
                    # 其他未知类型的熔断（兜底处理）
                    report.append(f"❌ 本场次已熔断。")
                    if result.equipment_selection_logic:
                        report.append(f"   {result.equipment_selection_logic}")
                    report.append("")
                    report.append("1. 实时现金流穿透审计")
                    report.append(f"   （1）名义余额：{result.nominal_balance:.2f} 元")
                    report.append(f"   （2）未退押金占用额：{result.deposit_occupied:.2f} 元")
                    report.append(f"   （3）实际可用余额：{result.actual_available_balance:.2f} 元")
                    report.append("")
                    report.append(non_c_meltdown_notice)
                
                report.append("")
                continue
            
            # 1. 实时现金流穿透审计
            report.append("1. 实时现金流穿透审计")
            report.append(f"   （1）名义余额：{result.nominal_balance:.2f} 元")
            report.append(f"   （2）未退押金占用额：{result.deposit_occupied:.2f} 元")
            report.append(f"   （3）实际可用余额：{result.actual_available_balance:.2f} 元")
            report.append(f"   （4）酒店选择：{result.hotel_selection}")
            report.append(f"   （5）交通方式选择：{result.transport_selection}")
            report.append(f"   （6）门票选择：{result.ticket_selection}")
            if result.equipment_rent is not None:
                report.append(f"   （7）拍摄器材费用：租金 {result.equipment_rent:.2f} 元，押金 {result.equipment_deposit:.2f} 元")
            if result.risk_buffer:
                report.append(f"   （8）风险缓冲金：{result.risk_buffer:.2f} 元")
                # 展示激活指标校验结果
                ind_a_str = f"✅ 指标A（演出价值分≥13）：{result.score}分，达标" if result.buffer_indicator_a else f"❌ 指标A（演出价值分≥13）：{result.score}分，未达标"
                if result.buffer_indicator_b is not None:
                    ind_b_str = "✅ 指标B（稀缺度校验）：达标" if result.buffer_indicator_b else "❌ 指标B（稀缺度校验）：未达标"
                else:
                    ind_b_str = "指标B：不适用"
                report.append(f"       └ 激活校验：{ind_a_str} | {ind_b_str}")
            # 本场总计花费
            if result.ticket_cost is not None and result.transport_cost is not None and result.hotel_cost is not None:
                actual_spend = result.ticket_cost + result.transport_cost + result.hotel_cost
                if result.equipment_rent is not None:
                    actual_spend += result.equipment_rent
                deposit_freeze = result.equipment_deposit if result.equipment_deposit is not None else 0.0
                rent_part = f" + 器材租金 {result.equipment_rent:.2f}" if result.equipment_rent else ""
                report.append(f"   ──────────────────────────────")
                report.append(f"   本场总计花费：实际支出 {actual_spend:.2f} 元（门票 {result.ticket_cost:.2f} + 交通 {result.transport_cost:.2f} + 酒店 {result.hotel_cost:.2f}{rent_part}），押金冻结 {deposit_freeze:.2f} 元")
            report.append("")

            
            # 2. 物理准入权与光学冲突判定
            report.append("2. 物理准入权与光学冲突判定")
            report.append(f"   （1）场馆安保等级：{result.security_level}")
            report.append(f"   （2）拍摄器材：{result.equipment}")
            if result.equipment_selection_logic:
                report.append(f"   （3）器材选择逻辑：{result.equipment_selection_logic}")
            report.append("")
            
            # 3. 生理资产 BE 动态结算
            report.append("3. 生理资产 BE 动态结算")
            report.append(f"   （1）机能结论：")
            
            # 计算结算数值（可能超过100%）
            calculated_be = result.previous_be + result.days_since_last * result.recovery_rate
            
            # 格式化输出BE计算公式
            if calculated_be > 100.0:
                report.append(f"       本场初始 BE = {result.previous_be:.1f}% + {result.days_since_last} 天 × {result.recovery_rate:.0f}% RR = 100%封顶")
            else:
                report.append(f"       本场初始 BE = {result.previous_be:.1f}% + {result.days_since_last} 天 × {result.recovery_rate:.0f}% RR = {result.initial_be:.1f}%")
            
            # 输出损耗详情
            if result.loss_details:
                loss_parts = [f"{k} {v:.0f}%" for k, v in result.loss_details.items()]
                loss_breakdown = " + ".join(loss_parts)
                report.append(f"       本场总损耗 = {result.total_loss:.1f}%（{loss_breakdown}）")
            else:
                report.append(f"       本场总损耗 = {result.total_loss:.1f}%")
            report.append(f"       离场残值结算：本场离场 BE = {result.initial_be:.1f}% - {result.total_loss:.1f}% = {result.final_be:.1f}%")
            if result.rr_collapsed_this_session:
                report.append(f"       ⚠️ RR永久坍塌触发：{result.rr_collapse_reason}")
            report.append("")
            
            # 4. 演出价值分定格与定级
            report.append("4. 演出价值分定格与定级")
            report.append(f"   （1）定级判决：最终分值 {result.score} 分，等级 {result.grade} 级")
            report.append("")
            report.append("   （2）得分明细：")
            
            # 输出核心情感维度得分
            emotion_details = result.score_details.get("emotion", {})
            emotion_score = emotion_details.get("score", 0)
            emotion_reasons = emotion_details.get("reasons", [])
            report.append(f"       一、核心情感与歌手状态维度：{emotion_score:+d} 分")
            if emotion_reasons:
                for reason in emotion_reasons:
                    report.append(f"          - {reason}")
            elif emotion_score == 0:
                report.append(f"          - 未触发任何加分或扣分项")
            
            # 输出物理加权维度得分
            physical_details = result.score_details.get("physical", {})
            physical_score = physical_details.get("score", 0)
            physical_reasons = physical_details.get("reasons", [])
            report.append(f"       二、物理加权维度：{physical_score:+d} 分")
            if physical_reasons:
                for reason in physical_reasons:
                    report.append(f"          - {reason}")
            elif physical_score == 0:
                report.append(f"          - 场馆为露天或超大型场地，听感收益中平（0分）")
            
            # 输出市场压力与特殊节点得分
            market_details = result.score_details.get("market", {})
            market_score = market_details.get("score", 0)
            market_reasons = market_details.get("reasons", [])
            report.append(f"       三、市场压力与特殊节点：{market_score:+d} 分")
            if market_reasons:
                for reason in market_reasons:
                    report.append(f"          - {reason}")
            elif market_score == 0:
                report.append(f"          - 未触发任何加分或扣分项")
            
            report.append("")
            report.append("")
        
        # ── 年度资产总结报告（仅在全年规划触发时输出）──────────────────────────
        if is_annual_plan:
            report.append("=" * 80)
            report.append("年度资产总结报告")
            report.append("=" * 80)
            report.append("")

            # （1）年度总预算残值：20,000 - 所有已执行支出
            total_executed_spend = 0.0
            for r in results:
                if not r.is_cancelled:
                    if r.ticket_cost is not None:
                        total_executed_spend += r.ticket_cost
                    if r.transport_cost is not None:
                        total_executed_spend += r.transport_cost
                    if r.hotel_cost is not None:
                        total_executed_spend += r.hotel_cost
                    if r.equipment_rent is not None:
                        total_executed_spend += r.equipment_rent
            annual_budget_residual = 20000.0 - total_executed_spend
            report.append(f"（1）年度总预算残值：20,000 - {total_executed_spend:.2f}（已执行支出）= {annual_budget_residual:.2f} 元")

            # （2）风险缓冲金池余额：1,000 - 已永久减记额度
            risk_buffer_remaining = self.risk_buffer_total - self.risk_buffer_used
            report.append(f"（2）风险缓冲金池余额：1,000 - {self.risk_buffer_used:.2f}（已永久减记）= {risk_buffer_remaining:.2f} 元")

            # （3）年度机能均值：剩余体力值与自然恢复率现状
            # 取最后一场未熔断场次的 final_be 作为当前剩余体力值
            last_valid_result = None
            for r in reversed(results):
                if not r.is_cancelled:
                    last_valid_result = r
                    break
            if last_valid_result is not None:
                current_be = last_valid_result.final_be
            else:
                current_be = 100.0  # 若全部熔断，体力未损耗，保持初始值
            rr_status = f"{self.recovery_rate:.0f}%/24h"
            if self.recovery_rate < 10.0:
                rr_status += "（已永久坍缩，不可逆）"
            report.append(f"（3）年度机能均值：当前剩余体力值 {current_be:.1f}%，自然恢复率 {rr_status}")

            # （4）核心资产产出统计
            # S+ 级执行次数：未熔断且 grade == "S+" 的场次数
            sp_count = sum(1 for r in results if not r.is_cancelled and r.grade == "S+")
            # 高阶图像产出件数：未熔断且器材为 ZC-02/WC-03/PQ-04/TQ-05（安保未拦截）
            high_tier_equipment = {"ZC-02", "WC-03", "PQ-04", "TQ-05"}
            high_image_count = sum(
                1 for r in results
                if not r.is_cancelled and r.equipment is not None and r.equipment in high_tier_equipment
            )
            report.append(f"（4）核心资产产出统计：")
            report.append(f"    ● S+ 级执行次数：{sp_count} 次")
            report.append(f"    ● 高阶图像产出件数：{high_image_count} 件")
            report.append("")

        # ── Checklist 生成 ──────────────────────────────────────────────────────
        if results:
            last_result = results[-1]
            report.append("=" * 80)
            report.append("【Checklist】")
            report.append("=" * 80)
            report.append("")
            
            # 辅助函数：去掉括号中的原因说明，只保留核心信息
            import re
            def extract_hotel_simple(text: str) -> str:
                """提取酒店选择简化格式：T1级 - 酒店名；实付 xxx 元"""
                if not text:
                    return text
                # 匹配 T1/T2/T3级 - 酒店名；实付 xxx 元
                match = re.match(r'^(T[123]级\s*-\s*[^；]+；实付\s*[\d.]+\s*元)', text)
                if match:
                    return match.group(1)
                return text
            
            def extract_transport_simple(text: str) -> str:
                """提取交通选择简化格式：交通方式；实付 xxx 元"""
                if not text:
                    return text
                # 匹配 交通方式（时长）；实付 xxx 元，去掉时长括号
                match = re.match(r'^([^（(；]+)[（(][^）)]*[）)]\s*；\s*(实付\s*[\d.]+\s*元)', text)
                if match:
                    return f"{match.group(1)}；{match.group(2)}"
                # 如果没有时长括号，直接匹配 交通方式；实付 xxx 元
                match = re.match(r'^(.+?；实付\s*[\d.]+\s*元)', text)
                if match:
                    return match.group(1)
                return text
            
            # 提取简化版本的酒店和交通选择
            hotel_selection_simple = extract_hotel_simple(last_result.hotel_selection)
            transport_selection_simple = extract_transport_simple(last_result.transport_selection)
            # 提取门票选择的简化版本：仅保留实付金额
            ticket_selection_simple = last_result.ticket_selection
            if ticket_selection_simple:
                # 从 ticket_selection 中提取实付金额
                match = re.search(r'实付\s*(\d+(?:\.\d+)?)\s*元', ticket_selection_simple)
                if match:
                    ticket_selection_simple = f"实付 {match.group(1)} 元"
            
            if last_result.is_cancelled:
                # 最后一场熔断了，只需要检查熔断关键句
                is_c_grade_meltdown = last_result.grade == "C"
                
                if is_c_grade_meltdown:
                    # C级熔断
                    report.append(f"1.模型回复是否显示该场次已熔断，且包含：“本场次综合评分为 {last_result.score} 分，系统已将其标记为\"无效逻辑点\"，执行资产清算”？")
                    report.append("")
                else:
                    # 非C级熔断
                    report.append(f"1.模型回复是否显示该场次已熔断，且包含：“本场熔断，该场次关联的所有资金将统一回收”？")
                    report.append("")
            else:
                # 最后一场没有熔断，正常输出 checklist
                report.append(f"1.模型回复中是否包含 \"实时现金流穿透审计\"，且 \"实时现金流穿透审计\" 中\"名义余额\" 为 {last_result.nominal_balance:.2f} 元、\"未退押金占用额\" 为 {last_result.deposit_occupied:.2f} 元、\"实际可用余额\" 为 {last_result.actual_available_balance:.2f} 元？（注：金额数值相同即可，是否带小数位、是否使用千位分隔符不影响判定。）")
                # 不check其他
                if '其他' in transport_selection_simple:
                    transport_selection_simple = transport_selection_simple.replace('其他；', '')
                # 不check交通方式，只check价格
                transport_price_match = re.search(r'实付\s*(\d+(?:\.\d+)?)\s*元', transport_selection_simple)
                if transport_price_match:
                    transport_selection_simple = f"实付 {transport_price_match.group(1)} 元"
                report.append(f"2.模型回复的 \"实时现金流穿透审计\" 中是否包含 \"酒店选择\"、\"交通方式选择\" 和 \"门票选择\"，且\"酒店选择\" 为 {hotel_selection_simple}；\"交通方式选择\" 为 {transport_selection_simple}；\"门票选择\" 为 {ticket_selection_simple}？（注：金额数值相同即可，是否带小数位、是否使用千位分隔符不影响判定。）")
                equipment_display = last_result.equipment if last_result.equipment else '无'
                equipment_note = ''
                if '(' in equipment_display:
                    equipment_code = equipment_display.split(' ')[0]
                    equipment_note = f"（注：拍摄器材写出型号即可，括号内的中文名称可有可无，即“{equipment_code}”与“{equipment_display}”视为相同。）"
                report.append(f"3.模型回复是否包含 \"物理准入权与光学冲突判定\"，\"物理准入权与光学冲突判定\" 中包括 \"场馆安保等级\" 和 \"拍摄器材\"，且\"场馆安保等级\" 为 \"{last_result.security_level}\"；\"拍摄器材\" 为 \"{equipment_display}\"？{equipment_note}")
                # 生理资产 BE 动态结算
                calculated_be = last_result.previous_be + last_result.days_since_last * last_result.recovery_rate
                if calculated_be > 100.0:
                    be_formula = f"本场初始 BE = {last_result.previous_be:.1f}% + {last_result.days_since_last} 天 × {last_result.recovery_rate:.0f}% RR = 100%封顶"
                else:
                    be_formula = f"本场初始 BE = {last_result.previous_be:.1f}% + {last_result.days_since_last} 天 × {last_result.recovery_rate:.0f}% RR = {last_result.initial_be:.1f}%"
                be_settlement = f"本场离场 BE = {last_result.initial_be:.1f}% - {last_result.total_loss:.1f}% = {last_result.final_be:.1f}%"
                be_note = "（注：百分数数值相同即可，是否带小数位不影响判定；“100%封顶”与“100% 封顶”视为相同。）" if calculated_be > 100.0 else "（注：百分数数值相同即可，是否带小数位不影响判定。）"
                report.append(f"4.模型回复中是否包含 \"生理资产 BE 动态结算\"，\"生理资产 BE 动态结算\" 中包含 \"机能结论\" 和 \"离场残值结算\"，且\"机能结论\" 中包含 \"{be_formula}\"；\"离场残值结算\" 中包含 \"{be_settlement}\"？{be_note}")
                report.append(f"5.模型回复是否包含 \"演出价值分定格与定级\"，且 \"演出价值分定格与定级\" 中分数为 \"{last_result.score} 分\"，等级为 \"{last_result.grade} 级\"？")

        return "\n".join(report)


def verified_concert(test_case, is_annual_plan: bool = None):
    """主函数：处理输入样例
    
    Args:
        test_case: 输入样例
        is_annual_plan: 是否为全年规划触发（只有全年规划触发时才输出年度资产总结报告）
                       如果为 None，则自动检测输入中是否包含全年规划触发关键句
    """
    system = ConcertAuditSystem()
    concerts = system.parse_input(test_case)
    
    # 自动检测是否为全年规划触发
    if is_annual_plan is None:
        # 全年规划触发关键句
        annual_plan_keywords = [
            "生成年度全景规划",
            "输出当前所有场次的规划",
            "整合年度规划，进行总结",
            "展示目前的追星资产配置全貌"
        ]
        # 将 test_case 转换为字符串进行检测
        test_case_str = str(test_case) if not isinstance(test_case, str) else test_case
        is_annual_plan = any(keyword in test_case_str for keyword in annual_plan_keywords)
    
    # print(f"解析到 {len(concerts)} 场演唱会")
    # print()
    
    results = []
    previous_be = 100.0
    previous_date = None
    previous_concerts = []  # 维护历史演唱会列表（包括当前场次及之前的所有场次）
    
    for concert in concerts:
        # print(f"处理场次：{concert.name}")
        # print(f"  日期：{concert.date}")
        # print(f"  场馆：{concert.venue}")
        # print()
        
        # 计算距离上一场的天数
        if previous_date:
            current_date = datetime.strptime(concert.date, "%Y-%m-%d")
            days_since_last = (current_date - previous_date).days - 1
        else:
            days_since_last = 0
        
        # 最差环境预设（3）：财务占用预设 —— 强制执行"押金无限期冻结"
        # 若两场演出之间无明确日期差（previous_date 为 None 且不是第一场），
        # 系统默认前一场器材押金尚未归还，从实时可用余额中扣除上一场最高规格器材押金
        if results and previous_date is None:
            # 不是第一场，但上一场日期缺失，无法确定押金是否归还
            # 检查上一场是否有器材信息
            last_result = results[-1]
            if last_result.equipment_deposit is not None and last_result.equipment_deposit > 0:
                # 上一场有器材押金记录，直接冻结该押金
                frozen_deposit = last_result.equipment_deposit
                frozen_reason = f"上一场器材押金（{last_result.equipment}，{frozen_deposit:.0f}元）"
            else:
                # 上一场无器材信息，假设使用 TQ-05（财务风险最高），冻结15000元
                frozen_deposit = EQUIPMENT_LIB["TQ-05"].deposit  # 15000元
                frozen_reason = "上一场器材信息缺失，最差预设假设使用 TQ-05（旗舰特写），冻结押金15000元"
            # 将冻结押金注入系统的押金列表（设置为永不退回，即 return_date 为极远未来）
            system.deposits.append({
                "equipment_code": "TQ-05（最差预设）",
                "deposit": frozen_deposit,
                "return_date": datetime(9999, 12, 31),  # 无限期冻结
                "worst_case_reason": frozen_reason
            })
            days_since_last = -1  # 特殊标记：日期跨度未知，触发极端转场预设
        
        # 传入历史演唱会列表（不包括当前场次，因为calculate_score中会加上）
        result = system.audit_concert(concert, previous_be, days_since_last, previous_concerts)
        results.append(result)
        
        # 更新历史演唱会列表（将当前场次加入）
        previous_concerts.append(concert)
        
        # 只有当场次没有被熔断时才更新previous_be和previous_date
        # 熔断场次不产生体力损耗，所以下一场的初始BE应该基于最近一场正常执行的演唱会
        if not result.is_cancelled:
            previous_be = result.final_be
            previous_date = datetime.strptime(concert.date, "%Y-%m-%d")
    
    # 生成审计报告
    report = system.generate_audit_report(results, is_annual_plan=is_annual_plan)
    return report


def recompute_constraints(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Recompute concert answers and rubrics from the complete authored sessions.

    The function is pure with respect to its input and returns an explicit
    structured change list for the integration layer; it never writes datasets.
    """
    from copy import deepcopy

    output = deepcopy(rows)
    changes: List[Dict[str, Any]] = []
    checklist_marker = "【Checklist】"

    for row in output:
        if not str(row.get("id", "")).startswith("演唱会_"):
            continue
        sessions = [
            turn["content"][0]["value"]
            for turn in row.get("history", [])
            if turn.get("role") == "user"
        ]
        sessions.append(row["question"])
        report = verified_concert(sessions, is_annual_plan=False)
        marker_index = report.find(checklist_marker)
        if marker_index < 0:
            raise ValueError(f"{row['id']}: replay report has no checklist")
        separator_index = report.rfind("=" * 80, 0, marker_index)
        ground_truth = report[:separator_index].rstrip()
        descriptions = re.findall(
            r"(?m)^\d+\.模型回复.*$", report[marker_index:]
        )
        if len(descriptions) not in {1, 5}:
            raise ValueError(
                f"{row['id']}: expected 1 or 5 replay rubrics, got {len(descriptions)}"
            )

        old_rubrics = row.get("rubrics") or []
        new_rubrics = []
        rubric_changes = []
        for index, description in enumerate(descriptions):
            if index < len(old_rubrics):
                rubric = deepcopy(old_rubrics[index])
            else:
                rubric = {"id": str(index)}
            rubric["id"] = str(index)
            rubric["desc"] = description
            rubric["evaluation"] = [
                {"type": "llm", "complete_constraint": description}
            ]
            new_rubrics.append(rubric)
            before = (
                old_rubrics[index]["desc"] if index < len(old_rubrics) else None
            )
            if before != description:
                rubric_changes.append(
                    {
                        "rubric_id": str(index),
                        "before": before,
                        "after": description,
                    }
                )
        for deleted in old_rubrics[len(new_rubrics) :]:
            rubric_changes.append(
                {
                    "rubric_id": deleted["id"],
                    "before": deleted.get("desc"),
                    "after": None,
                }
            )

        ground_truth_changed = row.get("ground-truth derivation") != ground_truth
        rubrics_changed = old_rubrics != new_rubrics
        row["ground-truth derivation"] = ground_truth
        row["rubrics"] = new_rubrics
        if ground_truth_changed or rubrics_changed:
            changes.append(
                {
                    "record_id": row["id"],
                    "ground_truth_changed": ground_truth_changed,
                    "rubric_changes": rubric_changes,
                    "session_count": len(sessions),
                }
            )
    return output, changes


_HOTEL_BRAND_EN = {
    "希尔顿": "Hilton Hotel",
    "喜来登": "Sheraton",
    "威斯汀": "Westin",
    "君悦": "Grand Hyatt Hotel",
    "瑞吉": "St. Regis",
    "半岛": "Peninsula Hotel",
    "柏悦": "Park Hyatt",
    "丽思卡尔顿": "Ritz-Carlton",
    "洲际": "InterContinental",
    "华尔道夫": "Waldorf Astoria",
    "香格里拉": "Shangri-La",
    "悦榕庄": "Banyan Tree",
    "全季": "Ji Hotel",
    "亚朵": "Atour Hotel",
    "橘子": "Orange Hotel",
    "欢漫": "Huanman",
    "智选假日": "Holiday Inn Express",
    "维也纳": "Vienna Hotel",
    "美豪": "Mehood",
    "和颐": "Yitel",
    "丽枫": "Lavande",
    "假日酒店": "Holiday Inn",
    "汉庭": "Hanting Hotel",
    "如家": "Home Inn",
    "7天": "7 Days Inn",
    "布丁": "Pod Inn",
    "速8": "Super 8",
    "格林豪泰": "GreenTree Inn",
    "锦江之星": "Jinjiang Inn",
    "海友": "Hi Inn",
    # Unlisted in the SP, therefore deterministically reachable through its
    # explicit "all other unmentioned brands default to T3" clause.
    "美居": "Mercure Hotel",
}

_EQUIPMENT_EN = {
    "MT-01": "Mobile Terminal",
    "ZC-02": "Integrated Telephoto",
    "WC-03": "Physical Super Telephoto",
    "PQ-04": "Professional Image Quality",
    "TQ-05": "Flagship Close-up",
}


def _english_hotel_brand(chinese_name: str) -> str:
    for chinese, english in sorted(
        _HOTEL_BRAND_EN.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if chinese in chinese_name:
            return english
    raise ValueError(f"unmapped concert hotel brand: {chinese_name!r}")


def _translate_be_formula(formula: str) -> str:
    initial = re.fullmatch(
        r"本场初始 BE = ([\d.]+)% \+ ([-\d]+) 天 × ([\d.]+)% RR = "
        r"(100%封顶|[\d.]+%)",
        formula,
    )
    if initial:
        result = "100% capped" if initial.group(4) == "100%封顶" else initial.group(4)
        return (
            f"Session initial BE = {initial.group(1)}% + {initial.group(2)} days "
            f"× {initial.group(3)}% RR = {result}"
        )
    settlement = re.fullmatch(
        r"本场离场 BE = ([\d.]+)% - ([\d.]+)% = ([\d.]+)%", formula
    )
    if settlement:
        return (
            f"Session exit BE = {settlement.group(1)}% - "
            f"{settlement.group(2)}% = {settlement.group(3)}%"
        )
    raise ValueError(f"unsupported BE formula: {formula!r}")


def _render_english_constraint(chinese: str) -> str:
    number_match = re.match(r"(\d+)\.", chinese)
    if not number_match:
        raise ValueError(f"constraint has no numeric prefix: {chinese!r}")
    number = number_match.group(1)

    if "无效逻辑点" in chinese:
        score = re.search(r"综合评分为 ([-\d]+) 分", chinese).group(1)
        return (
            f'{number}.Does the model response show that this session has been '
            f'circuit-broken, and include: "The overall score for this session '
            f"is {score} points, and the system has already marked it as "
            f"'Invalid Logic Point', execute asset liquidation\"?"
        )
    if "统一回收" in chinese:
        return (
            f'{number}.Does the model response show that this session has been '
            f'circuit-broken, and include: "This session is circuit-broken; all '
            f'funds associated with this session will be uniformly reclaimed"?'
        )
    if "名义余额" in chinese:
        match = re.search(
            r'名义余额" 为 ([\d.]+) 元、"未退押金占用额" 为 ([\d.]+) 元、'
            r'"实际可用余额" 为 ([\d.]+) 元',
            chinese,
        )
        if not match:
            raise ValueError(f"unsupported cash constraint: {chinese!r}")
        return (
            f'{number}.Does the model response include "Real-time Cash Flow '
            f'Penetration Audit", and in "Real-time Cash Flow Penetration Audit" '
            f'is "Nominal Balance" {match.group(1)} CNY, "Unrefunded Deposit '
            f'Occupied Amount" {match.group(2)} CNY, "Actual Available Balance" '
            f"{match.group(3)} CNY?"
        )
    if "酒店选择" in chinese:
        match = re.search(
            r'酒店选择" 为 (T[123])级 - ([^；]+)；实付 ([\d.]+) 元；'
            r'"交通方式选择" 为 实付 ([\d.]+) 元；'
            r'"门票选择" 为 实付 ([\d.]+) 元',
            chinese,
        )
        if not match:
            raise ValueError(f"unsupported travel constraint: {chinese!r}")
        hotel = _english_hotel_brand(match.group(2))
        return (
            f'{number}.Does the model response\'s "Real-time Cash Flow Penetration '
            f'Audit" include "Hotel Selection", "Transportation Mode Selection" '
            f'and "Ticket Selection", and is "Hotel Selection" {match.group(1)} '
            f"level - {hotel}; actually paid {match.group(3)} CNY; "
            f'"Transportation Mode Selection" actually paid {match.group(4)} CNY; '
            f'"Ticket Selection" actually paid {match.group(5)} CNY?'
        )
    if "场馆安保等级" in chinese:
        match = re.search(
            r'场馆安保等级" 为 "([高中低])"；"拍摄器材" 为 "([^"]+)"',
            chinese,
        )
        if not match:
            raise ValueError(f"unsupported physical constraint: {chinese!r}")
        equipment_match = re.search(r"(?:MT|ZC|WC|PQ|TQ)-\d{2}", match.group(2))
        equipment = (
            f"{equipment_match.group(0)} "
            f"({_EQUIPMENT_EN[equipment_match.group(0)]})"
            if equipment_match
            else "None"
        )
        security = {"高": "High", "中": "Medium", "低": "Low"}[match.group(1)]
        return (
            f'{number}.Does the model response include "Physical Admission Rights '
            f'and Optical Conflict Determination", does "Physical Admission Rights '
            f'and Optical Conflict Determination" include "Venue Security Level" '
            f'and "Photography Equipment", and is "Venue Security Level" '
            f'"{security}"; "Photography Equipment" "{equipment}"?'
        )
    if "BE 动态结算" in chinese:
        match = re.search(
            r'机能结论" 中包含 "([^"]+)"；"离场残值结算" 中包含 "([^"]+)"',
            chinese,
        )
        if not match:
            raise ValueError(f"unsupported BE constraint: {chinese!r}")
        initial = _translate_be_formula(match.group(1))
        settlement = _translate_be_formula(match.group(2))
        return (
            f'{number}.Does the model response include "Physiological Asset BE '
            f'Dynamic Settlement", does "Physiological Asset BE Dynamic Settlement" '
            f'contain "Functional Conclusion" and "Departure Residual Value '
            f'Settlement", and does "Functional Conclusion" contain "{initial}"; '
            f'does "Departure Residual Value Settlement" contain "{settlement}"?'
        )
    if "演出价值分定格与定级" in chinese:
        match = re.search(
            r'分数为 "([-\d]+) 分"，等级为 "(S\+|S|A|C) 级"', chinese
        )
        if not match:
            raise ValueError(f"unsupported grade constraint: {chinese!r}")
        return (
            f'{number}.Does the model response include "Performance Value Score '
            f'Finalization and Grading", and in "Performance Value Score '
            f'Finalization and Grading", is the score "{match.group(1)} points" '
            f'and the grade "{match.group(2)} Grade"?'
        )
    raise ValueError(f"unsupported concert constraint template: {chinese!r}")


def recompute_english_constraints(
    en_rows: List[Dict[str, Any]],
    recomputed_zh_rows: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Render English constraints deterministically from recomputed Chinese rubrics."""
    from copy import deepcopy

    output = deepcopy(en_rows)
    zh_by_id = {
        row["id"]: row
        for row in recomputed_zh_rows
        if str(row.get("id", "")).startswith("演唱会_")
    }
    changes: List[Dict[str, Any]] = []

    for row in output:
        record_id = str(row.get("id", ""))
        if not record_id.startswith("演唱会_"):
            continue
        if record_id not in zh_by_id:
            raise KeyError(f"{record_id}: missing recomputed Chinese concert row")
        old_constraints = row.get("constraint") or []
        new_constraints = []
        constraint_changes = []
        for index, rubric in enumerate(zh_by_id[record_id]["rubrics"]):
            description = _render_english_constraint(rubric["desc"])
            if index < len(old_constraints):
                constraint = deepcopy(old_constraints[index])
                before = old_constraints[index].get("desc")
            else:
                constraint = {"id": str(index)}
                before = None
            constraint["id"] = rubric["id"]
            constraint["desc"] = description
            constraint["evaluation"] = [
                {"type": "llm", "complete_constraint": description}
            ]
            new_constraints.append(constraint)
            if before != description:
                constraint_changes.append(
                    {
                        "constraint_id": rubric["id"],
                        "before": before,
                        "after": description,
                    }
                )
        for deleted in old_constraints[len(new_constraints) :]:
            constraint_changes.append(
                {
                    "constraint_id": deleted["id"],
                    "before": deleted.get("desc"),
                    "after": None,
                }
            )
        row["constraint"] = new_constraints
        if old_constraints != new_constraints:
            changes.append(
                {
                    "record_id": record_id,
                    "constraint_changes": constraint_changes,
                }
            )
    return output, changes


if __name__ == "__main__":
    # usage: python -m code_simulation_engines.optimization_and_planning.concert_audit.concert_audit_engine [question id], e.g. concert_1
    import ast
    import json
    import sys
    from pathlib import Path

    qid = sys.argv[1] if len(sys.argv) > 1 else "concert_1"
    with open(Path(__file__).resolve().parents[2] / "structured_inputs.jsonl", encoding="utf-8") as f:
        rows = {r["id"]: r for r in map(json.loads, f)}
    raw = rows[qid]["structured_input"]
    try:
        case = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        case = json.loads(raw)
    print(verified_concert(case, is_annual_plan=False))
