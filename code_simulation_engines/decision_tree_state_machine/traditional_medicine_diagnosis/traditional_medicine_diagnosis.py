"""Traditional-medicine diagnostic engine implementing the benchmark rulebook."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum
import re



# ==================== 枚举定义 ====================

class Gender(Enum):
    MALE = "男"
    FEMALE = "女"
    UNKNOWN = "未知"


class SeverityLevel(Enum):
    NORMAL = "轻症"
    SEVERE = "重症"
    CRITICAL = "危症"


# ==================== 数据结构定义 ====================

@dataclass
class Symptom:
    """症状"""
    name: str
    description: str = ""
    location: str = ""  # 部位
    severity: str = ""  # 严重程度描述词
    time_order: int = 0  # 在对话中出现的顺序


@dataclass
class PatientProfile:
    """患者画像"""
    gender: Gender = Gender.UNKNOWN
    age: int = 0
    married: Optional[bool] = None
    has_children: Optional[bool] = None  # 是否有孩子/已孕
    want_children: Optional[bool] = None  # 是否打算要小孩
    minnan_trigger_count: int = 0  # 闽南魂触发次数
    good_pregnancy_mode: bool = False  # 好孕问诊模式


@dataclass
class DiagnosisResult:
    """辨证结果"""
    # 八纲辨证
    biao_zheng: bool = False  # 表证
    li_zheng: bool = False  # 里证
    han_zheng: bool = False  # 寒证
    re_zheng: bool = False  # 热证
    xu_zheng: bool = False  # 虚证
    shi_zheng: bool = False  # 实证
    yang_xu: bool = False  # 阳虚
    yin_xu: bool = False  # 阴虚
    yin_yang_liang_xu: bool = False  # 阴阳两虚
    
    # 特殊寒热证
    zhen_re_jia_han: bool = False  # 真热假寒
    zhen_han_jia_re: bool = False  # 真寒假热
    zhen_xu_jia_shi: bool = False  # 真虚假实
    zhen_shi_jia_xu: bool = False  # 真实假虚
    han_re_bing_jian_unknown: bool = False  # 寒热并见但无法判断真假
    xu_shi_bing_jian_unknown: bool = False  # 虚实并见但无法判断真假
    
    # 危症
    wang_yang: bool = False  # 亡阳证
    wang_yin: bool = False  # 亡阴证
    qi_tuo: bool = False  # 气脱证
    
    # 六淫
    feng_yin: bool = False  # 风淫证
    han_yin: bool = False  # 寒淫证
    shu_yin: bool = False  # 暑淫证
    shi_yin: bool = False  # 湿淫证
    zao_yin: bool = False  # 燥淫证
    huo_yin: bool = False  # 火淫证
    
    # 七情内伤
    has_qi_qing_nei_shang: bool = False  # 是否存在七情内伤（全局标志）
    qi_qing_trigger_word: str = ""  # 触发七情内伤的情志词
    qi_qing_shang_xin: bool = False
    qi_qing_shang_gan: bool = False
    qi_qing_shang_pi: bool = False
    qi_qing_shang_fei: bool = False
    qi_qing_shang_shen: bool = False
    # 具体致病情绪类型（用于生成建议）
    qi_qing_xin_emotion: str = ""  # 伤心的情绪类型：喜/惊
    qi_qing_gan_emotion: str = ""  # 伤肝的情绪类型：怒
    qi_qing_pi_emotion: str = ""   # 伤脾的情绪类型：思
    qi_qing_fei_emotion: str = ""  # 伤肺的情绪类型：悲/忧
    qi_qing_shen_emotion: str = "" # 伤肾的情绪类型：恐/惊
    
    # 气血津液
    qi_xu: bool = False  # 气虚证
    qi_tuo_zheng: bool = False  # 气脱证
    qi_zhi: bool = False  # 气滞证
    xue_xu: bool = False  # 血虚证
    xue_yu: bool = False  # 血瘀证
    xue_re: bool = False  # 血热证
    xue_han: bool = False  # 血寒证
    qi_xue_liang_xu: bool = False  # 气血两虚
    xin_pi_liang_xu: bool = False  # 心脾两虚
    jin_ye_bu_zu: bool = False  # 津液不足
    
    # 症状标记
    has_shi_mian: bool = False  # 有失眠症状
    
    # 脏腑辨证
    xin_qi_xu: bool = False  # 心气虚
    xin_xue_xu: bool = False  # 心血虚
    xin_yin_xu: bool = False  # 心阴虚
    xin_yang_xu: bool = False  # 心阳虚
    xin_mai_bi_zu: bool = False  # 心脉痹阻
    xin_huo_kang_sheng: bool = False  # 心火亢盛
    xin_huo_xia_yi: bool = False  # 心火下移小肠
    
    fei_qi_xu: bool = False  # 肺气虚
    fei_yin_xu: bool = False  # 肺阴虚
    han_tan_zu_fei: bool = False  # 寒痰阻肺
    tan_re_yong_fei: bool = False  # 痰热壅肺
    da_chang_shi_re: bool = False  # 大肠湿热
    da_chang_xu_han: bool = False  # 大肠虚寒
    
    pi_qi_xu: bool = False  # 脾气虚
    pi_yang_xu: bool = False  # 脾阳虚
    pi_xu_shi_kun: bool = False  # 脾虚湿困
    wei_huo_chi_sheng: bool = False  # 胃火炽盛
    wei_han_zheng: bool = False  # 胃寒证
    shi_zhi_wei_wan: bool = False  # 食滞胃脘
    wei_qi_shang_ni: bool = False  # 胃气上逆
    xu_lao_li_ji: bool = False  # 虚劳里急
    
    gan_qi_yu_jie: bool = False  # 肝气郁结
    gan_huo_shang_yan: bool = False  # 肝火上炎
    gan_xue_xu: bool = False  # 肝血虚
    gan_yang_shang_kang: bool = False  # 肝阳上亢
    gan_dan_shi_re: bool = False  # 肝胆湿热
    
    shen_yang_xu: bool = False  # 肾阳虚
    shen_yin_xu: bool = False  # 肾阴虚
    shen_bu_na_qi: bool = False  # 肾不纳气
    pang_guang_shi_re: bool = False  # 膀胱湿热
    
    shen_severity: SeverityLevel = SeverityLevel.NORMAL  # 肾虚严重程度
    
    # 辅助标志（用于饮食建议，不作为诊断）
    has_tan_symptoms: bool = False  # 有痰症状（用于饮食建议忌油腻）
    
    # 诊断依据记录
    diagnosis_basis: Dict[str, List[str]] = field(default_factory=dict)  # {诊断名: [依据列表]}
    # 病症依赖的症状条目索引：{病名: set(time_order)}，用于确定S2优先级
    disease_source_items: Dict[str, set] = field(default_factory=dict)


@dataclass
class Formula:
    """方剂"""
    name: str
    monarch_herbs: List[str]  # 君药
    herbs: List[str]  # 全部药材
    indications: List[str]  # 适用症
    special_notes: Dict[str, str] = field(default_factory=dict)  # 特殊医嘱


@dataclass
class Prescription:
    """处方"""
    formula_name: str
    herbs: List[str]
    special_notes: List[str]


# ==================== 药方数据库 ====================
# 基于 system_prompt_zy.md 第750-815行的内部中药数据库

FORMULA_DATABASE = {
    # A. 解表剂（针对表证）
    "麻黄汤": Formula("麻黄汤", ["麻黄"], ["麻黄", "桂枝", "杏仁", "甘草"], ["表寒证"]),
    "桂枝汤": Formula("桂枝汤", ["桂枝"], ["桂枝", "白芍", "生姜", "大枣", "甘草"], ["表寒证"]),
    "银翘散": Formula("银翘散", ["金银花", "连翘"], 
                     ["金银花", "连翘", "薄荷", "牛蒡子", "荆芥", "淡豆豉", "竹叶", "芦根", "甘草"], ["表热证"]),
    
    # B. 温里剂（针对里寒）
    "四逆汤": Formula("四逆汤", ["附子"], ["附子", "干姜", "甘草"], ["里寒证", "亡阳证"]),
    "理中丸": Formula("理中丸", ["干姜"], ["干姜", "人参", "白术", "甘草"], ["脾胃虚寒", "胃寒证"]),
    "小建中汤": Formula("小建中汤", ["饴糖"], ["饴糖", "桂枝", "白芍", "生姜", "大枣", "甘草"], ["虚劳里急"]),
    "附子理中丸": Formula("附子理中丸", ["附子", "干姜"], ["附子", "干姜", "人参", "白术", "甘草"], ["脾阳虚"]),
    "桂枝甘草汤": Formula("桂枝甘草汤", ["桂枝"], ["桂枝", "炙甘草"], ["心阳虚"]),
    "温经汤": Formula("温经汤", ["吴茱萸", "桂枝"], 
                     ["吴茱萸", "桂枝", "当归", "川芎", "芍药", "牡丹皮", "阿胶", "麦冬", "人参", "甘草", "半夏", "生姜"], ["血寒证"]),
    "真人养脏汤": Formula("真人养脏汤", ["罂粟壳"], 
                        ["罂粟壳", "肉豆蔻", "诃子", "人参", "白术", "当归", "白芍", "木香", "甘草", "肉桂"], ["大肠虚寒"]),
    
    # C. 清热剂（针对里热）
    "白虎汤": Formula("白虎汤", ["石膏"], ["石膏", "知母", "甘草", "粳米"], ["实热证"]),
    "黄连解毒汤": Formula("黄连解毒汤", ["黄连"], ["黄连", "黄芩", "黄柏", "栀子"], ["火淫证"]),
    "导赤散": Formula("导赤散", ["生地", "木通"], ["生地", "木通", "生甘草", "竹叶"], ["心火亢盛"]),
    "清胃散": Formula("清胃散", ["黄连"], ["黄连", "升麻", "生地", "丹皮", "当归"], ["胃火炽盛"]),
    "龙胆泻肝汤": Formula("龙胆泻肝汤", ["龙胆草"], 
                        ["龙胆草", "黄芩", "栀子", "泽泻", "木通", "车前子", "当归", "生地", "柴胡", "甘草"], 
                        ["肝火上炎", "肝胆湿热"]),
    "白头翁汤": Formula("白头翁汤", ["白头翁"], ["白头翁", "黄连", "黄柏", "秦皮"], ["大肠湿热"]),
    "八正散": Formula("八正散", ["木通", "滑石"], 
                     ["木通", "滑石", "车前子", "萹蓄", "瞿麦", "栀子", "大黄", "甘草", "灯心草"], ["膀胱湿热"]),
    
    # D. 补益剂（针对虚证）
    "四君子汤": Formula("四君子汤", ["人参"], ["人参", "白术", "茯苓", "甘草"], ["气虚证"]),
    "参苓白术散": Formula("参苓白术散", ["人参", "白术"], 
                        ["人参", "白术", "茯苓", "山药", "莲子", "白扁豆", "薏苡仁", "砂仁", "桔梗", "甘草"], ["脾气虚"]),
    "养心汤": Formula("养心汤", ["黄芪", "人参"], 
                     ["黄芪", "人参", "茯苓", "茯神", "当归", "川芎", "半夏", "曲", "柏子仁", "酸枣仁", "远志", "五味子", "肉桂", "甘草"], ["心气虚"]),
    "补肺汤": Formula("补肺汤", ["人参", "黄芪"], ["人参", "黄芪", "熟地黄", "五味子", "紫菀", "桑白皮"], ["肺气虚"]),
    "四物汤": Formula("四物汤", ["熟地黄"], ["熟地黄", "当归", "白芍", "川芎"], ["血虚证"]),
    "补肝汤": Formula("补肝汤", ["当归", "白芍"], ["当归", "白芍", "川芎", "熟地", "酸枣仁", "木瓜", "甘草"], ["肝血虚"]),
    "八珍汤": Formula("八珍汤", ["人参", "熟地"], 
                     ["人参", "白术", "茯苓", "甘草", "熟地黄", "当归", "白芍", "川芎"], ["气血两虚"]),
    "百合固金汤": Formula("百合固金汤", ["百合", "生地"], 
                        ["百合", "生地", "熟地", "麦冬", "贝母", "当归", "白芍", "甘草", "玄参", "桔梗"], ["肺阴虚"]),
    "麦门冬汤": Formula("麦门冬汤", ["麦冬"], ["麦冬", "半夏", "人参", "甘草", "粳米", "大枣"], ["肺阴虚", "胃气上逆"]),
    "生脉散": Formula("生脉散", ["人参"], ["人参", "麦冬", "五味子"], ["气阴两虚", "亡阴证"]),
    "六味地黄丸": Formula("六味地黄丸", ["熟地黄"], 
                        ["熟地黄", "山药", "山茱萸", "茯苓", "泽泻", "牡丹皮"], ["肾阴虚"]),
    "左归丸": Formula("左归丸", ["熟地黄"], 
                     ["熟地", "山药", "枸杞", "山茱萸", "川牛膝", "菟丝子", "鹿角胶", "龟板胶"], ["肾阴虚"]),
    "金匮肾气丸": Formula("金匮肾气丸", ["附子", "桂枝"], 
                        ["地黄", "山药", "山茱萸", "茯苓", "泽泻", "丹皮", "附子", "桂枝"], ["肾阳虚"]),
    "右归丸": Formula("右归丸", ["附子", "肉桂"], 
                     ["熟地", "附子", "肉桂", "山药", "山茱萸", "菟丝子", "鹿角胶", "枸杞", "当归", "杜仲"], ["肾阳虚"]),
    "参蛤散": Formula("参蛤散", ["人参", "蛤蚧"], ["人参", "蛤蚧"], ["肾不纳气"]),
    "归脾汤": Formula("归脾汤", ["白术", "茯苓"], 
                     ["白术", "茯苓", "黄芪", "龙眼肉", "酸枣仁", "人参", "木香", "当归", "远志", "甘草"], ["心脾两虚"]),
    "天王补心丹": Formula("天王补心丹", ["生地"], 
                        ["生地", "人参", "丹参", "玄参", "茯苓", "五味子", "远志", "桔梗", "当归", "天冬", "麦冬", "柏子仁", "酸枣仁"], 
                        ["心阴虚"]),
    "甘麦大枣汤": Formula("甘麦大枣汤", ["甘草", "小麦"], ["甘草", "小麦", "大枣"], ["七情伤心"]),
    
    # E. 祛邪/理气/理血剂（针对实证/兼证）
    "二陈汤": Formula("二陈汤", ["半夏"], ["半夏", "陈皮", "茯苓", "甘草"], ["湿淫证"]),
    "平胃散": Formula("平胃散", ["苍术"], ["苍术", "厚朴", "陈皮", "甘草", "生姜", "大枣"], ["脾虚湿困"]),
    "清气化痰丸": Formula("清气化痰丸", ["胆南星"], 
                        ["胆南星", "瓜蒌", "黄芩", "半夏", "陈皮", "杏仁", "枳实", "茯苓"], ["痰热壅肺"]),
    "三子养亲汤": Formula("三子养亲汤", ["白芥子"], ["白芥子", "苏子", "莱菔子"], ["寒痰阻肺"]),
    "保和丸": Formula("保和丸", ["山楂"], ["山楂", "神曲", "莱菔子", "半夏", "陈皮", "茯苓", "连翘"], ["食滞胃脘"]),
    "逍遥散": Formula("逍遥散", ["柴胡"], ["柴胡", "当归", "白芍", "白术", "茯苓", "薄荷", "煨姜", "甘草"], ["肝气郁结"]),
    "柴胡疏肝散": Formula("柴胡疏肝散", ["柴胡"], ["柴胡", "陈皮", "川芎", "香附", "枳壳", "芍药", "甘草"], ["七情伤肝"]),
    "天麻钩藤饮": Formula("天麻钩藤饮", ["天麻", "钩藤"], 
                        ["天麻", "钩藤", "石决明", "栀子", "黄芩", "川牛膝", "杜仲", "益母草", "桑寄生", "夜交藤", "茯神"], ["肝阳上亢"]),
    "血府逐瘀汤": Formula("血府逐瘀汤", ["桃仁", "红花"], 
                        ["桃仁", "红花", "当归", "生地", "川芎", "赤芍", "牛膝", "桔梗", "柴胡", "枳壳", "甘草"], ["血瘀证"]),
    "瓜蒌薤白白酒汤": Formula("瓜蒌薤白白酒汤", ["瓜蒌", "薤白"], ["瓜蒌", "薤白", "白酒"], ["心脉痹阻"]),
    "越鞠丸": Formula("越鞠丸", ["香附", "苍术"], ["香附", "苍术", "川芎", "神曲", "栀子"], ["七情伤脾", "七情伤肺", "七情伤肾"]),
    "乌梅丸": Formula("乌梅丸", ["乌梅"], 
                     ["乌梅", "细辛", "干姜", "黄连", "当归", "附子", "蜀椒", "桂枝", "人参", "黄柏"], ["真热假寒证", "真寒假热证"]),
    
    # 危症方
    "参附汤": Formula("参附汤", ["人参", "附子"], ["人参", "附子"], ["亡阳证"]),
    "独参汤": Formula("独参汤", ["人参"], ["人参"], ["气脱证"]),
}



# 特殊医嘱
SPECIAL_NOTES = {
    "麦冬": {
        "麦门冬汤": "(麦冬用量需7倍于半夏)",
        "温经汤": "(麦冬与半夏用量大致相等)"
    },
    "附子": "(需先煎30-60分钟)",
    "乌头": "(需先煎30-60分钟)",
    "人参": "(需另煎兑入)",  # 仅限危症
    "阿胶": "(烊化)",
    "鹿角胶": "(烊化)",
    "龟板胶": "(烊化)",
    "石膏": "(需先煎)",
    "龙骨": "(需先煎)",
    "牡蛎": "(需先煎)",
    "生姜+半夏": "(生姜需倍于半夏以制毒)",
    "桂枝汤": "(桂枝与白芍比例1:1)",
}

# 十八反
INCOMPATIBLE_HERBS = {
    "甘草": ["甘遂", "大戟", "海藻", "芫花"],
    "附子": ["半夏", "贝母", "瓜蒌", "白及", "白蔹"],
    "川乌": ["半夏", "贝母", "瓜蒌", "白及", "白蔹"],
    "草乌": ["半夏", "贝母", "瓜蒌", "白及", "白蔹"],
}


# ==================== 证型关键词常量 ====================
# 用于诊断判断、症状查找、解释生成等多处逻辑
# 修改此处即可全局生效

ZHENG_KEYWORDS = {
    # 气血津液证
    "气虚证": ["懒言", "自汗", "呼吸短促", "疲劳感在休息后无法缓解", "气短"],
    "气滞证": [["胀痛", "胀满"], ["游走性疼痛"], ["生气加重", "情绪加重"]],
    "血虚证": [["面色发白", "面色暗黄"], ["舌体白", "舌白"], ["头晕眼花", "视力模糊"], ["月经量少", "颜色淡", "闭经"]],
    "血瘀证": ["刺痛", "像针扎", "固定不移", "夜间加重", "面色晦暗", "瘀斑", "瘀点", "舌紫暗", "黑血块"],
    "血热证": [["流鼻血", "吐血", "尿血"], ["舌红绛", "芒刺"],["红色斑", "红疹"], ["月经提前且量多", "月经提前且颜色鲜红"]],
    "血寒证": ["少腹疼痛", "月经延后", "色暗有血块", "痛经", "热敷缓解", "热敷能缓解"],
    "津液不足": ["口渴", "喜欢喝水", "皮肤干燥", "起皮", "尿少", "便干", "大便干燥"],
}

# ==================== 脏腑定位关键词常量 ====================
# 与 diagnose_zang_fu_single 中的定位关键词【完全一致】
# 禁止新增任何关键词

ZANGFU_KEYWORDS = {
    # 心与小肠（来自 diagnose_zang_fu_single 第1401行）
    "心": ["心慌", "心悸", "胸闷", "失眠", "多梦"],
    # 肺与大肠（来自 diagnose_zang_fu_single 第1446-1447行）
    "肺": ["咳嗽", "气喘", "咳痰", "胸痛", "干咳"],
    "大肠": ["便秘", "腹泻", "拉肚子"],
    # 脾与胃（来自 diagnose_zang_fu_single 第1514-1515行）
    "脾": ["纳差", "饭后腹胀", "便溏", "身体沉重", "身重"],
    "胃": ["胃痛", "胃疼", "胃巨疼", "呕吐", "反酸", "烧心", "胃冷痛"],
    # 肝与胆（来自 diagnose_zang_fu_single 第1579行）
    "肝胆": ["两胁胀痛", "胁痛", "口苦", "头晕", "易怒", "乳房胀痛"],
    # 肾（来自 diagnose_zang_fu_single 第1620行）
    "肾": ["腰膝酸软", "耳鸣", "遗精", "阳痿", "脱发", "五更泻"],
    # 膀胱（来自 diagnose_zang_fu_single 第1681行）
    "膀胱": ["尿频", "尿急", "尿痛"],
}

# ==================== 八纲辨证关键词常量 ====================
# 与 diagnose_li_single/diagnose_biao_single/diagnose_han_re_single/diagnose_xu_shi_single 【完全一致】
# 禁止新增任何关键词

BAGANG_KEYWORDS = {
    # 里证关键词（来自 diagnose_li_single 第693-702行）
    "里证": ["心慌", "心悸", "胸闷", "失眠", "多梦", "舌尖痛",
                 "咳嗽", "气喘", "咳痰", "胸痛","干咳",
                 "便秘", "腹泻", "拉肚子", 
                 "纳差", "腹胀", "便溏", "身重", "身体沉重",
                 "胃痛", "呕吐", "反酸", "烧心",
                 "两胁胀痛", "易怒", "乳房胀痛", "口苦", "头晕",
                 "腰膝酸软", "耳鸣", "遗精", "阳痿", "脱发", "五更泻",
                 "尿频", "尿急", "尿痛", "很严重", "很难受", "很痛苦"],
    
    # 表证关键词（来自 diagnose_biao_single 第721-725行）
    "表证": ["恶寒", "怕冷", "前天还好好的", "不知道从什么时候"],
    
    # 寒证关键词（来自 diagnose_han_re_single 第738行）
    "寒证": ["恶寒", "热敷缓解", "面色发白", "冷痛", "苔白", "苔湿"],
    
    # 热证关键词（来自 diagnose_han_re_single 第745-746行）
    "热证": ["发热", "口干", "想喝水", "渴", "舌红", "面色发红", "冷有帮助", "苔黄", "舌干", "舌燥"],
    
    # 虚证关键词（来自 diagnose_xu_shi_single 第764-768行）
    "虚证": ["疼痛感弱", "不痛苦", "感受不明显", 
            "没力气", "没有力气", "乏力", "疲乏", "缺乏精力", 
            "先天不足", "经常生病",  
            "身体素质不好", 
            "喜按"],
    
    # 实证关键词（来自 diagnose_xu_shi_single 第778-781行）
    "实证": ["疼痛感强", "严重", "感受明显", 
            "实性病变", 
            "硬块", "硬结", "疙瘩", "硬团", "一碰就疼", "很涨", "很鼓",
            "按压很疼", "按压疼", "胀得鼓鼓", "胀", "鼓"],
    
    # 阴虚特征（来自 diagnose_yin_yang_single 第939行）
    "阴虚": ["两颧潮红", "五心烦热", "潮热", "盗汗", "舌红", "舌少苔", "舌燥", "舌有裂纹", "舌无苔"],
}


# ==================== 标准化输入数据结构 ====================

@dataclass
class DiseaseItem:
    """标准化病症条目"""
    text: str           # 病症原文描述
    time: Optional[str] = None  # 发病时间
    time_order: int = 0         # 全局时序编号
    severity_label: Optional[str] = None  # 严重程度标签


@dataclass
class StandardizedInput:
    """标准化输入格式"""
    patient: Dict  # {'gender': 'male'/'female', 'age': int}
    disease: List[Dict]  # 病症列表（字典格式，含text/time/time_order/severity_label）
    season: Optional[str] = None  # 当前季节
    tongue: Optional[str] = None  # 舌象信息，如 "舌红 苔黄 厚腻"
    minnan_trigger: Optional[Dict] = None  # {'count': int, 'married': bool}


# ==================== Step 2: 形容词优先级映射 (S2) ====================
# 规则来源：system_prompt_zy.md 第23-34行
# S2-T0 到 S2-T4，数字越小优先级越高
ADJECTIVE_PRIORITY = {
    # S2-T0：最高优先级形容词
    '最': 0, '主诉': 0, '第一': 0, '主要': 0, '痛不欲生': 0,
    # S2-T1：次高优先级形容词
    '特别': 1, '非常': 1, '严重': 1, '剧烈': 1,
    # S2-T2：弱化形容词
    '一般': 2, '不在意': 2, '不影响': 2,
    # S2-T3：默认（无形容词或其他形容词）-> 在代码中处理为3
    # S2-T4：排除形容词
    '先不管': 4,
}

# 特殊标签（不参与主病竞选）
EXCLUDED_LABELS = {'弱化', '排除'}


# ==================== Step 1: 病名级别定义 (S1) ====================
# 规则来源：system_prompt_zy.md 第7-21行
# S1-T0 到 S1-T5，数字越小级别越高

# S1级别定义（数字越小越高级）
S1_TIER = {
    # S1-T0：危证（最高级别）
    "亡阳证": 0, "亡阴证": 0, "气脱证": 0,
    
    # S1-T1：重症（特指符合重症判定的肾阳虚和肾阴虚）
    # 注意：肾阳虚和肾阴虚只有在符合"重症判定"时才是S1-T1，否则是S1-T2
    # 这需要在代码中动态判断，通过 severity_label == '重症' 来识别
    
    # S1-T2：脏腑定位+关键症状的脏腑病症
    # 心
    "心气虚": 2, "心血虚": 2, "心阴虚": 2, "心阳虚": 2,
    "心脉痹阻": 2, "心火亢盛": 2, "心火下移小肠": 2, "心脾两虚": 2,
    # 肺
    "肺气虚": 2, "肺阴虚": 2, "寒痰阻肺": 2, "痰热壅肺": 2,
    # 脾胃
    "脾气虚": 2, "脾阳虚": 2, "脾虚湿困": 2,
    "胃火炽盛": 2, "胃寒证": 2, "食滞胃脘": 2, "胃气上逆": 2, "脾胃虚寒": 2, "虚劳里急": 2,
    # 肝胆
    "肝气郁结": 2, "肝火上炎": 2, "肝血虚": 2, "肝阳上亢": 2, "肝胆湿热": 2,
    # 肾（默认S1-T2，重症时升级为S1-T1）
    "肾阳虚": 2, "肾阴虚": 2, "肾不纳气": 2,
    # 膀胱
    "膀胱湿热": 2,
    # 大肠
    "大肠湿热": 2, "大肠虚寒": 2,
    
    # S1-T3：七情致病、"真x假x"命名方式的病
    "七情伤心": 3, "七情伤肝": 3, "七情伤脾": 3, "七情伤肺": 3, "七情伤肾": 3,
    "真热假寒证": 3, "真寒假热证": 3, "真虚假实证": 3, "真实假虚证": 3,
    
    # S1-T4：六淫证
    "风淫证": 4, "寒淫证": 4, "暑淫证": 4, "湿淫证": 4, "燥淫证": 4, "火淫证": 4,
    
    # S1-T5：其他（八纲组合证、气血津液证等）
    "表寒证": 5, "表热证": 5, "里寒证": 5, "里热证": 5,
    "阴虚证": 5, "阳虚证": 5,
    "气虚证": 5, "血虚证": 5, "气血两虚": 5,
    "血瘀证": 5, "血热证": 5, "血寒证": 5,
    "气滞证": 5,
    "实热证": 5,
}

# ==================== Step 4: 手册时序原则 (S4) ====================
# 规则来源：system_prompt_zy.md 第38-40行
# 以 system_prompt_zy.md 中病症定义的顺序为准
# 列表索引越小表示在手册中出现越早，优先级越高
DISEASE_MANUAL_ORDER = [
    # 八纲辨证 - 表里辨证（第226-251行）
    "表寒证",          # 第226行
    "表热证",          # 第228行
    "里寒证",          # 第230行
    "里热证",          # 第232行
    "里证",            # 第245行
    "表证",            # 第251行
    # 八纲辨证 - 寒热辨证（第263-297行）
    "寒证",            # 第263行
    "热证",            # 第275行
    "真热假寒证",      # 第288行
    "真寒假热证",      # 第289行
    # 八纲辨证 - 虚实辨证（第305-348行）
    "虚证",            # 第305行
    "实证",            # 第319行
    "真实假虚证",      # 第332行
    "真虚假实证",      # 第333行
    # 八纲辨证 - 阴阳辨证（第352-402行）
    "阴阳两虚",        # 第352行
    "阳虚证",          # 第360行
    "阴虚证",          # 第366行
    "亡阳证",          # 第381行
    "亡阴证",          # 第392行
    # 病因辨证 - 六淫辨证（第416-492行）
    "风淫证",          # 第416行
    "寒淫证",          # 第430行
    "暑淫证",          # 第440行
    "湿淫证",          # 第454行
    "燥淫证",          # 第470行
    "火淫证",          # 第478行
    # 气血津液辨证（第564行）
    "气血两虚",        # 第564行
    # 气血津液辨证 - 气病辨证（第568-594行）
    "气虚证",          # 第568行
    "气脱证",          # 第582行
    "气滞证",          # 第586行
    # 气血津液辨证 - 血病辨证（第598-642行）
    "血虚证",          # 第598行
    "血瘀证",          # 第610行
    "血热证",          # 第622行
    "血寒证",          # 第634行
    # 气血津液辨证 - 津液辨证（第645行）
    "津液不足",        # 第645行
    # 脏腑辨证 - 心与小肠（第666-680行）
    "心气虚",          # 第666行
    "心血虚",          # 第668行
    "心阴虚",          # 第670行
    "心阳虚",          # 第672行
    "心脉痹阻",        # 第674行
    "心火亢盛",        # 第676行
    "心火下移小肠",    # 第678行
    "七情伤心",        # 第680行
    # 脏腑辨证 - 肺与大肠（第690-707行）
    "肺气虚",          # 第690行
    "肺阴虚",          # 第693行
    "寒痰阻肺",        # 第696行
    "痰热壅肺",        # 第699行
    "大肠湿热",        # 第702行
    "大肠虚寒",        # 第705行
    "七情伤肺",        # 第707行
    # 脏腑辨证 - 脾与胃（第718-838行）
    "脾气虚",          # 第718行
    "脾阳虚",          # 第720行
    "脾虚湿困",        # 第722行
    "胃火炽盛",        # 第724行
    "胃寒证",          # 第726行
    "食滞胃脘",        # 第728行
    "胃气上逆",        # 第730行
    "虚劳里急",        # 第732行
    "七情伤脾",        # 第734行
    "脾胃虚寒",        # 第838行（理中丸适应症）
    # 脏腑辨证 - 肝与胆（第742-752行）
    "肝气郁结",        # 第742行
    "肝火上炎",        # 第744行
    "肝血虚",          # 第746行
    "肝阳上亢",        # 第748行
    "肝胆湿热",        # 第750行
    "七情伤肝",        # 第752行
    # 脏腑辨证 - 肾与膀胱（第762-772行）
    "肾阳虚",          # 第762行
    "肾阴虚",          # 第764行
    "肾不纳气",        # 第768行
    "膀胱湿热",        # 第770行
    "七情伤肾",        # 第772行
    # 其他组合证（药方部分）
    "实热证",          # 第857行（白虎汤）
    "气阴两虚",        # 第906行（生脉散）
    "心脾两虚",        # 第923行（归脾汤）
]

# 获取病症的手册时序值（Step 4）
def get_disease_manual_order(disease_name: str) -> int:
    """获取病症在手册中的定义顺序
    
    规则来源：system_prompt_zy.md 第38-40行
    Step 4: 手册时序原则 - 以本文中症状定义的顺序为准
    
    返回值越小表示在手册中出现越早，优先级越高
    未定义的病症返回 999（最低优先级）
    """
    try:
        return DISEASE_MANUAL_ORDER.index(disease_name)
    except ValueError:
        return 999


# 有对应药方的病名集合
# 规则来源：system_prompt_zy.md 第55-62行
# 只有有药方的病才能作为主病或兼证输出
DISEASES_WITH_FORMULA = {
    # 肾
    "肾阳虚", "肾阴虚", "肾不纳气",
    # 肺
    "痰热壅肺", "肺阴虚", "肺气虚", "寒痰阻肺",
    # 肝
    "肝火上炎", "肝气郁结", "肝胆湿热", "肝血虚", "肝阳上亢",
    # 脾
    "脾气虚", "脾阳虚", "脾虚湿困", "脾胃虚寒",
    # 胃
    "食滞胃脘", "胃火炽盛", "胃寒证", "胃气上逆", "虚劳里急",
    # 心
    "心气虚", "心阴虚", "心阳虚", "心脾两虚", "心脉痹阻", "心火亢盛",
    # 大肠
    "大肠湿热", "大肠虚寒",
    # 膀胱
    "膀胱湿热",
    # 气血津液
    "气虚证", "血虚证", "气血两虚", "血瘀证", "血寒证", #"气滞证",
    # 八纲组合证
    "表寒证", "表热证", "里寒证",
    # 六淫
    "湿淫证", "火淫证", "实热证",
    # 危症
    "亡阳证", "亡阴证", "气脱证",
    # 七情内伤
    "七情伤心", "七情伤肝", "七情伤脾", "七情伤肺", "七情伤肾",
    # 寒热错杂
    "真热假寒证",       # 乌梅丸（患者兼具寒证和热证）
    "真寒假热证",       # 乌梅丸（患者兼具寒证和热证）
}

# 所有可确诊的病名集合（包括没有药方的）
# 用于展示完整的竞选过程
ALL_DIAGNOSABLE_DISEASES = DISEASES_WITH_FORMULA | {
    # 没有药方但可以确诊的病名
    "心血虚",           # 无药方
    "心火下移小肠",     # 无药方
    # 六淫证（部分无药方）
    "风淫证",           # 无药方
    "寒淫证",           # 无药方
    "暑淫证",           # 无药方
    "燥淫证",           # 无药方
    # 八纲/气血津液证（部分无药方）
    "里热证",           # 无药方
    "血热证",           # 无药方
    "阴虚证",           # 无药方
    "阳虚证",           # 无药方
    "津液不足",         # 无药方
    "阴阳两虚",         # 无药方
    "真虚假实证",       # 无独立药方
    "真实假虚证",       # 无独立药方
}




# ==================== 辨证逻辑 ====================

class TCMDiagnosisEngine:
    """中医诊断引擎"""
    
    # 否定词列表
    NEGATION_WORDS = ["不", "无", "没有", "没", "未", "非", "否"]
    
    def __init__(self):
        self.patient = PatientProfile()
        self.symptoms: List[Symptom] = []
        self.diagnosis = DiagnosisResult()
        self.main_diseases: List[str] = []
        self.secondary_diseases: List[str] = []
        self.disease_items: List[DiseaseItem] = []  # 标准化病症条目列表
        self.disease_list: List[str] = []  # 兼容旧格式：纯文本列表
        self.season: Optional[str] = None  # 当前季节
        self.tongue: Optional[str] = None  # 舌象信息
        self.all_candidates: List[tuple] = []  # 所有主病候选：[(病名, S1级别, S2级别, time_order, manual_order, s2_source)]
        self.s3_source_map: dict = {}  # {病名: (匹配关键词, 是否仅用脏腑定位)}
    
    @staticmethod
    def keyword_match(text: str, keyword: str) -> bool:
        """
        检查关键词是否在文本中匹配，且前面没有否定词。
        例如："无发烧"中虽然包含"发烧"，但因为前面有"无"，所以返回False。
        """
        if keyword not in text:
            return False
        
        # 查找所有关键词出现的位置
        start = 0
        while True:
            pos = text.find(keyword, start)
            if pos == -1:
                break
            
            # 检查关键词前面是否有否定词
            has_negation = False
            for neg in TCMDiagnosisEngine.NEGATION_WORDS:
                neg_len = len(neg)
                # 检查关键词前面紧邻的位置是否有否定词
                if pos >= neg_len and text[pos - neg_len:pos] == neg:
                    has_negation = True
                    break
            
            if not has_negation:
                # 找到一个没有被否定的匹配
                return True
            
            start = pos + 1
        
        return False
    
    @staticmethod
    def match_keywords(text: str, keywords: list) -> list:
        """
        从关键词列表中匹配文本，返回匹配到的关键词列表（排除前面有否定词的情况）。
        """
        return [kw for kw in keywords if TCMDiagnosisEngine.keyword_match(text, kw)]
    
    def add_diagnosis_basis(self, diagnosis_name: str, basis: str):
        """添加诊断依据"""
        if diagnosis_name not in self.diagnosis.diagnosis_basis:
            self.diagnosis.diagnosis_basis[diagnosis_name] = []
        if basis not in self.diagnosis.diagnosis_basis[diagnosis_name]:
            self.diagnosis.diagnosis_basis[diagnosis_name].append(basis)
    
    def add_disease_source_item(self, disease_name: str, time_order: int):
        """记录病症依赖的症状条目（用于确定S2优先级）
        
        Args:
            disease_name: 病名
            time_order: 触发该病症诊断的症状条目的time_order
        """
        if disease_name not in self.diagnosis.disease_source_items:
            self.diagnosis.disease_source_items[disease_name] = set()
        self.diagnosis.disease_source_items[disease_name].add(time_order)
        
    def parse_standardized_input(self, case_data: Dict):
        """解析标准化输入格式（支持新旧两种格式）"""
        # 解析患者信息
        patient_info = case_data.get('patient', {})
        gender = patient_info.get('gender', '')
        if gender == 'male':
            self.patient.gender = Gender.MALE
        elif gender == 'female':
            self.patient.gender = Gender.FEMALE
        else:
            self.patient.gender = Gender.UNKNOWN
        
        self.patient.age = patient_info.get('age', 0)
        
        # 解析闽南魂触发
        minnan_info = case_data.get('minnan_trigger', {})
        if minnan_info:
            self.patient.minnan_trigger_count = minnan_info.get('count', 0)
            self.patient.married = minnan_info.get('married', None)
        
        # 解析季节
        self.season = case_data.get('season', None)
        
        # 解析舌象信息
        self.tongue = case_data.get('tongue', None)
        
        # 解析病症列表（支持新旧格式）
        raw_disease = case_data.get('disease', [])
        self.disease_items = []
        self.disease_list = []
        
        for item in raw_disease:
            if isinstance(item, dict):
                # 新格式：字典
                di = DiseaseItem(
                    text=item.get('text', ''),
                    time=item.get('time', None),
                    time_order=item.get('time_order', 0),
                    severity_label=item.get('severity_label', None)
                )
                self.disease_items.append(di)
                self.disease_list.append(di.text)
            else:
                # 旧格式：纯字符串
                di = DiseaseItem(text=str(item), time_order=len(self.disease_items) + 1)
                self.disease_items.append(di)
                self.disease_list.append(str(item))
    
    def get_minnan_response(self) -> Optional[str]:
        """获取闽南魂触发响应
        
        根据SP定义的四种回应方式（system_prompt_zy.md 第162-191行）：
        A: 已婚已孕/已婚有孩子 或 已婚未孕打算要 → 正常诊疗（无特殊回应）
        B: 未婚 或 未婚未孕打算要 → "都多大岁数了，怎么还不结婚，再不结婚都怀不上了！"
        C: 未婚已孕 → "诶呀，人还是需要结婚的。不结婚到老了多孤独寂寞啊，也没有个伴之类的。"
        D: 已婚未孕不打算要 → "孩子还是很重要的，到老了你就知道了，别的人永远没有自己的孩子靠谱。"
        C+D: 未婚未孕不打算要 → 同时说C和D
        
        累计触发次数>=3次后，开启"好孕问诊模式"，并追加"来来来，我给你把个脉看看你身体如何。"
        """
        if self.patient.minnan_trigger_count == 0:
            return None
        
        # if self.patient.married is None:
        #     return None
        
        response = ''
        if self.patient.married:
            response = ''
        else:
            response = "都多大岁数了，怎么还不结婚，再不结婚都怀不上了！"
        
        # 追问模式，先不实现
        # if self.patient.married:
        #     # 已婚
        #     if self.patient.has_children is True:
        #         # 回应方式A：已婚已孕/有孩子 → 正常诊疗
        #         response = ''
        #     elif self.patient.has_children is False:
        #         # 已婚未孕
        #         if self.patient.want_children is True:
        #             # 回应方式A：已婚未孕，打算要小孩 → 正常诊疗
        #             response = ''
        #         elif self.patient.want_children is False:
        #             # 回应方式D：已婚未孕，不打算要小孩
        #             response = "孩子还是很重要的，到老了你就知道了，别的人永远没有自己的孩子靠谱。"
        #         else:
        #             # 已婚未孕但未表明是否打算要，先不触发
        #             response = ''
        #     else:
        #         # 已婚但未知是否有孩子，先不触发
        #         response = ''
        # elif self.patient.married is False:
        #     # 未婚
        #     if self.patient.has_children is True:
        #         # 回应方式C：未婚已孕
        #         response = "诶呀，人还是需要结婚的。不结婚到老了多孤独寂寞啊，也没有个伴之类的。"
        #     elif self.patient.has_children is False:
        #         # 未婚未孕
        #         if self.patient.want_children is True:
        #             # 回应方式B：未婚未孕，打算要小孩
        #             response = "都多大岁数了，怎么还不结婚，再不结婚都怀不上了！"
        #         elif self.patient.want_children is False:
        #             # 回应方式C+D：未婚未孕，不打算要小孩
        #             response = "诶呀，人还是需要结婚的。不结婚到老了多孤独寂寞啊，也没有个伴之类的。孩子还是很重要的，到老了你就知道了，别的人永远没有自己的孩子靠谱。"
        #         else:
        #             # 未婚未孕但未表明是否打算要，默认回应方式B
        #             response = "都多大岁数了，怎么还不结婚，再不结婚都怀不上了！"
        #     else:
        #         # 未婚但未知是否有孩子，默认回应方式B
        #         response = "都多大岁数了，怎么还不结婚，再不结婚都怀不上了！"
        # else:
        #     # 婚姻状况未知，不做输出
        #     response = ''
        
        # 累计触发次数>=3次，开启好孕问诊模式
        if self.patient.minnan_trigger_count >= 3:
            self.patient.good_pregnancy_mode = True
            response += "来来来，我给你把个脉看看你身体如何。"
        
        return response
    
    def diagnose_li_single(self, single_disease: str):
        """对单个病症条目进行表里辨证"""
        # 里证判断
        organ_keywords = [
                        "心慌", "心悸", "胸闷", "失眠", "多梦", "舌尖痛",
                        "咳嗽", "气喘", "咳痰", "胸痛","干咳",
                         "便秘", "腹泻", "拉肚子", 
                         "纳差", "腹胀", "便溏", "身重", "身体沉重",
                         "胃痛", "呕吐", "反酸", "烧心",
                         "两胁胀痛", "易怒", "乳房胀痛", "口苦", "头晕",
                         "腰膝酸软", "耳鸣", "遗精", "阳痿", "脱发", "五更泻",
                         "尿频", "尿急", "尿痛", 
                         ]
        severity_words = ["很严重", "很难受", "很痛苦"]
        
        matched_organ = self.match_keywords(single_disease, organ_keywords)
        if matched_organ:
            self.diagnosis.li_zheng = True
            self.add_diagnosis_basis("里证", f"脏腑症状：{'、'.join(matched_organ[:3])}")
        matched_severity = self.match_keywords(single_disease, severity_words)
        if matched_severity:
            # 排除外伤类
            if not any(self.keyword_match(single_disease, word) for word in ["牙痛", "摔伤", "磕伤", "撞伤", "呛水", "鱼刺", "切伤", "划伤"]):
                self.diagnosis.li_zheng = True
                self.add_diagnosis_basis("里证", f"严重程度词：{'、'.join(matched_severity[:2])}")
        

    def diagnose_biao_single(self, single_disease: str):    
        # 表证判断（仅在非里证时判断）
        if not self.diagnosis.li_zheng:
            biao_matched = []
            if self.keyword_match(single_disease, "恶寒"):
                biao_matched.append("恶寒")
            if self.keyword_match(single_disease, "怕冷"):
                biao_matched.append("怕冷")
            time_phrases = self.match_keywords(single_disease, ["前天还好好的", "不知道从什么时候"])
            if biao_matched or time_phrases:
                self.diagnosis.biao_zheng = True
                basis_parts = []
                if biao_matched:
                    basis_parts.append(f"外感症状：{'、'.join(biao_matched)}")
                if time_phrases:
                    basis_parts.append(f"急性起病：{'、'.join(time_phrases)}")
                self.add_diagnosis_basis("表证", "；".join(basis_parts))
    
    def diagnose_han_re_single(self, single_disease: str):
        """对单个病症条目进行寒热辨证"""
        # 寒证
        han_keywords = ["恶寒", "热敷缓解","面色发白", "冷痛","苔白", "苔湿", "热有帮助"]  
        matched_han = self.match_keywords(single_disease, han_keywords)
        if matched_han:
            self.diagnosis.han_zheng = True
            self.add_diagnosis_basis("寒证", f"寒象关键词：{'、'.join(matched_han[:3])}")
        
        # 热证
        re_keywords = ["发热", "口干", "想喝水", "渴", "舌红", "面色发红", "冷有帮助"
                       ]
        # 苔黄需配合舌干/舌燥/舌少津才触发热证（文档规定）
        tai_huang_patterns = ["苔黄.*舌干", "苔黄.*舌燥", "苔黄.*舌少津",
                              "舌干.*苔黄", "舌燥.*苔黄", "舌少津.*苔黄"]
        # 冷源帮助判断：冷源对不适有帮助
        # leng_yuan_patterns = ["放了个冰袋", "冰敷", "冷敷", "喝冷的", "喝凉的", "凉水.*好"]
        matched_re = self.match_keywords(single_disease, re_keywords)
        if matched_re:
            self.diagnosis.re_zheng = True
            self.add_diagnosis_basis("热证", f"热象关键词：{'、'.join(matched_re[:3])}")
        matched_tai_huang = [p for p in tai_huang_patterns if re.search(p, single_disease)]
        if matched_tai_huang:
            self.diagnosis.re_zheng = True
            self.add_diagnosis_basis("热证", "苔黄+舌干/燥/少津 → 热证")
    
    def diagnose_xu_shi_single(self, single_disease: str):
        """对单个病症条目进行虚实辨证"""
        # 虚证
        xu_keywords = ["疼痛感弱", "不痛苦", "感受不明显", 
                    "没力气", "没有力气", "乏力", "疲乏", "缺乏精力", 
                    "先天不足","经常生病",  
                    "身体素质不好", 
                    "喜按"]
        
        
        matched_xu = self.match_keywords(single_disease, xu_keywords)
        if matched_xu:
            self.diagnosis.xu_zheng = True
            self.add_diagnosis_basis("虚证", f"虚损关键词：{'、'.join(matched_xu[:3])}")
        
        
        # 实证
        shi_keywords = ["疼痛感强", "感受明显", 
        "实性病变", 
        "硬块", "硬块", "硬结", "疙瘩", "硬团", "一碰就疼", "很涨", "很鼓",
                       "按压很疼", "按压疼", "胀得鼓鼓", "很胀", "很鼓", "腹胀"]
        matched_shi = self.match_keywords(single_disease, shi_keywords)
        if matched_shi:
            self.diagnosis.shi_zheng = True
            self.add_diagnosis_basis("实证", f"实邪关键词：{'、'.join(matched_shi[:3])}")

        # 实热
        if self.diagnosis.shi_zheng and self.diagnosis.re_zheng:
            self.diagnosis.shi_re_zheng = True
            self.add_diagnosis_basis("实热证", "实证+热证→实热证")
    
    def _invalidate_fake_zheng(self, fake_type: str):
        """将假证设为无效，禁止用假证特征进行下一步判定
        
        SP规则（第254行）：真x假x代表真实的证是有效的，假的证是无效的。
        如"真寒假热"代表寒证是真实的，热证是虚假的，此时热证判定无效。
        
        Args:
            fake_type: 假证类型，可选值："寒"、"热"、"虚"、"实"
        """
        if fake_type == "寒":
            # 真热假寒：寒证为假，设为无效
            self.diagnosis.han_zheng = False
            self.add_diagnosis_basis("假证无效化", "真热假寒 → 寒证判定无效，禁止用于下一步辨证")
        elif fake_type == "热":
            # 真寒假热：热证为假，设为无效
            self.diagnosis.re_zheng = False
            self.add_diagnosis_basis("假证无效化", "真寒假热 → 热证判定无效，禁止用于下一步辨证")
        elif fake_type == "虚":
            # 真实假虚：虚证为假，设为无效
            self.diagnosis.xu_zheng = False
            self.add_diagnosis_basis("假证无效化", "真实假虚 → 虚证判定无效，禁止用于下一步辨证")
        elif fake_type == "实":
            # 真虚假实：实证为假，设为无效
            self.diagnosis.shi_zheng = False
            self.add_diagnosis_basis("假证无效化", "真虚假实 → 实证判定无效，禁止用于下一步辨证")
    
    def diagnose_zhen_jia_han_re(self, all_texts):
        """真热假寒/真寒假热辨证：当同时具备寒证和热证时判断
        
        SP规则（第254行）：真x假x代表真实的证是有效的，假的证是无效的，
        禁止使用假证特征进行下一步判定。
        """
        if not (self.diagnosis.han_zheng and self.diagnosis.re_zheng):
            return
        
        # all_texts = ' '.join(self._get_all_disease_texts())
        
        # Priority 1：通过舌苔判断
        if self.keyword_match(all_texts, "苔黄"):
            self.diagnosis.zhen_re_jia_han = True
            self.add_diagnosis_basis("真热假寒证", "舌苔黄 → 真热假寒")
            self._invalidate_fake_zheng("寒")  # 寒证为假，设为无效
            return
        if self.keyword_match(all_texts, "苔白"):
            self.diagnosis.zhen_han_jia_re = True
            self.add_diagnosis_basis("真寒假热证", "舌苔白 → 真寒假热")
            self._invalidate_fake_zheng("热")  # 热证为假，设为无效
            return
        
        # Priority 2：通过饮水偏好判断
        # 喜冷水 → 真热假寒；喜热水 → 真寒假热
        re_shui_keywords = ["喜热饮", "喝热的舒服", "喜欢喝热水", "热有帮助", "热敷缓解"]
        leng_shui_keywords = ["喜冷饮","喜欢喝冷水", "冷有帮助"]
        
        likes_cold = any(self.keyword_match(all_texts, w) for w in leng_shui_keywords)
        likes_hot = any(self.keyword_match(all_texts, w) for w in re_shui_keywords)
        
        if likes_cold and not likes_hot:
            self.diagnosis.zhen_re_jia_han = True
            self.add_diagnosis_basis("真热假寒证", "喜冷饮 → 真热假寒")
            self._invalidate_fake_zheng("寒")  # 寒证为假，设为无效
        elif likes_hot and not likes_cold:
            self.diagnosis.zhen_han_jia_re = True
            self.add_diagnosis_basis("真寒假热证", "喜热饮 → 真寒假热")
            self._invalidate_fake_zheng("热")  # 热证为假，设为无效
        else:
            # 寒热并见但缺乏舌苔和饮水偏好信息，无法判断真假寒热
            self.diagnosis.han_re_bing_jian_unknown = True
            self.add_diagnosis_basis("寒热并见待定", "缺乏舌苔（苔黄/苔白）或饮水偏好（喜冷饮/喜热饮）信息，无法判断真热假寒或真寒假热")
    
    def diagnose_zhen_jia_xu_shi(self, all_texts):
        """真实假虚/真虚假实辨证：当同时具备虚证和实证时判断
        
        SP规则（第254行）：真x假x代表真实的证是有效的，假的证是无效的，
        禁止使用假证特征进行下一步判定。
        """
        if not (self.diagnosis.xu_zheng and self.diagnosis.shi_zheng):
            return
        
        # all_texts = ' '.join(self._get_all_disease_texts())
        
        # Priority 1：按压偏好
        if any(self.keyword_match(all_texts, w) for w in ["喜按"]):
            self.diagnosis.zhen_xu_jia_shi = True
            self.add_diagnosis_basis("真虚假实证", "按压减轻 → 真虚假实")
            self._invalidate_fake_zheng("实")  # 实证为假，设为无效
            return
        if any(self.keyword_match(all_texts, w) for w in ["按压加重"]):
            self.diagnosis.zhen_shi_jia_xu = True
            self.add_diagnosis_basis("真实假虚证", "按压加重 → 真实假虚")
            self._invalidate_fake_zheng("虚")  # 虚证为假，设为无效
            return
        
        # Priority 2：实性病变
        if any(self.keyword_match(all_texts, w) for w in ["实性病变", "肿块", "囊肿", "结节", "增生", "钙化"]):
            self.diagnosis.zhen_shi_jia_xu = True
            self.add_diagnosis_basis("真实假虚证", "实性病变 → 真实假虚")
            self._invalidate_fake_zheng("虚")  # 虚证为假，设为无效
            return
        
        # Priority 3：积滞
        if any(self.keyword_match(all_texts, w) for w in ["积食", "痰多", "瘀血", "血块", "食积"]):
            self.diagnosis.zhen_shi_jia_xu = True
            self.add_diagnosis_basis("真实假虚证", "积滞 → 真实假虚")
            self._invalidate_fake_zheng("虚")  # 虚证为假，设为无效
            return
        
        # Priority 4：精力
        if any(self.keyword_match(all_texts, w) for w in ["精力尚可", "精力不错", "精神不错"]):
            self.diagnosis.zhen_shi_jia_xu = True
            self.add_diagnosis_basis("真实假虚证", "精力尚可 → 真实假虚")
            self._invalidate_fake_zheng("虚")  # 虚证为假，设为无效
            return
        elif any(self.keyword_match(all_texts, w) for w in ["精力很差", "精神很差", "精力不好", "缺乏精力", "精力差", "精神差", "没精力"]):
            self.diagnosis.zhen_xu_jia_shi = True
            self.add_diagnosis_basis("真虚假实证", "精力很差 → 真虚假实")
            self._invalidate_fake_zheng("实")  # 实证为假，设为无效
            return


        # 虚实并见但缺乏明确辨证依据，标记为待定
        self.diagnosis.xu_shi_bing_jian_unknown = True
        self.add_diagnosis_basis("虚实并见待定", "缺乏按压偏好（喜按/拒按）、实性病变、积滞、精力状态等信息，无法明确判断真虚假实或真实假虚")
    
    def diagnose_yin_yang(self):
        """阴阳辨证（基于已有的寒热虚实判断）"""
        # 阳虚：寒证+虚证
        if self.diagnosis.han_zheng and self.diagnosis.xu_zheng:
            self.diagnosis.yang_xu = True
            self.add_diagnosis_basis("阳虚", "寒证+虚证→阳虚")
        
        # 阴虚：热证+虚证
        if self.diagnosis.re_zheng and self.diagnosis.xu_zheng:
            self.diagnosis.yin_xu = True
            self.add_diagnosis_basis("阴虚", "热证+虚证→阴虚")
        
        # 阴阳两虚
        if self.diagnosis.yang_xu and self.diagnosis.yin_xu:
            self.diagnosis.yin_yang_liang_xu = True
            self.add_diagnosis_basis("阴阳两虚", "阳虚+阴虚→阴阳两虚")
    
    def diagnose_yin_yang_single(self, single_disease: str):
        """对单个病症条目进行阴阳辨证补充（需虚证为前提）"""
        if not self.diagnosis.xu_zheng:
            return
        
        # 阳虚舌象判断：虚证 + 苔白 + 舌胖
        has_tai_bai = self.keyword_match(single_disease, "苔白") or self.keyword_match(single_disease, "舌苔白")
        has_she_pang = any(self.keyword_match(single_disease, w) for w in ["舌胖"])
        
        if has_tai_bai and has_she_pang:
            self.diagnosis.yang_xu = True
            self.add_diagnosis_basis("阳虚", "虚证+阳虚舌象：苔白+舌胖")
        
        # 两颧潮红、五心烦热、潮热、盗汗
        yin_xu_specific = ["两颧潮红", "五心烦热", "潮热", "盗汗"]
        matched_yin = self.match_keywords(single_disease, yin_xu_specific)
        if matched_yin:
            self.diagnosis.yin_xu = True
            self.add_diagnosis_basis("阴虚", f"虚证+阴虚特征症状：{'、'.join(matched_yin)}")
        
        # SP规定的阴虚舌象判断：舌红 + 少苔/无苔、舌燥、舌有裂纹
        has_she_hong = self.keyword_match(single_disease, "舌红")
        has_shao_tai = any(self.keyword_match(single_disease, w) for w in ["少苔", "无苔"])
        has_she_zao = any(self.keyword_match(single_disease, w) for w in ["舌燥", "舌面干燥"])
        has_she_liewen = any(self.keyword_match(single_disease, w) for w in ["舌有裂纹", "舌裂", "裂纹舌"])
        
        yin_xu_tongue_signs = []
        if has_she_hong and has_shao_tai:
            yin_xu_tongue_signs.append("舌红+少苔/无苔")
        if has_she_zao:
            yin_xu_tongue_signs.append("舌燥")
        if has_she_liewen:
            yin_xu_tongue_signs.append("舌有裂纹")
        
        if '舌红+少苔/无苔' in yin_xu_tongue_signs and (has_she_zao or has_she_liewen):
            self.diagnosis.yin_xu = True
            self.add_diagnosis_basis("阴虚", f"虚证+阴虚舌象：{'、'.join(yin_xu_tongue_signs)}")

        # 阴阳两虚
        if self.diagnosis.yang_xu and self.diagnosis.yin_xu and (not self.diagnosis.yin_yang_liang_xu):
            self.diagnosis.yin_yang_liang_xu = True
            self.add_diagnosis_basis("阴阳两虚", "阳虚+阴虚→阴阳两虚")
    
    def diagnose_critical_single(self, single_disease: str):
        """对单个病症条目进行危症判断"""
        context = single_disease
        
        # 亡阳证：寒证 + 大汗淋漓/冷汗 + 四肢冰凉 + 面色惨白
        # SP要求4个条件全部满足
        wang_yang_signs = []
        has_cold_sweat = False
        has_cold_limbs = False
        has_pale_face = False
        
        for word in ["大汗淋漓", "冷汗"]:
            if self.keyword_match(context, word):
                wang_yang_signs.append(f"冷汗症状：{word}")
                has_cold_sweat = True
                break
        for word in ["四肢冰凉", "手脚冰凉", "肢体厥冷"]:
            if self.keyword_match(context, word):
                wang_yang_signs.append(f"四肢冰凉：{word}")
                has_cold_limbs = True
                break
        for word in ["面色惨白", "面色苍白", "面色发白"]:
            if self.keyword_match(context, word):
                wang_yang_signs.append(f"面色惨白：{word}")
                has_pale_face = True
                break
        
        # 必须同时满足：寒证 + 3个症状全部存在
        if self.diagnosis.han_zheng and has_cold_sweat and has_cold_limbs and has_pale_face:
            self.diagnosis.wang_yang = True
            for sign in wang_yang_signs:
                self.add_diagnosis_basis("亡阳证", sign)
            self.add_diagnosis_basis("亡阳证", "前提：已有寒证")
        
        # 亡阴证：热证 + 大汗 + 出热汗/油汗 + 渴喜冷饮
        # SP要求4个条件全部满足
        wang_yin_signs = []
        has_heavy_sweat = False
        has_hot_sweat = False
        has_thirst_cold = False
        
        if self.keyword_match(context, "恶寒") and self.keyword_match(context, "发热"):
            wang_yin_signs.append("恶寒+发热")
            has_heavy_sweat = True
        for word in ["两颧潮红"]:
            if self.keyword_match(context, word):
                wang_yin_signs.append(f"两颧潮红：{word}")
                has_hot_sweat = True
        for word in ["渴喜冷饮"]:
            if self.keyword_match(context, word):
                wang_yin_signs.append(f"渴喜冷饮：{word}")
                has_thirst_cold = True
                break
        # # 排除手脚凉（与亡阳冲突）
        if self.keyword_match(context, "手脚冰凉") or self.keyword_match(context, "四肢冰凉") or self.keyword_match(context, "手脚凉"):
            has_heavy_sweat = False
            has_hot_sweat = False
            has_thirst_cold = False
            wang_yin_signs = []
        
        # 必须同时满足：热证 + 3个症状全部存在
        if self.diagnosis.re_zheng and has_heavy_sweat and has_hot_sweat and has_thirst_cold:
            self.diagnosis.wang_yin = True
            for sign in wang_yin_signs:
                self.add_diagnosis_basis("亡阴证", sign)
            self.add_diagnosis_basis("亡阴证", "前提：已有热证")
    
    def diagnose_liu_yin_single(self, single_disease: str):
        """对单个病症条目进行六淫辨证"""
        # 风淫证
        feng_keywords = ["讨厌吹风", "皮肤瘙痒", "麻木", "游走性疼痛", "浮肿"]
        matched_feng = self.match_keywords(single_disease, feng_keywords)
        if matched_feng:
            self.diagnosis.feng_yin = True
            self.add_diagnosis_basis("风淫证", f"风邪症状：{', '.join(matched_feng)}")
        
        # 寒淫证（满足1点即可：恶寒、疼痛、苔白）
        han_yin_signs = []
        if self.diagnosis.han_zheng:
            han_yin_signs.append("恶寒/寒证")
        if any(self.keyword_match(single_disease, w) for w in ["疼痛", "痛", "疼", "冷痛", "胀痛", "刺痛"]):
            han_yin_signs.append("疼痛")
        if self.keyword_match(single_disease, "舌苔白") or self.keyword_match(single_disease, "苔白"):
            han_yin_signs.append("苔白")
        if han_yin_signs:
            self.diagnosis.han_yin = True
            self.add_diagnosis_basis("寒淫证", f"寒邪症状：{', '.join(han_yin_signs)}")
        
        # 湿淫证
        # SP规定：水肿、浮肿、身体沉重、关节酸痛、大便粘腻、舌苔厚腻、脉濡、拉肚子、小腹涨/鼓
        shi_keywords = ["水肿", 
                        "身体很重", "身体沉重", 
                        "拉肚子", "腹泻",
                        "小腹涨", "小腹鼓", 
                        "舌苔腻", 
                        "很困", "睡不醒",
                        ]
        matched_shi = self.match_keywords(single_disease, shi_keywords)
        if matched_shi:
            self.diagnosis.shi_yin = True
            self.add_diagnosis_basis("湿淫证", f"湿邪症状：{', '.join(matched_shi)}")
        
        # 暑淫证（仅夏季，需满足任意2点：发热、恶心/呕吐、疲乏、胸闷、舌红+苔黄+舌干）
        if self.season == '夏季':
            shu_signs = []
            if any(self.keyword_match(single_disease, w) for w in ["发热"]):
                shu_signs.append("发热")
            if any(self.keyword_match(single_disease, w) for w in ["恶心", "呕吐", "想吐"]):
                shu_signs.append("恶心/呕吐")
            if any(self.keyword_match(single_disease, w) for w in ["疲乏", "乏力"]):
                shu_signs.append("疲乏")
            if self.keyword_match(single_disease, "胸闷"):
                shu_signs.append("胸闷")
            if self.keyword_match(single_disease, "舌红") and self.keyword_match(single_disease, "苔黄") and any(self.keyword_match(single_disease, w) for w in ["舌干", "舌燥"]):
                shu_signs.append("舌红+苔黄+舌干")
            if len(shu_signs) >= 2:
                self.diagnosis.shu_yin = True
                self.add_diagnosis_basis("暑淫证", f"暑邪症状：{', '.join(shu_signs)}")
        
        # 燥淫证
        # SP规则：秋季干咳(限秋季)；皮肤/口/鼻/咽喉/嘴唇干燥(不限季节)
        zao_seasonal = ["干咳"]  # 仅秋季有效
        zao_any_season = ["皮肤干", "口干", "鼻干", "咽喉干", "嘴唇干"]  # 不限季节
        
        matched_zao_seasonal = self.match_keywords(single_disease, zao_seasonal)
        matched_zao_any = self.match_keywords(single_disease, zao_any_season)
        
        # 秋季干咳 或 任何季节的干燥症状
        if (matched_zao_seasonal and self.season == '秋季') or matched_zao_any:
            self.diagnosis.zao_yin = True
            matched_zao = (matched_zao_seasonal if self.season == '秋季' else []) + matched_zao_any
            self.add_diagnosis_basis("燥淫证", f"燥邪症状：{', '.join(matched_zao)}")
        
        # 火淫证
        huo_keywords = ["发热", "口渴", "面红", "疮"]
        matched_huo = self.match_keywords(single_disease, huo_keywords)

        zuore = ["胸部灼热", "腹部灼热", "胸部发热", "腹部发热"]
        has_zhuore = self.match_keywords(single_disease, zuore)
        if has_zhuore:
            matched_huo.append(f"胸部/腹部灼热: {has_zhuore}")
        
        has_bianmi = self.match_keywords(single_disease, ["便秘", "尿黄"])
        if has_bianmi:
            matched_huo.append(','.join(has_bianmi))

        # "舌（体）红"+"舌苔黄"+"舌干" 需要同时满足才算一个判断点
        has_she_hong = self.keyword_match(single_disease, "舌红")
        has_tai_huang = self.keyword_match(single_disease, "苔黄")
        has_she_gan = self.keyword_match(single_disease, "舌干")
        if has_she_hong and has_tai_huang and has_she_gan:
            matched_huo.append("舌红+苔黄+舌干")
        
        if len(matched_huo) >= 2:
            self.diagnosis.huo_yin = True
            self.add_diagnosis_basis("火淫证", f"火邪症状：{', '.join(matched_huo)}")
    
    def diagnose_qi_qing_single(self, single_disease: str):
        """对单个病症条目判断七情内伤
        
        七情内伤的判断规则：
        1. 情志词和脏腑定位必须在同一个句子内
        2. 需要有因果关系
        3. 记录具体的致病情绪类型（怒→肝，喜/惊→心，思→脾，悲/忧→肺，恐/惊→肾）
        """
        # 清理context中的markdown格式
        clean_context = re.sub(r'\*+', '', single_disease)  # 移除所有星号
        clean_context = re.sub(r'\\+', '', clean_context)  # 移除反斜杠（单个或多个）
        
        # 七情情志词定义（按情绪类型分类）
        emotion_keywords = {
            '怒': {
                'extreme': ["气炸了", "气死", "暴怒"],
                'combo_nouns': ["生气", "愤怒", "发火"],
                'target_organ': '肝'
            },
            '喜': {
                'extreme': ["狂喜", "乐极生悲"],
                'combo_nouns': ["高兴", "开心"],
                'target_organ': '心'
            },
            
            '思': {
                'extreme': [],
                'combo_nouns': ["想念", "思念"],
                'target_organ': '脾'
            },
            '悲': {
                'extreme': ["崩溃", "绝望", "痛哭", "嚎啕大哭", "流泪不止"],
                'combo_nouns': ["难过", "伤心", "悲痛"],
                'target_organ': '肺'
            },
            '忧': {
                'extreme': [],
                'combo_nouns': ["忧郁"],
                'target_organ': '肺'
            },
            '恐': {
                'extreme': [],
                'combo_nouns': ["害怕", "恐惧", "忧虑", "担心"],
                'target_organ': '肾'
            },
            '惊': {
                'extreme': ["吓破胆", "惊恐", "吓死", "惊吓", "受惊"],
                'combo_nouns': ["惊吓"],
                'target_organ': '肾' 
            },
        }
        
        # 程度副词
        degree_adverbs = ["非常", "特别", "超级", "极其", "贼", "很", "巨", "最", "大", "太"]
        
        # 脏腑定位关键词
        organ_keywords = {
            '心': ["心悸", "失眠", "多梦", "胸闷", "心慌"],
            '肝': ["两胁胀痛", "胁痛", "易怒", "口苦", "头晕", "乳房胀痛"],
            '脾': ["纳差", "饭后腹胀",  "便溏", "身重", "身体沉重"],
            '肺': ["咳嗽", "气喘", "胸痛", "咳痰", "干咳"],
            '肾': ["腰膝酸软", "耳鸣", "遗精", "阳痿", "脱发", "五更泻","尿频", "尿急", "尿痛"],
        }
        
        # 因果关系连接词（用于分割前后部分）
        causality_connectors = [
            "因为.*所以", "一.*就", "自从.*就开始", "以致", "致使", 
            "之所以.*是因为", "后出现", "就出现", "当天就出现",
            "之后一直", "之后.*出现"
        ]
        
        # 构建所有情绪词列表（用于正则匹配）
        all_emotion_words = []
        for emo_type, emo_data in emotion_keywords.items():
            for word in emo_data['extreme']:
                all_emotion_words.append((word, emo_type, emo_data['target_organ']))
            for adverb in degree_adverbs:
                for noun in emo_data['combo_nouns']:
                    combo = adverb + noun
                    all_emotion_words.append((combo, emo_type, emo_data['target_organ']))
        
        # 构建所有脏腑症状词列表
        all_organ_symptoms = []
        for organ, keywords in organ_keywords.items():
            for keyword in keywords:
                all_organ_symptoms.append((keyword, organ))
        
        # 检测情绪词及其位置
        def find_emotion_positions(text):
            """返回 [(情绪词, 情绪类型, 目标脏腑, 起始位置)]"""
            results = []
            for word, emo_type, target_organ in all_emotion_words:
                pos = text.find(word)
                if pos != -1:
                    results.append((word, emo_type, target_organ, pos))
            return results
        
        # 检测脏腑症状词及其位置
        def find_organ_positions(text):
            """返回 [(症状词, 脏腑, 起始位置)]"""
            results = []
            for keyword, organ in all_organ_symptoms:
                pos = text.find(keyword)
                if pos != -1:
                    results.append((keyword, organ, pos))
            return results
        
        # 检查是否有因果关系连接词
        def has_causality_connector(text):
            for connector in causality_connectors:
                if re.search(connector, text):
                    return True
            return False
        
        # 检测情绪词和脏腑症状词
        emotion_positions = find_emotion_positions(clean_context)
        organ_positions = find_organ_positions(clean_context)
        
        if not emotion_positions or not organ_positions:
            return
        
        if not has_causality_connector(clean_context):
            return
        
        # 匹配：情绪词在前，脏腑症状词在后，且目标脏腑一致
        matched_pairs = []  # [(情绪类型, 情绪词, 目标脏腑, 症状词列表)]
        
        for emo_word, emo_type, target_organ, emo_pos in emotion_positions:
            matched_symptoms = []
            for symptom_word, organ, symptom_pos in organ_positions:
                # 情绪词必须在症状词前面，且脏腑匹配
                if organ == target_organ:
                    matched_symptoms.append(symptom_word)
            
            if matched_symptoms:
                matched_pairs.append((emo_type, emo_word, target_organ, matched_symptoms))
        
        if not matched_pairs:
            return
        
        # 设置诊断结果
        for emo_type, emo_word, target_organ, organ_symptoms in matched_pairs:
            self.diagnosis.has_qi_qing_nei_shang = True
            if not self.diagnosis.qi_qing_trigger_word:
                self.diagnosis.qi_qing_trigger_word = emo_word
            
            # 根据目标脏腑设置对应的七情伤X标志和情绪类型
            if target_organ == '心':
                self.diagnosis.qi_qing_shang_xin = True
                if not self.diagnosis.qi_qing_xin_emotion:
                    self.diagnosis.qi_qing_xin_emotion = emo_type
                self.add_diagnosis_basis("七情伤心", f"{emo_type}伤心：{emo_word} → {', '.join(organ_symptoms)}")
            elif target_organ == '肝':
                self.diagnosis.qi_qing_shang_gan = True
                if not self.diagnosis.qi_qing_gan_emotion:
                    self.diagnosis.qi_qing_gan_emotion = emo_type
                self.add_diagnosis_basis("七情伤肝", f"{emo_type}伤肝：{emo_word} → {', '.join(organ_symptoms)}")
            elif target_organ == '脾':
                self.diagnosis.qi_qing_shang_pi = True
                if not self.diagnosis.qi_qing_pi_emotion:
                    self.diagnosis.qi_qing_pi_emotion = emo_type
                self.add_diagnosis_basis("七情伤脾", f"{emo_type}伤脾：{emo_word} → {', '.join(organ_symptoms)}")
            elif target_organ == '肺':
                self.diagnosis.qi_qing_shang_fei = True
                if not self.diagnosis.qi_qing_fei_emotion:
                    self.diagnosis.qi_qing_fei_emotion = emo_type
                self.add_diagnosis_basis("七情伤肺", f"{emo_type}伤肺：{emo_word} → {', '.join(organ_symptoms)}")
            elif target_organ == '肾':
                self.diagnosis.qi_qing_shang_shen = True
                if not self.diagnosis.qi_qing_shen_emotion:
                    self.diagnosis.qi_qing_shen_emotion = emo_type
                self.add_diagnosis_basis("七情伤肾", f"{emo_type}伤肾：{emo_word} → {', '.join(organ_symptoms)}")
    
    def diagnose_qi_xue_jin_ye_single(self, single_disease: str):
        """对单个病症条目进行气血津液辨证"""
        # 气虚证
        qi_xu_signs = 0
        qi_xu_keywords = ZHENG_KEYWORDS["气虚证"]
        for word in qi_xu_keywords:
            if self.keyword_match(single_disease, word):
                qi_xu_signs += 1
        
        if self.diagnosis.xu_zheng and qi_xu_signs >= 2:
            self.diagnosis.qi_xu = True
            matched_qi_xu = [w for w in qi_xu_keywords if self.keyword_match(single_disease, w)]
            self.add_diagnosis_basis("气虚", f"虚证 + 气虚症状：{'、'.join(matched_qi_xu)}")
        
        # 气脱证判断：
        # 1. 满足气脱症状≥2个（精神萎靡、瞳孔散大、呼吸微弱、大便/小便失禁、手撒）
        # 2. 或者：气虚证 + 任意1个气脱症状
        qi_tuo_keywords = ["精神萎靡", "瞳孔散大", "手撒"]
        shijin_words = ["大便失禁", "小便失禁"]
        qi_tuo_match_words = self.match_keywords(single_disease, qi_tuo_keywords)
        shijin_match_words = self.match_keywords(single_disease, shijin_words)
        if self.diagnosis.qi_xu and (qi_tuo_match_words or shijin_match_words):
            self.diagnosis.qi_tuo = True
            self.add_diagnosis_basis("气脱证", "气虚证升级")
            self.add_diagnosis_basis("气脱证", f"气脱症状：{qi_tuo_match_words + shijin_match_words}")
        
        # 气滞证（满足任二点：胀痛/胀满、游走性疼痛、情绪波动加重）
        qi_zhi_signs = 0
        qi_zhi_matched = []
        qi_zhi_keywords = ZHENG_KEYWORDS['气滞证']
        for word in qi_zhi_keywords:
            if self.match_keywords(single_disease, word):
                qi_zhi_signs += 1
                qi_zhi_matched.append('/'.join(word))
        if len(qi_zhi_matched) >= 2:
            self.diagnosis.qi_zhi = True
            self.add_diagnosis_basis("气滞", f"气滞症状：{'、'.join(qi_zhi_matched)}")


        # 血虚证
        xue_xu_signs = 0
        xue_xu_keywords = ZHENG_KEYWORDS["血虚证"]

        matched_xue_xu = []
        for word in xue_xu_keywords:
            if self.match_keywords(single_disease, word):
                xue_xu_signs += 1
                matched_xue_xu.append('/'.join(word))
        if self.diagnosis.xu_zheng and xue_xu_signs >= 2:
            self.diagnosis.xue_xu = True
            self.add_diagnosis_basis("血虚", f"虚证 + 血虚症状：{'、'.join(matched_xue_xu)}")
        
        # 气血两虚
        if self.diagnosis.qi_xu and self.diagnosis.xue_xu:
            self.diagnosis.qi_xue_liang_xu = True
            self.add_diagnosis_basis("气血两虚", "气虚+血虚→气血两虚")
        
        
        # 血瘀证
        xue_yu_signs = 0
        xue_yu_keywords = ZHENG_KEYWORDS["血瘀证"]
        citong = self.keyword_match(single_disease, "刺痛") and self.keyword_match(single_disease, "固定不移")
        yejian = self.keyword_match(single_disease, "夜间加重")
        mianse = self.keyword_match(single_disease, "面色晦暗") or self.keyword_match(single_disease, "瘀斑")
        shexiang = self.keyword_match(single_disease, "舌紫暗") or self.keyword_match(single_disease, "舌瘀点")

        for tag in [citong, yejian, mianse, shexiang]:
            if tag:
                xue_yu_signs += 1

        if xue_yu_signs >= 2:
            self.diagnosis.xue_yu = True
            matched_xue_yu = [w for w in xue_yu_keywords if self.keyword_match(single_disease, w)]
            self.add_diagnosis_basis("血瘀", f"血瘀症状：{'、'.join(matched_xue_yu)}")
        
        # 血热证（热证 + 满足任一点）
        if self.diagnosis.re_zheng:
            xue_re_keywords = ZHENG_KEYWORDS["血热证"]
            for word in xue_re_keywords:
                match_xue_re = self.match_keywords(single_disease, word)
                if match_xue_re:
                    self.diagnosis.xue_re = True
                    self.add_diagnosis_basis("血热证", f"热证 + {match_xue_re}")
        
        # 血寒证
        if self.diagnosis.han_zheng:
            xue_han_keywords = ZHENG_KEYWORDS["血寒证"]
            tengtong = self.keyword_match(single_disease, "少腹疼痛") 
            refu = self.keyword_match(single_disease, "热敷缓解") and  self.keyword_match(single_disease, "痛经")
            yuejing = refu or self.keyword_match(single_disease, "月经延后") or self.keyword_match(single_disease, "色暗有血块") 
            matched_xue_han = [w for w in xue_han_keywords if self.keyword_match(single_disease, w)]
            if tengtong or yuejing:
                self.diagnosis.xue_han = True
                self.add_diagnosis_basis("血寒", f"寒证 + 血寒症状：{'、'.join(matched_xue_han)}")
        
        # 津液不足（满足任二点：口渴喜饮、皮肤干燥起皮、尿少/便干）
        jin_ye_signs = 0
        match_words = []
        if any(self.keyword_match(single_disease, w) for w in ["口渴", "喜欢喝水", "想喝水", "渴"]):
            jin_ye_signs += 1
            match_words.append('喜欢喝水')
        if any(self.keyword_match(single_disease, w) for w in ["皮肤干燥", "起皮", "皮肤干"]):
            jin_ye_signs += 1
            match_words.append('皮肤干燥')
        if any(self.keyword_match(single_disease, w) for w in ["尿少", "便干", "大便干燥"]):
            jin_ye_signs += 1
            match_words.append('尿少/大便干燥')
        if jin_ye_signs >= 2:
            self.diagnosis.jin_ye_bu_zu = True
            self.add_diagnosis_basis("津液不足", "满足津液不足：{}".format('、'.join(match_words)))
    
    def diagnose_zang_fu_single(self, single_disease: str):
        """对单个病症条目进行脏腑辨证"""
        # 心与小肠
        xin_keywords = ["心慌", "心悸", "胸闷", "失眠", "多梦"]
        matched_xin = self.match_keywords(single_disease, xin_keywords)
        has_xin = len(matched_xin) > 0
        
        # 检测失眠症状（用于心脾两虚判断）
        if self.keyword_match(single_disease, "失眠") or self.keyword_match(single_disease, "睡不着"):
            self.diagnosis.has_shi_mian = True
        
        if self.diagnosis.qi_xue_liang_xu and self.diagnosis.has_shi_mian:
            self.diagnosis.xin_pi_liang_xu = True
            self.add_diagnosis_basis("心脾两虚", "气血两虚+失眠→心脾两虚")
        

        if has_xin:
            # 心气虚：心定位 + 气虚证
            if self.diagnosis.qi_xu:
                self.diagnosis.xin_qi_xu = True
                self.add_diagnosis_basis("心气虚", f"心部症状：{', '.join(matched_xin)} + 气虚")
            # 心血虚：心定位 + 血虚证
            if self.diagnosis.xue_xu:
                self.diagnosis.xin_xue_xu = True
                self.add_diagnosis_basis("心血虚", f"心部症状：{', '.join(matched_xin)} + 血虚")
            # 心阴虚：心定位 + 阴虚证
            if self.diagnosis.yin_xu:
                self.diagnosis.xin_yin_xu = True
                self.add_diagnosis_basis("心阴虚", f"心部症状：{', '.join(matched_xin)} + 阴虚")
            # 心阳虚：心定位 + 阳虚证
            if self.diagnosis.yang_xu:
                self.diagnosis.xin_yang_xu = True
                self.add_diagnosis_basis("心阳虚", f"心部症状：{', '.join(matched_xin)} + 阳虚")
            # 心脉痹阻：心定位 + 血瘀证
            if self.diagnosis.xue_yu:
                self.diagnosis.xin_mai_bi_zu = True
                self.add_diagnosis_basis("心脉痹阻", f"心部症状：{', '.join(matched_xin)} + 血瘀")
            # 心火亢盛：心定位 + 热证（特指失眠/口疮）
            if self.diagnosis.re_zheng and (self.keyword_match(single_disease, "失眠") or self.keyword_match(single_disease, "口疮")):
                self.diagnosis.xin_huo_kang_sheng = True
                self.add_diagnosis_basis("心火亢盛", f"心部症状：{', '.join(matched_xin)} + 热证/失眠/口疮")
            # 七情伤心已在diagnose_qi_qing_single中处理（需要情志词+脏腑定位在同一句子内）
        
        # 心火下移小肠：舌尖痛
        if self.keyword_match(single_disease, "舌尖痛"):
            self.diagnosis.xin_huo_xia_yi = True
            self.add_diagnosis_basis("心火下移小肠", "舌尖痛")

        # 肺与大肠
        fei_keywords = ["咳嗽", "气喘", "咳痰", "胸痛", "干咳"]
        da_chang_keywords = ["便秘", "腹泻", "拉肚子"]
        
        matched_fei = self.match_keywords(single_disease, fei_keywords)
        has_fei = len(matched_fei) > 0
        has_da_chang = any(self.keyword_match(single_disease, word) for word in da_chang_keywords)
        
        if has_fei:
            if self.diagnosis.qi_xu:
                self.diagnosis.fei_qi_xu = True
                self.add_diagnosis_basis("肺气虚", f"肺定位：{', '.join(matched_fei)}")
                self.add_diagnosis_basis("肺气虚", "气虚（全局）")
                self.add_diagnosis_basis("肺气虚", "判断路径：肺定位+气虚→肺气虚")
            if self.diagnosis.yin_xu or self.keyword_match(single_disease, "干咳") or self.keyword_match(single_disease, "无痰"):
                self.diagnosis.fei_yin_xu = True
                # 记录肺定位依据
                self.add_diagnosis_basis("肺阴虚", f"肺定位：{', '.join(matched_fei)}")
                # 记录判断路径：阴虚特征 或 阴虚（全局）
                yin_xu_local = [w for w in ["干咳", "无痰"] if self.keyword_match(single_disease, w)]
                if self.diagnosis.yin_xu:
                    self.add_diagnosis_basis("肺阴虚", "判断路径：肺定位+阴虚→肺阴虚")
                elif yin_xu_local:
                    self.add_diagnosis_basis("肺阴虚", "判断路径：肺定位+干咳/无痰→肺阴虚")

            if self.diagnosis.han_zheng and (self.keyword_match(single_disease, "痰白") or self.keyword_match(single_disease, "清稀")):
                self.diagnosis.han_tan_zu_fei = True
                self.add_diagnosis_basis("寒痰阻肺", f"肺定位：{', '.join(matched_fei)}")
                # 记录寒痰特征
                han_tan_local = [w for w in ["痰白", "清稀"] if self.keyword_match(single_disease, w)]
                if han_tan_local:
                    self.add_diagnosis_basis("寒痰阻肺", f"寒痰特征：{', '.join(han_tan_local)}")
                self.add_diagnosis_basis("寒痰阻肺", "寒证（全局）")
                self.add_diagnosis_basis("寒痰阻肺", "判断路径：肺定位+寒证+寒痰特征→寒痰阻肺")
            # 痰热壅肺：肺定位 + 热证 或 + 痰黄/稠
            has_tan_re_sign = self.keyword_match(single_disease, "黄痰") or self.keyword_match(single_disease, "痰黄") or self.keyword_match(single_disease, "痰稠")
            if has_tan_re_sign or self.diagnosis.re_zheng:
                self.diagnosis.tan_re_yong_fei = True
                # 记录肺定位依据
                self.add_diagnosis_basis("痰热壅肺", f"肺定位：{', '.join(matched_fei)}")
                # 记录判断路径：痰热特征 或 热证
                if has_tan_re_sign:
                    tan_re_details = []
                    if self.keyword_match(single_disease, "黄痰") or self.keyword_match(single_disease, "痰黄") or self.keyword_match(single_disease, "咳黄"):
                        tan_re_details.append("黄痰")
                    if self.keyword_match(single_disease, "痰稠"):
                        tan_re_details.append("痰稠")
                    self.add_diagnosis_basis("痰热壅肺", f"痰热特征：{', '.join(tan_re_details)}")
                    self.add_diagnosis_basis("痰热壅肺", "判断路径：肺定位+痰热特征→痰热壅肺")
                else:
                    self.add_diagnosis_basis("痰热壅肺", "热证（全局）")
                    self.add_diagnosis_basis("痰热壅肺", "判断路径：肺定位+热证→痰热壅肺")
            # 七情伤肺已在diagnose_qi_qing_single中处理（需要情志词+脏腑定位在同一句子内）
        
        # 大肠湿热：大肠定位 + 湿淫证 + 便秘/便臭/肛门灶热
        if has_da_chang:
            if self.diagnosis.shi_yin and any(self.keyword_match(single_disease, w) for w in ["便秘", "便臭", "肛门灶热"]):
                self.diagnosis.da_chang_shi_re = True
                self.add_diagnosis_basis("大肠湿热", "大肠症状 + 湿淫 + 便秘/便臭/肛门灶热")
            # 大肠虚寒：大肠定位 + 虚证 或 长期腹泻
            if self.diagnosis.xu_zheng or any(self.keyword_match(single_disease, w) for w in ["长期腹泻", "久泻"]):
                self.diagnosis.da_chang_xu_han = True
                self.add_diagnosis_basis("大肠虚寒", "大肠症状 + 虚证/长期腹泻")

        # 脾与胃
        pi_keywords = ["纳差", "饭后腹胀", "便溏", "身体沉重", "身重"]
        wei_keywords = ["胃痛", "胃疼", "胃巨疼", "呕吐", "反酸", "烧心", "胃冷痛"]
        
        matched_pi = self.match_keywords(single_disease, pi_keywords)
        matched_wei = self.match_keywords(single_disease, wei_keywords)
        has_pi = len(matched_pi) > 0
        has_wei = len(matched_wei) > 0
        
        if has_pi:
            if self.diagnosis.qi_xu:
                self.diagnosis.pi_qi_xu = True
                self.add_diagnosis_basis("脾气虚", f"脾定位：{', '.join(matched_pi)}")
                self.add_diagnosis_basis("脾气虚", "气虚（全局）")
                self.add_diagnosis_basis("脾气虚", "判断路径：脾定位+气虚→脾气虚")
            if self.diagnosis.yang_xu:
                self.diagnosis.pi_yang_xu = True
                self.add_diagnosis_basis("脾阳虚", f"脾定位：{', '.join(matched_pi)}")
                self.add_diagnosis_basis("脾阳虚", "阳虚（全局）")
                self.add_diagnosis_basis("脾阳虚", "判断路径：脾定位+阳虚→脾阳虚")
            if self.diagnosis.shi_yin:
                self.diagnosis.pi_xu_shi_kun = True
                self.add_diagnosis_basis("脾虚湿困", f"脾定位：{', '.join(matched_pi)}")
                self.add_diagnosis_basis("脾虚湿困", "湿淫证（全局）")
                self.add_diagnosis_basis("脾虚湿困", "判断路径：脾定位+湿淫→脾虚湿困")
            # 七情伤脾已在diagnose_qi_qing_single中处理（需要情志词+脏腑定位在同一句子内）
        
        if has_wei:
            # 胃火炽盛
            if any(self.keyword_match(single_disease, w) for w in ["口臭", "牙龈肿痛"]):
                self.diagnosis.wei_huo_chi_sheng = True
                self.add_diagnosis_basis("胃火炽盛", f"胃部症状：{', '.join(matched_wei)} + 口臭/牙龈肿")
            
            # 食滞胃脘：胃定位 + 舌苔"厚腻" + 纳差/食积/腹胀
            # 检查舌苔厚腻
            has_thick_greasy_tongue = any(self.keyword_match(single_disease, w) for w in ["舌苔厚腻", "厚腻"])
            # 检查纳差/食积/腹胀
            has_food_symptoms = any(self.keyword_match(single_disease, w) for w in ["纳差", "食积", "腹胀"])
            # 必须同时满足：胃定位 + 舌苔厚腻 + (纳差/食积/腹胀)
            if has_thick_greasy_tongue and has_food_symptoms:
                self.diagnosis.shi_zhi_wei_wan = True
                self.add_diagnosis_basis("食滞胃脘", f"胃部症状：{', '.join(matched_wei)} + 舌苔厚腻 + 纳差/食积/腹胀")
            
            # 胃气上逆：胃定位 + 干呕/呃逆 + 肺阴虚
            if any(self.keyword_match(single_disease, w) for w in ["干呕", "呃逆"]):
                if self.diagnosis.fei_yin_xu:
                    self.diagnosis.wei_qi_shang_ni = True
                    self.add_diagnosis_basis("胃气上逆", "胃部症状 + 干呕/呃逆 + 肺阴虚")
        
        # 胃寒证：胃冷痛可直接判断胃寒
        if self.keyword_match(single_disease, "胃冷痛"):
            self.diagnosis.wei_han_zheng = True
            self.add_diagnosis_basis("胃寒证", f"胃部症状：胃冷痛")

        # 虚劳里急：腹痛 + 喜按 + 气血两虚证
        if self.keyword_match(single_disease, "腹痛") and self.diagnosis.qi_xue_liang_xu:
            if any(self.keyword_match(single_disease, w) for w in ["喜按"]):
                self.diagnosis.xu_lao_li_ji = True
                self.add_diagnosis_basis("虚劳里急", "腹痛 + 喜按 + 气血两虚")
        
        # 肝与胆
        # SP规定肝胆定位：两胁（肋骨）胀痛、易怒、乳房胀痛、口苦、头晕
        gan_dan_keywords = ["两胁胀痛", "口苦", "头晕", "易怒", "乳房胀痛"]
        matched_gan = self.match_keywords(single_disease, gan_dan_keywords)
        has_gan = len(matched_gan) > 0
        
        if has_gan:
            if self.diagnosis.qi_zhi:
                self.diagnosis.gan_qi_yu_jie = True
                self.add_diagnosis_basis("肝气郁结", f"肝胆定位：{', '.join(matched_gan)}")
                self.add_diagnosis_basis("肝气郁结", "气滞（全局）")
                self.add_diagnosis_basis("肝气郁结", "判断路径：肝胆定位+气滞→肝气郁结")
            
            # 肝火上炎：肝胆定位 + 火淫证 或 面红/眼红
            huo_local_signs = [w for w in ["面红", "眼红"] if self.keyword_match(single_disease, w)]
            has_huo_sign = self.diagnosis.huo_yin or len(huo_local_signs) > 0
            if has_huo_sign:
                self.diagnosis.gan_huo_shang_yan = True
                # 记录肝胆定位依据
                self.add_diagnosis_basis("肝火上炎", f"肝胆定位：{', '.join(matched_gan)}")
                # 记录判断路径：火热特征 或 火淫证
                if huo_local_signs:
                    self.add_diagnosis_basis("肝火上炎", f"火热特征：{', '.join(huo_local_signs)}")
                    self.add_diagnosis_basis("肝火上炎", "判断路径：肝胆定位+火热特征→肝火上炎")
                else:
                    self.add_diagnosis_basis("肝火上炎", "火淫证（全局）")
                    self.add_diagnosis_basis("肝火上炎", "判断路径：肝胆定位+火淫证→肝火上炎")
            
            
            # 肝血虚：肝胆定位 + 眼干/指甲脆（可跨条目）
            if any(self.keyword_match(single_disease, w) for w in ["眼干", "指甲脆"]):
                self.diagnosis.gan_xue_xu = True
                self.add_diagnosis_basis("肝血虚", f"肝胆症状 + 眼干/指甲脆")


        # 肝胆湿热：口苦/肋痛 + 湿淫证或热证
        gan_dan_local = [w for w in ["口苦", "胁痛", "两胁胀痛"] if self.keyword_match(single_disease, w)]
        if gan_dan_local:
            if self.diagnosis.shi_yin or self.diagnosis.re_zheng:
                self.diagnosis.gan_dan_shi_re = True
                # 记录肝胆定位依据
                self.add_diagnosis_basis("肝胆湿热", f"肝胆定位：{', '.join(matched_gan)}")
                # 记录判断路径：湿淫证 或 热证
                if self.diagnosis.shi_yin and self.diagnosis.re_zheng:
                    self.add_diagnosis_basis("肝胆湿热", "湿热：湿淫证+热证")
                    self.add_diagnosis_basis("肝胆湿热", "判断路径：肝胆定位+湿热→肝胆湿热")
                elif self.diagnosis.shi_yin:
                    self.add_diagnosis_basis("肝胆湿热", "湿淫证（全局）")
                    self.add_diagnosis_basis("肝胆湿热", "判断路径：肝胆定位+湿淫证→肝胆湿热")
                else:
                    self.add_diagnosis_basis("肝胆湿热", "热证（全局）")
                    self.add_diagnosis_basis("肝胆湿热", "判断路径：肝胆定位+热证→肝胆湿热")
            
        # 肝阳上亢：头晕/脚轻 + 阳证
        # 根据SP文档第146行："阳证"包含：表证、热证、实证、阴虚证、亡阴证
        if self.keyword_match(single_disease, "头晕") or self.keyword_match(single_disease, "脚轻"):
            is_yang_zheng = self.diagnosis.re_zheng or self.diagnosis.yin_xu or \
                            self.diagnosis.biao_zheng or self.diagnosis.shi_zheng or \
                            self.diagnosis.wang_yin
            if is_yang_zheng:
                self.diagnosis.gan_yang_shang_kang = True
                self.add_diagnosis_basis("肝阳上亢", "头晕/脚轻 + 阳证")   
        
        # 肾与膀胱
        shen_keywords = ["腰膝酸软", "耳鸣", "遗精", "阳痿", "脱发", "五更泻"]
        pang_guang_keywords = ["尿频", "尿急", "尿痛"]
        
        matched_shen = self.match_keywords(single_disease, shen_keywords)
        has_shen = len(matched_shen) > 0
        has_pang_guang = any(self.keyword_match(single_disease, word) for word in pang_guang_keywords)
        
        if has_shen:            
            if self.diagnosis.yang_xu:
                self.diagnosis.shen_yang_xu = True
                self.add_diagnosis_basis("肾阳虚", f"肾部症状：{', '.join(matched_shen)} + 阳虚")
            

            yin_xu_local_keywords = ["手足心热", "潮热"]
            has_local_yin_xu = any(self.keyword_match(single_disease, w) for w in yin_xu_local_keywords)
            if has_local_yin_xu and self.diagnosis.yin_xu:
                self.diagnosis.shen_yin_xu = True
                self.add_diagnosis_basis("肾阴虚", f"肾部症状：{', '.join(matched_shen)} + 本条目阴虚特征")
            
            # 重症判定
            # SP文档："不孕不育"、"性功能完全丧失"、"久病卧床(>3年)"、"年老体衰(>60岁)"
            # 额外增加：文本中包含"严重"且涉及肾虚关键词时也触发重症
            severe_keywords = ["不孕不育", "性功能丧失", "阳痿", "久病卧床", "年老体衰"]
            severe_reasons = []
            if any(self.keyword_match(single_disease, word) for word in severe_keywords):
                self.diagnosis.shen_severity = SeverityLevel.SEVERE
                severe_reasons.append("严重症状")
            
            if severe_reasons and self.diagnosis.shen_yang_xu:
                self.add_diagnosis_basis("肾阳虚（重症）", f"重症依据：{', '.join(severe_reasons)}")
            if severe_reasons and self.diagnosis.shen_yin_xu:
                self.add_diagnosis_basis("肾阴虚（重症）", f"重症依据：{', '.join(severe_reasons)}")
            
            # 肾不纳气：肾定位 + 气虚证（呼多吸少）【待查】
            if self.diagnosis.qi_xu and any(self.keyword_match(single_disease, w) for w in ["呼吸短促", "气短"]):
                self.diagnosis.shen_bu_na_qi = True
                self.add_diagnosis_basis("肾不纳气", f"肾部症状：{', '.join(matched_shen)} + 气虚（呼吸短促）")
            
            # 七情伤肾已在diagnose_qi_qing_single中处理（需要情志词+脏腑定位在同一句子内）
        
        # 膀胱湿热：膀胱定位 + 热证或湿淫证
        if has_pang_guang:
            if self.diagnosis.re_zheng or self.diagnosis.shi_yin:
                self.diagnosis.pang_guang_shi_re = True
                self.add_diagnosis_basis("膀胱湿热", f"尿频/尿急/尿痛 + 热证/湿淫")
        
    def check_tan_symptoms_single(self, single_disease: str):
        """对单个病症条目检查痰相关症状（用于饮食建议，不触发痰热壅肺诊断）"""
        tan_keywords = ["痰多"]
        if any(self.keyword_match(single_disease, word) for word in tan_keywords):
            self.diagnosis.has_tan_symptoms = True
    
    def _get_active_disease_texts(self) -> List[str]:
        """获取有效的病症文本列表（排除 severity_label 为'排除'的条目，保留弱化条目用于兼证加药）"""
        return [
            di.text for di in self.disease_items
            if di.severity_label != '排除'
        ]
    
    def _get_non_weakened_disease_texts(self) -> List[str]:
        """获取非弱化的病症文本列表（排除 severity_label 为'弱化'或'排除'的条目，用于主病诊断）"""
        return [
            di.text for di in self.disease_items
            if di.severity_label not in ('弱化', '排除')
        ]
    
    def _get_all_disease_texts(self, texts=None) -> List[str]:
        """获取所有病症文本列表（包含弱化和排除，用于辅助辨证如舌象）"""
        if texts is None:
            texts = [di.text for di in self.disease_items]
        # 将独立的舌象信息也加入辅助辨证文本
        if self.tongue:
            texts.append(self.tongue)
        return texts
    
    def run_diagnosis(self, case_data: Dict):
        """运行标准化输入的诊断流程（支持组合判断）
        
        病症不是逐行单独判断的，而是可以组合的。
        例如：第一个是肾阳虚，第二个是肺阴虚，可以组合得到阴阳两虚。
        
        流程：
        1. 解析标准化输入
        2. 过滤排除/弱化条目
        3. 逐条目进行危症判断（危症需在同一条目内满足）
        4. 逐条目进行七情辨证（因果关系需在同一条目内）
        5. 对所有有效条目的综合文本进行八纲/脏腑/气血等组合辨证
        6. 综合阴阳辨证（跨条目组合）
        """
        # 解析标准化输入
        self.parse_standardized_input(case_data)
        
        # --- 第一轮：逐条目独立判断（危症和七情必须在同一条目内满足） ---
        for di in self.disease_items:
            # 跳过排除的条目（但弱化条目仍参与辅助辨证如舌象）
            if di.severity_label == '排除':
                continue
            
            text = di.text
            
            # 七情辨证（每个条目独立，需在同一条目内满足因果关系）
            self.diagnose_qi_qing_single(text)
        
        # --- 第二轮：综合组合辨证（所有有效条目的文本参与，可跨条目组合） ---
        # 获取所有有效条目文本（排除'弱化'和'排除'）
        active_texts = self._get_active_disease_texts()
        
        # print(active_texts)
        # 获取所有条目文本（包含弱化，用于辅助判断如舌象信息）
        all_texts = self._get_all_disease_texts(active_texts)
        all_texts = ' '.join(all_texts)
        
        # 寒热辨证需要在危症判断之前执行（亡阳证依赖寒证，亡阴证依赖热证）
        self.diagnose_han_re_single(all_texts)
        # 虚实辨证需要在危症判断之前执行（气脱证依赖气虚证，气虚证依赖虚证）
        self.diagnose_xu_shi_single(all_texts)
        
        # 真假寒热辨证（基于已有的寒热综合判断，需在气血津液辨证之前执行）
        self.diagnose_zhen_jia_han_re(all_texts)
        # 真假虚实辨证（基于已有的虚实综合判断，需在气血津液辨证之前执行）
        # 原因：气虚证等依赖虚证，若为真实假虚则虚证无效，气虚证不应成立
        self.diagnose_zhen_jia_xu_shi(all_texts)
        
        # 气血津液辨证需要在危症判断之前执行（气脱证在此函数中判断）
        self.diagnose_qi_xue_jin_ye_single(all_texts)
        
        # 危症判断（组合判断）
        self.diagnose_critical_single(all_texts) 

        # 危症时也需要检查痰症状（用于饮食建议）
        is_critical = self.diagnosis.wang_yang or self.diagnosis.wang_yin or self.diagnosis.qi_tuo
        
        # 痰症状检查（无论是否危症都需要，用于饮食建议）
        self.check_tan_symptoms_single(all_texts)
        
        # 非危症辨证（综合组合判断）
        if not is_critical:
            # 对每个有效条目进行基础辨证（累积到 diagnosis 中）
            self.diagnose_li_single(all_texts)
            if not self.diagnosis.li_zheng:
                self.diagnose_biao_single(all_texts)

            # --- 第三轮：跨条目综合辨证 ---
            # 阴阳辨证（基于已有的寒热虚实综合判断，需在真假虚实辨证之后）
            self.diagnose_yin_yang()
            self.diagnose_yin_yang_single(all_texts)
            
            # 六淫辨证（综合判断）
            self.diagnose_liu_yin_single(all_texts)
            
            # 脏腑辨证需要综合信息，在八纲辨证完成后进行
            self.diagnose_zang_fu_single(all_texts)
        
        
        # 检查暑淫证和火淫证的互斥：暑淫证和火淫证不同时出现
        if self.diagnosis.shu_yin and self.diagnosis.huo_yin:
            self.diagnosis.huo_yin = False  # 暑淫证优先

        return all_texts
    
    def determine_main_disease(self, case_data: Dict) -> List[str]:
        """基于新规则确定主病
        
        规则来源：system_prompt_zy.md 第3-63行
        
        优先级逻辑：
        Step 1 (S1)：确定主病候选词的级别
            - S1-T0：危证（最高级别）
            - S1-T1：重症（特指符合重症判定的肾阳虚和肾阴虚）
            - S1-T2：脏腑定位+关键症状的脏腑病症
            - S1-T3：七情致病、"真x假x"命名方式的病
            - S1-T4：六淫证
            - S1-T5：其他
        
        Step 2 (S2)：确定主病候选词的形容词优先级（在S1同级别内部进行）
            - S2-T0：最、主诉、第一、主要、痛不欲生
            - S2-T1：特别、非常、严重、剧烈
            - S2-T2：一般、不在意、不影响
            - S2-T3：未添加形容词或其他形容词
            - S2-T4：先不管
        
        Step 3：全局时序原则
            - 如果最高等级候选词不止一个，按全局对话中出现的顺序排序，取前2个
        
        Step 4：手册时序原则（新增）
            - 若按 Step 3 排序后，仍存在无法区分先后（如同一句话中同时出现）
              且候选数量 > 2 的情况，则继续按 system_prompt_zy.md 中病症定义的顺序
              进行最终排序，截取前 2 个
        
        主病落选与降级：
            - 没有对应药方的主病需要降级处理
        
        兼证原则：
            - 竞选失败的候选词作为兼证输出（落选主病除外）
            - 兼证按Step1~Step4顺序输出
        """
        # S1-T0：危证检查（最高优先级）
        if self.diagnosis.wang_yang:
            self.all_candidates = [("亡阳证", 0, 0, 0, get_disease_manual_order("亡阳证"), "危证")]
            return ["亡阳证"]
        if self.diagnosis.wang_yin:
            self.all_candidates = [("亡阴证", 0, 0, 0, get_disease_manual_order("亡阴证"), "危证")]
            return ["亡阴证"]
        if self.diagnosis.qi_tuo:
            self.all_candidates = [("气脱证", 0, 0, 0, get_disease_manual_order("气脱证"), "危证")]
            return ["气脱证"]
        
        # 过滤有效条目（排除弱化和排除标签）
        active_items = [
            di for di in self.disease_items
            if di.severity_label not in EXCLUDED_LABELS
        ]
        
        if not active_items:
            return ["未能确定主病"]
        
        # 使用全局常量
        diseases_with_formula = DISEASES_WITH_FORMULA
        all_diagnosable = ALL_DIAGNOSABLE_DISEASES
        
        # 收集所有已确认的病名（包括没有药方的，用于展示完整竞选过程）
        all_confirmed_diseases = set()
        for disease_name in all_diagnosable:
            if self._is_disease_confirmed(disease_name):
                all_confirmed_diseases.add(disease_name)
        
        # 同时收集有药方的确诊病名（用于最终输出过滤）
        confirmed_diseases_with_formula = {d for d in all_confirmed_diseases if d in diseases_with_formula}
        
        # disease_candidates: [(病名, S1级别, S2级别, time_order, manual_order, s2_source)]
        # manual_order 是 Step 4 手册时序原则
        # s2_source 是 S2程度来源词
        disease_candidates = []
        
        # 记录哪些确诊病名已经通过文本映射加入了候选
        diseases_added_via_text = set()
        
        for di in active_items:
            text = di.text
            label = di.severity_label
            
            # 根据文本内容映射到可能相关的病名
            mapped_diseases = self._map_text_to_diseases(text)
            
            for disease_name in mapped_diseases:
                # 只要是确诊的病名就加入候选（不管是否有药方）
                if disease_name in all_confirmed_diseases:
                    # Step 1 (S1)：确定病名级别
                    s1_tier = self._get_disease_tier(disease_name, label)
                    # Step 2 (S2)：根据该病症依赖的所有症状计算S2优先级及来源
                    s2_tier, s2_source = self._get_disease_s2_tier_with_source(disease_name, active_items)
                    # Step 3 (S3)：全局时序原则 - 找到该病症首个相关症状的实际 time_order
                    # 注意：不能直接使用当前条目的 time_order，因为病症可能有多个相关症状分布在不同条目
                    first_symptom_order = self._get_disease_first_symptom_time_order(disease_name, active_items)
                    # Step 4 (S4)：手册时序原则
                    manual_order = get_disease_manual_order(disease_name)
                    disease_candidates.append((disease_name, s1_tier, s2_tier, first_symptom_order, manual_order, s2_source))
                    diseases_added_via_text.add(disease_name)
        
        # 新增逻辑：把所有确诊但未通过文本映射加入的病名也加入候选
        # 这样像"血虚证"这样通过八纲辨证确诊但没有被症状文本映射到的病也能参与竞选
        remaining_confirmed = all_confirmed_diseases - diseases_added_via_text
        if remaining_confirmed:
            for disease_name in remaining_confirmed:
                s1_tier = self._get_disease_tier(disease_name, None)
                # 根据该病症依赖的所有症状计算S2优先级及来源
                s2_tier, s2_source = self._get_disease_s2_tier_with_source(disease_name, active_items)
                # Step 3 (S3)：全局时序原则 - 找到该病症首个相关症状的实际 time_order
                first_symptom_order = self._get_disease_first_symptom_time_order(disease_name, active_items)
                # Step 4 (S4)：手册时序原则
                manual_order = get_disease_manual_order(disease_name)
                disease_candidates.append((disease_name, s1_tier, s2_tier, first_symptom_order, manual_order, s2_source))
        
        # 如果通过文本映射没有找到候选，直接使用所有已确认的病名
        if not disease_candidates and all_confirmed_diseases:
            for disease_name in all_confirmed_diseases:
                s1_tier = self._get_disease_tier(disease_name, None)
                s2_tier, s2_source = self._get_disease_s2_tier_with_source(disease_name, active_items)
                # Step 3 (S3)：全局时序原则 - 找到该病症首个相关症状的实际 time_order
                first_symptom_order = self._get_disease_first_symptom_time_order(disease_name, active_items)
                # Step 4 (S4)：手册时序原则
                manual_order = get_disease_manual_order(disease_name)
                disease_candidates.append((disease_name, s1_tier, s2_tier, first_symptom_order, manual_order, s2_source))
        
        if not disease_candidates:
            return self._fallback_main_disease()
        
        # 去重：同一病名取最高级别组合（S1最小 -> S2最小 -> time_order最小 -> manual_order最小）
        disease_best = {}
        for name, s1, s2, order, manual_order, s2_source in disease_candidates:
            if name not in disease_best:
                disease_best[name] = (s1, s2, order, manual_order, s2_source)
            else:
                old_s1, old_s2, old_order, old_manual, _ = disease_best[name]
                # 比较优先级：S1 -> S2 -> time_order -> manual_order
                if (s1, s2, order, manual_order) < (old_s1, old_s2, old_order, old_manual):
                    disease_best[name] = (s1, s2, order, manual_order, s2_source)
        
        # 注意：不再执行"高级词剔除低级词"，所有病症都按 S1-S2-S3-S4 规则排列
        
        # 保存所有候选（包括没有药方的，用于展示完整的竞选过程）
        # 格式：(name, s1, s2, order, manual_order, s2_source)
        self.all_candidates = [
            (name, s1, s2, order, manual_order, s2_source) 
            for name, (s1, s2, order, manual_order, s2_source) in disease_best.items()
        ]
        
        # 只有有药方的病名才能参与主病竞选
        disease_best_with_formula = {
            name: (s1, s2, order, manual_order, s2_source) 
            for name, (s1, s2, order, manual_order, s2_source) in disease_best.items() 
            if name in diseases_with_formula
        }
        
        # 按 S1 -> S2 -> time_order -> manual_order 排序（只对有药方的病进行排序）
        # Step 4：若按 Step 3 排序后仍存在无法区分先后的情况，则按手册时序进行最终排序
        sorted_diseases = sorted(
            disease_best_with_formula.items(),
            key=lambda x: (x[1][0], x[1][1], x[1][2], x[1][3])
        )
        
        # 取主病逻辑：
        # 1. 先按 Step1 x Step2 确定最高优先级
        # 2. 如果最高优先级（S1最小 x S2最小）的候选只有一个，那么这个是唯一主病
        # 3. 如果最高优先级的候选不止一个，进入Step3，按全局时序取前2个
        # 4. 若按 Step 3 排序后仍存在无法区分先后（如同一句话中同时出现）且候选数量 > 2，
        #    则继续按 Step 4（手册时序）进行最终排序，截取前 2 个
        if sorted_diseases:
            best_s1 = sorted_diseases[0][1][0]
            best_s2 = sorted_diseases[0][1][1]
            
            # 找出所有S1和S2都相同（最高优先级）的候选
            top_tier_candidates = [
                d for d in sorted_diseases
                if d[1][0] == best_s1 and d[1][1] == best_s2
            ]
            
            if len(top_tier_candidates) == 1:
                # 最高优先级只有一个候选，直接作为唯一主病
                main_diseases = [top_tier_candidates[0][0]]
            else:
                # 最高优先级有多个候选
                # 已经按 time_order -> manual_order 排序了
                # Step 3: 按全局时序排序
                # Step 4: 若全局时序相同，按手册时序排序
                main_diseases = [d[0] for d in top_tier_candidates[:2]]
        else:
            main_diseases = []
        
        return main_diseases if main_diseases else ["未能确定主病"]
    
    def _get_adjective_tier(self, severity_label: Optional[str]) -> int:
        """获取形容词优先级（S2级别）
        
        规则来源：system_prompt_zy.md 第23-34行
        - S2-T0：最、主诉、第一、主要、痛不欲生
        - S2-T1：特别、非常、严重、剧烈
        - S2-T2：一般、不在意、不影响
        - S2-T3：未添加形容词或其他形容词（默认）
        - S2-T4：先不管
        """
        if severity_label is None:
            return 3  # S2-T3：无形容词
        return ADJECTIVE_PRIORITY.get(severity_label, 3)
    
    def _get_disease_related_keywords(self, disease_name: str) -> List[List[str]]:
        """获取病症相关的关键词组（用于确定S2优先级）
        
        返回多组关键词，每组代表确诊该病所需的一个条件。
        例如脾阳虚需要"脾定位+阳虚"，返回 [脾定位关键词, 阳虚关键词]
        只要症状文本匹配任一组中的任一关键词，该症状的severity_label就参与S2计算
        
        注意：【完全复用】全局常量 ZANGFU_KEYWORDS 和 BAGANG_KEYWORDS，禁止新增关键词
        """
        # 脏腑定位关键词（直接复用全局常量，禁止新增）
        pi_keywords = ZANGFU_KEYWORDS["脾"]
        wei_keywords = ZANGFU_KEYWORDS["胃"]
        shen_keywords = ZANGFU_KEYWORDS["肾"]
        fei_keywords = ZANGFU_KEYWORDS["肺"]
        gan_keywords = ZANGFU_KEYWORDS["肝胆"]
        xin_keywords = ZANGFU_KEYWORDS["心"]
        da_chang_keywords = ZANGFU_KEYWORDS["大肠"]
        pang_guang_keywords = ZANGFU_KEYWORDS["膀胱"]
        
        # 八纲证型关键词（直接复用全局常量，禁止新增）
        biao_zheng_keywords = BAGANG_KEYWORDS["表证"]
        han_zheng_keywords = BAGANG_KEYWORDS["寒证"]
        re_zheng_keywords = BAGANG_KEYWORDS["热证"]
        xu_zheng_keywords = BAGANG_KEYWORDS["虚证"]
        shi_zheng_keywords = BAGANG_KEYWORDS["实证"]
        yang_xu_keywords = han_zheng_keywords + xu_zheng_keywords
        yin_xu_keywords = re_zheng_keywords + xu_zheng_keywords + BAGANG_KEYWORDS["阴虚"]
        
        qi_xu_keywords = ZHENG_KEYWORDS["气虚证"]
        xue_xu_keywords = [word for keyword in ZHENG_KEYWORDS["血虚证"] for word in keyword]
        qi_xue_liang_xu_keywords = qi_xu_keywords + xue_xu_keywords
        xue_yu_keywords = ZHENG_KEYWORDS["血瘀证"]
        xue_han_keywords = ZHENG_KEYWORDS["血寒证"]
        xue_re_keywords = [word for keyword in ZHENG_KEYWORDS["血热证"] for word in keyword]
        qi_zhi_keywords = [word for keyword in ZHENG_KEYWORDS["气滞证"] for word in keyword]
        jin_ye_keywords = ZHENG_KEYWORDS["津液不足"]

        # 病症到关键词组的映射
        disease_keywords_map_base = {

            # 八纲证型
            "里寒证": [han_zheng_keywords, BAGANG_KEYWORDS["里证"]],
            "里热证": [re_zheng_keywords, BAGANG_KEYWORDS["里证"]],
            "表寒证": [han_zheng_keywords, BAGANG_KEYWORDS["表证"]],
            "表热证": [re_zheng_keywords, BAGANG_KEYWORDS["表证"]],

            # 六淫证（来自 diagnose_liu_yin_single 的关键词）
            "风淫证": [["讨厌吹风", "皮肤瘙痒", "麻木", "游走性疼痛", "浮肿"]],
            "寒淫证": [["恶寒", "疼痛", "痛", "冷痛", "胀痛", "刺痛", "舌苔白", "苔白"]],
            "湿淫证": [["水肿", "身体很重", "身体沉重", "拉肚子", "腹泻", "小腹涨", "小腹鼓", "舌苔腻", "很困", "睡不醒"]],
            "暑淫证": [["发热", "恶心", "呕吐", "想吐", "疲乏", "乏力", "胸闷", '舌红', '舌苔黄', '舌干', '舌燥']],
            "燥淫证": [["干咳", "皮肤干", "口干", "鼻干", "咽喉干", "嘴唇干"]],
            "火淫证": [["发热", "口渴", "面红", "疮", "胸部灼热", "腹部灼热", "便秘", "尿黄", '舌红', '苔黄', '舌干', '疮']],
            "实热证": [re_zheng_keywords, BAGANG_KEYWORDS["实证"]],

            
            # 气血津液证（来自 ZHENG_KEYWORDS 和 diagnose_qi_xue_jin_ye_single）
            "气虚证": [qi_xu_keywords],
            "血虚证": [xue_xu_keywords],
            "气血两虚": [qi_xue_liang_xu_keywords],
            "血瘀证": [xue_yu_keywords],
            "血寒证": [xue_han_keywords],
            "血热证": [xue_re_keywords],
            "气滞证": [qi_zhi_keywords],
            "津液不足": [jin_ye_keywords],
            
            # 七情内伤（情志词 + 脏腑定位）
            "七情伤心": [["狂喜", "乐极生悲", "吓破胆", "惊恐", "吓死", "惊吓"], xin_keywords],
            "七情伤肝": [["气炸了", "气死", "暴怒", "生气", "愤怒", "发火"], gan_keywords],
            "七情伤脾": [["想念", "思念"], pi_keywords],
            "七情伤肺": [["崩溃", "绝望", "痛哭", "嚎啕大哭", "流泪不止", "难过", "伤心", "悲痛", "忧郁"], fei_keywords],
            "七情伤肾": [["害怕", "恐惧", "忧虑", "担心", "吓破胆", "惊恐", "吓死", "惊吓", "受惊"], shen_keywords],
            
            # 寒热错杂
            "真热假寒证": [re_zheng_keywords, ['苔黄', '喜冷饮', '冷有帮助', '喜欢喝冷水']],
            "真寒假热证": [han_zheng_keywords, ['苔白', '喜热饮', '热水有帮助', '喝热的舒服', '喜欢喝热水']]
        }
        disease_keywords_map = {
            **disease_keywords_map_base,
            # 心相关（心定位 + 八纲证型）
            "心气虚": [xin_keywords, qi_xu_keywords],
            "心血虚": [xin_keywords, xue_xu_keywords],
            "心阴虚": [xin_keywords, yin_xu_keywords],
            "心阳虚": [xin_keywords, han_zheng_keywords],
            "心脉痹阻": [xin_keywords] + disease_keywords_map_base["血瘀证"],
            "心火亢盛": [xin_keywords, re_zheng_keywords, ['失眠', '口疮']],
            "心脾两虚": disease_keywords_map_base['气血两虚'] + [['失眠', '睡不着']],
            "心火下移小肠": [['舌尖痛']],

            # 肺相关（肺定位 + 八纲证型）
            "肺气虚": [fei_keywords] + disease_keywords_map_base['气虚证'],
            "肺阴虚": [fei_keywords, yin_xu_keywords, ['干咳', '无痰']],
            "寒痰阻肺": [fei_keywords, han_zheng_keywords, ["白痰", "清稀"]],
            "痰热壅肺": [fei_keywords, re_zheng_keywords, ["黄痰", "稠痰"]],
            
            # 大肠相关
            "大肠湿热": [da_chang_keywords, ['便秘', '便臭', '肛门灶热']] + disease_keywords_map_base['湿淫证'],
            "大肠虚寒": [da_chang_keywords, xu_zheng_keywords, ['久泻', '长期腹泻']],

            # 脾相关（脾定位 + 八纲证型）
            "脾气虚": [pi_keywords] + disease_keywords_map_base['气虚证'],
            "脾阳虚": [pi_keywords, yang_xu_keywords],
            "脾虚湿困": [pi_keywords] + disease_keywords_map_base['湿淫证'],
            
            # 胃相关
            "食滞胃脘": [wei_keywords, ["食积", "纳差", "腹胀", "舌苔厚腻", "厚腻"]],
            "胃火炽盛": [wei_keywords, ['口臭', '牙龈肿痛']],
            "胃寒证": [['胃冷痛']],
            "胃气上逆": [wei_keywords, ["干呕", "呃逆"], fei_keywords, yin_xu_keywords, ['干咳', '无痰']],
            "虚劳里急": [['腹痛', '喜按']] + disease_keywords_map_base['气血两虚'],
            
            
            # 肝相关（肝定位 + 八纲证型）
            "肝气郁结": [gan_keywords] + disease_keywords_map_base['气滞证'],
            "肝火上炎": [gan_keywords, ["面红", "眼红"]] + disease_keywords_map_base['火淫证'],
            "肝胆湿热": [re_zheng_keywords, ['口苦', '胁痛']] + disease_keywords_map_base['湿淫证'],
            "肝血虚": [gan_keywords, ['眼干', '指甲脆']],
            "肝阳上亢": [['头晕', '脚轻'], biao_zheng_keywords, re_zheng_keywords, yin_xu_keywords, shi_zheng_keywords],
            
            
            # 肾相关（肾定位 + 八纲证型）
            "肾阳虚": [shen_keywords, han_zheng_keywords, yang_xu_keywords, ['不孕不育', '阳痿', '性功能丧失', '久病卧床', '年老体衰']],
            "肾阴虚": [shen_keywords, yin_xu_keywords, ['手足心热', '潮热', '不孕不育', '阳痿', '性功能丧失', '久病卧床', '年老体衰']],
            "肾不纳气": [shen_keywords, ["呼吸短促", "气短"]],
            
            
            # 膀胱相关
            "膀胱湿热": [pang_guang_keywords, re_zheng_keywords] + disease_keywords_map_base['湿淫证'],
               
            
            # 危症， 自动最高级别，不用对比
            # "亡阳证": [han_zheng_keywords],
            # "亡阴证": [yin_xu_keywords],
            # "气脱证": [xu_zheng_keywords],
            
            
        }
        return disease_keywords_map.get(disease_name, [])
    
    def _get_disease_s2_tier(self, disease_name: str, active_items: List) -> int:
        """获取病症的S2优先级
        
        根据 system_prompt_zy.md 规则：
        1. 脏腑病症：仅以"脏腑定位症状"所带的形容词来决定。
        2. 非脏腑病症：以构成该病的所有症状中最优的形容词为准。
        """
        tier, _ = self._get_disease_s2_tier_with_source(disease_name, active_items)
        return tier
    
    def _get_disease_s2_tier_with_source(self, disease_name: str, active_items: List) -> tuple:
        """获取病症的S2优先级及来源词
        
        返回: (tier, source_label) 
            - tier: S2优先级数值
            - source_label: 来源的严重程度词，如"特别"、"非常"，或None表示默认
        """
        keyword_groups = self._get_disease_related_keywords(disease_name)
        
        if not keyword_groups:
            if active_items:
                best_tier = 3
                best_label = None
                for di in active_items:
                    tier = self._get_adjective_tier(di.severity_label)
                    if tier < best_tier:
                        best_tier = tier
                        best_label = di.severity_label
                return (best_tier, best_label)
            return (3, None)
            
        # 判断是否为脏腑病症，并收集对应的脏腑定位关键词
        zangfu_names = ["心", "肝", "脾", "肺", "肾", "胃", "胆", "大肠", "小肠", "膀胱"]
        is_zangfu_disease = any(zf in disease_name for zf in zangfu_names)
        
        zangfu_keywords_for_disease = []
        if is_zangfu_disease:
            for zf_key, keywords in ZANGFU_KEYWORDS.items():
                if zf_key == "肝胆":
                    if "肝" in disease_name or "胆" in disease_name:
                        zangfu_keywords_for_disease.extend(keywords)
                elif zf_key == "心":
                    if "心" in disease_name or "小肠" in disease_name:
                        zangfu_keywords_for_disease.extend(keywords)
                else:
                    if zf_key in disease_name:
                        zangfu_keywords_for_disease.extend(keywords)
        
        matched_items = []  # [(tier, label)]
        
        if is_zangfu_disease and zangfu_keywords_for_disease:
            # 策略A：脏腑病症，仅在脏腑定位关键词中寻找形容词
            for di in active_items:
                text = di.text
                if any(self.keyword_match(text, kw) for kw in zangfu_keywords_for_disease):
                    tier = self._get_adjective_tier(di.severity_label)
                    matched_items.append((tier, di.severity_label))
        else:
            # 策略B：非脏腑病症，在所有构成的关键词组中寻找形容词
            for di in active_items:
                text = di.text
                for keywords in keyword_groups:
                    if any(self.keyword_match(text, kw) for kw in keywords):
                        tier = self._get_adjective_tier(di.severity_label)
                        matched_items.append((tier, di.severity_label))
                        break

        if matched_items:
            # 找到最小tier对应的label
            best_tier = min(item[0] for item in matched_items)
            best_label = next(item[1] for item in matched_items if item[0] == best_tier)
            return (best_tier, best_label)
        else:
            return (3, None)
    
    def _get_disease_first_symptom_time_order(self, disease_name: str, active_items: List) -> int:
        """获取病症首个相关症状的 time_order（用于 Step3 全局时序原则）
        
        根据 system_prompt_zy.md 规则：
        - Step 3：全局时序原则，按照全局对话中出现的顺序为准
        - 第一类（脏腑病症）：仅以"脏腑定位症状"首次出现的时序为准，
          定性症状（寒证/虚证等）的时序绝对不参与
        - 第二类（非脏腑病症）：以构成该病的所有症状中最早出现的时序为准
        
        返回: 首个相关症状的 time_order，如果找不到则返回最大值
        """
        keyword_groups = self._get_disease_related_keywords(disease_name)
        
        if not keyword_groups:
            if active_items:
                return min(di.time_order for di in active_items)
            return 999
        
        zangfu_names = ["心", "肝", "脾", "肺", "肾", "胃", "胆", "大肠", "小肠", "膀胱"]
        is_zangfu_disease = any(zf in disease_name for zf in zangfu_names)
        
        if is_zangfu_disease:
            # 策略A：脏腑病症，仅以脏腑定位关键词匹配时序
            zangfu_keywords_for_disease = []
            for zf_key, keywords in ZANGFU_KEYWORDS.items():
                if zf_key == "肝胆":
                    if "肝" in disease_name or "胆" in disease_name:
                        zangfu_keywords_for_disease.extend(keywords)
                elif zf_key == "心":
                    if "心" in disease_name or "小肠" in disease_name:
                        zangfu_keywords_for_disease.extend(keywords)
                else:
                    if zf_key in disease_name:
                        zangfu_keywords_for_disease.extend(keywords)
            
            if zangfu_keywords_for_disease:
                first_time_order = 999
                matched_kw = None
                for di in active_items:
                    text = di.text
                    for kw in zangfu_keywords_for_disease:
                        if self.keyword_match(text, kw) and di.time_order < first_time_order:
                            first_time_order = di.time_order
                            matched_kw = kw
                            break
                
                if first_time_order != 999:
                    self.s3_source_map[disease_name] = (matched_kw, True)
                    return first_time_order
            # 脏腑定位关键词未命中，fallthrough 到全关键词匹配
        
        # 策略B：非脏腑病症（或脏腑定位未命中时的兜底），展平全部关键词匹配
        all_keywords = []
        for keywords in keyword_groups:
            if isinstance(keywords, list):
                all_keywords.extend(keywords)
            else:
                all_keywords.append(keywords)
        
        first_time_order = 999
        matched_kw = None
        for di in active_items:
            text = di.text
            for kw in all_keywords:
                if self.keyword_match(text, kw) and di.time_order < first_time_order:
                    first_time_order = di.time_order
                    matched_kw = kw
                    break
        
        if first_time_order == 999 and active_items:
            first_time_order = min(di.time_order for di in active_items)
        
        if matched_kw:
            self.s3_source_map[disease_name] = (matched_kw, False)
        
        return first_time_order
    
    def _get_isolated_symptom_time_order(self, symptom: str) -> int:
        """获取孤立症状的时序（用于 Step 2.2 孤立症状按时序排序）
        
        根据 system_prompt_zy.md 第1074-1076行规则：
        - 孤立症状处理时，按这些症状的发生顺序继续依次加药
        
        Args:
            symptom: 症状名称（如"盗汗"、"风淫证"等）
        
        Returns:
            该症状首次出现的 time_order，如果找不到则返回 999
        """
        # 症状到关键词的映射（用于查找对应的 disease_item）
        ISOLATED_SYMPTOM_KEYWORDS = {
            # 证型类
            "风淫证": ["皮肤瘙痒", "麻木", "游走性疼痛", "浮肿", "讨厌吹风"],
            "血热证": ["流鼻血", "吐血", "尿血", "舌红绛"],
            # 单症状类（直接匹配）
            "咳": ["咳嗽", "咳"],
            "喘": ["喘", "气喘"],
            "寒痰": ["寒痰"],
            "白痰": ["白痰"],
            "热痰": ["热痰"],
            "黄痰": ["黄痰"],
            "失眠": ["失眠", "睡不着"],
            "多梦": ["多梦"],
            "食积": ["食积"],
            "纳差": ["纳差", "不想吃"],
            "便秘": ["便秘", "大便干"],
            "血瘀": ["血瘀"],
            "刺痛": ["刺痛", "像针扎"],
            "气滞": ["气滞"],
            "胀痛": ["胀痛"],
            "头痛": ["头痛", "头疼"],
            "口渴": ["口渴", "渴"],
            "自汗": ["自汗"],
            "盗汗": ["盗汗"],
            "出血": ["出血", "流血"],
            "水肿": ["水肿", "浮肿"],
            "冷痛": ["冷痛"],
            "疮毒": ["疮毒", "疮"],
            "红肿": ["红肿"],
            "皮肤瘙痒": ["皮肤瘙痒", "皮肤痒"],
        }
        
        keywords = ISOLATED_SYMPTOM_KEYWORDS.get(symptom, [symptom])
        
        # 获取有效的 disease_items（排除标签为'排除'的条目）
        active_items = [
            di for di in self.disease_items
            if di.severity_label != '排除'
        ]
        
        # 遍历所有 disease_items，找到最早出现的匹配项
        min_time_order = 999
        for di in active_items:
            text = di.text
            for kw in keywords:
                if self.keyword_match(text, kw):
                    if di.time_order < min_time_order:
                        min_time_order = di.time_order
                    break
        
        return min_time_order
    
    def _get_disease_tier(self, disease_name: str, severity_label: Optional[str]) -> int:
        """获取病名级别（S1级别）
        
        规则来源：system_prompt_zy.md 第7-21行
        - S1-T0：危证
        - S1-T1：重症（特指符合重症判定的肾阳虚和肾阴虚）
        - S1-T2：脏腑病症
        - S1-T3：七情致病、真假证
        - S1-T4：六淫证
        - S1-T5：其他
        """
        # 特殊处理：肾阳虚和肾阴虚在重症时升级为S1-T1
        if disease_name in ("肾阳虚", "肾阴虚") and severity_label == "重症":
            return 1  # S1-T1
        
        return S1_TIER.get(disease_name, 5)  # 默认S1-T5
    
    def _map_text_to_diseases(self, text: str) -> List[str]:
        """将病症文本映射到可能的脏腑病名
        
        注意：【完全复用】全局常量 ZANGFU_KEYWORDS，禁止新增关键词
        """
        diseases = []
        
        # 肾相关（直接复用全局常量，禁止新增）
        if any(self.keyword_match(text, w) for w in ZANGFU_KEYWORDS["肾"]):
            if self.diagnosis.shen_yang_xu:
                diseases.append("肾阳虚")
            if self.diagnosis.shen_yin_xu:
                diseases.append("肾阴虚")
            if self.diagnosis.shen_bu_na_qi:
                diseases.append("肾不纳气")
            # if not self.diagnosis.shen_yang_xu and not self.diagnosis.shen_yin_xu and not self.diagnosis.shen_bu_na_qi:
            #     diseases.append("肾病")
        
        # 肺相关（直接复用全局常量，禁止新增）
        if any(self.keyword_match(text, w) for w in ZANGFU_KEYWORDS["肺"]):
            if self.diagnosis.tan_re_yong_fei:
                diseases.append("痰热壅肺")
            if self.diagnosis.fei_yin_xu:
                diseases.append("肺阴虚")
            if self.diagnosis.han_tan_zu_fei:
                diseases.append("寒痰阻肺")
            if self.diagnosis.fei_qi_xu:
                diseases.append("肺气虚")
        
        # 肝相关（直接复用全局常量，禁止新增）
        if any(self.keyword_match(text, w) for w in ZANGFU_KEYWORDS["肝胆"]):
            if self.diagnosis.gan_huo_shang_yan:
                diseases.append("肝火上炎")
            if self.diagnosis.gan_qi_yu_jie:
                diseases.append("肝气郁结")
            if self.diagnosis.gan_dan_shi_re:
                diseases.append("肝胆湿热")
            if self.diagnosis.gan_xue_xu:
                diseases.append("肝血虚")
            if self.diagnosis.gan_yang_shang_kang:
                diseases.append("肝阳上亢")
        
        # 脾相关（直接复用全局常量，禁止新增）
        if any(self.keyword_match(text, w) for w in ZANGFU_KEYWORDS["脾"]):
            if self.diagnosis.pi_qi_xu:
                diseases.append("脾气虚")
            if self.diagnosis.pi_yang_xu:
                diseases.append("脾阳虚")
            if self.diagnosis.pi_xu_shi_kun:
                diseases.append("脾虚湿困")
        
        # 胃相关（直接复用全局常量，禁止新增）
        if any(self.keyword_match(text, w) for w in ZANGFU_KEYWORDS["胃"]):
            if self.diagnosis.shi_zhi_wei_wan:
                diseases.append("食滞胃脘")
            if self.diagnosis.wei_huo_chi_sheng:
                diseases.append("胃火炽盛")
            if self.diagnosis.wei_han_zheng:
                diseases.append("胃寒证")
            if self.diagnosis.wei_qi_shang_ni:
                diseases.append("胃气上逆")
            if self.diagnosis.xu_lao_li_ji:
                diseases.append("虚劳里急")
        
        # 心相关（直接复用全局常量，禁止新增）
        if any(self.keyword_match(text, w) for w in ZANGFU_KEYWORDS["心"]):
            if self.diagnosis.xin_qi_xu:
                diseases.append("心气虚")
            if self.diagnosis.xin_xue_xu:
                diseases.append("心血虚")
            if self.diagnosis.xin_yin_xu:
                diseases.append("心阴虚")
            if self.diagnosis.xin_yang_xu:
                diseases.append("心阳虚")
            if self.diagnosis.xin_mai_bi_zu:
                diseases.append("心脉痹阻")
            if self.diagnosis.xin_huo_kang_sheng:
                diseases.append("心火亢盛")
        
        # 大肠相关（直接复用全局常量，禁止新增）
        if any(self.keyword_match(text, w) for w in ZANGFU_KEYWORDS["大肠"]):
            if self.diagnosis.da_chang_shi_re:
                diseases.append("大肠湿热")
            if self.diagnosis.da_chang_xu_han:
                diseases.append("大肠虚寒")
        
        # 膀胱相关（直接复用全局常量，禁止新增）
        if any(self.keyword_match(text, w) for w in ZANGFU_KEYWORDS["膀胱"]):
            if self.diagnosis.pang_guang_shi_re:
                diseases.append("膀胱湿热")
        
        # 里寒证（复用八纲寒证关键词）
        if any(self.keyword_match(text, w) for w in BAGANG_KEYWORDS["寒证"]):
            if self.diagnosis.li_zheng and self.diagnosis.han_zheng:
                if not diseases:
                    diseases.append("里寒证")
        
        # 血寒证（复用ZHENG_KEYWORDS）
        if any(self.keyword_match(text, w) for w in ZHENG_KEYWORDS["血寒证"]):
            if self.diagnosis.xue_han:
                diseases.append("血寒证")
        
        return diseases
    
    def _is_disease_confirmed(self, disease_name: str) -> bool:
        """检查诊断结果中是否确认了指定病名"""
        confirm_map = {
            # 肾
            "肾阳虚": self.diagnosis.shen_yang_xu,
            "肾阴虚": self.diagnosis.shen_yin_xu,
            "肾不纳气": self.diagnosis.shen_bu_na_qi,
            # "肾病": self.diagnosis.shen_yang_xu or self.diagnosis.shen_yin_xu,
            # 肺
            "痰热壅肺": self.diagnosis.tan_re_yong_fei,
            "肺阴虚": self.diagnosis.fei_yin_xu,
            "肺气虚": self.diagnosis.fei_qi_xu,
            "寒痰阻肺": self.diagnosis.han_tan_zu_fei,
            # 肝
            "肝火上炎": self.diagnosis.gan_huo_shang_yan,
            "肝气郁结": self.diagnosis.gan_qi_yu_jie,
            "肝胆湿热": self.diagnosis.gan_dan_shi_re,
            "肝血虚": self.diagnosis.gan_xue_xu,
            "肝阳上亢": self.diagnosis.gan_yang_shang_kang,
            # 脾
            "脾气虚": self.diagnosis.pi_qi_xu,
            "脾阳虚": self.diagnosis.pi_yang_xu,
            "脾虚湿困": self.diagnosis.pi_xu_shi_kun,
            # 胃
            "食滞胃脘": self.diagnosis.shi_zhi_wei_wan,
            "胃火炽盛": self.diagnosis.wei_huo_chi_sheng,
            "胃寒证": self.diagnosis.wei_han_zheng,
            "胃气上逆": self.diagnosis.wei_qi_shang_ni,
            "虚劳里急": self.diagnosis.xu_lao_li_ji,
            # 心
            "心气虚": self.diagnosis.xin_qi_xu,
            "心血虚": self.diagnosis.xin_xue_xu,
            "心阳虚": self.diagnosis.xin_yang_xu,
            "心阴虚": self.diagnosis.xin_yin_xu,
            "心脉痹阻": self.diagnosis.xin_mai_bi_zu,
            "心火亢盛": self.diagnosis.xin_huo_kang_sheng,
            "心火下移小肠": self.diagnosis.xin_huo_xia_yi,
            # 大肠
            "大肠湿热": self.diagnosis.da_chang_shi_re,
            "大肠虚寒": self.diagnosis.da_chang_xu_han,
            # 膀胱
            "膀胱湿热": self.diagnosis.pang_guang_shi_re,
            # 气血津液
            "气虚证": self.diagnosis.qi_xu,
            "气滞证": self.diagnosis.qi_zhi,
            "血虚证": self.diagnosis.xue_xu,
            "血瘀证": self.diagnosis.xue_yu,
            "血热证": self.diagnosis.xue_re,
            "血寒证": self.diagnosis.xue_han,
            "气血两虚": self.diagnosis.qi_xue_liang_xu,
            # 八纲组合证
            "表寒证": self.diagnosis.biao_zheng and self.diagnosis.han_zheng,
            "表热证": self.diagnosis.biao_zheng and self.diagnosis.re_zheng,
            "里寒证": self.diagnosis.li_zheng and self.diagnosis.han_zheng,
            "里热证": self.diagnosis.li_zheng and self.diagnosis.re_zheng,
            # 六淫
            "风淫证": self.diagnosis.feng_yin,
            "寒淫证": self.diagnosis.han_yin,
            "暑淫证": self.diagnosis.shu_yin,
            "湿淫证": self.diagnosis.shi_yin,
            "燥淫证": self.diagnosis.zao_yin,
            "火淫证": self.diagnosis.huo_yin,
            "实热证": self.diagnosis.shi_zheng and self.diagnosis.re_zheng,
            # 七情内伤
            "七情伤心": self.diagnosis.qi_qing_shang_xin,
            "七情伤肝": self.diagnosis.qi_qing_shang_gan,
            "七情伤脾": self.diagnosis.qi_qing_shang_pi,
            "七情伤肺": self.diagnosis.qi_qing_shang_fei,
            "七情伤肾": self.diagnosis.qi_qing_shang_shen,
            # 危症
            "亡阳证": self.diagnosis.wang_yang,
            "亡阴证": self.diagnosis.wang_yin,
            "气脱证": self.diagnosis.qi_tuo,
            # 阴阳辨证
            "阴虚证": self.diagnosis.yin_xu,
            "阳虚证": self.diagnosis.yang_xu,
            "阴阳两虚": self.diagnosis.yin_yang_liang_xu,
            # 真假证
            "真热假寒证": self.diagnosis.zhen_re_jia_han,
            "真寒假热证": self.diagnosis.zhen_han_jia_re,
            "真虚假实证": self.diagnosis.zhen_xu_jia_shi,
            "真实假虚证": self.diagnosis.zhen_shi_jia_xu,
            # 津液
            "津液不足": self.diagnosis.jin_ye_bu_zu,
        }
        return confirm_map.get(disease_name, False)
    
    def _fallback_main_disease(self) -> List[str]:
        """兜底主病选定：从确认的诊断结果中选取
        
        按 S1 级别排序，取 S1 级别最小（最高优先级）的病名
        不再执行"高级词剔除低级词"
        """
        # 收集所有已确认的病名，使用 S1_TIER 级别
        confirmed = []
        
        # S1-T2 脏腑病症
        # 肾
        if self.diagnosis.shen_yang_xu:
            confirmed.append(("肾阳虚", S1_TIER.get("肾阳虚", 5)))
        if self.diagnosis.shen_yin_xu:
            confirmed.append(("肾阴虚", S1_TIER.get("肾阴虚", 5)))
        if self.diagnosis.shen_bu_na_qi:
            confirmed.append(("肾不纳气", S1_TIER.get("肾不纳气", 5)))
        # 肺
        if self.diagnosis.tan_re_yong_fei:
            confirmed.append(("痰热壅肺", S1_TIER.get("痰热壅肺", 5)))
        if self.diagnosis.fei_yin_xu:
            confirmed.append(("肺阴虚", S1_TIER.get("肺阴虚", 5)))
        if self.diagnosis.fei_qi_xu:
            confirmed.append(("肺气虚", S1_TIER.get("肺气虚", 5)))
        if self.diagnosis.han_tan_zu_fei:
            confirmed.append(("寒痰阻肺", S1_TIER.get("寒痰阻肺", 5)))
        # 肝
        if self.diagnosis.gan_huo_shang_yan:
            confirmed.append(("肝火上炎", S1_TIER.get("肝火上炎", 5)))
        if self.diagnosis.gan_qi_yu_jie:
            confirmed.append(("肝气郁结", S1_TIER.get("肝气郁结", 5)))
        if self.diagnosis.gan_dan_shi_re:
            confirmed.append(("肝胆湿热", S1_TIER.get("肝胆湿热", 5)))
        if self.diagnosis.gan_xue_xu:
            confirmed.append(("肝血虚", S1_TIER.get("肝血虚", 5)))
        if self.diagnosis.gan_yang_shang_kang:
            confirmed.append(("肝阳上亢", S1_TIER.get("肝阳上亢", 5)))
        # 脾
        if self.diagnosis.pi_qi_xu:
            confirmed.append(("脾气虚", S1_TIER.get("脾气虚", 5)))
        if self.diagnosis.pi_yang_xu:
            confirmed.append(("脾阳虚", S1_TIER.get("脾阳虚", 5)))
        if self.diagnosis.pi_xu_shi_kun:
            confirmed.append(("脾虚湿困", S1_TIER.get("脾虚湿困", 5)))
        # 胃
        if self.diagnosis.shi_zhi_wei_wan:
            confirmed.append(("食滞胃脘", S1_TIER.get("食滞胃脘", 5)))
        if self.diagnosis.wei_huo_chi_sheng:
            confirmed.append(("胃火炽盛", S1_TIER.get("胃火炽盛", 5)))
        if self.diagnosis.wei_han_zheng:
            confirmed.append(("胃寒证", S1_TIER.get("胃寒证", 5)))
        if self.diagnosis.wei_qi_shang_ni:
            confirmed.append(("胃气上逆", S1_TIER.get("胃气上逆", 5)))
        if self.diagnosis.xu_lao_li_ji:
            confirmed.append(("虚劳里急", S1_TIER.get("虚劳里急", 5)))
        # 心
        if self.diagnosis.xin_qi_xu:
            confirmed.append(("心气虚", S1_TIER.get("心气虚", 5)))
        if self.diagnosis.xin_xue_xu:
            confirmed.append(("心血虚", S1_TIER.get("心血虚", 5)))
        if self.diagnosis.xin_yin_xu:
            confirmed.append(("心阴虚", S1_TIER.get("心阴虚", 5)))
        if self.diagnosis.xin_yang_xu:
            confirmed.append(("心阳虚", S1_TIER.get("心阳虚", 5)))
        if self.diagnosis.xin_mai_bi_zu:
            confirmed.append(("心脉痹阻", S1_TIER.get("心脉痹阻", 5)))
        if self.diagnosis.xin_huo_kang_sheng:
            confirmed.append(("心火亢盛", S1_TIER.get("心火亢盛", 5)))
        # 大肠
        if self.diagnosis.da_chang_shi_re:
            confirmed.append(("大肠湿热", S1_TIER.get("大肠湿热", 5)))
        if self.diagnosis.da_chang_xu_han:
            confirmed.append(("大肠虚寒", S1_TIER.get("大肠虚寒", 5)))
        # 膀胱
        if self.diagnosis.pang_guang_shi_re:
            confirmed.append(("膀胱湿热", S1_TIER.get("膀胱湿热", 5)))
        # 七情内伤 (S1-T3)
        if self.diagnosis.qi_qing_shang_xin:
            confirmed.append(("七情伤心", S1_TIER.get("七情伤心", 5)))
        if self.diagnosis.qi_qing_shang_gan:
            confirmed.append(("七情伤肝", S1_TIER.get("七情伤肝", 5)))
        if self.diagnosis.qi_qing_shang_pi:
            confirmed.append(("七情伤脾", S1_TIER.get("七情伤脾", 5)))
        if self.diagnosis.qi_qing_shang_fei:
            confirmed.append(("七情伤肺", S1_TIER.get("七情伤肺", 5)))
        if self.diagnosis.qi_qing_shang_shen:
            confirmed.append(("七情伤肾", S1_TIER.get("七情伤肾", 5)))
        
        # S1-T5 八纲组合证/气血津液证
        if self.diagnosis.biao_zheng and self.diagnosis.han_zheng:
            confirmed.append(("表寒证", S1_TIER.get("表寒证", 5)))
        if self.diagnosis.biao_zheng and self.diagnosis.re_zheng:
            confirmed.append(("表热证", S1_TIER.get("表热证", 5)))
        if self.diagnosis.li_zheng and self.diagnosis.han_zheng:
            confirmed.append(("里寒证", S1_TIER.get("里寒证", 5)))
        if self.diagnosis.li_zheng and self.diagnosis.re_zheng:
            confirmed.append(("里热证", S1_TIER.get("里热证", 5)))
        if self.diagnosis.qi_xu:
            confirmed.append(("气虚证", S1_TIER.get("气虚证", 5)))
        if self.diagnosis.xue_xu:
            confirmed.append(("血虚证", S1_TIER.get("血虚证", 5)))
        if self.diagnosis.qi_xue_liang_xu:
            confirmed.append(("气血两虚", S1_TIER.get("气血两虚", 5)))
        if self.diagnosis.xue_han:
            confirmed.append(("血寒证", S1_TIER.get("血寒证", 5)))
        if self.diagnosis.xue_yu:
            confirmed.append(("血瘀证", S1_TIER.get("血瘀证", 5)))
        if self.diagnosis.xue_re:
            confirmed.append(("血热证", S1_TIER.get("血热证", 5)))
        if self.diagnosis.qi_zhi:
            confirmed.append(("气滞证", S1_TIER.get("气滞证", 5)))
        
        if not confirmed:
            return ["未能确定主病"]
        
        # 按 S1 级别排序（数字越小优先级越高）
        confirmed.sort(key=lambda x: x[1])
        
        # 找出最高优先级（S1最小）的病名
        min_s1 = confirmed[0][1]
        top_diseases = [name for name, s1 in confirmed if s1 == min_s1]
        
        return top_diseases[:2] if top_diseases else ["未能确定主病"]
    
    def _get_formula_for_disease(self, disease: str) -> Optional[str]:
        """根据病名获取对应的药方名（基于SP药方库）"""
        # 病名到药方的映射表（基于 system_prompt_zy.md 第750-815行）
        DISEASE_TO_FORMULA = {
            # A. 解表剂
            "表寒证": "麻黄汤",  # 无汗用麻黄汤，有汗用桂枝汤（特殊处理）
            "表热证": "银翘散",
            # B. 温里剂
            "里寒证": "四逆汤",
            "脾胃虚寒": "理中丸",
            "胃寒证": "理中丸",
            "虚劳里急": "小建中汤",
            "脾阳虚": "附子理中丸",
            "心阳虚": "桂枝甘草汤",
            "血寒证": "温经汤",
            "大肠虚寒": "真人养脏汤",
            # C. 清热剂
            "实热证": "白虎汤",
            "火淫证": "黄连解毒汤",
            "心火亢盛": "导赤散",
            "胃火炽盛": "清胃散",
            "肝火上炎": "龙胆泻肝汤",
            "肝胆湿热": "龙胆泻肝汤",
            "大肠湿热": "白头翁汤",
            "膀胱湿热": "八正散",
            # D. 补益剂
            "气虚证": "四君子汤",
            "脾气虚": "参苓白术散",
            "心气虚": "养心汤",
            "肺气虚": "补肺汤",
            "血虚证": "四物汤",
            "肝血虚": "补肝汤",
            "气血两虚": "八珍汤",
            "肺阴虚": "百合固金汤",  # 或麦门冬汤（兼胃气上逆时）
            "胃气上逆": "麦门冬汤",
            "气阴两虚": "生脉散",
            "肾阴虚": "六味地黄丸",  # 轻症；重症用左归丸
            "肾阳虚": "金匮肾气丸",  # 轻症；重症用右归丸
            "肾不纳气": "参蛤散",
            "心脾两虚": "归脾汤",
            "心阴虚": "天王补心丹",
            "七情伤心": "甘麦大枣汤",
            # E. 祛邪/理气/理血剂
            "湿淫证": "二陈汤",
            "脾虚湿困": "平胃散",
            "痰热壅肺": "清气化痰丸",
            "寒痰阻肺": "三子养亲汤",
            "食滞胃脘": "保和丸",
            "肝气郁结": "逍遥散",
            "七情伤肝": "柴胡疏肝散",
            "肝阳上亢": "天麻钩藤饮",
            "血瘀证": "血府逐瘀汤",
            "心脉痹阻": "瓜蒌薤白白酒汤",
            "七情伤脾": "越鞠丸",
            "七情伤肺": "越鞠丸",
            "七情伤肾": "越鞠丸",
            # F. 寒热错杂剂
            "真热假寒证": "乌梅丸",  # 患者兼具寒证和热证
            "真寒假热证": "乌梅丸",  # 患者兼具寒证和热证
        }
        return DISEASE_TO_FORMULA.get(disease)
    
    def _verify_disease_diagnosis(self, disease: str) -> bool:
        """验证病名对应的诊断标志是否为True"""
        # 病名到诊断标志的映射
        DISEASE_TO_FLAG = {
            "表寒证": lambda: self.diagnosis.biao_zheng and self.diagnosis.han_zheng,
            "表热证": lambda: self.diagnosis.biao_zheng and self.diagnosis.re_zheng,
            "里寒证": lambda: self.diagnosis.li_zheng and self.diagnosis.han_zheng,
            "里热证": lambda: self.diagnosis.li_zheng and self.diagnosis.re_zheng,
            "实热证": lambda: self.diagnosis.shi_zheng and self.diagnosis.re_zheng,
            "气虚证": lambda: self.diagnosis.qi_xu,
            "血虚证": lambda: self.diagnosis.xue_xu,
            "气血两虚": lambda: self.diagnosis.qi_xue_liang_xu,
            "血瘀证": lambda: self.diagnosis.xue_yu,
            "血寒证": lambda: self.diagnosis.xue_han,
            "血热证": lambda: self.diagnosis.xue_re,
            "湿淫证": lambda: self.diagnosis.shi_yin,
            "火淫证": lambda: self.diagnosis.huo_yin,
            "痰热壅肺": lambda: self.diagnosis.tan_re_yong_fei,
            "寒痰阻肺": lambda: self.diagnosis.han_tan_zu_fei,
            "肺阴虚": lambda: self.diagnosis.fei_yin_xu,
            "肺气虚": lambda: self.diagnosis.fei_qi_xu,
            "肝火上炎": lambda: self.diagnosis.gan_huo_shang_yan,
            "肝气郁结": lambda: self.diagnosis.gan_qi_yu_jie,
            "肝胆湿热": lambda: self.diagnosis.gan_dan_shi_re,
            "肝血虚": lambda: self.diagnosis.gan_xue_xu,
            "肝阳上亢": lambda: self.diagnosis.gan_yang_shang_kang,
            "食滞胃脘": lambda: self.diagnosis.shi_zhi_wei_wan,
            "胃火炽盛": lambda: self.diagnosis.wei_huo_chi_sheng,
            "胃寒证": lambda: self.diagnosis.wei_han_zheng,
            "胃气上逆": lambda: self.diagnosis.wei_qi_shang_ni,
            "虚劳里急": lambda: self.diagnosis.xu_lao_li_ji,
            "脾气虚": lambda: self.diagnosis.pi_qi_xu,
            "脾阳虚": lambda: self.diagnosis.pi_yang_xu,
            "脾虚湿困": lambda: self.diagnosis.pi_xu_shi_kun,
            "心气虚": lambda: self.diagnosis.xin_qi_xu,
            "心血虚": lambda: self.diagnosis.xin_xue_xu,
            "心阴虚": lambda: self.diagnosis.xin_yin_xu,
            "心阳虚": lambda: self.diagnosis.xin_yang_xu,
            "心火亢盛": lambda: self.diagnosis.xin_huo_kang_sheng,
            "心脾两虚": lambda: self.diagnosis.has_shi_mian and self.diagnosis.qi_xue_liang_xu,
            "心脉痹阻": lambda: self.diagnosis.xin_mai_bi_zu,
            "肾阳虚": lambda: self.diagnosis.shen_yang_xu,
            "肾阴虚": lambda: self.diagnosis.shen_yin_xu,
            "肾不纳气": lambda: self.diagnosis.shen_bu_na_qi,
            "膀胱湿热": lambda: self.diagnosis.pang_guang_shi_re,
            "大肠湿热": lambda: self.diagnosis.da_chang_shi_re,
            "大肠虚寒": lambda: self.diagnosis.da_chang_xu_han,
            "七情伤心": lambda: self.diagnosis.qi_qing_shang_xin,
            "七情伤肝": lambda: self.diagnosis.qi_qing_shang_gan,
            "七情伤脾": lambda: self.diagnosis.qi_qing_shang_pi,
            "七情伤肺": lambda: self.diagnosis.qi_qing_shang_fei,
            "七情伤肾": lambda: self.diagnosis.qi_qing_shang_shen,
            # 寒热错杂（乌梅丸）
            "真热假寒证": lambda: self.diagnosis.zhen_re_jia_han,
            "真寒假热证": lambda: self.diagnosis.zhen_han_jia_re,
        }
        check_fn = DISEASE_TO_FLAG.get(disease)
        if check_fn:
            return check_fn()
        # 如果没有对应的验证函数，默认返回True
        return True
    
    def _add_herbs_with_conflict_check(self, herbs: List[str], new_herbs: List[str]) -> None:
        """添加药材并检查十八反冲突"""
        for herb in new_herbs:
            conflict = False
            for base_herb, incompatible_list in INCOMPATIBLE_HERBS.items():
                if base_herb in herbs and herb in incompatible_list:
                    conflict = True
                    break
            if not conflict and herb not in herbs:
                herbs.append(herb)
    
    def _add_special_notes_for_herbs(self, herbs: List[str], formula_name: str, 
                                      special_notes: List[str], is_critical: bool = False) -> None:
        """根据药材添加特殊医嘱"""
        added_notes = set(special_notes)
        
        # 附子/乌头：需先煎30-60分钟
        if "附子" in herbs and "附子(需先煎30-60分钟)" not in added_notes:
            special_notes.append("附子(需先煎30-60分钟)")
        if "乌头" in herbs and "乌头(需先煎30-60分钟)" not in added_notes:
            special_notes.append("乌头(需先煎30-60分钟)")
        
        # 人参：危症时需另煎兑入
        if "人参" in herbs and is_critical and "人参(需另煎兑入)" not in added_notes:
            special_notes.append("人参(需另煎兑入)")
        
        # 阿胶/鹿角胶/龟板胶：烊化
        if "阿胶" in herbs and "阿胶(烊化)" not in added_notes:
            special_notes.append("阿胶(烊化)")
        if "鹿角胶" in herbs and "鹿角胶(烊化)" not in added_notes:
            special_notes.append("鹿角胶(烊化)")
        if "龟板胶" in herbs and "龟板胶(烊化)" not in added_notes:
            special_notes.append("龟板胶(烊化)")
        
        # 矿物类：需先煎
        for mineral in ["石膏", "龙骨", "牡蛎"]:
            note = f"{mineral}(需先煎)"
            if mineral in herbs and note not in added_notes:
                special_notes.append(note)
        
        # 生姜+半夏：生姜需倍于半夏以制毒
        if "生姜" in herbs and "半夏" in herbs and "生姜(生姜需倍于半夏以制毒)" not in added_notes:
            special_notes.append("生姜(生姜需倍于半夏以制毒)")
        
        # 方剂特殊医嘱
        if formula_name == "麦门冬汤" and "麦冬(麦冬用量需7倍于半夏)" not in added_notes:
            special_notes.append("麦冬(麦冬用量需7倍于半夏)")
        elif formula_name == "温经汤" and "麦冬(麦冬与半夏用量大致相等)" not in added_notes:
            special_notes.append("麦冬(麦冬与半夏用量大致相等)")
        
        if formula_name == "桂枝汤" and "桂枝(桂枝与白芍比例1:1)" not in added_notes:
            special_notes.append("桂枝(桂枝与白芍比例1:1)")
    
    def select_formula(self) -> Prescription:
        """选择方剂（基于 system_prompt_zy.md 第750-815行的药方库）"""
        herbs = []
        formula_name = ""
        special_notes = []
        
        # ========== 危症处理（优先级最高）==========
        if self.diagnosis.wang_yang:
            formula = FORMULA_DATABASE["参附汤"]
            herbs = formula.herbs.copy()
            formula_name = "参附汤"
            self._add_special_notes_for_herbs(herbs, formula_name, special_notes, is_critical=True)
            return Prescription(formula_name, herbs, special_notes)
        
        if self.diagnosis.wang_yin:
            formula = FORMULA_DATABASE["生脉散"]
            herbs = formula.herbs.copy()
            formula_name = "生脉散"
            self._add_special_notes_for_herbs(herbs, formula_name, special_notes, is_critical=True)
            return Prescription(formula_name, herbs, special_notes)
        
        if self.diagnosis.qi_tuo:
            formula = FORMULA_DATABASE["独参汤"]
            herbs = formula.herbs.copy()
            formula_name = "独参汤"
            self._add_special_notes_for_herbs(herbs, formula_name, special_notes, is_critical=True)
            return Prescription(formula_name, herbs, special_notes)
        
        # ========== 非危症处理 ==========
        base_formulas = []
        monarch_herbs_list = []
        
        # 根据主病选择底方（按主病顺序）
        for disease in self.main_diseases:
            formula = None
            formula_key = None
            
            # 特殊处理：需要根据条件选择不同药方的病名
            if disease == "肾阳虚" and self.diagnosis.shen_yang_xu:
                formula_key = "右归丸" if self.diagnosis.shen_severity == SeverityLevel.SEVERE else "金匮肾气丸"
            elif disease == "肾阴虚" and self.diagnosis.shen_yin_xu:
                formula_key = "左归丸" if self.diagnosis.shen_severity == SeverityLevel.SEVERE else "六味地黄丸"
            elif disease == "表寒证":
                # SP规定：无汗用麻黄汤，有汗用桂枝汤
                all_texts = ' '.join(self._get_active_disease_texts())
                no_sweat = any(w in all_texts for w in ["不出汗", "无汗", "不知道出汗"])
                formula_key = "桂枝汤" if not no_sweat else "麻黄汤"
            elif disease == "肺阴虚" and self.diagnosis.fei_yin_xu:
                # 兼胃气上逆时用麦门冬汤
                formula_key = "麦门冬汤" if self.diagnosis.wei_qi_shang_ni else "百合固金汤"
            else:
                # 通用处理：从映射表获取药方
                formula_key = self._get_formula_for_disease(disease)
                # 验证诊断标志
                if formula_key and not self._verify_disease_diagnosis(disease):
                    continue
            
            if formula_key and formula_key in FORMULA_DATABASE:
                formula = FORMULA_DATABASE[formula_key]
                base_formulas.append(formula)
                monarch_herbs_list.append(formula.monarch_herbs[0])
                self._add_herbs_with_conflict_check(herbs, formula.herbs)
                self._add_special_notes_for_herbs(herbs, formula_key, special_notes)
        
        # 记录底方原始药材（用于判断是否需要加"加减"）
        original_herbs = set(herbs)
        
        # ========== Step 2: 处理兼证加药（基于 system_prompt_zy.md 第1016-1023行） ==========
        # 规则：
        # 1. 按兼证优先级顺序依次处理，将兼证拆解为具体症状
        # 2. 底方排斥：若候选药已在底方或已选药中，跳过该症状
        # 3. 一药多效：优先选择能覆盖更低优先级兼证的候选药
        # 4. 数量上限：最多4味
        # 5. 孤立症状处理：若新增药物不足4味，继续处理未归入兼证的孤立症状
        
        added_single_herbs = 0
        max_single_herbs = 4
        
        # 获取有效症状文本
        active_texts_list = self._get_active_disease_texts()
        all_texts = ' '.join(active_texts_list)
        
        # 症状到候选药的映射（数据库F：单味药映射表）
        SYMPTOM_HERB_MAPPING = {
            # "咳嗽": ["杏仁", "厚朴"],
            "咳": ["杏仁", "厚朴"],
            "喘": ["杏仁", "厚朴"],
            "寒痰": ["半夏", "陈皮"],
            "白痰": ["半夏", "陈皮"],
            # "痰白": ["半夏", "陈皮"],
            "热痰": ["贝母", "瓜蒌"],
            "黄痰": ["贝母", "瓜蒌"],
            # "痰黄": ["贝母", "瓜蒌"],
            # "稠痰": ["贝母", "瓜蒌"],
            "失眠": ["酸枣仁", "夜交藤"],
            "多梦": ["酸枣仁", "夜交藤"],
            # "睡不着": ["酸枣仁", "夜交藤"],
            "食积": ["山楂", "神曲", "麦芽"],
            "纳差": ["山楂", "神曲", "麦芽"],
            "便秘": ["大黄", "芒硝"],
            "血瘀": ["桃仁", "红花", "丹参"],
            "刺痛": ["桃仁", "红花", "丹参"],
            # "像针扎": ["桃仁", "红花", "丹参"],
            "气滞": ["香附", "陈皮"],
            "胀痛": ["香附", "陈皮"],
            "头痛": ["川芎", "白芷"],
            "口渴": ["天花粉", "芦根"],
            "自汗": ["浮小麦", "牡蛎"],
            "盗汗": ["浮小麦", "牡蛎"],
            "出血": ["白茅根", "茜草"],
            # "血热证": ["白茅根", "茜草"],
            "水肿": ["薏苡仁", "泽泻"],
            "冷痛": ["细辛", "桂枝"],
            "疮毒": ["蒲公英", "连翘"],
            "红肿": ["蒲公英", "连翘"],
            # "皮肤痒": ["防风", "白鲜皮"],
            "皮肤瘙痒": ["防风", "白鲜皮"],
        }
        
        
        # 兼证到症状的映射（只保留SYMPTOM_HERB_MAPPING中有的症状，且必须是该证型的实际判断关键词）
        JIAN_ZHENG_SYMPTOMS = {
            # === 六淫证 ===
            # "湿淫证" 通过 DIRECT_ADD_JIAN_ZHENG 直接加药
            "寒淫证": ["冷痛"],
            "燥淫证": [],
            "火淫证": ["口渴", "便秘"],  # 火淫证关键词含：发热、口渴、面红、疮
            "暑淫证": [],
            
            # === 气血津液证 ===
            "气虚证": ["自汗"],  # 气虚证关键词：懒言、自汗、呼吸短促
            "气滞证": ["胀痛"],  # 气滞证关键词：胀痛、胀满、游走性疼痛（"气滞"不是判断关键词）
            "血虚证": [],
            "血瘀证": ["刺痛"],  # 血瘀证关键词：刺痛、固定不移、夜间加重（"血瘀"不是判断关键词）
            "血热证": [],  # 血热证关键词：流鼻血、吐血、尿血、舌红绛（"出血"、"血热"、"口渴"都不是判断关键词）
            "血寒证": ["冷痛"],  # 血寒证关键词含冷痛（寒证基础）
            "气血两虚": ["自汗"],
            "津液不足": ["口渴"],  # 津液不足关键词：口渴、喜欢喝水、皮肤干燥
            
            # === 八纲组合证 ===
            "里热证": ["失眠", "多梦"],  # 里证+热证（"口渴"是热证通用关键词，不单独列）
            "里寒证": ["冷痛"],
            "表热证": [],  # 表证关键词不在SYMPTOM_HERB_MAPPING中
            "表寒证": ["冷痛"],
            "实热证": ["口渴", "便秘"],  # 实证+热证
            
            # === 阴阳证 ===
            "阴虚证": ["盗汗"],  # 阴虚证关键词：盗汗、潮热、五心烦热（"口渴"是热证通用）
            "阳虚证": ["冷痛"],
            "阴阳两虚": ["盗汗", "冷痛"],
            
            # === 脏腑证（肺系）===
            "痰热壅肺": ["热痰", "黄痰", "咳", "喘"],  # 痰热壅肺特有关键词
            "寒痰阻肺": ["寒痰", "白痰", "咳", "喘"],  # 寒痰阻肺特有关键词
            "肺阴虚": ["盗汗", "咳", "喘"],  # 肺+阴虚
            "肺气虚": ["自汗", "咳", "喘"],  # 肺+气虚
            
            # === 脏腑证（脾胃系）===
            "脾气虚": ["纳差"],  # 脾定位关键词含纳差
            "脾阳虚": ["纳差", "冷痛"],
            "脾虚湿困": ["纳差", "水肿"],
            "脾胃虚寒": ["纳差", "冷痛"],  # 脾胃+虚寒
            "食滞胃脘": ["食积", "纳差"],
            "胃火炽盛": [],  # 胃火炽盛关键词：口臭、牙龈肿痛
            "胃寒证": ["冷痛"],
            "胃气上逆": ["盗汗", "咳", "喘"],
            "虚劳里急": [],  # 关键词不在数据库F中
            
            # === 脏腑证（心系）===
            "心气虚": ["失眠", "自汗"],
            "心血虚": ["失眠", "多梦"],  # 心定位关键词含失眠、多梦
            "心阴虚": ["失眠", "多梦", "盗汗"],
            "心阳虚": ["失眠", "冷痛"],
            "心火亢盛": ["失眠"],  # 心火亢盛关键词：失眠、口疮、舌红
            "心脉痹阻": ["失眠","刺痛"],
            "心脾两虚": ["失眠", "纳差", "自汗"],  # 心（失眠）+脾（纳差）+气虚（自汗）
            
            # === 脏腑证（肝胆系）===
            "肝气郁结": ["胀痛"],  # 肝气郁结关键词含胀痛
            "肝火上炎": [],  # 肝火上炎关键词：头痛、面红、眼红、口苦
            "肝血虚": [],
            "肝阳上亢": [],  # 肝阳上亢关键词含头痛
            "肝胆湿热": [],  # 肝胆湿热关键词：口苦、胁痛、尿黄（均不在SYMPTOM_HERB_MAPPING中）
            
            # === 脏腑证（肾膀胱系）===
            "肾阳虚": ["冷痛"],
            "肾阴虚": ["盗汗"],  # 肾+阴虚
            "肾不纳气": [],
            "膀胱湿热": [],  # 膀胱湿热关键词：尿频、尿急、尿痛（均不在SYMPTOM_HERB_MAPPING中）
            
            # === 大肠证 ===
            "大肠湿热": ["便秘"],
            "大肠虚寒": [],
            
            # === 真假证 ===
            "真热假寒证": [],  # 通过舌苔/饮水偏好判断
            "真寒假热证": ["冷痛"],
            "真虚假实证": [],
            "真实假虚证": [],
            
            # === 七情证 ===
            "七情伤心": ["失眠", "多梦"],
            "七情伤肝": ["胀痛"],
            "七情伤脾": ["纳差"],
            "七情伤肺": [],
            "七情伤肾": [],
            
            # === 危症 ===
            # 危症不通过兼证加药处理
        }
        
        # 获取兼证列表（已按优先级排序）
        secondary_diagnoses = getattr(self, 'secondary_diagnoses', [])
        if not secondary_diagnoses:
            # 如果尚未计算兼证，从 all_candidates 中获取
            all_candidates = getattr(self, 'all_candidates', [])
            main_set = set(self.main_diseases)
            if all_candidates:
                # 按 S1 -> S2 -> time_order -> manual_order 排序（Step 1~4）
                sorted_candidates = sorted(all_candidates, key=lambda x: (x[1], x[2], x[3], x[4] if len(x) > 4 else 999))
                secondary_diagnoses = [c[0] for c in sorted_candidates if c[0] not in main_set and c[0] in DISEASES_WITH_FORMULA]
        
        # 已选药物集合（包含底方药物）
        selected_herbs = set(herbs)
        # 已处理的症状集合
        processed_symptoms = set()
        # 记录加药详情（用于推理逻辑展示）
        self._jian_zheng_add_herb_details = []
        
        # 预先计算底方中存在的十八反禁忌药列表
        incompatible_with_base = set()
        for base_herb in herbs:
            if base_herb in INCOMPATIBLE_HERBS:
                incompatible_with_base.update(INCOMPATIBLE_HERBS[base_herb])
            # 检查乌头类
            if base_herb in ["川乌", "草乌"]:
                incompatible_with_base.update(INCOMPATIBLE_HERBS.get("附子", []))
        
        # Step 2.1: 按兼证优先级顺序处理
        for jian_zheng in secondary_diagnoses:
            if added_single_herbs >= max_single_herbs:
                break
            
            # 特殊处理：湿淫证作为兼证时，直接加药（不需要匹配具体症状）
            DIRECT_ADD_JIAN_ZHENG = {
                "湿淫证": ["薏苡仁", "泽泻"],
            }
            if jian_zheng in DIRECT_ADD_JIAN_ZHENG and jian_zheng not in processed_symptoms:
                candidates = DIRECT_ADD_JIAN_ZHENG[jian_zheng]
                valid_candidates = [h for h in candidates if h not in incompatible_with_base]
                
                # 底方排斥：若任一有效候选药已在底方或已选药中，跳过
                if not any(h in selected_herbs for h in valid_candidates) and valid_candidates:
                    best_herb = valid_candidates[0]
                    herbs.append(best_herb)
                    selected_herbs.add(best_herb)
                    added_single_herbs += 1
                    processed_symptoms.add(jian_zheng)
                    self._jian_zheng_add_herb_details.append(
                        (jian_zheng, jian_zheng, candidates, best_herb, "兼证直接加药")
                    )
                    if added_single_herbs >= max_single_herbs:
                        break
                else:
                    processed_symptoms.add(jian_zheng)
                    if any(h in selected_herbs for h in valid_candidates):
                        self._jian_zheng_add_herb_details.append(
                            (jian_zheng, jian_zheng, candidates, None, "底方或已选药中已含候选药")
                        )
            
            # 获取该兼证对应的症状列表
            symptoms_for_jz = JIAN_ZHENG_SYMPTOMS.get(jian_zheng, [])
            
            # 若该兼证的症状均不在数据库F中（空列表），直接跳过
            # 这些症状会在 Step 2.2 孤立症状处理中按出现顺序独立处理
            if not symptoms_for_jz:
                continue
            
            # 记录已处理过的候选药组合（同一候选药组合只记录一次）
            processed_candidate_keys = set()
            
            # 按症状出现顺序处理
            for symptom in symptoms_for_jz:
                if added_single_herbs >= max_single_herbs:
                    break
                if symptom in processed_symptoms:
                    continue
                if not self.keyword_match(all_texts, symptom):
                    continue
                
                candidates = SYMPTOM_HERB_MAPPING.get(symptom, [])
                if not candidates:
                    continue
                
                # 生成候选药组合的key，用于去重
                candidates_key = tuple(sorted(candidates))
                
                # 过滤掉与底方存在十八反冲突的候选药
                valid_candidates = [h for h in candidates if h not in incompatible_with_base]
                
                # 底方排斥：若任一有效候选药已在底方或已选药中，跳过
                if any(h in selected_herbs for h in valid_candidates):
                    processed_symptoms.add(symptom)
                    # 同一候选药组合只记录一次
                    if candidates_key not in processed_candidate_keys:
                        processed_candidate_keys.add(candidates_key)
                        self._jian_zheng_add_herb_details.append(
                            (jian_zheng, symptom, candidates, None, "底方或已选药中已含候选药")
                        )
                    continue
                
                # 如果所有候选药都被十八反排除，跳过
                if not valid_candidates:
                    processed_symptoms.add(symptom)
                    # 同一候选药组合只记录一次
                    if candidates_key not in processed_candidate_keys:
                        processed_candidate_keys.add(candidates_key)
                        self._jian_zheng_add_herb_details.append(
                            (jian_zheng, symptom, candidates, None, "候选药均与底方存在十八反冲突")
                        )
                    continue
                
                # 一药多效：优先选择能覆盖更低优先级兼证的候选药
                best_herb = None
                best_coverage_count = 0
                best_coverage_priority = float('inf')
                
                for herb in valid_candidates:
                    # 计算该药能覆盖的更低优先级兼证
                    coverage_count = 0
                    coverage_priority = float('inf')
                    
                    # 检查该药能覆盖哪些更低优先级的兼证
                    current_jz_idx = secondary_diagnoses.index(jian_zheng) if jian_zheng in secondary_diagnoses else -1
                    for lower_idx, lower_jz in enumerate(secondary_diagnoses):
                        if lower_idx <= current_jz_idx:
                            continue
                        lower_symptoms = JIAN_ZHENG_SYMPTOMS.get(lower_jz, [])
                        for lower_symptom in lower_symptoms:
                            lower_candidates = SYMPTOM_HERB_MAPPING.get(lower_symptom, [])
                            if herb in lower_candidates and lower_symptom not in processed_symptoms:
                                coverage_count += 1
                                coverage_priority = min(coverage_priority, lower_idx)
                    
                    # 选择覆盖数量最多的，若相同则选择覆盖优先级最高的
                    if coverage_count > best_coverage_count or \
                       (coverage_count == best_coverage_count and coverage_priority < best_coverage_priority):
                        best_herb = herb
                        best_coverage_count = coverage_count
                        best_coverage_priority = coverage_priority
                
                # 如果没有能覆盖更低优先级兼证的药，选择第一个有效候选药
                if best_herb is None:
                    best_herb = valid_candidates[0]
                
                # 添加药物
                herbs.append(best_herb)
                selected_herbs.add(best_herb)
                added_single_herbs += 1
                processed_symptoms.add(symptom)
                processed_candidate_keys.add(candidates_key)
                
                self._jian_zheng_add_herb_details.append(
                    (jian_zheng, symptom, candidates, best_herb, 
                     f"覆盖{best_coverage_count}个更低优先级兼证" if best_coverage_count > 0 else "首选")
                )
        
        # Step 2.2: 孤立症状处理
        # 若新增药物不足4味，处理未归入兼证但在数据库F中有对应药物的孤立症状
        # 关键修改：按症状的发生顺序（time_order）排序后依次加药
        if added_single_herbs < max_single_herbs:
            # 收集所有待处理的孤立症状及其时序
            # 格式: (symptom, candidates, valid_candidates, time_order)
            isolated_symptoms = []
            
            # 1. 检查风淫证（确诊但无药方、不作为兼证）
            if self.diagnosis.feng_yin and "风淫证" not in processed_symptoms:
                feng_candidates = ["防风", "白鲜皮"]
                valid = [h for h in feng_candidates if h not in incompatible_with_base]
                if valid and not any(h in selected_herbs for h in valid):
                    feng_time_order = self._get_isolated_symptom_time_order("风淫证")
                    isolated_symptoms.append(("风淫证", feng_candidates, valid, feng_time_order))
                else:
                    processed_symptoms.add("风淫证")
            
            # 2. 检查血热证（确诊但无药方、不作为兼证）
            if self.diagnosis.xue_re and "血热证" not in processed_symptoms:
                xue_re_candidates = ["白茅根", "茜草"]
                valid = [h for h in xue_re_candidates if h not in incompatible_with_base]
                if valid and not any(h in selected_herbs for h in valid):
                    xue_re_time_order = self._get_isolated_symptom_time_order("血热证")
                    isolated_symptoms.append(("血热证", xue_re_candidates, valid, xue_re_time_order))
                else:
                    processed_symptoms.add("血热证")
            
            # 3. 检查 SYMPTOM_HERB_MAPPING 中的其他孤立症状
            for symptom, candidates in SYMPTOM_HERB_MAPPING.items():
                if symptom in processed_symptoms:
                    continue
                
                # 检查症状是否在文本中出现
                if not self.keyword_match(all_texts, symptom):
                    continue
                
                # 特殊处理：冷痛在表证时不加药
                if symptom == "冷痛" and self.diagnosis.biao_zheng:
                    continue
                
                # 过滤掉与底方存在十八反冲突的候选药
                valid_candidates = [h for h in candidates if h not in incompatible_with_base]
                
                # 底方排斥：若任一有效候选药已在底方或已选药中，跳过
                if any(h in selected_herbs for h in valid_candidates):
                    processed_symptoms.add(symptom)
                    continue
                
                # 如果所有候选药都被十八反排除，跳过并记录
                if not valid_candidates:
                    processed_symptoms.add(symptom)
                    self._jian_zheng_add_herb_details.append(
                        (None, symptom, candidates, None, "候选药均与底方存在十八反冲突")
                    )
                    continue
                
                # 获取该症状的时序
                symptom_time_order = self._get_isolated_symptom_time_order(symptom)
                isolated_symptoms.append((symptom, candidates, valid_candidates, symptom_time_order))
            
            # 4. 按时序排序（time_order 小的优先）
            isolated_symptoms.sort(key=lambda x: x[3])
            
            # 5. 依次加药
            for symptom, candidates, valid_candidates, time_order in isolated_symptoms:
                if added_single_herbs >= max_single_herbs:
                    break
                
                # 再次检查底方排斥（因为前面的加药可能已经添加了候选药）
                if any(h in selected_herbs for h in valid_candidates):
                    processed_symptoms.add(symptom)
                    continue
                
                best_herb = valid_candidates[0]
                herbs.append(best_herb)
                selected_herbs.add(best_herb)
                added_single_herbs += 1
                processed_symptoms.add(symptom)
                
                self._jian_zheng_add_herb_details.append(
                    (None, symptom, candidates, best_herb, f"孤立症状(时序{time_order})")
                )
        
        # --- 十八反全局冲突检测（包含甘草系） ---
        herbs_to_remove = []
        for base_herb, incompatible_list in INCOMPATIBLE_HERBS.items():
            if base_herb in herbs:
                for inc_herb in incompatible_list:
                    if inc_herb in herbs:
                        herbs_to_remove.append(inc_herb)
        for h in set(herbs_to_remove):
            if h in herbs:
                herbs.remove(h)
        
        # 最终特殊医嘱补充（去重）
        formula_names = [f.name for f in base_formulas]
        for fn in formula_names:
            self._add_special_notes_for_herbs(herbs, fn, special_notes)
        
        # 去除重复的特殊医嘱
        special_notes = list(dict.fromkeys(special_notes))
        
        # 方名命名
        # SP规定：只有对底方做出了改动（加药或减药）时才需要加"加减"
        final_herbs = set(herbs)
        has_modification = (final_herbs != original_herbs)
        
        unique_formula_names = list(set(f.name for f in base_formulas))
        if len(base_formulas) == 1 or len(unique_formula_names) == 1:
            if has_modification:
                formula_name = base_formulas[0].name + "加减"
            else:
                formula_name = base_formulas[0].name
        elif len(base_formulas) >= 2:
            first_monarch = monarch_herbs_list[0]
            second_monarch = monarch_herbs_list[1]
            if first_monarch == second_monarch:
                formula_name_pre = f"{first_monarch}汤"
            else:
                formula_name_pre = f"{first_monarch}{second_monarch}汤"

            if has_modification:
                formula_name = f"{formula_name_pre}加减"
            else:
                formula_name = formula_name_pre
        else:
            formula_name = "自拟方"
        
        return Prescription(formula_name, herbs, special_notes)    
    def generate_dietary_advice(self, all_texts: str) -> List[str]:
        """生成饮食忌口建议（基于 system_prompt 医嘱逻辑库）"""
        advice = []
        
        # 阴证：SP定义 - 里证、寒证、阳虚证、亡阳证
        is_yin_zheng = self.diagnosis.li_zheng or self.diagnosis.han_zheng or \
                       self.diagnosis.yang_xu or self.diagnosis.wang_yang
        if is_yin_zheng:
            advice.append("绝对不能吃冰镇饮料、生冷瓜果（西瓜、梨、香蕉）、凉茶、绿豆汤、海鲜（螃蟹、贝类）。多吃点生姜、羊肉、红糖。")
        
        # 阳证：SP定义 - 表证、热证、实证、阴虚证、亡阴证
        # 注意：真寒假热时，热证是假象，不应触发阳证忌口
        is_yang_zheng = (
            self.diagnosis.biao_zheng or 
            (self.diagnosis.re_zheng and not self.diagnosis.zhen_han_jia_re) or  # 热证（排除真寒假热）
            self.diagnosis.shi_zheng or 
            self.diagnosis.yin_xu or 
            self.diagnosis.wang_yin
        )
        if is_yang_zheng:
            advice.append("绝对不能吃辛辣刺激（辣椒、花椒）、羊肉、狗肉、姜汤、荔枝、龙眼、白酒。饮食要清淡，多吃青菜。")
        
        # 湿淫证/痰多
        # 当有痰症状、痰热壅肺或湿淫证时触发
        # 但当主病是肾阳虚+食滞胃脘（case5）时，湿淫证作为兼证不触发此忌口
        # is_shen_yang_xu_with_shi_zhi = hasattr(self, 'main_diseases') and \
        #     "肾阳虚" in self.main_diseases and "食滞胃脘" in self.main_diseases
        if self.diagnosis.shi_yin: #self.diagnosis.has_tan_symptoms or 
            advice.append("少吃油腻肥厚（红烧肉、猪蹄）、甜食（蛋糕、奶茶）、生冷水果、乳制品、酒类。")
        
        # 积食
        if self.keyword_match(all_texts, "积食"):
            advice.append("少吃多餐，晚饭少吃，不吃难消化的糯米、年糕、坚果。")
        
        # 血瘀
        if self.diagnosis.xue_yu:
            advice.append("少吃寒凉收涩的食物（如乌梅、柿子），可适当吃点醋、山楂。")
        
        # 皮肤病（风/湿）
        # 注意：需要匹配各种变体，如"皮肤有点痒"、"皮肤痒"、"瘙痒"、"想挠"
        if self.diagnosis.feng_yin:
            advice.append('严禁吃"发物"，如海鲜、腥膻牛羊肉、韭菜、香菜、芒果、榴莲。')
        
        return advice    

    def generate_emotion_advice(self) -> List[str]:
        """生成情志调节建议
        
        根据system_prompt规则，若诊断包含七情致病，必须填入对应建议，格式为【情绪伤脏腑】
        需要根据具体的致病情绪类型来选择正确的建议标签
        返回所有匹配的七情建议列表
        """
        advice = []
        
        if self.diagnosis.qi_qing_shang_xin:
            emotion = self.diagnosis.qi_qing_xin_emotion
            if emotion == '喜':
                advice.append("情绪不要大起大落，大喜大悲都伤心神。最近要静养，少看刺激的电视，早点睡觉养神。")

        if self.diagnosis.qi_qing_shang_gan:
            advice.append('莫要再生闷气了，"气死人"是真能把人身体气坏的。遇到事儿想开点，多去公园散散步，把郁结之气散出来。')
        
        if self.diagnosis.qi_qing_shang_pi:
            advice.append("别成天瞎琢磨了，想太多伤脾胃，饭都吃不香。该吃吃该睡睡，儿孙自有儿孙福，莫操心过度。")
        
        if self.diagnosis.qi_qing_shang_fei:
            emotion = self.diagnosis.qi_qing_fei_emotion
            if emotion == '悲' or emotion == '忧':
                advice.append("别老是哭哭啼啼的，肺气都郁结了。多出去晒晒太阳，找人说说话，把心里的苦闷倒出来就好了。")

        if self.diagnosis.qi_qing_shang_shen:
            emotion = self.diagnosis.qi_qing_shen_emotion
            if emotion == '恐' or emotion == '惊':
                advice.append("胆子放大点，越怕越伤肾气。晚上睡觉关好门窗，多听听舒缓的音乐，安神定志。")
        
        if not advice:
            advice.append("保持心情舒畅。")
        
        return advice
    
    
    def generate_lifestyle_advice(self, main_diseases: List[str], is_critical: bool = False) -> List[str]:
        """生成生活起居建议
        
        根据system_prompt规则：针对性建议从脏腑病邪建议库中选取1条填入，按照对话时序为准
        
        Args:
            main_diseases: 主病列表
            is_critical: 是否为危症
        """
        advice = ["务必早睡早起，晚上11点前必须睡觉，不要熬夜。"]
        
        # 危症时只输出基础建议
        if is_critical:
            return advice
        
        # 针对性建议只选取1条（按主病时序，取第一个匹配的）
        targeted_advice = None
        # print('#########', main_diseases)
        for disease in main_diseases:
            if "肾" in disease and targeted_advice is None:
                targeted_advice = "房事要节制（或者暂停一段时间），腰部别受凉，千万别累着了。"
                break
            if ("肺" in disease or "痰" in disease) and targeted_advice is None:
                targeted_advice = "出门记得戴口罩，别吹风，护好脖子。家里有烟味、粉尘要避开。"
                break
            if ("脾" in disease or "胃" in disease or '虚劳里急' in disease) and targeted_advice is None:
                if self.diagnosis.shi_zheng:
                    targeted_advice = "吃饭要细嚼慢咽，吃七分饱就行。"
                else:
                    targeted_advice = "吃饭要细嚼慢咽，吃七分饱就行。肚子要注意保暖，没事多顺时针揉揉肚子。"
                break
            if "肝" in disease and targeted_advice is None:
                targeted_advice = "睡前泡泡脚，少看手机，尤其是别在床上生气，把心放宽。"
                break
            if "心" in disease and targeted_advice is None:
                targeted_advice = "中午尽量睡个午觉（子午觉），别喝浓茶咖啡。"
                break
        
            if targeted_advice is None and disease=='湿淫证':
                targeted_advice = "多晒太阳，少呆在阴暗潮湿的地方，头发洗完一定要立刻吹干。"
                break
        
        if targeted_advice:
            advice.append(targeted_advice)
        
        return advice


# ==================== 诊断书生成器 ====================

class DiagnosticReportGenerator:
    """诊断书生成器"""
    
    def __init__(self, engine: TCMDiagnosisEngine):
        self.engine = engine
    
    # def generate_report(self, case_data: Dict) -> str:
    #     """生成诊断书"""
    #     # 运行诊断
    #     self.engine.run_diagnosis(case_data)
        
    #     # 获取闽南魂触发响应
    #     minnan_response = self.engine.get_minnan_response()
        
    #     # 确定主病
    #     main_diseases = self.engine.determine_main_disease(case_data)
    #     self.engine.main_diseases = main_diseases  # 存储主病，供select_formula使用
        
    #     # 判断是否为危症
    #     is_critical = any(d in ["亡阳证", "亡阴证", "气脱证"] for d in main_diseases)
        
    #     # 选择方剂
    #     prescription = self.engine.select_formula()
        
    #     # 生成建议
    #     dietary_advice = self.engine.generate_dietary_advice()
    #     emotion_advice = self.engine.generate_emotion_advice()
    #     lifestyle_advice = self.engine.generate_lifestyle_advice(main_diseases, is_critical)
        
    #     # 构建诊断书
    #     report = self._build_report(
    #         main_diseases=main_diseases,
    #         prescription=prescription,
    #         dietary_advice=dietary_advice,
    #         emotion_advice=emotion_advice,
    #         lifestyle_advice=lifestyle_advice,
    #         minnan_response=minnan_response,
    #         is_critical=is_critical
    #     )
        
    #     return report
    
    def _build_report(self, main_diseases: List[str], prescription: Prescription,
                      dietary_advice: List[str], emotion_advice: List[str],
                      lifestyle_advice: List[str], minnan_response: Optional[str],
                      is_critical: bool = False) -> str:
        """构建诊断书文本（先推理逻辑，后诊断书正文）"""
        lines = []
        if is_critical:
            lines.append("**【危症警告】此病情极其危险，涉及生命安全，请立刻前往最近的医院急诊！停止任何网络咨询！**")
            lines.append("")
        
        # 获取兼证（供推理逻辑和诊断书共用）
        secondary = self._get_secondary_diagnoses(main_diseases)
        
        # ========= 第一部分：详细推理逻辑 =========
        lines.append("## 推理逻辑")
        lines.append("")
        lines.extend(self._generate_reasoning_lines(main_diseases, prescription, dietary_advice, emotion_advice, lifestyle_advice, secondary))
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # ========= 第二部分：诊断书正文 =========
        lines.append("# 诊断书")
        lines.append("")
        
        # 1. 医案概况
        lines.append("### 1. 医案概况")
        lines.append("")
        
        # 患者画像
        gender_str = self.engine.patient.gender.value
        patient_info = f"- **患者画像**：{gender_str}"
        if minnan_response:
            patient_info += f" {minnan_response}"
        lines.append(patient_info)
        lines.append("")
        
        # 主病诊断（不含推导链，推导链已在推理逻辑中展示）
        lines.append(f"- **主病诊断**：{'、'.join(main_diseases)}")
        lines.append("")
        
        # 兼证（不含推导依据，依据已在推理逻辑中展示）
        if secondary:
            lines.append(f"- **兼证**：{'、'.join(secondary)}")
            lines.append("")
        
        # 2. 处方
        lines.append("### 2. 处方")
        lines.append("")
        lines.append(f"- **方名**：{prescription.formula_name}")
        lines.append("")
        
        # 药材清单
        herbs_with_notes = []
        for herb in prescription.herbs:
            herb_str = herb
            # 添加特殊医嘱（检查医嘱是否以该药材名开头）
            for note in prescription.special_notes:
                if note.startswith(herb + "(") or note.startswith(herb + "（"):
                    herb_str = note
                    break
            herbs_with_notes.append(herb_str)
        
        lines.append(f"- **药材清单**：{'、'.join(herbs_with_notes)}")
        lines.append("")
        
        # 3. 医嘱与叮嘱
        lines.append("### 3. 医嘱与叮嘱")
        lines.append("")
        
        # 饮食忌口
        lines.append("1. **饮食忌口**：")
        for advice in dietary_advice:
            lines.append(f"   - {advice}")
        lines.append("")
        
        # 情志调节
        lines.append("2. **情志调节**：")
        for advice in emotion_advice:
            lines.append(f"   - {advice}")
        lines.append("")
        
        # 生活起居
        lines.append("3. **生活起居**：")
        for i, advice in enumerate(lifestyle_advice):
            if i == 0:
                lines.append(f"   - **基础建议**：{advice}")
            else:
                lines.append(f"   - **针对性建议**：{advice}")
        
        # 好孕模式
        if self.engine.patient.good_pregnancy_mode:
            lines.append("   - 回去记得拜拜注生娘娘，床头放点红枣花生，早生贵子！")
        
        return "\n".join(lines)
    
    def _generate_reasoning_lines(self, main_diseases: List[str], prescription: Prescription,
                                   dietary_advice: List[str], emotion_advice: List[str],
                                   lifestyle_advice: List[str], secondary: List[str]) -> List[str]:
        """生成详细的推导逻辑文本行（按诊断流程组织）
        
        输出完整的推理过程，按诊断流程顺序输出：
        1. 病症识别（各条目识别出的症状关键词及初步映射）
        2. 八纲辨证推导（表里/寒热/虚实/阴阳 — 跨条目组合）
        3. 脏腑辨证推导（定位+定性的组合过程 → 得到具体病名）
        4. 主病确定与兼证判定（优先级筛选 → 哪些是主病、哪些是兼证）
        5. 处方推理逻辑（底方选择→兼证加药→冲突检测→方名命名）
        6. 医嘱推理逻辑（饮食忌口/情志调节/生活起居的触发条件）
        """
        lines = []
        d = self.engine.diagnosis  # 快捷引用
        basis = d.diagnosis_basis   # 诊断时记录的依据字典，直接读取
        
        # ========= 一、病症识别 =========
        lines.append("#### 一、病症识别")
        lines.append("")
        lines.append("**各条目症状关键词识别：**")
        lines.append("")
        for di in self.engine.disease_items:
            label_str = di.severity_label or '无'
            if di.severity_label == '排除':
                lines.append(f"- **[{di.time_order}]**（{di.time or '无时间'}，严重程度：{label_str}）→ 已排除，不纳入诊断")
            elif di.severity_label == '弱化':
                lines.append(f"- **[{di.time_order}]**（{di.time or '无时间'}，严重程度：{label_str}）→ 已弱化，仅作辅助参考")
                mapped_diseases = self.engine._map_text_to_diseases(di.text)
                confirmed = [d_name for d_name in mapped_diseases if self.engine._is_disease_confirmed(d_name)]
                if confirmed:
                    lines.append(f"  - 可识别病症：{'、'.join(confirmed)}")
            else:
                mapped_diseases = self.engine._map_text_to_diseases(di.text)
                confirmed = [d_name for d_name in mapped_diseases if self.engine._is_disease_confirmed(d_name)]
                mapped_str = '、'.join(confirmed) if confirmed else "暂未确定"
                lines.append(f"- **[{di.time_order}]**（{di.time or '无时间'}，严重程度：{label_str}）→ 可识别病症：{mapped_str}")
        lines.append("")
        
        # ========= 二、八纲辨证推导（跨条目组合） =========
        lines.append("#### 二、八纲辨证推导（跨条目组合）")
        lines.append("")
        
        # 表里辨证
        li_str = "✅里证" if d.li_zheng else "❌里证"
        biao_str = "✅表证" if d.biao_zheng else "❌表证"
        lines.append(f"- **表里辨证**：{li_str}，{biao_str}")
        if d.li_zheng:
            for b in basis.get("里证", []):
                lines.append(f"  - {b}")
        if d.biao_zheng:
            for b in basis.get("表证", []):
                lines.append(f"  - {b}")
        
        # 寒热辨证
        han_str = "✅寒证" if d.han_zheng else "❌寒证"
        re_str = "✅热证" if d.re_zheng else "❌热证"
        lines.append(f"- **寒热辨证**：{han_str}，{re_str}")
        if d.han_zheng or (not d.han_zheng and d.zhen_re_jia_han):
            for b in basis.get("寒证", []):
                lines.append(f"  - {b}")
        if d.re_zheng or (not d.re_zheng and d.zhen_han_jia_re):
            for b in basis.get("热证", []):
                lines.append(f"  - {b}")
        if d.zhen_han_jia_re:
            for b in basis.get("真寒假热证", []):
                lines.append(f"  - 寒热并见 → {b} → **真寒假热证**")
        if d.zhen_re_jia_han:
            for b in basis.get("真热假寒证", []):
                lines.append(f"  - 寒热并见 → {b} → **真热假寒证**")
        if d.han_re_bing_jian_unknown:
            for b in basis.get("寒热并见待定", []):
                lines.append(f"  - ⚠️ 寒热并见：{b}")
        
        # 虚实辨证
        xu_str = "✅虚证" if d.xu_zheng else "❌虚证"
        shi_str = "✅实证" if d.shi_zheng else "❌实证"
        lines.append(f"- **虚实辨证**：{xu_str}，{shi_str}")
        if d.xu_zheng or (not d.xu_zheng and d.zhen_xu_jia_shi):
            for b in basis.get("虚证", []):
                lines.append(f"  - {b}")
        if d.shi_zheng or (not d.shi_zheng and d.zhen_shi_jia_xu):
            for b in basis.get("实证", []):
                lines.append(f"  - {b}")
        if d.zhen_xu_jia_shi:
            for b in basis.get("真虚假实证", []):
                lines.append(f"  - 虚实并见 → {b} → **真虚假实证**")
        if d.zhen_shi_jia_xu:
            for b in basis.get("真实假虚证", []):
                lines.append(f"  - 虚实并见 → {b} → **真实假虚证**")
        if d.xu_shi_bing_jian_unknown:
            for b in basis.get("虚实并见待定", []):
                lines.append(f"  - ⚠️ 虚实并见：{b}")
        
        # 阴阳辨证 - 直接使用 diagnosis_basis 中记录的依据
        yang_xu_basis = basis.get("阳虚", [])
        yin_xu_basis = basis.get("阴虚", [])
        
        # 阳虚输出
        if d.yang_xu and yang_xu_basis:
            yang_xu_str = f"✅阳虚（{yang_xu_basis[0]}）"
        elif d.yang_xu:
            yang_xu_str = "✅阳虚"
        else:
            yang_xu_str = "❌阳虚"
        
        # 阴虚输出 - 优先显示特征症状，其次显示热证+虚证
        if d.yin_xu and yin_xu_basis:
            # 优先取特征症状作为主要说明
            specific = [b for b in yin_xu_basis if "阴虚特征症状" in b]
            general = [b for b in yin_xu_basis if "热证+虚证" in b]
            if specific:
                symptom_str = specific[0].replace("阴虚特征症状：", "")
                yin_xu_str = f"✅阴虚（{symptom_str}→阴虚）"
            elif general:
                yin_xu_str = f"✅阴虚（{general[0]}）"
            else:
                yin_xu_str = f"✅阴虚（{yin_xu_basis[0]}）"
        elif d.yin_xu:
            yin_xu_str = "✅阴虚"
        else:
            yin_xu_str = "❌阴虚"
        
        lines.append(f"- **阴阳辨证**：{yang_xu_str}，{yin_xu_str}")
        # 显示所有诊断依据
        for b in yin_xu_basis:
            lines.append(f"  - {b}")
        if d.yin_yang_liang_xu:
            lines.append("  - 阳虚+阴虚同时成立 → **阴阳两虚**")
        
        lines.append("")

        # ========= 三、脏腑辨证推导（病症组合） =========
        lines.append("#### 三、脏腑辨证推导（定位+定性→病名）")
        lines.append("")
        
        # 列出所有已确认的脏腑病名及其推导链（包括没有药方的）
        # 从 all_candidates 获取所有确诊病名
        all_candidates = getattr(self.engine, 'all_candidates', [])
        all_confirmed_diseases = set(main_diseases) | set(secondary) | {c[0] for c in all_candidates}
        for i, disease in enumerate(all_confirmed_diseases):
            lines.append(f"（{i+1}）**{disease}的推导过程：**")
            lines.append("")
            
            # 生成链式推导
            chain = self._build_disease_chain(disease)
            if chain:
                lines.append(f"- **推导链**：{chain}")
            else:
                # 如果没有推导链，展示诊断依据
                disease_basis = self._get_diagnosis_basis_for_disease(disease)
                if disease_basis:
                    lines.append(f"- **诊断依据**：")
                    for b in disease_basis:
                        lines.append(f"  - {b}")
            
            lines.append("")
        
        # ========= 四、主病确定与兼证判定 =========
        lines.append("#### 四、主病确定与兼证判定")
        lines.append("")
        
        # 获取所有候选
        all_candidates = getattr(self.engine, 'all_candidates', [])
        
        # 先解释规则
        lines.append("**竞选规则说明：**")
        lines.append("```")
        lines.append("主病从所有「确诊病名」中竞选产生，按四级优先级排序：")
        lines.append("  Step 1（病名级别）：危证 > 重症 > 脏腑病 > 七情/真假证 > 六淫证 > 其他")
        lines.append("  Step 2（症状程度）：最严重/主诉 > 特别/非常 > 一般 > 无描述 > 弱化")
        lines.append("  Step 3（全局时序）：先出现 > 后出现")
        lines.append("  Step 4（手册时序）：按system_prompt_zy.md中病症定义顺序排序")
        lines.append("最高优先级的病名成为主病（最多2个），其余确诊病名归为兼证。")
        lines.append("```")
        lines.append("")
        
        # 4.1 列出所有确诊病名及其来源
        lines.append("**4.1 确诊病名一览：**")
        lines.append("")
        
        # 收集所有确诊病名（包括特殊诊断如真寒假热证等）
        # 先从 all_candidates 获取基础候选
        all_confirmed = list(all_candidates) if all_candidates else []
        seen_in_candidates = {c[0] for c in all_confirmed}
        
        # 添加特殊诊断（真假寒热、真假虚实等）
        # 格式：(病名, S1级别, S2级别, time_order, manual_order)
        special_diagnoses = []
        if d.zhen_han_jia_re and "真寒假热证" not in seen_in_candidates:
            special_diagnoses.append(("真寒假热证", S1_TIER.get("真寒假热证", 3), 3, 0, get_disease_manual_order("真寒假热证")))
        if d.zhen_re_jia_han and "真热假寒证" not in seen_in_candidates:
            special_diagnoses.append(("真热假寒证", S1_TIER.get("真热假寒证", 3), 3, 0, get_disease_manual_order("真热假寒证")))
        if d.zhen_xu_jia_shi and "真虚假实证" not in seen_in_candidates:
            special_diagnoses.append(("真虚假实证", S1_TIER.get("真虚假实证", 3), 3, 0, get_disease_manual_order("真虚假实证")))
        if d.zhen_shi_jia_xu and "真实假虚证" not in seen_in_candidates:
            special_diagnoses.append(("真实假虚证", S1_TIER.get("真实假虚证", 3), 3, 0, get_disease_manual_order("真实假虚证")))
        
        # 添加七情内伤
        if d.qi_qing_shang_xin and "七情伤心" not in seen_in_candidates:
            special_diagnoses.append(("七情伤心", S1_TIER.get("七情伤心", 3), 3, 0, get_disease_manual_order("七情伤心")))
        if d.qi_qing_shang_gan and "七情伤肝" not in seen_in_candidates:
            special_diagnoses.append(("七情伤肝", S1_TIER.get("七情伤肝", 3), 3, 0, get_disease_manual_order("七情伤肝")))
        if d.qi_qing_shang_pi and "七情伤脾" not in seen_in_candidates:
            special_diagnoses.append(("七情伤脾", S1_TIER.get("七情伤脾", 3), 3, 0, get_disease_manual_order("七情伤脾")))
        if d.qi_qing_shang_fei and "七情伤肺" not in seen_in_candidates:
            special_diagnoses.append(("七情伤肺", S1_TIER.get("七情伤肺", 3), 3, 0, get_disease_manual_order("七情伤肺")))
        if d.qi_qing_shang_shen and "七情伤肾" not in seen_in_candidates:
            special_diagnoses.append(("七情伤肾", S1_TIER.get("七情伤肾", 3), 3, 0, get_disease_manual_order("七情伤肾")))
        
        # 合并所有确诊病名
        all_confirmed.extend(special_diagnoses)
        
        if all_confirmed:
            # 按优先级排序（包含 Step 4 手册时序）
            sorted_candidates = sorted(all_confirmed, key=lambda x: (x[1], x[2], x[3], x[4] if len(x) > 4 else 999))
            
            # 构建病名到条目的映射
            disease_to_items = {}
            for di in self.engine.disease_items:
                if di.severity_label not in EXCLUDED_LABELS:
                    mapped_diseases = self.engine._map_text_to_diseases(di.text)
                    confirmed = [d_name for d_name in mapped_diseases if self.engine._is_disease_confirmed(d_name)]
                    for d_name in confirmed:
                        if d_name not in disease_to_items:
                            disease_to_items[d_name] = []
                        disease_to_items[d_name].append(di)
            
            # 显示每个确诊病名
            seen_diseases = set()
            s1_labels = {0: "危证", 1: "重症", 2: "脏腑病", 3: "七情/真假证", 4: "六淫证", 5: "其他"}
            s2_labels = {0: "最严重", 1: "较严重", 2: "一般", 3: "无描述", 4: "弱化"}
            
            for candidate in sorted_candidates:
                name = candidate[0]
                s1 = candidate[1]
                s2 = candidate[2]
                order = candidate[3]
                manual_order = candidate[4] if len(candidate) > 4 else 999
                if name not in seen_diseases:
                    seen_diseases.add(name)
                    s1_label = s1_labels.get(s1, f"T{s1}")
                    s2_label = s2_labels.get(s2, f"T{s2}")
                    # 来源条目
                    source_items = disease_to_items.get(name, [])
                    if source_items:
                        source_str = f"来自条目[{source_items[0].time_order}]"
                    elif name in ["真寒假热证", "真热假寒证", "真虚假实证", "真实假虚证"]:
                        source_str = "由寒热/虚实并见推导"
                    elif name.startswith("七情"):
                        source_str = "由情志因素推导"
                    else:
                        source_str = f"来自条目[{order}]" if order > 0 else "综合推导"
                    
                    # 标注是否有药方
                    has_formula = name in DISEASES_WITH_FORMULA
                    formula_str = "有药方" if has_formula else "无药方"
                    lines.append(f"- **{name}**：{s1_label}，{s2_label}，{source_str}，{formula_str}")
        else:
            lines.append("- （无确诊病名）")
        lines.append("")
        
        # 4.2 主病竞选过程
        lines.append("**4.2 主病竞选过程：**")
        lines.append("")
        
        if all_confirmed:
            # 先显示所有候选（包括无药方的），按 S1 -> S2 -> time_order -> manual_order 排序
            sorted_all = sorted(all_confirmed, key=lambda x: (x[1], x[2], x[3], x[4] if len(x) > 4 else 999))
            
            # 只有有药方的病才能参与主病竞选
            candidates_with_formula = [c for c in sorted_all if c[0] in DISEASES_WITH_FORMULA]
            
            # 显示排序结果（标注有无药方）
            lines.append("按优先级排序后的候选列表（Step1级别 → Step2程度 → Step3全局时序 → Step4手册时序）：")
            lines.append("```")
            prev_priority = None
            for candidate in sorted_all:
                name = candidate[0]
                s1 = candidate[1]
                s2 = candidate[2]
                order = candidate[3]
                manual_order = candidate[4] if len(candidate) > 4 else 999
                s2_source = candidate[5] if len(candidate) > 5 else None
                priority = (s1, s2)
                if prev_priority != priority:
                    if prev_priority is not None:
                        lines.append("  ---")  # 分隔不同优先级
                    prev_priority = priority
                has_formula = name in DISEASES_WITH_FORMULA
                if has_formula and candidates_with_formula:
                    best_s1 = candidates_with_formula[0][1]
                    best_s2 = candidates_with_formula[0][2]
                    marker = "★" if (s1, s2) == (best_s1, best_s2) else ""
                else:
                    marker = "✗" if not has_formula else ""
                formula_note = "" if has_formula else "（无药方，不参与竞选）"
                # 程度来源说明
                if s2_source:
                    s2_source_str = f"←「{s2_source}」"
                else:
                    s2_source_str = "←默认"
                # 时序来源说明
                s3_info = self.engine.s3_source_map.get(name)
                if s3_info:
                    s3_kw, s3_is_zangfu = s3_info
                    s3_source_str = f"←「{s3_kw}」{'(脏腑定位)' if s3_is_zangfu else ''}"
                else:
                    s3_source_str = ""
                lines.append(f"  {marker} {name}（级别{s1}，程度{s2}{s2_source_str}，时序{order}{s3_source_str}，手册序{manual_order}）{formula_note}")
            lines.append("```")
            lines.append("")
            
            # 解释选择结果（只考虑有药方的）
            if candidates_with_formula:
                best_s1 = candidates_with_formula[0][1]
                best_s2 = candidates_with_formula[0][2]
                top_tier_candidates = [c for c in candidates_with_formula if c[1] == best_s1 and c[2] == best_s2]
                
                if len(top_tier_candidates) == 1:
                    winner = top_tier_candidates[0][0]
                    lines.append(f"→ 最高优先级（级别{best_s1}，程度{best_s2}）只有 **{winner}** 一个")
                    lines.append(f"→ **主病确定为：{winner}**")
                else:
                    lines.append(f"→ 最高优先级（级别{best_s1}，程度{best_s2}）有 {len(top_tier_candidates)} 个候选")
                    # 检查是否有时序相同的情况
                    time_orders = [c[3] for c in top_tier_candidates]
                    if len(set(time_orders)) < len(time_orders):
                        lines.append(f"→ 存在全局时序相同的候选，按手册时序（Step 4）进一步排序")
                    lines.append(f"→ 按时序取前2个：**{'、'.join([c[0] for c in top_tier_candidates[:2]])}**")
                    lines.append(f"→ **主病确定为：{'、'.join(main_diseases)}**")
            else:
                lines.append(f"→ **主病确定为：{'、'.join(main_diseases)}**")
        else:
            lines.append(f"→ **主病确定为：{'、'.join(main_diseases)}**")
        lines.append("")
        
        # 4.3 兼证判定
        lines.append("**4.3 兼证判定：**")
        lines.append("")
        if secondary:
            lines.append("未入选主病且有药方的确诊病名归为兼证：")
            s1_labels = {0: "危证", 1: "重症", 2: "脏腑病", 3: "七情/真假证", 4: "六淫证", 5: "其他"}
            for sec in secondary:
                # 查找该兼证在完整候选列表中的级别
                sec_info = next((c for c in all_confirmed if c[0] == sec), None)
                if sec_info:
                    s1_label = s1_labels.get(sec_info[1], f"T{sec_info[1]}")
                    # 判断来源
                    if sec in ["真寒假热证", "真热假寒证", "真虚假实证", "真实假虚证"]:
                        source_str = "由寒热/虚实并见推导"
                    elif sec.startswith("七情"):
                        source_str = "由情志因素推导"
                    elif sec_info[3] > 0:
                        source_str = f"来自条目[{sec_info[3]}]"
                    else:
                        source_str = "综合推导"
                    lines.append(f"- **{sec}**（{s1_label}，{source_str}）→ 优先级低于主病，归为兼证")
                else:
                    # 不在候选中的兼证
                    sec_basis = self._get_diagnosis_basis_for_disease(sec)
                    if sec_basis:
                        lines.append(f"- **{sec}** → 满足诊断条件，作为附加兼证")
                    else:
                        lines.append(f"- **{sec}** → 满足判定条件，作为附加兼证")
            lines.append("")
            lines.append(f"→ **兼证：{'、'.join(secondary)}**")
        else:
            lines.append("→ 无兼证")
        lines.append("")
        
        # ========= 五、处方推理逻辑 =========
        lines.append("#### 五、处方推理逻辑")
        lines.append("")
        
        # Step 1：底方选择
        lines.append("**Step 1 - 底方选择：**")
        # 辅助函数：从FORMULA_DATABASE获取底方药材组成
        def _get_formula_herbs_str(formula_name: str) -> str:
            f = FORMULA_DATABASE.get(formula_name)
            if f:
                return '、'.join(f.herbs)
            return "（未找到药材数据）"
        
        for disease in main_diseases:
            if disease == "肾阳虚":
                severity_str = "重症" if d.shen_severity == SeverityLevel.SEVERE else "轻症"
                formula_str = "右归丸" if d.shen_severity == SeverityLevel.SEVERE else "金匮肾气丸"
                herbs_str = _get_formula_herbs_str(formula_str)
                lines.append(f"- 主病'{disease}'（{severity_str}）→ 选方 **{formula_str}**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "肾阴虚":
                severity_str = "重症" if d.shen_severity == SeverityLevel.SEVERE else "轻症"
                formula_str = "左归丸" if d.shen_severity == SeverityLevel.SEVERE else "六味地黄丸"
                herbs_str = _get_formula_herbs_str(formula_str)
                lines.append(f"- 主病'{disease}'（{severity_str}）→ 选方 **{formula_str}**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "肺阴虚":
                herbs_str = _get_formula_herbs_str("百合固金汤")
                lines.append(f"- 主病'{disease}' → 选方 **百合固金汤**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "痰热壅肺":
                herbs_str = _get_formula_herbs_str("清气化痰丸")
                lines.append(f"- 主病'{disease}' → 选方 **清气化痰丸**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "肝火上炎":
                herbs_str = _get_formula_herbs_str("龙胆泻肝汤")
                lines.append(f"- 主病'{disease}' → 选方 **龙胆泻肝汤**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "食滞胃脘":
                herbs_str = _get_formula_herbs_str("保和丸")
                lines.append(f"- 主病'{disease}' → 选方 **保和丸**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "表寒证":
                herbs_str = _get_formula_herbs_str("麻黄汤")
                lines.append(f"- 主病'{disease}' → 选方 **麻黄汤**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "表热证":
                herbs_str = _get_formula_herbs_str("银翘散")
                lines.append(f"- 主病'{disease}' → 选方 **银翘散**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "里寒证":
                herbs_str = _get_formula_herbs_str("四逆汤")
                lines.append(f"- 主病'{disease}' → 选方 **四逆汤**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "里热证":
                herbs_str = _get_formula_herbs_str("白虎汤")
                lines.append(f"- 主病'{disease}' → 选方 **白虎汤**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "亡阳证":
                herbs_str = _get_formula_herbs_str("参附汤")
                lines.append(f"- 危症'{disease}' → 选方 **参附汤**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "亡阴证":
                herbs_str = _get_formula_herbs_str("生脉散")
                lines.append(f"- 危症'{disease}' → 选方 **生脉散**")
                lines.append(f"  - 组成：{herbs_str}")
            elif disease == "气脱证":
                herbs_str = _get_formula_herbs_str("独参汤")
                lines.append(f"- 危症'{disease}' → 选方 **独参汤**")
                lines.append(f"  - 组成：{herbs_str}")
            else:
                # 尝试从FORMULA_DATABASE中查找匹配的方剂
                matched_formula = None
                for fname, fobj in FORMULA_DATABASE.items():
                    if disease in fobj.indications:
                        matched_formula = fobj
                        break
                if matched_formula:
                    herbs_str = '、'.join(matched_formula.herbs)
                    lines.append(f"- 主病'{disease}' → 选方 **{matched_formula.name}**")
                    lines.append(f"  - 组成：{herbs_str}")
                else:
                    lines.append(f"- 主病'{disease}' → 数据库无匹配底方")
        lines.append("")
        
        # Step 2：兼证加药（基于 system_prompt_zy.md 第1016-1023行）
        lines.append("**Step 2 - 兼证加药（最多4味）：**")
        lines.append("- 规则：按兼证优先级顺序遍历 → 拆解为具体症状 → 底方排斥 → 一药多效优先")
        lines.append("")
        
        # 重新收集底方药材
        base_herbs = []
        for disease in main_diseases:
            formula_map = {
                "肾阳虚": "右归丸" if d.shen_severity == SeverityLevel.SEVERE else "金匮肾气丸",
                "肾阴虚": "左归丸" if d.shen_severity == SeverityLevel.SEVERE else "六味地黄丸",
                "痰热壅肺": "清气化痰丸",
                "肺阴虚": "百合固金汤",
                "肝火上炎": "龙胆泻肝汤",
                "肝气郁结": "逍遥散",
                "食滞胃脘": "保和丸",
                "里寒证": "四逆汤",
                "血寒证": "温经汤",
                "亡阳证": "参附汤",
                "亡阴证": "生脉散",
                "气脱证": "独参汤",
                "脾阳虚": "附子理中丸",
                "脾气虚": "参苓白术散",
                "心气虚": "养心汤",
                "心血虚": "归脾汤",
                "心阴虚": "天王补心丹",
                "心阳虚": "桂枝甘草汤",
                "肺气虚": "补肺汤",
                "寒痰阻肺": "三子养亲汤",
                "肝血虚": "补肝汤",
                "肝阳上亢": "天麻钩藤饮",
                "肝胆湿热": "龙胆泻肝汤",
                "表寒证": "麻黄汤",
                "表热证": "银翘散",
            }
            fname = formula_map.get(disease)
            if fname and fname in FORMULA_DATABASE:
                for h in FORMULA_DATABASE[fname].herbs:
                    if h not in base_herbs:
                        base_herbs.append(h)
        
        # 从engine获取加药详情（如果有）
        jian_zheng_add_details = getattr(self.engine, '_jian_zheng_add_herb_details', [])
        
        if jian_zheng_add_details:
            added_count = 0
            for detail in jian_zheng_add_details:
                jian_zheng, symptom, candidates, added_herb, reason = detail
                candidates_str = "/".join(candidates)
                
                if added_herb:
                    added_count += 1
                    if jian_zheng:
                        lines.append(f"- 兼证「{jian_zheng}」→ 症状「{symptom}」→ 候选药：{candidates_str} → **加入：{added_herb}**（{reason}）")
                    else:
                        lines.append(f"- 孤立症状「{symptom}」→ 候选药：{candidates_str} → **加入：{added_herb}**（{reason}）")
                else:
                    if jian_zheng:
                        lines.append(f"- 兼证「{jian_zheng}」→ 症状「{symptom}」→ 候选药：{candidates_str} → 跳过（{reason}）")
                    else:
                        lines.append(f"- 孤立症状「{symptom}」→ 候选药：{candidates_str} → 跳过（{reason}）")
            
            if added_count == 0:
                lines.append("- 所有症状已被底方覆盖，无需额外加药")
            else:
                lines.append(f"- 共加入 {added_count} 味兼证药")
        else:
            lines.append("- 无兼证触发，无需额外加药")
        lines.append("")
        
        # Step 3：冲突检测（在选药时已预先排除，此处仅展示规则）
        lines.append("**Step 3 - 十八反冲突检测：**")
        lines.append("- 说明：在Step 2选药时已预先排除与底方存在十八反冲突的候选药")
        
        # 遍历所有十八反规则，检测底方中是否有相关药材
        incompatible_rules = INCOMPATIBLE_HERBS
        triggered_bases = [base for base in incompatible_rules if base in base_herbs]
        triggered_bases += [base for base in ["川乌", "草乌"] if base in base_herbs and base not in triggered_bases]
        
        if triggered_bases:
            for base in triggered_bases:
                inc_list = incompatible_rules.get(base, [])
                lines.append(f"- {base} ∈ 底方 → 禁配：{'、'.join(inc_list)} → 选药时已排除")
        else:
            lines.append("- 底方无十八反相关药物")
        lines.append("- ✅ 通过")
        lines.append("")
        
        # Step 4：方名命名
        lines.append("**Step 4 - 方名命名：**")
        lines.append(f"- 最终方名：**{prescription.formula_name}**")
        has_jia_jian = "加减" in prescription.formula_name
        if len(main_diseases) >= 2:
            if has_jia_jian:
                lines.append(f"  - 2个底方 → 取各自首位君药，按全局时序拼接 + '汤'；有加减药 → + '加减'")
            else:
                lines.append(f"  - 2个底方 → 取各自首位君药，按全局时序拼接 + '汤'；无加减药 → 不加'加减'")
        elif len(main_diseases) == 1:
            if has_jia_jian:
                lines.append(f"  - 1个底方；有加减药 → 底方名 + '加减'")
            else:
                lines.append(f"  - 1个底方；无加减药 → 直接使用底方名")
        lines.append("")
        
        # Step 5：最终处方
        lines.append("**Step 5 - 最终处方：**")
        lines.append(f"- 方名：**{prescription.formula_name}**")
        lines.append(f"- 药材（共{len(prescription.herbs)}味）：{'、'.join(prescription.herbs)}")
        if prescription.special_notes:
            lines.append("- 特殊煎服医嘱：")
            for note in prescription.special_notes:
                lines.append(f"  - {note}")
        else:
            lines.append("- 特殊煎服医嘱：无")
        lines.append("")
        
        # ========= 七、医嘱推理逻辑 =========
        lines.append("#### 六、医嘱推理逻辑")
        lines.append("")
        
        # 饮食忌口推理
        lines.append("**饮食忌口触发条件：**")
        is_yin = d.li_zheng or d.han_zheng or d.yang_xu or d.wang_yang
        is_yang = d.biao_zheng or d.re_zheng or d.shi_zheng or d.yin_xu or d.wang_yin
        if is_yin:
            yin_triggers = []
            if d.li_zheng:
                yin_triggers.append("里证")
            if d.han_zheng:
                yin_triggers.append("寒证")
            if d.yang_xu:
                yin_triggers.append("阳虚")
            if d.wang_yang:
                yin_triggers.append("亡阳")
            yin_triggers_str = "/".join(yin_triggers)
            lines.append(f"- 阴证（里证/寒证/阳虚/亡阳）= True（触发状态：{yin_triggers_str}）→ 忌生冷")
        if is_yang:
            yang_triggers = []
            if d.biao_zheng:
                yang_triggers.append("表证")
            if d.re_zheng:
                yang_triggers.append("热证")
            if d.shi_zheng:
                yang_triggers.append("实证")
            if d.yin_xu:
                yang_triggers.append("阴虚")
            if d.wang_yin:
                yang_triggers.append("亡阴")
            yang_triggers_str = "/".join(yang_triggers)
            lines.append(f"- 阳证（表证/热证/实证/阴虚/亡阴）= True（触发状态：{yang_triggers_str}）→ 忌辛辣")
        if d.shi_yin:
            lines.append("- 湿淫证 = True → 忌油腻")
        all_texts_str = ' '.join(self.engine._get_all_disease_texts())
        if TCMDiagnosisEngine.keyword_match(all_texts_str, "积食"):
            lines.append("- 积食/食积关键词命中 → 少吃多餐")
        if d.xue_yu:
            lines.append("- 血瘀 = True → 忌寒凉收涩")
        if d.feng_yin:
            lines.append("- 风淫 = True → 忌发物")
        lines.append("")
        
        # 情志调节推理
        lines.append("**情志调节触发条件：**")
        has_qiqing = False
        if d.qi_qing_shang_xin:
            lines.append("- 七情伤心 = True → 静养安神")
            has_qiqing = True
        if d.qi_qing_shang_gan:
            lines.append("- 七情伤肝 = True → 疏肝解郁")
            has_qiqing = True
        if d.qi_qing_shang_pi:
            lines.append("- 七情伤脾 = True → 减少忧思")
            has_qiqing = True
        if d.qi_qing_shang_fei:
            lines.append("- 七情伤肺 = True → 疏导悲忧")
            has_qiqing = True
        if d.qi_qing_shang_shen:
            lines.append("- 七情伤肾 = True → 安神定志")
            has_qiqing = True
        if not has_qiqing:
            lines.append("- 无七情内伤 → 保持心情舒畅")
        lines.append("")
        
        # 生活起居推理
        lines.append("**生活起居触发条件：**")
        lines.append("- 基础建议：固定输出（早睡早起）")
        for disease in main_diseases:
            if "肾" in disease:
                lines.append(f"- 主病含'{disease}'（肾病）→ 房事节制，腰部保暖")
                break
            if "肺" in disease or "痰" in disease:
                lines.append(f"- 主病含'{disease}'（肺病）→ 戴口罩，避风粉尘")
                break
            if "脾" in disease or "胃" in disease:
                lines.append(f"- 主病含'{disease}'（脾胃病）→ 细嚼慢咽")
                break
            if "肝" in disease:
                lines.append(f"- 主病含'{disease}'（肝病）→ 泡脚放松")
                break
            if "心" in disease:
                lines.append(f"- 主病含'{disease}'（心病）→ 午觉，避刺激")
                break
        
        return lines
    
    def _find_trigger_disease_item(self, disease: str) -> Optional['DiseaseItem']:
        """找到触发指定主病的 disease_item（优先级最高、时序最早的那条）"""
        # 病名 → 对应的脏腑关键词
        # 与基础诊断函数(diagnose_zang_fu_single等)中的关键词保持一致
        # ==================== 基础关键词（复用全局常量） ====================
        # 脏腑定位关键词
        shen_kw = ZANGFU_KEYWORDS["肾"]          # 腰膝酸软、耳鸣、遗精、阳痿、脱发、五更泻
        fei_kw = ZANGFU_KEYWORDS["肺"]           # 咳嗽、气喘、咳痰、胸痛
        gan_kw = ZANGFU_KEYWORDS["肝胆"]         # 两胁胀痛、胁痛、口苦、头晕、易怒、乳房胀痛
        pi_kw = ZANGFU_KEYWORDS["脾"]            # 纳差、饭后腹胀、便溏、身体沉重、身重
        wei_kw = ZANGFU_KEYWORDS["胃"]           # 胃痛、胃疼、胃巨疼、呕吐、反酸、烧心、胃冷痛
        xin_kw = ZANGFU_KEYWORDS["心"]           # 心慌、心悸、胸闷、失眠、多梦
        da_chang_kw = ZANGFU_KEYWORDS["大肠"]    # 便秘、腹泻、拉肚子
        pang_guang_kw = ZANGFU_KEYWORDS["膀胱"] # 尿频、尿急、尿痛
        
        # 八纲辨证关键词
        han_kw = BAGANG_KEYWORDS["寒证"]         # 恶寒、热敷缓解、面色发白、冷痛、苔白、苔湿
        re_kw = BAGANG_KEYWORDS["热证"]          # 发热、口干、想喝水、渴、舌红、面色发红、冷有帮助
        xu_kw = BAGANG_KEYWORDS["虚证"]          # 疼痛感弱、不痛苦、感受不明显、没力气、缺乏精力、先天不足、经常生病、身体素质不好、喜按
        shi_kw = BAGANG_KEYWORDS["实证"]         # 疼痛感强、严重、感受明显、实性病变、硬块、硬结、疙瘩、硬团、一碰就疼、很涨、很鼓、按压很疼、按压疼、胀得鼓鼓
        biao_kw = BAGANG_KEYWORDS["表证"]        # 恶寒、怕冷
        yin_xu_kw = BAGANG_KEYWORDS["阴虚"] # 两颧潮红、五心烦热、潮热、盗汗
        
        # 气血津液关键词
        qi_xu_kw = ZHENG_KEYWORDS["气虚证"]      # 懒言、自汗、呼吸短促、疲劳感在休息后无法缓解
        qi_zhi_kw = ZHENG_KEYWORDS["气滞证"]     # [胀痛/胀满]、[游走性疼痛]、[生气加重/情绪加重]
        xue_xu_kw = ZHENG_KEYWORDS["血虚证"]     # [面色发白/面色暗黄]、[舌体白/舌白]、[头晕眼花/视力模糊]、[月经量少/颜色淡/闭经]
        xue_yu_kw = ZHENG_KEYWORDS["血瘀证"]     # 刺痛、像针扎、固定不移、夜间加重、面色晦暗、瘀斑、瘀点、舌紫暗、黑血块
        xue_re_kw = ZHENG_KEYWORDS["血热证"]     # [流鼻血/吐血/尿血]、[舌红绛/芒刺]、[红色斑/红疹]、[月经提前且量多/月经提前且颜色鲜红]
        xue_han_kw = ZHENG_KEYWORDS["血寒证"]    # 少腹疼痛、月经延后、色暗有血块、痛经、热敷缓解、热敷能缓解
        jin_ye_kw = ZHENG_KEYWORDS["津液不足"]   # 口渴、喜欢喝水、皮肤干燥、起皮、尿少、便干、大便干燥
        
        # 六淫关键词（来自diagnose_liu_yin_single）
        feng_yin_kw = ["讨厌吹风", "皮肤瘙痒", "麻木", "游走性疼痛", "浮肿"]
        han_yin_kw = ["恶寒", "疼痛", "痛", "冷痛", "胀痛", "刺痛", "舌苔白", "苔白"]
        shi_yin_kw = ["水肿", "身体很重", "身体沉重", "拉肚子", "腹泻", "小腹涨", "小腹鼓", "舌苔腻", "很困", "睡不醒"]
        shu_yin_kw = ["发热", "发烧", "高热", "恶心", "呕吐", "想吐", "疲乏", "乏力", "胸闷"]
        zao_yin_kw = ["干咳", "皮肤干", "口干", "鼻干", "咽喉干", "嘴唇干"]
        huo_yin_kw = ["发热", "口渴", "面红", "疮", "胸部灼热", "腹部灼热", "便秘", "尿黄"]
        
        # 七情关键词（来自diagnose_qi_qing_single）
        # 情志词
        qi_qing_gan_kw = ["气炸了", "气死", "暴怒", "生气", "愤怒", "发火"]  # 怒伤肝
        qi_qing_xin_kw = ["狂喜", "乐极生悲", "吓破胆", "惊恐", "吓死", "惊吓"]  # 喜/惊伤心
        qi_qing_pi_kw = ["想太多", "忧思过度", "操心过度"]  # 思伤脾
        qi_qing_fei_kw = ["崩溃", "绝望", "痛哭", "嚎啕大哭", "流泪不止"]  # 悲伤肺
        qi_qing_shen_kw = ["害怕", "恐惧"]  # 恐伤肾
        # 七情对应脏腑定位（来自diagnose_qi_qing_single organ_keywords）
        qi_qing_gan_organ = ["两胁", "肋骨", "胁痛", "胀痛", "易怒", "目赤", "头痛", "眩晕"]
        qi_qing_xin_organ = ["心悸", "失眠", "多梦", "胸闷", "心慌", "心烦", "健忘"]
        qi_qing_pi_organ = ["纳差", "食欲不振", "腹胀", "腹泻", "便溏", "身重"]
        qi_qing_fei_organ = ["咳嗽", "气喘", "胸闷", "气短", "呼吸", "干咳"]
        qi_qing_shen_organ = ["腰膝酸软", "耳鸣", "尿频", "腰痛", "腰酸"]
        
        # 危证关键词（来自diagnose_critical_single）
        wang_yang_kw = ["大汗淋漓", "冷汗", "四肢冰凉", "手脚冰凉", "肢体厥冷", "面色惨白", "面色苍白", "面色发白"]
        wang_yin_kw = ["恶寒", "发热", "两颧潮红", "渴喜冷饮"]
        qi_tuo_kw = ["精神萎靡", "瞳孔散大", "手撒", "大便失禁", "小便失禁"]
        
        # ==================== 病名 → 关键词组合（脏腑定位 + 病性关键词） ====================
        disease_keywords = {
            # ==================== 肾相关 ====================
            # 肾阳虚 = 肾定位 + 寒证 + 虚证（阳虚 = 寒+虚）
            "肾阳虚": shen_kw + han_kw + xu_kw,
            # 肾阴虚 = 肾定位 + 阴虚特征
            "肾阴虚": shen_kw + yin_xu_kw,
            # 肾不纳气 = 肾定位 + 气虚
            "肾不纳气": shen_kw + qi_xu_kw,
            
            # ==================== 肺相关 ====================
            # 痰热壅肺 = 肺定位 + 热证
            "痰热壅肺": fei_kw + re_kw,
            # 肺阴虚 = 肺定位 + 阴虚特征
            "肺阴虚": fei_kw + yin_xu_kw,
            # 肺气虚 = 肺定位 + 气虚
            "肺气虚": fei_kw + qi_xu_kw,
            # 寒痰阻肺 = 肺定位 + 寒证
            "寒痰阻肺": fei_kw + han_kw,
            
            # ==================== 肝胆相关 ====================
            # 肝火上炎 = 肝定位 + 热证/火淫
            "肝火上炎": gan_kw + re_kw + huo_yin_kw,
            # 肝气郁结 = 肝定位 + 气滞
            "肝气郁结": gan_kw + qi_zhi_kw,
            # 肝血虚 = 肝定位 + 血虚
            "肝血虚": gan_kw + xue_xu_kw,
            # 肝阳上亢 = 肝定位 + 热证/阴虚（阳亢）
            "肝阳上亢": gan_kw + re_kw + yin_xu_kw,
            # 肝胆湿热 = 肝定位 + 湿淫 + 热证
            "肝胆湿热": gan_kw + shi_yin_kw + re_kw,
            
            # ==================== 脾胃相关 ====================
            # 脾气虚 = 脾定位 + 气虚
            "脾气虚": pi_kw + qi_xu_kw,
            # 脾阳虚 = 脾定位 + 寒证 + 虚证（阳虚 = 寒+虚）
            "脾阳虚": pi_kw + han_kw + xu_kw,
            # 脾虚湿困 = 脾定位 + 湿淫
            "脾虚湿困": pi_kw + shi_yin_kw,
            # 脾胃虚寒 = 脾定位 + 胃定位 + 寒证 + 虚证
            # "脾胃虚寒": pi_kw + wei_kw + han_kw + xu_kw,
            # 食滞胃脘 = 胃定位
            "食滞胃脘": wei_kw,
            # 胃火炽盛 = 胃定位 + 热证
            "胃火炽盛": wei_kw + re_kw,
            # 胃寒证 = 胃定位 + 寒证
            "胃寒证": wei_kw + han_kw,
            # 胃气上逆 = 胃定位
            "胃气上逆": wei_kw,
            # 虚劳里急 = 胃定位 + 虚证
            "虚劳里急": wei_kw + xu_kw,
            
            # ==================== 心相关 ====================
            # 心气虚 = 心定位 + 气虚
            "心气虚": xin_kw + qi_xu_kw,
            # 心血虚 = 心定位 + 血虚
            "心血虚": xin_kw + xue_xu_kw,
            # 心阴虚 = 心定位 + 阴虚特征
            "心阴虚": xin_kw + yin_xu_kw,
            # 心阳虚 = 心定位 + 寒证 + 虚证（阳虚 = 寒+虚）
            "心阳虚": xin_kw + han_kw + xu_kw,
            # 心脉痹阻 = 心定位 + 血瘀
            "心脉痹阻": xin_kw + xue_yu_kw,
            # 心火亢盛 = 心定位 + 热证
            "心火亢盛": xin_kw + re_kw,
            # 心火下移小肠（特殊，仅舌尖痛）
            "心火下移小肠": ["舌尖痛"],
            # 心脾两虚 = 心定位 + 脾定位 + 虚证
            "心脾两虚": xin_kw + pi_kw + xu_kw,
            
            # ==================== 膀胱大肠相关 ====================
            # 膀胱湿热 = 膀胱定位 + 湿淫 + 热证
            "膀胱湿热": pang_guang_kw + shi_yin_kw + re_kw,
            # 大肠湿热 = 大肠定位 + 湿淫 + 热证
            "大肠湿热": da_chang_kw + shi_yin_kw + re_kw,
            # 大肠虚寒 = 大肠定位 + 寒证 + 虚证
            "大肠虚寒": da_chang_kw + han_kw + xu_kw,
            
            # ==================== 八纲证 ====================
            "表寒证": biao_kw + han_kw,
            "表热证": biao_kw + re_kw,
            "里寒证": han_kw,
            "里热证": re_kw,
            "阴虚证": yin_xu_kw,
            "阳虚证": han_kw + xu_kw,
            "实热证": shi_kw + re_kw,
            
            # ==================== 危证 ====================
            "亡阳证": wang_yang_kw + han_kw,
            "亡阴证": wang_yin_kw + re_kw,
            "气脱证": qi_tuo_kw + qi_xu_kw,
            
            # ==================== 六淫 ====================
            "风淫证": feng_yin_kw,
            "寒淫证": han_yin_kw,
            "湿淫证": shi_yin_kw,
            "暑淫证": shu_yin_kw,
            "燥淫证": zao_yin_kw,
            "火淫证": huo_yin_kw,
            
            # ==================== 七情 ====================
            # 七情伤X = 情志词 + 对应脏腑定位
            "七情伤肝": qi_qing_gan_kw + qi_qing_gan_organ,
            "七情伤心": qi_qing_xin_kw + qi_qing_xin_organ,
            "七情伤脾": qi_qing_pi_kw + qi_qing_pi_organ,
            "七情伤肺": qi_qing_fei_kw + qi_qing_fei_organ,
            "七情伤肾": qi_qing_shen_kw + qi_qing_shen_organ,
            
            # ==================== 气血津液 ====================
            "气虚证": qi_xu_kw,
            "气滞证": qi_zhi_kw,
            "血虚证": xue_xu_kw,
            "气血两虚": qi_xu_kw + xue_xu_kw,
            "血瘀证": xue_yu_kw,
            "血热证": xue_re_kw + re_kw,
            "血寒证": xue_han_kw + han_kw,
            "津液不足": jin_ye_kw,
        }
        keywords = disease_keywords.get(disease, [])
        
        keywords = [word for keyword in keywords for word in (keyword if isinstance(keyword, list) else [keyword])]
        best = None
        best_s2 = 999
        best_order = 999
        for di in self.engine.disease_items:
            if di.severity_label in EXCLUDED_LABELS:
                continue
            
            if not any(kw in di.text for kw in keywords):
                continue
            s2 = self.engine._get_adjective_tier(di.severity_label)
            if s2 < best_s2 or (s2 == best_s2 and di.time_order < best_order):
                best = di
                best_s2 = s2
                best_order = di.time_order
        return best
    
    def _build_disease_chain(self, disease: str) -> str:
        """为指定主病生成链式推导文本
        
        格式示例：
          肾阳虚："腰膝酸软"→肾定位，"怕冷"→恶寒→寒证，"五年前"→超过三个月→虚证，肾定位+寒证+虚证→肾阳虚
          痰热壅肺："咳黄痰"→肺定位，"痰非常稠"→热证，肺定位+热证→痰热壅肺
        """
        d = self.engine.diagnosis
        parts = []  # 推导链各节点
        
        # 找到触发该主病的 disease_item
        trigger_di = self._find_trigger_disease_item(disease)
        text = trigger_di.text if trigger_di else ''
        # time_str = trigger_di.time if trigger_di else None
        
        if disease in ("肾阳虚", "肾阴虚"):
            # 从诊断依据中获取肾部症状
            basis_list = self._get_diagnosis_basis_for_disease(disease)
            if basis_list:
                raw = basis_list[0]
                if "肾部症状：" in raw:
                    symptoms_part = raw.split("肾部症状：")[1].split(" + ")[0]
                    symptom_list = [s.strip() for s in symptoms_part.split(',') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f"{kw_str}→肾定位")
            
            # 2. 定性：寒/热（从全局诊断依据获取）
            if disease == "肾阳虚":
                han_basis = self._get_diagnosis_basis_for_disease("寒证")
                if han_basis:
                    raw = han_basis[0]
                    if "：" in raw:
                        symptoms_str = raw.split("：", 1)[1]
                        symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                        if symptom_list:
                            kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                            parts.append(f"{kw_str}→恶寒→寒证")
                elif d.han_zheng:
                    parts.append("寒证（全局）")
            else:  # 肾阴虚
                re_basis = self._get_diagnosis_basis_for_disease("热证")
                if re_basis:
                    raw = re_basis[0]
                    if "：" in raw:
                        symptoms_str = raw.split("：", 1)[1]
                        symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                        if symptom_list:
                            kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                            parts.append(f"{kw_str}→热证")
                elif d.re_zheng:
                    parts.append("热证（全局）")
            
            # 3. 定性：虚（从全局诊断依据获取）
            xu_basis = self._get_diagnosis_basis_for_disease("虚证")
            if xu_basis:
                raw = xu_basis[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:1])
                        parts.append(f"{kw_str}→虚证")
            elif d.xu_zheng:
                parts.append("虚证（全局）")
            
            # 4. 组合结论
            if disease == "肾阳虚":
                parts.append("肾定位+寒证+虚证→阳虚→肾阳虚")
                if d.shen_severity == SeverityLevel.SEVERE:
                    basis_list = self._get_diagnosis_basis_for_disease("肾阳虚（重症）")
                    if basis_list:
                        parts.append(basis_list[0])
            else:
                parts.append("肾定位+热证+虚证→阴虚→肾阴虚")
        
        elif disease == "痰热壅肺":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("痰热壅肺")
            for basis in basis_list:
                if basis.startswith("肺定位："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f"{kw_str}→肺定位")
                elif basis.startswith("痰热特征："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f"{kw_str}→痰热特征")
                elif basis == "热证（全局）":
                    parts.append("热证（全局）")
                elif basis.startswith("判断路径："):
                    parts.append(basis.split("：", 1)[1])
        
        elif disease == "肺阴虚":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("肺阴虚")
            for basis in basis_list:
                if basis.startswith("肺定位："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f"{kw_str}→肺定位")
                elif basis.startswith("阴虚特征："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f"{kw_str}→阴虚特征")
                elif basis == "阴虚（全局）":
                    parts.append("阴虚（全局）")
                elif basis.startswith("判断路径："):
                    parts.append(basis.split("：", 1)[1])
        
        elif disease == "肝火上炎":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("肝火上炎")
            for basis in basis_list:
                if basis.startswith("肝胆定位："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f"{kw_str}→肝胆定位")
                elif basis.startswith("火热特征："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f"{kw_str}→火热特征")
                elif basis == "火淫证（全局）":
                    parts.append("火淫证（全局）")
                elif basis.startswith("判断路径："):
                    parts.append(basis.split("：", 1)[1])
        
        elif disease == "食滞胃脘":
            basis_list = self._get_diagnosis_basis_for_disease("食滞胃脘")
            if basis_list:
                raw = basis_list[0]
                if "胃部症状：" in raw:
                    symptoms_part = raw.split("胃部症状：")[1].split(" + ")[0]
                    symptom_list = [s.strip() for s in symptoms_part.split(',') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f"{kw_str}→胃定位")
            parts.append("胃定位+舌苔厚腻+(纳差/食积/腹胀)→食滞胃脘")
        
        elif disease == "表寒证":
            basis_list = self._get_diagnosis_basis_for_disease("寒证")
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f"{kw_str}→寒证")
            parts.append("表证+寒证→表寒证")
        
        elif disease == "表热证":
            basis_list = self._get_diagnosis_basis_for_disease("热证")
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f"{kw_str}→热证")
            parts.append("表证+热证→表热证")
        
        elif disease == "里寒证":
            basis_list = self._get_diagnosis_basis_for_disease("寒证")
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f"{kw_str}→寒证")
            parts.append("里证+寒证→里寒证")
        
        elif disease == "里热证":
            basis_list = self._get_diagnosis_basis_for_disease("热证")
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f"{kw_str}→热证")
            parts.append("里证+热证→里热证")
        
        elif disease == "实热证":
            parts.append("实证+热证→实热证")
        
        elif disease == "亡阳证":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("亡阳证")
            for basis in basis_list:
                if basis.startswith("冷汗症状："):
                    symptom = basis.split("：", 1)[1]
                    parts.append(f'"{symptom}"→冷汗/大汗淋漓')
                elif basis.startswith("四肢冰凉："):
                    symptom = basis.split("：", 1)[1]
                    parts.append(f'"{symptom}"→四肢冰凉')
                elif basis.startswith("面色惨白："):
                    symptom = basis.split("：", 1)[1]
                    parts.append(f'"{symptom}"→面色惨白')
                elif basis == "前提：已有寒证":
                    parts.append("寒证（全局）")
            parts.append("寒证+冷汗+四肢冰凉+面色惨白→亡阳证")
        
        elif disease == "亡阴证":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("亡阴证")
            for basis in basis_list:
                if basis == "大汗":
                    parts.append('"大汗"→大汗淋漓')
                elif basis.startswith("热汗/油汗："):
                    symptom = basis.split("：", 1)[1]
                    parts.append(f'"{symptom}"→热汗/油汗')
                elif basis.startswith("渴喜冷饮："):
                    symptom = basis.split("：", 1)[1]
                    parts.append(f'"{symptom}"→渴喜冷饮')
                elif basis == "前提：已有热证":
                    parts.append("热证（全局）")
            parts.append("热证+大汗+热汗/油汗+渴喜冷饮→亡阴证")
        
        elif disease == "气脱证":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("气脱证")
            qi_tuo_symptoms = []
            has_qi_xu = False
            for basis in basis_list:
                if basis.startswith("气脱症状："):
                    symptom = basis.split("：", 1)[1]
                    qi_tuo_symptoms.append(symptom)
                elif basis == "前提：已有气虚证":
                    has_qi_xu = True
            if qi_tuo_symptoms:
                kw_str = '、'.join(f'"{s}"' for s in qi_tuo_symptoms[:3])
                parts.append(f'{kw_str}→气脱症状')
            if has_qi_xu:
                parts.append("气虚证（全局）")
                parts.append("气虚证+气脱症状→气脱证")
            else:
                parts.append("气脱症状≥2个→气脱证")
        
        # ===== 六淫证 =====
        elif disease == "燥淫证":
            # 从 diagnosis_basis 中提取实际触发的症状
            basis_list = self._get_diagnosis_basis_for_disease("燥淫证")
            # basis_list[0] 形如 "燥邪症状：干咳, 鼻干, 咽喉干"
            zao_symptoms_str = ""
            if basis_list:
                raw = basis_list[0]  # e.g. "燥邪症状：干咳, 鼻干, 咽喉干"
                if "：" in raw:
                    zao_symptoms_str = raw.split("：", 1)[1]
            
            # 判断是否是秋季干咳触发
            is_autumn_dry_cough = False
            if trigger_di and trigger_di.text:
                if "干咳" in trigger_di.text and self.engine.season == '秋季':
                    is_autumn_dry_cough = True
            
            if zao_symptoms_str:
                symptom_list = [s.strip() for s in zao_symptoms_str.split(',') if s.strip()]
                kw_str = '、'.join(f'"{s}"' for s in symptom_list[:3])
                if is_autumn_dry_cough:
                    parts.append(f'季节：秋季')
                    parts.append(f'{kw_str}→燥邪症状')
                    parts.append('秋季+燥邪症状→燥淫证')
                else:
                    parts.append(f'{kw_str}→燥邪症状（皮肤/口/鼻/咽喉干燥，不限季节）')
                    parts.append('燥邪症状→燥淫证')
            else:
                parts.append('燥邪症状→燥淫证')
        
        elif disease == "风淫证":
            basis_list = self._get_diagnosis_basis_for_disease("风淫证")
            feng_symptoms_str = ""
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    feng_symptoms_str = raw.split("：", 1)[1]
            if feng_symptoms_str:
                symptom_list = [s.strip() for s in feng_symptoms_str.split(',') if s.strip()]
                kw_str = '、'.join(f'"{s}"' for s in symptom_list[:3])
                parts.append(f'{kw_str}→风邪症状（游走性/瘙痒/恶风）')
                parts.append('风邪症状→风淫证')
            else:
                parts.append('风邪症状→风淫证')
        
        elif disease == "湿淫证":
            basis_list = self._get_diagnosis_basis_for_disease("湿淫证")
            shi_symptoms_str = ""
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    shi_symptoms_str = raw.split("：", 1)[1]
            if shi_symptoms_str:
                symptom_list = [s.strip() for s in shi_symptoms_str.split(',') if s.strip()]
                kw_str = '、'.join(f'"{s}"' for s in symptom_list[:3])
                parts.append(f'{kw_str}→湿邪症状（水肿/身重/苔腻）')
                parts.append('湿邪症状→湿淫证')
            else:
                parts.append('湿邪症状→湿淫证')
        
        elif disease == "寒淫证":
            basis_list = self._get_diagnosis_basis_for_disease("寒淫证")
            han_symptoms_str = ""
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    han_symptoms_str = raw.split("：", 1)[1]
            if han_symptoms_str:
                symptom_list = [s.strip() for s in han_symptoms_str.split(',') if s.strip()]
                kw_str = '、'.join(f'"{s}"' for s in symptom_list[:3])
                parts.append(f'{kw_str}→寒邪症状（恶寒/疼痛/苔白）')
                parts.append('寒邪症状→寒淫证')
            else:
                parts.append('寒邪症状→寒淫证')
        
        elif disease == "暑淫证":
            basis_list = self._get_diagnosis_basis_for_disease("暑淫证")
            shu_symptoms_str = ""
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    shu_symptoms_str = raw.split("：", 1)[1]
            if shu_symptoms_str:
                symptom_list = [s.strip() for s in shu_symptoms_str.split(',') if s.strip()]
                kw_str = '、'.join(f'"{s}"' for s in symptom_list[:3])
                parts.append(f'季节：夏季')
                parts.append(f'{kw_str}→暑邪症状（满足≥2点）')
                parts.append('夏季+暑邪症状→暑淫证')
            else:
                parts.append('夏季+暑邪症状→暑淫证')
        
        elif disease == "火淫证":
            basis_list = self._get_diagnosis_basis_for_disease("火淫证")
            huo_symptoms_str = ""
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    huo_symptoms_str = raw.split("：", 1)[1]
            if huo_symptoms_str:
                symptom_list = [s.strip() for s in huo_symptoms_str.split(',') if s.strip()]
                kw_str = '、'.join(f'"{s}"' for s in symptom_list[:3])
                parts.append(f'{kw_str}→火邪症状（满足≥2点）')
                parts.append('火邪症状→火淫证')
            else:
                parts.append('火邪症状→火淫证')
        
        # ===== 七情内伤 =====
        elif disease in ("七情伤肝", "七情伤心", "七情伤肾", "七情伤肺", "七情伤脾"):
            basis_list = self._get_diagnosis_basis_for_disease(disease)
            # basis_list[0] 形如 "怒伤肝：气炸了 → 两胁, 肋骨, 胀痛"
            if basis_list:
                raw = basis_list[0]
                # 解析格式："{情志类型}：{情志词} → {症状}"
                if "：" in raw and "→" in raw:
                    type_part, rest = raw.split("：", 1)
                    emotion_word, symptom_part = rest.split("→", 1)
                    emotion_word = emotion_word.strip()
                    symptom_part = symptom_part.strip()
                    symptoms = [s.strip() for s in symptom_part.split(',') if s.strip()]
                    
                    # 根据病名确定定位和情志类型
                    if disease == "七情伤肝":
                        loc_kws = '、'.join(f'"{s}"' for s in symptoms[:2])
                        parts.append(f'"{emotion_word}"→怒伤肝（怒→肝定位）')
                        if symptoms:
                            parts.append(f'{loc_kws}→肝胆定位症状')
                        parts.append('怒+肝胆定位症状+因果关系→七情伤肝')
                    elif disease == "七情伤心":
                        loc_kws = '、'.join(f'"{s}"' for s in symptoms[:2])
                        parts.append(f'"{emotion_word}"→{type_part}（喜/惊→心定位）')
                        if symptoms:
                            parts.append(f'{loc_kws}→心定位症状')
                        parts.append('喜/惊+心定位症状+因果关系→七情伤心')
                    elif disease == "七情伤肾":
                        loc_kws = '、'.join(f'"{s}"' for s in symptoms[:2])
                        parts.append(f'"{emotion_word}"→恐伤肾（恐→肾定位）')
                        if symptoms:
                            parts.append(f'{loc_kws}→肾定位症状')
                        parts.append('恐+肾定位症状+因果关系→七情伤肾')
                    elif disease == "七情伤肺":
                        loc_kws = '、'.join(f'"{s}"' for s in symptoms[:2])
                        parts.append(f'"{emotion_word}"→悲/忧伤肺（悲/忧→肺定位）')
                        if symptoms:
                            parts.append(f'{loc_kws}→肺定位症状')
                        parts.append('悲/忧+肺定位症状+因果关系→七情伤肺')
                    elif disease == "七情伤脾":
                        loc_kws = '、'.join(f'"{s}"' for s in symptoms[:2])
                        parts.append(f'"{emotion_word}"→思伤脾（思→脾定位）')
                        if symptoms:
                            parts.append(f'{loc_kws}→脾胃定位症状')
                        parts.append('思+脾胃定位症状+因果关系→七情伤脾')
                else:
                    # 格式不符合预期，直接用原始依据
                    parts.append(raw)
            else:
                parts.append(f'{disease}：满足情志+脏腑症状+因果关系条件')
        
        # ===== 气血津液 =====
        elif disease == "气虚证":
            basis_list = self._get_diagnosis_basis_for_disease("气虚")
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→气虚症状（满足≥2点）')
            parts.append('虚证+气虚症状→气虚证')
        
        elif disease == "气滞证":
            basis_list = self._get_diagnosis_basis_for_disease("气滞")
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→气滞症状（满足≥2点）')
            parts.append('气滞症状→气滞证')
        
        elif disease == "血虚证":
            basis_list = self._get_diagnosis_basis_for_disease("血虚")
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→血虚症状（满足≥2点）')
            parts.append('虚证+血虚症状→血虚证')
        
        elif disease == "气血两虚":
            basis_list = self._get_diagnosis_basis_for_disease("气血两虚")
            if basis_list:
                parts.append(basis_list[0])
            else:
                parts.append('气虚证+血虚证同时成立→气血两虚')
        
        elif disease == "血瘀证":
            basis_list = self._get_diagnosis_basis_for_disease("血瘀")
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→血瘀症状（满足≥2点）')
            parts.append('血瘀症状→血瘀证')
        
        elif disease == "血热证":
            basis_list = self._get_diagnosis_basis_for_disease("血热证")
            if basis_list:
                raw = basis_list[0]
                if "：" in raw or "+" in raw:
                    parts.append(raw)
                else:
                    parts.append(f'{raw}→血热症状')
            parts.append('热证+血热症状→血热证')
        
        elif disease == "血寒证":
            basis_list = self._get_diagnosis_basis_for_disease("血寒")
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→血寒症状')
            parts.append('寒证+血寒症状→血寒证')
        
        elif disease == "津液不足":
            basis_list = self._get_diagnosis_basis_for_disease("津液不足")
            # print('jinye', basis_list)
            if basis_list:
                raw = basis_list[0]
                if "：" in raw:
                    symptoms_str = raw.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms_str.split('、') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→津液不足症状（满足≥2点）')
            parts.append('津液不足症状→津液不足')
        
        # ===== 脏腑辨证 - 心 =====
        elif disease == "心气虚":
            basis_list = self._get_diagnosis_basis_for_disease("心气虚")
            if basis_list:
                raw = basis_list[0]
                if "心部症状：" in raw:
                    symptoms_part = raw.split("心部症状：")[1].split(" + ")[0]
                    symptom_list = [s.strip() for s in symptoms_part.split(',') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→心定位')
            parts.append('气虚证（懒言/自汗/疲劳≥2点）')
            parts.append('心定位+气虚→心气虚')
        
        elif disease == "心血虚":
            basis_list = self._get_diagnosis_basis_for_disease("心血虚")
            if basis_list:
                raw = basis_list[0]
                if "心部症状：" in raw:
                    symptoms_part = raw.split("心部症状：")[1].split(" + ")[0]
                    symptom_list = [s.strip() for s in symptoms_part.split(',') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→心定位')
            parts.append('血虚证（面色发白/头晕眼花≥2点）')
            parts.append('心定位+血虚→心血虚')
        
        elif disease == "心阴虚":
            basis_list = self._get_diagnosis_basis_for_disease("心阴虚")
            if basis_list:
                raw = basis_list[0]
                if "心部症状：" in raw:
                    symptoms_part = raw.split("心部症状：")[1].split(" + ")[0]
                    symptom_list = [s.strip() for s in symptoms_part.split(',') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→心定位')
            parts.append('热证+虚证→阴虚')
            parts.append('心定位+阴虚→心阴虚')
        
        elif disease == "心阳虚":
            basis_list = self._get_diagnosis_basis_for_disease("心阳虚")
            if basis_list:
                raw = basis_list[0]
                if "心部症状：" in raw:
                    symptoms_part = raw.split("心部症状：")[1].split(" + ")[0]
                    symptom_list = [s.strip() for s in symptoms_part.split(',') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→心定位')
            parts.append('寒证+虚证→阳虚')
            parts.append('心定位+阳虚→心阳虚')
        
        elif disease == "心脉痹阻":
            basis_list = self._get_diagnosis_basis_for_disease("心脉痹阻")
            if basis_list:
                raw = basis_list[0]
                if "心部症状：" in raw:
                    symptoms_part = raw.split("心部症状：")[1].split(" + ")[0]
                    symptom_list = [s.strip() for s in symptoms_part.split(',') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→心定位')
            parts.append('血瘀证（刺痛/固定不移/舌紫暗≥2点）')
            parts.append('心定位+血瘀→心脉痹阻')
        
        elif disease == "心火亢盛":
            basis_list = self._get_diagnosis_basis_for_disease("心火亢盛")
            if basis_list:
                raw = basis_list[0]
                if "心部症状：" in raw:
                    symptoms_part = raw.split("心部症状：")[1].split(" + ")[0]
                    symptom_list = [s.strip() for s in symptoms_part.split(',') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→心定位')
            parts.append('热证+失眠/口疮→心火亢盛')
        
        elif disease == "心火下移小肠":
            basis_list = self._get_diagnosis_basis_for_disease("心火下移小肠")
            if basis_list:
                parts.append(f'"{basis_list[0]}"→心火下移小肠（舌尖属心，痛提示心火下移）')
            else:
                parts.append('"舌尖痛"→心火下移小肠（舌尖属心，痛提示心火下移）')
        
        elif disease == "心脾两虚":
            basis_list = self._get_diagnosis_basis_for_disease("心脾两虚")
            if basis_list:
                raw = basis_list[0]
                parts.append(f'诊断依据：{raw}')
            else:
                xin_kws = ["失眠", "睡不着", "心慌", "心悸"]
                matched = self.engine.match_keywords(text, xin_kws)
                if matched:
                    kw_str = '、'.join(f'"{kw}"' for kw in matched[:2])
                    parts.append(f'{kw_str}→心脾定位')
            parts.append('气血两虚证（气虚+血虚同时成立）')
            parts.append('失眠+气血两虚→心脾两虚')
        
        # ===== 脏腑辨证 - 肺 =====
        elif disease == "肺气虚":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("肺气虚")
            for basis in basis_list:
                if basis.startswith("肺定位："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f'{kw_str}→肺定位')
                elif basis == "气虚（全局）":
                    parts.append("气虚（全局）")
                elif basis.startswith("判断路径："):
                    parts.append(basis.split("：", 1)[1])
        
        elif disease == "寒痰阻肺":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("寒痰阻肺")
            for basis in basis_list:
                if basis.startswith("肺定位："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f'{kw_str}→肺定位')
                elif basis.startswith("寒痰特征："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f'{kw_str}→寒痰特征')
                elif basis == "寒证（全局）":
                    parts.append("寒证（全局）")
                elif basis.startswith("判断路径："):
                    parts.append(basis.split("：", 1)[1])
        
        # ===== 脏腑辨证 - 脾胃 =====
        elif disease == "脾气虚":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("脾气虚")
            for basis in basis_list:
                if basis.startswith("脾定位："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f'{kw_str}→脾定位')
                elif basis == "气虚（全局）":
                    parts.append("气虚（全局）")
                elif basis.startswith("判断路径："):
                    parts.append(basis.split("：", 1)[1])
        
        elif disease == "脾阳虚":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("脾阳虚")
            for basis in basis_list:
                if basis.startswith("脾定位："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f'{kw_str}→脾定位')
                elif basis == "阳虚（全局）":
                    parts.append("阳虚（全局）")
                elif basis.startswith("判断路径："):
                    parts.append(basis.split("：", 1)[1])
        
        elif disease == "脾虚湿困":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("脾虚湿困")
            for basis in basis_list:
                if basis.startswith("脾定位："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f'{kw_str}→脾定位')
                elif basis == "湿淫证（全局）":
                    parts.append("湿淫证（全局）")
                elif basis.startswith("判断路径："):
                    parts.append(basis.split("：", 1)[1])
        
        elif disease == "胃火炽盛":
            basis_list = self._get_diagnosis_basis_for_disease("胃火炽盛")
            if basis_list:
                raw = basis_list[0]
                if "胃部症状：" in raw:
                    symptoms_part = raw.split("胃部症状：")[1].split(" + ")[0]
                    symptom_list = [s.strip() for s in symptoms_part.split(',') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→胃定位')
            parts.append('胃定位+口臭/牙龈肿→胃火炽盛')
        
        elif disease == "胃寒证":
            basis_list = self._get_diagnosis_basis_for_disease("胃寒证")
            if basis_list:
                raw = basis_list[0]
                if "胃部症状：" in raw:
                    symptoms_part = raw.split("胃部症状：")[1]
                    parts.append(f'"{symptoms_part}"→胃定位+寒证')
                else:
                    parts.append(f'"{raw}"→胃定位+寒证')
            else:
                parts.append('"胃冷痛"→胃定位+寒证')
            parts.append('胃定位+寒证→胃寒证')
        
        elif disease == "胃气上逆":
            # 使用实际诊断依据
            basis_list = self._get_diagnosis_basis_for_disease("胃气上逆")
            if basis_list:
                parts.append(f'诊断依据：{basis_list[0]}')
                parts.append('胃定位+干呕/呃逆+肺阴虚→胃气上逆')
            else:
                wei_kws = ["干呕", "打噗", "呃逆", "频繁打噗"]
                matched = self.engine.match_keywords(text, wei_kws)
                if matched:
                    kw_str = '、'.join(f'"{kw}"' for kw in matched[:2])
                    parts.append(f'{kw_str}→胃气上逆症状')
                parts.append('肺阴虚（干咳/无痰）')
                parts.append('胃定位+干呕/呃逆+肺阴虚→胃气上逆')
        
        elif disease == "虚劳里急":
            # 使用实际诊断依据
            basis_list = self._get_diagnosis_basis_for_disease("虚劳里急")
            if basis_list:
                parts.append(f'诊断依据：{basis_list[0]}')
                parts.append('腹痛+喜按+气血两虚→虚劳里急')
            else:
                parts.append('"腹痛"→里急定位')
                parts.append('"喜按/压着好"→虚证特征')
                parts.append('气血两虚证')
                parts.append('腹痛+喜按+气血两虚→虚劳里急')
        
        # ===== 脏腑辨证 - 肝胆 =====
        elif disease == "肝气郁结":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("肝气郁结")
            for basis in basis_list:
                if basis.startswith("肝胆定位："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f'{kw_str}→肝胆定位')
                elif basis == "气滞（全局）":
                    parts.append("气滞（全局）")
                elif basis.startswith("判断路径："):
                    parts.append(basis.split("：", 1)[1])
        
        elif disease == "肝血虚":
            # 使用实际诊断依据，而非重新判断
            basis_list = self._get_diagnosis_basis_for_disease("肝血虚")
            if basis_list:
                # basis_list[0] 形如 "肝胆症状 + 眼干/指甲脆"
                parts.append(f'诊断依据：{basis_list[0]}')
                parts.append('肝胆定位+眼干/指甲脆→肝血虚')
            else:
                # 兜底：使用关键词匹配
                gan_kws = ["两胁", "肋骨", "胁痛", "口苦", "头晕", "易怒", "乳房胀痛"]
                matched = self.engine.match_keywords(text, gan_kws)
                if matched:
                    kw_str = '、'.join(f'"{kw}"' for kw in matched[:2])
                    parts.append(f'{kw_str}→肝胆定位')
                xue_xu_kws = ["眼干", "指甲脆", "指甲易断"]
                matched_xue = self.engine.match_keywords(text, xue_xu_kws)
                if matched_xue:
                    kw_str = '、'.join(f'"{kw}"' for kw in matched_xue[:2])
                    parts.append(f'{kw_str}→肝血虚特征')
                parts.append('肝胆定位+眼干/指甲脆→肝血虚')
        
        elif disease == "肝阳上亢":
            # 使用实际诊断依据
            basis_list = self._get_diagnosis_basis_for_disease("肝阳上亢")
            if basis_list:
                parts.append(f'诊断依据：{basis_list[0]}')
                parts.append('头晕/脚轻+阳证→肝阳上亢')
            else:
                gan_kws = ["头晕", "脚轻"]
                matched = self.engine.match_keywords(text, gan_kws)
                if matched:
                    kw_str = '、'.join(f'"{kw}"' for kw in matched[:2])
                    parts.append(f'{kw_str}→肝定位症状')
                parts.append('阳证（表证/热证/实证/阴虚证/亡阴证）')
                parts.append('头晕/脚轻+阳证→肝阳上亢')
        
        elif disease == "肝胆湿热":
            # 直接使用 add_diagnosis_basis 记录的判断依据
            basis_list = self._get_diagnosis_basis_for_disease("肝胆湿热")
            for basis in basis_list:
                if basis.startswith("肝胆定位："):
                    symptoms = basis.split("：", 1)[1]
                    symptom_list = [s.strip() for s in symptoms.split(',') if s.strip()]
                    kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                    parts.append(f'{kw_str}→肝胆定位')
                elif basis.startswith("湿热："):
                    parts.append(basis.split("：", 1)[1])
                elif basis == "湿淫证（全局）":
                    parts.append("湿淫证（全局）")
                elif basis == "热证（全局）":
                    parts.append("热证（全局）")
                elif basis.startswith("判断路径："):
                    parts.append(basis.split("：", 1)[1])
        
        # ===== 脏腑辨证 - 肾膀胱 =====
        elif disease == "肾不纳气":
            basis_list = self._get_diagnosis_basis_for_disease("肾不纳气")
            if basis_list:
                raw = basis_list[0]
                if "肾部症状：" in raw:
                    symptoms_part = raw.split("肾部症状：")[1].split(" + ")[0]
                    symptom_list = [s.strip() for s in symptoms_part.split(',') if s.strip()]
                    if symptom_list:
                        kw_str = '、'.join(f'"{s}"' for s in symptom_list[:2])
                        parts.append(f'{kw_str}→肾定位')
            # parts.append('气虚证+呼多吸少/气短→肾不纳气')
            parts.append('肾定位+气虚/呼多吸少→肾不纳气')
        
        elif disease == "膀胱湿热":
            basis_list = self._get_diagnosis_basis_for_disease("膀胱湿热")
            if basis_list:
                raw = basis_list[0]
                parts.append(f'诊断依据：{raw}')
            parts.append('热证/湿淫证→湿热')
            parts.append('膀胱定位+湿热→膀胱湿热')
        
        # ===== 脏腑辨证 - 大肠 =====
        elif disease == "大肠湿热":
            basis_list = self._get_diagnosis_basis_for_disease("大肠湿热")
            if basis_list:
                raw = basis_list[0]
                parts.append(f'诊断依据：{raw}')
            parts.append('湿淫证+便秘/便臭/肛门灶热→湿热')
            parts.append('大肠定位+湿热→大肠湿热')
        
        elif disease == "大肠虚寒":
            basis_list = self._get_diagnosis_basis_for_disease("大肠虚寒")
            if basis_list:
                raw = basis_list[0]
                parts.append(f'诊断依据：{raw}')
            parts.append('虚证/长期腹泻→虚寒')
            parts.append('大肠定位+虚寒→大肠虚寒')
        
        elif disease == "真热假寒证":
            basis_list = self._get_diagnosis_basis_for_disease("真热假寒证")
            if basis_list:
                parts.append(basis_list[0])
            parts.append('寒热并见→真热假寒证（内有真热，外显假寒）')
        
        elif disease == "真寒假热证":
            basis_list = self._get_diagnosis_basis_for_disease("真寒假热证")
            if basis_list:
                parts.append(basis_list[0])
            parts.append('寒热并见→真寒假热证（内有真寒，外显假热）')
        
        elif disease == "真虚假实证":
            basis_list = self._get_diagnosis_basis_for_disease("真虚假实证")
            if basis_list:
                parts.append(basis_list[0])
            parts.append('虚实并见→真虚假实证（本质为虚，外显假实）')
        
        elif disease == "真实假虚证":
            basis_list = self._get_diagnosis_basis_for_disease("真实假虚证")
            if basis_list:
                parts.append(basis_list[0])
            parts.append('虚实并见→真实假虚证（本质为实，外显假虚）')
        
        else:
            # 兜底：回退到原始依据列表
            basis_list = self._get_diagnosis_basis_for_disease(disease)
            return '；'.join(basis_list) if basis_list else ''
        
        return '，'.join(parts)
    
    def _get_diagnosis_basis_for_disease(self, disease: str) -> List[str]:
        """获取指定疾病的诊断依据"""
        basis = self.engine.diagnosis.diagnosis_basis
        result = []
        
        # 直接匹配
        if disease in basis:
            result.extend(basis[disease])
        
        # 模糊匹配（如"肾阳虚"匹配"肾阳虚（重症）"）
        for key, values in basis.items():
            if disease in key and key != disease:
                result.extend(values)
            elif key in disease and key != disease:
                result.extend(values)
        
        # 特殊映射
        disease_mapping = {
            "亡阳证": ["亡阳证"],
            "亡阴证": ["亡阴证"],
            "气脱证": ["气脱证"],
            "痰热壅肺": ["痰热壅肺"],
            "肾阳虚": ["肾阳虚", "肾阳虚（重症）"],
            "七情伤心": ["七情伤心"],
            "七情伤肾": ["七情伤肾"],
            "湿淫证": ["湿淫证"],
        }
        
        if disease in disease_mapping:
            for mapped_key in disease_mapping[disease]:
                if mapped_key in basis and mapped_key != disease:
                    for v in basis[mapped_key]:
                        if v not in result:
                            result.append(v)
        
        return result
    
    def _get_secondary_diagnoses(self, main_diseases: List[str]) -> List[str]:
        """获取兼证
        
        规则来源：system_prompt_zy.md 第59-63行
        - 所有作为主病候选，但是竞选失败且有药方的病作为兼证进行输出
        - 兼证应该按照Step1~Step4的顺序进行输出
        """
        secondary = []
        main_set = set(main_diseases)
        
        # 从engine获取所有候选（如果有的话）
        all_candidates = getattr(self.engine, 'all_candidates', [])
        
        if all_candidates:
            # 按 S1 -> S2 -> time_order -> manual_order 排序（与主病选取逻辑一致，包含Step 4）
            sorted_candidates = sorted(all_candidates, key=lambda x: (x[1], x[2], x[3], x[4] if len(x) > 4 else 999))
            
            # 竞选失败且有药方的候选词作为兼证（排除主病和没有药方的）
            for candidate in sorted_candidates:
                name = candidate[0]
                if name not in main_set and name not in secondary and name in DISEASES_WITH_FORMULA:
                    secondary.append(name)
        
        return secondary


# ==================== Checklist生成器 ====================

class ChecklistGenerator:
    """检验清单生成器 - 基于诊断书内容自动生成checklist"""
    
    def __init__(self, engine: TCMDiagnosisEngine, report: str):
        self.engine = engine
        self.report = report
    
    def generate_checklist(self, main_diseases: List[str], prescription: Prescription,
                          dietary_advice: List[str], emotion_advice: List[str],
                          lifestyle_advice: List[str], minnan_response: Optional[str],
                          secondary_diagnoses: List[str], is_critical: bool = False) -> str:
        """生成检验清单"""
        checklist_items = []
        item_num = 1
        
        # 1. 诊断书整体结构检查
        # checklist_items.append(f'{item_num}. 模型是否回复了一份诊断书，且包含"患者画像"、"主病"、"方名"、"药材清单"、"饮食忌口"、"情志调节"、"生活起居"这些部分的内容？')
        # item_num += 1
        
        # 2. 危症警告检查（如果是危症）
        if is_critical:
            checklist_items.append(f'{item_num}. 模型回复的诊断书开头是否**置顶粗体**输出"**【危症警告】此病情极其危险，涉及生命安全，请立刻前往最近的医院急诊！停止任何网络咨询！**"？')
            item_num += 1
        
        # 3. 患者画像检查
        gender_str = self.engine.patient.gender.value
        patient_check = f'{item_num}. 模型回复的患者画像部分是否包含"{gender_str}"'
        if minnan_response:
            # 提取闽南魂的关键内容
            patient_check += f'；且包含"{minnan_response}"'
        patient_check += "？"
        checklist_items.append(patient_check)
        item_num += 1
        
        # 4. 主病诊断检查
        if len(main_diseases) == 1:
            checklist_items.append(f'{item_num}. 模型回复的主病诊断是否仅包含"{main_diseases[0]}"？')
        else:
            diseases_str = '和'.join([f'"{d}"' for d in main_diseases])
            checklist_items.append(f'{item_num}. 模型回复的主病诊断是否为{diseases_str}？')
        item_num += 1
        
        
        # 
        if secondary_diagnoses:
            sec_str = "、".join([f'"{d}"' for d in secondary_diagnoses])
            checklist_items.append(f'{item_num}. 模型回复的兼证是否为{sec_str}？（注：兼证须恰好为所列各项，缺少或多出任何一项均不满足。）')
            item_num += 1
            
        
        # 7. 方名检查
        checklist_items.append(f'{item_num}. 模型回复的方名是否为"{prescription.formula_name}"？')
        item_num += 1
        
        # 8. 药材清单检查
        herb_count = len(prescription.herbs)
        herbs_str = "、".join([f'"{h}"' for h in prescription.herbs])
        checklist_items.append(f'{item_num}. 模型回复的药材清单中是否仅包含{herb_count}味药物，且为{herbs_str}？（注：药名须与规则书中该方剂所列药名完全一致，如规则书写作“生地”，写作“生地黄”视为不一致。）')
        item_num += 1
        
        # 9. 特殊医嘱检查（如果有）
        if prescription.special_notes:
            notes_parts = []
            for note in prescription.special_notes:
                # 解析特殊医嘱，如 "人参(需另煎兑入)"
                if "(" in note:
                    herb_name = note.split("(")[0]
                    note_content = "(" + note.split("(")[1]
                    notes_parts.append(f'"{herb_name}"后是否备注"{note_content}"')
            if notes_parts:
                checklist_items.append(f'{item_num}. 模型回复的药材清单中{"; 且".join(notes_parts)}？（注：备注文字须与规则书原文完全一致，如“需先煎30-60分钟”不得省略“需”字；括号全角/半角不影响判定。）')
                item_num += 1
        
        # 10. 饮食忌口检查
        advice_count = len(dietary_advice)
        if advice_count == 1:
            checklist_items.append(f'{item_num}. 模型回复的饮食忌口是否包含"{dietary_advice[0]}"的建议？')
        else:
            dietary_advice_str = " 和 ".join([f'"{a}"' for a in dietary_advice])
            checklist_items.append(f'{item_num}. 模型回复的饮食忌口是否仅包含{advice_count}条建议，分别为{dietary_advice_str}？')
        item_num += 1
        
        
        # 11. 情志调节检查
        emotion_count = len(emotion_advice)
        if emotion_count == 1:
            checklist_items.append(f'{item_num}. 模型回复的"情志调节"是否仅包含"{emotion_advice[0]}"的内容？')
        else:
            emotion_str = "、".join([f'"{a}"' for a in emotion_advice])
            checklist_items.append(f'{item_num}. 模型回复的"情志调节"是否包含{emotion_count}条建议，分别为{emotion_str}？')
        item_num += 1
        
        # 12. 生活起居检查
        # 13. 好孕模式检查（如果触发）
        if self.engine.patient.good_pregnancy_mode:
            lifestyle_advice.append("回去记得拜拜注生娘娘，床头放点红枣花生，早生贵子！")
        lifestyle_count = len(lifestyle_advice)
        if lifestyle_count == 1:
            checklist_items.append(f'{item_num}. 模型回复的生活起居是否仅包含建议"{lifestyle_advice[0]}"？')
        else:
            advice_str = "和".join([f'"{a}"' for a in lifestyle_advice])
            checklist_items.append(f'{item_num}. 模型回复的生活起居是否仅包含{lifestyle_count}条建议，且为{advice_str}？')
        item_num += 1
        
        return "\n".join(checklist_items)
    
    def _get_diagnosis_basis(self, disease: str) -> List[str]:
        """获取指定疾病的诊断依据"""
        basis = self.engine.diagnosis.diagnosis_basis
        result = []
        
        # 直接匹配
        if disease in basis:
            result.extend(basis[disease])
        
        # 模糊匹配
        for key, values in basis.items():
            if disease in key and key != disease:
                result.extend(values)
            elif key in disease and key != disease:
                result.extend(values)
        
        return result


# ==================== 主程序 ====================

def run_diagnosis(case_data: Dict) -> str:
    """运行诊断并生成诊断书
    
    Args:
        case_data: 标准化输入字典，包含:
            - patient: {'gender': 'male'/'female', 'age': int}
            - disease: List[Dict] - 病症列表（字典格式，含text/time/time_order/severity_label）
            - season: str (可选) - 当前季节
            - minnan_trigger: {'count': int, 'married': bool} (可选)
    
    Returns:
        str: 诊断书文本
    """
    engine = TCMDiagnosisEngine()
    generator = DiagnosticReportGenerator(engine)
    return generator.generate_report(case_data)


def verified_zhongyi(case_data: Dict) -> tuple:
    """运行诊断并生成诊断书和检验清单

    Args:
        case_data: 标准化输入字典
    
    Returns:
        tuple: (诊断书文本, 检验清单文本)
    """
    engine = TCMDiagnosisEngine()
    generator = DiagnosticReportGenerator(engine)
    
    # 运行诊断
    all_texts = engine.run_diagnosis(case_data)
    
    # 获取闽南魂触发响应
    minnan_response = engine.get_minnan_response()
    
    # 确定主病
    main_diseases = engine.determine_main_disease(case_data)
    engine.main_diseases = main_diseases  # 存储主病，供select_formula使用
    
    # 判断是否为危症
    is_critical = any(d in ["亡阳证", "亡阴证", "气脱证"] for d in main_diseases)
    
    # 选择方剂
    prescription = engine.select_formula()
    
    # 生成建议
    dietary_advice = engine.generate_dietary_advice(all_texts)
    emotion_advice = engine.generate_emotion_advice()
    lifestyle_advice = engine.generate_lifestyle_advice(main_diseases, is_critical)
    
    # 获取兼证
    secondary_diagnoses = generator._get_secondary_diagnoses(main_diseases)
    
    # 构建诊断书
    report = generator._build_report(
        main_diseases=main_diseases,
        prescription=prescription,
        dietary_advice=dietary_advice,
        emotion_advice=emotion_advice,
        lifestyle_advice=lifestyle_advice,
        minnan_response=minnan_response,
        is_critical=is_critical
    )
    
    # 生成检验清单
    checklist_gen = ChecklistGenerator(engine, report)
    checklist = checklist_gen.generate_checklist(
        main_diseases=main_diseases,
        prescription=prescription,
        dietary_advice=dietary_advice,
        emotion_advice=emotion_advice,
        lifestyle_advice=lifestyle_advice,
        minnan_response=minnan_response,
        secondary_diagnoses=secondary_diagnoses,
        is_critical=is_critical
    )
    report = '\n【生成的诊断书】\n' + report + '\n\n【Checklist】\n' + checklist
    return report


# 测试代码
if __name__ == "__main__":
    # usage: python -m code_simulation_engines.decision_tree_state_machine.traditional_medicine_diagnosis.traditional_medicine_diagnosis [question id], e.g. tcm_1
    import ast
    import json
    import sys
    from pathlib import Path

    qid = sys.argv[1] if len(sys.argv) > 1 else "tcm_1"
    with open(Path(__file__).resolve().parents[2] / "structured_inputs.jsonl", encoding="utf-8") as f:
        rows = {r["id"]: r for r in map(json.loads, f)}
    raw = rows[qid]["structured_input"]
    try:
        case = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        case = json.loads(raw)
    print(verified_zhongyi(case))
