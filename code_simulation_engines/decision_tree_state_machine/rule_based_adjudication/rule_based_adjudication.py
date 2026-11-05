"""
春秋断狱裁断算法核心

核心公式: J（春秋）= M（原心动机）+ E（伦理位阶）+ N（名分正当性）- Q（权变修正）

裁断结果:
- J ≤ 2: 礼义无罪
- 3 ≤ J ≤ 7: 礼义可原
- J ≥ 8: 礼义有罪
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


@dataclass
class JudgmentResult:
    """裁断结果数据结构"""
    subject: str  # 裁断主体
    M: int = 2  # 原心动机 (0=志善, 2=不明, 5=志恶)
    M_state: str = "不明"
    M_reasoning: str = ""  # M值推导逻辑
    E: int = 0  # 伦理位阶 (1=低位, 3=中位, 5=高位, 0=未涉)
    E_state: str = "未涉伦理"
    E_reasoning: str = ""  # E值推导逻辑
    N: int = 0  # 名分正当性 (0=正当/未涉, 2=中性, 5=不正)
    N_state: str = "名分正当（N模块未启动）"
    N_reasoning: str = ""  # N值推导逻辑
    Q: int = 0  # 权变修正 (0=不成立, 1=弱权变, 3=强权变)
    Q_note: str = ""
    Q_reasoning: str = ""  # Q值推导逻辑
    J: int = 0  # 春秋裁断值
    verdict: str = ""  # 裁断结论
    CR: bool = False  # 刑事责任
    CR_basis: List[str] = field(default_factory=list)  # 刑事责任判别依据
    AR: bool = False  # 行政责任
    AR_basis: List[str] = field(default_factory=list)  # 行政责任判别依据
    MR: bool = False  # 民事责任
    MR_basis: List[str] = field(default_factory=list)  # 民事责任判别依据
    investigation_procedure: bool = False  # 调查/审查程序
    investigation_basis: List[str] = field(default_factory=list)  # 调查程序判别依据
    hearing_procedure: bool = False  # 听证/审理程序
    hearing_basis: List[str] = field(default_factory=list)  # 听证程序判别依据
    exemption_procedure: bool = False  # 免责/减免程序
    exemption_basis: List[str] = field(default_factory=list)  # 免责程序判别依据
    is_valid: bool = True  # 是否为有效裁断（要件是否齐备）
    invalid_reason: str = ""  # 要件缺失原因


class ChunqiuJudge:
    """春秋断狱算法核心"""
    
    def __init__(self):
        # ===== M模块关键词 =====
        # 目的标志词 (P)
        self.purpose_markers = ["以……为目的", 
                                 "为", "因", "迫于", "出于"]
        
        # 含"为"或"因"的非目的组词（需排除）
        self.purpose_excluded_compounds = [
            # 含"为"的组词
            "行为", "作为", "认为", "成为", "以为", "无为", "有为", "人为", 
            "甚为", "较为", "尤为", "颇为", "极为", "更为", "最为", "何为",
            "所为", "妄为", "胡为", "乱为", "不为", "难为", "能为", "可为",
            "有所作为", "无所作为", "大有作为", "胡作非为", "视为",
            # 含"因"的组词
            "原因", "起因", "病因", "基因", "主因", "死因", "诱因", "内因", 
            "外因", "成因", "事因", "缘因", "近因", "远因", "因素", "因此",
            "因而", "因果", "因由", "因缘"
        ]
        
        # 合法对象 (O) - 来自system_prompt.md第六章
        # 注意：除了以下关键词外，"具体人名"也是合法对象
        # 具体人名来自卷宗的subjects和identities字段，通过known_names参数传递
        self.valid_objects = {
            "person": ["父亲", "母亲", "儿子", "女儿", "丈夫", "妻子", "被害人"],
            "relation": ["家庭", "君臣", "上下级", "监护关系"],
            "order": ["家族延续", "职位完整", "制度稳定"],
            "interest": ["财产", "权力", "控制权"]  # 可触发志恶
        }
        
        # 行为关键词 (R) - 可计入
        self.action_keywords = {
            "direct": ["杀害", "伤害", "殴打", "拘禁", "释放", "强行带离", "驱逐", "侵入"],
            "state_change": ["藏匿", "转移", "交付", "伪造", "销毁", "破坏", "隐瞒", "隐瞒事实"],
            "violation": ["拒绝配合", "拒不报告", "违抗命令", "违反规定"]
        }
        
        # 行为排除关键词
        self.excluded_actions = [
            "保护", "为保护", "为救", "挽救", "维护", "保全", "防止", "避免", 
            "阻止", "掩护", "护送", "代替承担",
            "以免", "使其免于", "让其不至于", "防止发生",
            "害怕", "紧张", "愤怒", "情绪失控", "争吵", "逃跑", "犹豫"
        ]
        
        # 否定词
        self.negation_words = ["未", "没有", "并未", "未曾", "从未", "不曾", "并不", "未能", "未予"]
        
        # 志恶型触发词 (P1)
        self.evil_triggers = ["蓄意", "谋划", "报复", "为夺取", "意图颠覆"]
        
        # 志善型触发词 (P2)
        self.good_triggers = ["为救", "为保护", "因行孝", "为保全"]
        
        # ===== E模块关键词 =====
        # 高位伦理对象 (E=5) - 来自system_prompt.md第七章
        self.high_ethics = [
            "君臣", "君位", "国君", "朝廷", "国家", "制度稳定", "法统", "正统",
            "家国秩序", "血统与宗法根基", "宗庙", "祖宗", "家族延续", "血脉", 
            "正统继承"
        ]
        
        # 中位伦理对象 (E=3) - 来自system_prompt.md第七章
        # 注意："家"需要特殊处理，只有表示家庭/家族含义时才生效
        self.mid_ethics = [
            "家人","父亲", "母亲", "父母", "子女", "长辈", "夫妻", "家庭整体",
            "师徒", "主仆"
        ]
        
        # 低位伦理对象 (E=1) - 来自system_prompt.md第七章
        self.low_ethics = [
            "个体利益", "个人", "被害人", "财产", "利益", "名誉", "自身安全",
            "性命", "自保"
        ]
        
        # "家"字的排除组词（这些词中的"家"不应触发中位伦理）
        # 包括：皇家、国家等国家/机构类；专家、作家等职业类；商家、店家等商业类
        self.family_excluded_compounds = [
            # 国家/机构类（这些词中的"家"不表示家庭/家族）
            "皇家", "国家", "家国", "王家", "官家",
            # 职业/身份类（X家 = 某领域专家）
            "大家", "专家", "作家", "画家", "音乐家", "科学家", "艺术家", 
            "思想家", "哲学家", "政治家", "企业家", "银行家", "资本家",
            "文学家", "历史家", "教育家", "军事家", "战略家", "外交家",
            # 商业类
            "商家", "店家", "厂家", "买家", "卖家", "东家", "庄家",
            # 泛指/代词类
            "人家", "自家", "本家", "大家", "谁家", "哪家", "这家", "那家",
            # 亲属关系类（已有更明确的词如"父亲"、"母亲"）
            "婆家", "娘家", "亲家",
            # 其他不表示家庭/家族的组词
            "世家", "行家", "当家", "管家", "冤家", "仇家", "赢家", "输家",
            "玩家", "藏家", "住家", "搬家", "回家", "到家", "在家", "出家",
            "发家", "败家", "持家", "治家", "安家", "落家"
        ]
        
        # ===== N模块关键词 =====
        # 身份/名分要素 - 来自system_prompt.md第八章
        self.identity_keywords = {
            "family": ["父亲", "母亲", "子女", "兄长", "弟弟", "妻子", "丈夫", "家属", "监护人"],
            "power": ["上级", "下级", "领导", "部属", "君", "臣", "官员", "执法者", "管理者"],
            "role": ["教师", "学生", "医生", "患者", "看护人", "被监管人"]
        }
        
        # 越位/违名行为触发词
        self.transgression_strong = [
            "擅自决定", "越权", "代行职权", "私自处理", "未经允许", 
            "无视其身份", "不服从", "抗命", "僭越其位"
        ]
        self.transgression_mid = [
            "本应由……决定，却由其决定", "代替……作出决定", "未经其同意",
            "以其名义", "未告知当事人", "隐瞒于其"
        ]
        self.transgression_weak = ["破坏秩序", "冒名", "僭称", "名不正", "越位行为"]
        
        # 名分正当词 - 来自system_prompt.md第八章第五节
        self.legitimate_identity = ["依法履职", "依其身份", "在其职责范围内"]
        
        # ===== Q模块关键词 =====
        # 紧急胁迫类（强触发）
        self.urgency_strong = [
            "迫于威胁", "被胁迫", "若不……将立即", "当下只能如此",
            "别无选择", "情势紧急", "无可回避"
        ]
        
        # 非自主被动类（中触发）
        self.urgency_mid = [
            "被迫配合", "在强制要求下", "依上级强令", "在不可抗拒情况下"
        ]
        
        # 风险规避（弱触发）
        self.urgency_weak = [
            "为避免更大混乱", "为防止局势失控", "以免造成更严重后果"
        ]
        
        # 主动谋划类反向表述
        self.anti_urgency_plan = [
            "主动谋划", "预先设计", "事先策划", "周密安排", "精心布局",
            "长期准备", "早有打算", "蓄意安排", "事前已决定"
        ]
        
        # 从容选择类反向表述
        self.anti_urgency_choice = [
            "从容决定", "自主选择", "自行决定", "主动选择", "权衡之后决定",
            "冷静判断后", "明知可以不为而仍为之"
        ]
        
        # ===== 现代法律模块关键词 =====
        # 刑事责任
        self.criminal_keywords = [
            "犯罪", "构成犯罪", "依法追究刑事责任", "被刑事立案",
            "被逮捕", "被缉拿", "判处有期徒刑", "判处拘役", "判处死刑"
        ]
        self.criminal_patterns = [
            re.compile(r"涉嫌.{1,10}罪")
        ]
        
        # 行政责任
        self.admin_keywords = [
            "行政处罚", "纪律处分", "记过", "记大过", "撤职", "免职", "停职",
            "追究行政责任", "违反规定", "违反管理制度"
        ]
        
        # 民事责任
        self.civil_keywords = [
            "赔偿损失", "民事赔偿", "侵权责任", "返还财产", "承担赔偿责任",
            "经济损失", "要求赔偿"
        ]
        
        # 调查/审查程序
        self.investigation_keywords = [
            "立案调查", "启动调查", "接受调查", "接受审查", "进入审查程序", "组织调查组"
        ]
        
        # 听证/审理程序
        self.hearing_keywords = [
            "听证", "听证程序", "公开审理", "审理阶段", "庭审", "复核程序"
        ]
        
        # 免责/减免程序
        self.exemption_keywords = [
            "依法免责", "可以免责", "从轻处理", "减轻责任", "不予追究", "免予处罚"
        ]

    def _match_keyword(self, text: str, keyword: str) -> bool:
        """检查文本是否匹配单个关键词
        
        如果关键词包含省略号（……或...），则匹配省略号前后的模式，
        允许省略号位置有任意字符（0-20个字符）。
        例如："本应由……决定" 可以匹配 "本应由张三决定"、"本应由上级决定" 等。
        """
        if "……" in keyword or "..." in keyword:
            # 将省略号替换为正则表达式模式
            # 先按省略号分割，然后对每部分进行转义，最后用正则模式连接
            parts = re.split(r'……|\.\.\.', keyword)
            escaped_parts = [re.escape(p) for p in parts]
            pattern = ".{0,20}".join(escaped_parts)
            return bool(re.search(pattern, text))
        else:
            return keyword in text
    
    def _contains_keyword(self, text: str, keywords: List[str]) -> Tuple[bool, List[str]]:
        """检查文本是否包含关键词列表中的任一词"""
        found = []
        for kw in keywords:
            if self._match_keyword(text, kw):
                found.append(kw)
        return len(found) > 0, found

    def _is_negated(self, text: str, keyword: str) -> bool:
        """检查关键词是否被否定词修饰"""
        idx = text.find(keyword)
        if idx == -1:
            return False
        # 检查前方是否有否定词紧邻
        prefix = text[max(0, idx-10):idx]
        for neg in self.negation_words:
            if neg in prefix:
                return True
        return False

    def _check_R_valid_paths(self, text: str, actions: List[str], objects: List[str], purpose_markers: List[str] = None) -> Dict:
        """
        检查行为关键词是否满足R=1的三种合法成立路径
        
        规则（来自system_prompt.md第六章第三节第4条第7款）：
        1. 同句并列指向（最高优先）：目的标志词、对象名词、行为关键词出现在同一句，中间不出现句号、分号
           示例："为救父亲，隐瞒事实"、"为保护子女，藏匿其行踪"
        2. 固定闭合句式（中优先）：
           - 为（对象）而（行为关键词）
           - 因（对象）而（行为关键词）
           - 是为了（对象），而（行为关键词）
        3. 结果避免型指向（低优先）：
           - "以免（对象）......"、"避免（对象）......"、"防止（对象）......"
           - 在关键短语前的同一句内出现行为关键词
        
        返回: {'R': 0或1, 'found_actions': [], 'path': '路径描述'}
        """
        result = {'R': 0, 'found_actions': [], 'path': ''}
        
        if purpose_markers is None:
            purpose_markers = []
        
        # 先找出所有有效的行为关键词（未被否定、不在排除列表中）
        valid_actions = []
        for action in actions:
            if action in text:
                if not self._is_negated(text, action):
                    is_excluded = False
                    for exc in self.excluded_actions:
                        if exc in action or action == exc:
                            is_excluded = True
                            break
                    if not is_excluded:
                        valid_actions.append(action)
        
        if not valid_actions:
            return result
        
        # 按句子分割文本（句号、分号为分隔符）
        sentences = re.split(r'[。；]', text)
        
        # 路径1：同句并列指向（最高优先）
        # 要求：目的标志词、对象、行为关键词三者都在同一句中
        for action in valid_actions:
            for obj in objects:
                for sent in sentences:
                    
                    if action in sent and obj in sent:
                        # 检查同一句中是否也包含目的标志词
                        has_purpose_in_same_sent = False
                        for marker in purpose_markers:
                            if marker in sent:
                                has_purpose_in_same_sent = True
                                break
                        if has_purpose_in_same_sent:
                            result['R'] = 1
                            result['found_actions'].append(action)
                            result['path'] = '同句并列指向'
                            return result
        
        # 路径2：固定闭合句式（中优先）
        # 注意：行为关键词必须在同一句内（到句号或分号为止）
        fixed_patterns = [
            (r'为([^。；]+?)而([^。；]+)', '为...而...'),
            (r'因([^。；]+?)而([^。；]+)', '因...而...'),
            (r'是为了([^。；]+?)，而([^。；]+)', '是为了...，而...')
        ]
        for pattern, desc in fixed_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) >= 2:
                    obj_part, action_part = match[0], match[1]
                    # 检查对象部分是否包含合法对象
                    obj_found = any(obj in obj_part for obj in objects)
                    # 检查行为部分是否包含行为关键词
                    action_found = None
                    for action in valid_actions:
                        if action in action_part:
                            action_found = action
                            break
                    if obj_found and action_found:
                        result['R'] = 1
                        result['found_actions'].append(action_found)
                        result['path'] = f'固定闭合句式（{desc}）'
                        return result
        
        # 路径3：结果避免型指向（低优先）
        # 规则：行为关键词必须在"以免/避免/防止"关键短语之前的同一句内
        # 示例："隐瞒事实，以免父亲被追责" - "隐瞒事实"在"以免"之前
        avoid_keywords = ['以免', '避免', '防止']
        for keyword in avoid_keywords:
            if keyword in text:
                # 找到关键词的位置
                keyword_pos = text.find(keyword)
                # 获取关键词之前的文本
                text_before = text[:keyword_pos]
                # 获取关键词之后到句号/分号的文本（同一句内）
                text_after_match = re.match(r'([^。；]*)', text[keyword_pos + len(keyword):])
                text_after = text_after_match.group(1) if text_after_match else ''
                
                # 找到关键词之前最近的句子边界
                last_sentence_break = max(text_before.rfind('。'), text_before.rfind('；'))
                text_before_same_sentence = text_before[last_sentence_break + 1:] if last_sentence_break >= 0 else text_before
                
                # 检查关键短语后的同一句内是否包含合法对象
                obj_found = any(obj in text_after for obj in objects)
                
                # 检查关键短语前的同一句内是否有行为关键词
                action_found = None
                for action in valid_actions:
                    if action in text_before_same_sentence:
                        action_found = action
                        break
                
                if obj_found and action_found:
                    result['R'] = 1
                    result['found_actions'].append(action_found)
                    result['path'] = f'结果避免型指向（{keyword}...）'
                    return result
        
        # 凡不符合R=1的三种唯一合法成立路径的，一律直接判定为 R=0
        return result

    def _is_purpose_verb(self, text: str, char: str) -> bool:
        """
        检查单字符"为"或"因"在文本中是否作为目的动词使用，
        而非组词（如"行为"、"作为"、"原因"等）的一部分。
        
        目的动词的特征：前面是名词，后面是名词或动词
        例如：甲为救其父、因护国而...
        
        Args:
            text: 待检查的文本
            char: 要检查的字符（"为"或"因"）
        
        Returns:
            bool: 如果存在作为目的动词的用法返回True，否则返回False
        """
        for compound in self.purpose_excluded_compounds:
            text = text.replace(compound, "")
        if char in text:
            return text, True
        return text, False

    def _extract_subject_text(self, full_text: str, subject: str) -> str:
        """从卷宗中提取与特定主体相关的文本"""
        # 简单方法：返回包含主体名字的句子及其上下文
        # lines = full_text.split('\n')
        # relevant_lines = []
        # for i, line in enumerate(lines):
        #     if subject in line:
        #         # 获取上下文
        #         start = max(0, i-2)
        #         end = min(len(lines), i+3)
        #         relevant_lines.extend(lines[start:end])
        # return '\n'.join(relevant_lines) if relevant_lines else full_text
        return full_text

    def _extract_keyword_context(self, text: str, keyword: str, context_chars: int = 30) -> str:
        """提取包含关键词的原文片段
        
        支持省略号模式：如果keyword包含省略号，会使用正则匹配找到实际匹配的文本
        """
        # 处理省略号模式
        if "……" in keyword or "..." in keyword:
            parts = re.split(r'……|\.\.\.', keyword)
            escaped_parts = [re.escape(p) for p in parts]
            pattern = ".{0,20}".join(escaped_parts)
            match = re.search(pattern, text)
            if not match:
                return ""
            idx = match.start()
            matched_text = match.group()
            keyword_len = len(matched_text)
        else:
            idx = text.find(keyword)
            if idx == -1:
                return ""
            matched_text = keyword
            keyword_len = len(keyword)
        
        # 找到关键词所在句子的边界
        # 向前找句子开始
        start = idx
        for i in range(idx - 1, max(0, idx - context_chars) - 1, -1):
            if text[i] in '。；\n':
                start = i + 1
                break
            if i == max(0, idx - context_chars):
                start = i
        
        # 向后找句子结束
        end = idx + keyword_len
        for i in range(idx + keyword_len, min(len(text), idx + keyword_len + context_chars)):
            if text[i] in '。；\n':
                end = i + 1
                break
            if i == min(len(text), idx + keyword_len + context_chars) - 1:
                end = i + 1
        
        context = text[start:end].strip()
        # 高亮实际匹配的文本
        return context.replace(matched_text, f"【{matched_text}】")

    def _extract_object_context_with_purpose(self, text: str, obj: str, purpose_markers: List[str]) -> str:
        """
        提取与目的标志词同句的对象上下文
        
        规则（来自system_prompt.md第六章第三节第3条）：
        目的标志词后（仅指与目的标志词在同一句内）必须明确指向对象
        """
        # 按句号、分号分割句子
        sentence_delimiters = r'[。；;？]'
        sentences = re.split(sentence_delimiters, text)
        
        # 找到同时包含目的标志词和对象的句子
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            # 检查该句子是否包含目的标志词
            has_purpose = False
            for marker in purpose_markers:
                if marker in sent:
                    has_purpose = True
                    break
            # 检查该句子是否包含对象
            if has_purpose and obj in sent:
                # 高亮对象
                return sent.replace(obj, f"【{obj}】")
        
        # 如果没有找到同句的情况，返回普通上下文
        return self._extract_keyword_context(text, obj)

    def _extract_dossier(self, full_text: str, dossier_id: str) -> str:
        """从完整文本中提取特定卷宗"""
        # 查找卷宗开始和结束位置
        pattern = f"卷宗编号：{dossier_id}"
        start_idx = full_text.find(pattern)
        if start_idx == -1:
            # 尝试不带冒号的格式
            pattern = f"卷宗编号:{dossier_id}"
            start_idx = full_text.find(pattern)
        if start_idx == -1:
            return ""
        
        # 找下一个卷宗的开始位置
        next_dossier = full_text.find("卷宗编号：", start_idx + len(pattern))
        if next_dossier == -1:
            next_dossier = full_text.find("卷宗编号:", start_idx + len(pattern))
        
        if next_dossier == -1:
            return full_text[start_idx:]
        return full_text[start_idx:next_dossier]

    def judge_M(self, text: str, subject: str, known_names: List[str] = None, other_subjects: List[str] = None) -> Tuple[int, str, Dict, str]:
        """
        判断原心动机 M
        返回: (M值, 状态描述, 判定详情, 推导逻辑)
        
        规则：
        - P: 目的标志词（为、因、迫于、出于等）
        - O: 合法对象（人、关系、秩序、利益）- 仅限清单中的关键词，或具体人名
        - R: 行为关键词（需在清单内且未被否定）
        - P1: 志恶触发词（蓄意、谋划、报复、为夺取、意图颠覆）
        - P2: 志善触发词（为救、为保护、因行孝、为保全）
        
        参数:
            text: 卷宗文本
            subject: 裁断主体名称
            known_names: 卷宗中已知的人名列表（来自subjects和identities字段）
        """
        details = {
            'P': 0, 'O': 0, 'R': 0, 'P1': 0, 'P2': 0,
            'found_purpose': [], 'found_objects': [], 
            'found_actions': [], 'found_evil': [], 'found_good': [],
            'invalid_objects': []  # 记录不在清单中的对象
        }
        reasoning_parts = []
        
        # 提取主体相关文本（仅在当前卷宗范围内）
        subject_text = self._extract_subject_text(text, subject)
        reasoning_parts.append("准入检查 (T):")
        
        # 1. 检查目的标志词 P
        for marker in self.purpose_markers:
            clean_marker = marker
            if self._match_keyword(subject_text, clean_marker):
                # 对于单字符的"为"和"因"，需要检查是否为目的动词而非组词
                if clean_marker in ["为", "因"]:
                    subject_text, tag = self._is_purpose_verb(subject_text, clean_marker)
                    if not tag:
                        continue  # 不是目的动词，跳过
                details['P'] += 1
                details['found_purpose'].append(clean_marker)
        
        if details['P'] == 0:
            reasoning_parts.append(f"  - P检查: 未命中目的标志词 → P = 0")
            reasoning_parts.append("结论: 动机裁断模块不启动，锁定 M = 2（动机不明）")
            return 2, "不明", details, '\n'.join(reasoning_parts)
        else:
            # 展示命中的原文
            purpose_contexts = []
            for p in details['found_purpose'][:2]:  # 只展示前2个避免太长
                ctx = self._extract_keyword_context(subject_text, p)
                if ctx and ctx not in purpose_contexts:
                    purpose_contexts.append(ctx)
            reasoning_parts.append(f"  - P检查: 命中目的词「{'、'.join(details['found_purpose'])}」 → P ≥ 1")
            if purpose_contexts:
                reasoning_parts.append(f"    原文: 「{purpose_contexts[0]}」")
        
        # 2. 检查对象 O - 必须与目的标志词在同一句内
        # 规则（来自system_prompt.md第六章第三节第3条）：
        # 目的标志词后（仅指与目的标志词在同一句内，且不得跨越句号、分号），
        # 必须明确指向"具体人名"或被系统承认的对象关键词之一
        all_objects = []
        for cat, cat_objects in self.valid_objects.items():
            all_objects.extend(cat_objects)
        
        # 构建合法对象列表（清单关键词 + 已知人名）
        valid_object_list = list(all_objects)
        # if known_names:
        #     for name in known_names:
        #         if name != subject and name not in valid_object_list:
        #             valid_object_list.append(name)
        
        # 提取包含目的标志词的句子（以句号、分号为边界）
        # 只在这些句子中查找对象
        sentences_with_purpose = []
        # 按句号、分号、问号分割句子
        sentence_delimiters = r'[。；;？]'
        sentences = re.split(sentence_delimiters, subject_text)
        
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            # 检查该句子是否包含目的标志词
            has_purpose = False
            for marker in details['found_purpose']:
                if marker in sent:
                    has_purpose = True
                    break
            if has_purpose:
                sentences_with_purpose.append(sent)
        
        # 在包含目的标志词的句子中查找对象
        for obj in valid_object_list:
            if obj in details['found_objects']:
                continue
            # 检查该对象是否出现在包含目的标志词的句子中
            for sent in sentences_with_purpose:
                if obj in sent:
                    details['O'] += 1
                    details['found_objects'].append(obj)
                    break
        
        # 非人名词汇列表（用于排除非人名的匹配结果）
        non_name_words = [
            "性命", "全城", "大局", "稳定", "秩序", "安全", "利益", "局势", 
            "混乱", "后果", "情况", "事态", "局面", "问题", "目的", "理由",
            "原因", "结果", "影响", "损失", "伤害", "危险", "风险", "威胁"
        ]
        
        # 检查是否有人名在"为救"等后面（同句并列指向）
        # 这些模式本身就保证了同句约束
        # name_patterns = [
        #     (r'为救(\w{2,4})', '为救'),
        #     (r'为保护(\w{2,4})', '为保护'),
        #     (r'为保全(\w{2,4})', '为保全')
        # ]
        # for pattern, trigger in name_patterns:
        #     matches = re.findall(pattern, subject_text)
        #     for m in matches:
        #         # 检查匹配结果是否已经在合法对象中
        #         if m in details['found_objects']:
        #             continue
        #         # 检查是否是合法对象清单中的词或已知人名
        #         if m in valid_object_list:
        #             details['O'] += 1
        #             details['found_objects'].append(m)
        #         else:
        #             # 检查是否可能是具体人名
        #             # 排除条件：包含非人名词汇的匹配
        #             is_non_name = False
        #             for non_name in non_name_words:
        #                 if non_name in m or m in non_name:
        #                     is_non_name = True
        #                     break
                    
        #             if is_non_name:
        #                 # 记录无效对象
        #                 if m not in details['invalid_objects']:
        #                     details['invalid_objects'].append(m)
        #             else:
        #                 # 可能是具体人名（2-4字，不含明显非人名词）
        #                 # 进一步验证：检查该词是否在卷宗中作为行为主体或被提及的人物出现
        #                 print(re.search(rf'{m}[在为因的]|{m}，|，{m}|裁断主体[：:].*{m}', text))
        #                 if re.search(rf'{m}[在为因的]|{m}，|，{m}|裁断主体[：:].*{m}', text):
        #                     details['O'] += 1
        #                     details['found_objects'].append(m)
        #                 else:
        #                     if m not in details['invalid_objects']:
        #                         details['invalid_objects'].append(m)
        
        if details['O'] == 0:
            invalid_note = ""
            invalid_ctx = ""
            if details['invalid_objects']:
                invalid_note = f"（「{'、'.join(details['invalid_objects'])}」不在合法对象清单中）"
                # 获取无效对象的原文
                for inv_obj in details['invalid_objects'][:1]:
                    ctx = self._extract_keyword_context(subject_text, inv_obj)
                    if ctx:
                        invalid_ctx = ctx
            reasoning_parts.append(f"  - O检查: 未命中合法对象关键词{invalid_note} → O = 0")
            if invalid_ctx:
                reasoning_parts.append(f"    原文: 「{invalid_ctx}」")
            reasoning_parts.append("  - 根据规则：O = 0 时，禁止进入R判定流程")
            reasoning_parts.append("结论: 动机裁断模块不启动，锁定 M = 2（动机不明）")
            return 2, "不明", details, '\n'.join(reasoning_parts)
        else:
            # 展示命中的原文（优先显示与目的标志词同句的上下文）
            obj_contexts = []
            for obj in details['found_objects'][:2]:
                ctx = self._extract_object_context_with_purpose(subject_text, obj, details['found_purpose'])
                if ctx and ctx not in obj_contexts:
                    obj_contexts.append(ctx)
            reasoning_parts.append(f"  - O检查: 命中对象「{'、'.join(details['found_objects'])}」 → O ≥ 1")
            if obj_contexts:
                reasoning_parts.append(f"    原文: 「{obj_contexts[0]}」")
        
        # 3. 检查行为关键词 R - 需要验证三种合法成立路径
        # 规则（来自system_prompt.md第六章第三节第4条第7款）：
        # - 同句并列指向（最高优先）
        # - 固定闭合句式（中优先）
        # - 结果避免型指向（低优先）
        all_actions = []
        for cat_actions in self.action_keywords.values():
            all_actions.extend(cat_actions)
        
        r_result = self._check_R_valid_paths(subject_text, all_actions, details['found_objects'], details['found_purpose'])
        details['R'] = r_result['R']
        details['found_actions'] = r_result['found_actions']
        details['R_path'] = r_result.get('path', '')
        
        if details['R'] == 0:
            reasoning_parts.append(f"  - R检查: 未命中行为关键词或未满足合法成立路径 → R = 0")
            reasoning_parts.append("结论: 动机裁断模块不启动，锁定 M = 2（动机不明）")
            return 2, "不明", details, '\n'.join(reasoning_parts)
        else:
            # 展示命中的原文
            action_ctx = self._extract_keyword_context(subject_text, details['found_actions'][0])
            path_desc = f"（{details['R_path']}）" if details.get('R_path') else ""
            reasoning_parts.append(f"  - R检查: 命中行为「{'、'.join(details['found_actions'])}」{path_desc} → R = 1")
            if action_ctx:
                reasoning_parts.append(f"    原文: 「{action_ctx}」")
        
        reasoning_parts.append("准入检查通过，进入动机类型判定。")
        reasoning_parts.append("")
        reasoning_parts.append("触发词扫描:")
        
        # 4. 检查志恶触发词 P1（仅在当前主体相关句子中检查）
        subject_sentences = self._get_subject_sentences(text, subject, other_subjects or [])
        for trigger in self.evil_triggers:
            if trigger in subject_sentences:
                # "谋划"以"主动谋划"形式出现时不触发志恶
                if trigger == "谋划" and "主动谋划" in subject_sentences:
                    # 检查是否存在独立的"谋划"（不在"主动谋划"中）
                    temp_text = subject_sentences.replace("主动谋划", "")
                    if "谋划" not in temp_text:
                        continue
                details['P1'] += 1
                details['found_evil'].append(trigger)
        
        # 5. 检查志善触发词 P2（仅在当前主体相关句子中检查）
        for trigger in self.good_triggers:
            if trigger in subject_sentences:
                details['P2'] += 1
                details['found_good'].append(trigger)
        
        # 6. 确定M值并生成推导逻辑
        if details['P1'] >= 1:
            evil_ctx = self._extract_keyword_context(subject_sentences, details['found_evil'][0])
            reasoning_parts.append(f"  - 命中志恶触发词「{'、'.join(details['found_evil'])}」 → P1 ≥ 1")
            if evil_ctx:
                reasoning_parts.append(f"    原文: 「{evil_ctx}」")
            reasoning_parts.append("结论: 锁定 M = 5（志恶型动机）")
            return 5, "志恶", details, '\n'.join(reasoning_parts)
        elif details['P2'] >= 1:
            good_ctx = self._extract_keyword_context(subject_sentences, details['found_good'][0])
            reasoning_parts.append(f"  - 命中志善触发词「{'、'.join(details['found_good'])}」 → P2 ≥ 1")
            if good_ctx:
                reasoning_parts.append(f"    原文: 「{good_ctx}」")
            reasoning_parts.append(f"  - 未命中志恶触发词 → P1 = 0")
            reasoning_parts.append("结论: 锁定 M = 0（志善型动机）")
            return 0, "志善", details, '\n'.join(reasoning_parts)
        else:
            reasoning_parts.append("  - 未命中志恶触发词 → P1 = 0")
            reasoning_parts.append("  - 未命中志善触发词 → P2 = 0")
            reasoning_parts.append("结论: 锁定 M = 2（动机不明）")
            return 2, "不明", details, '\n'.join(reasoning_parts)
    
    def _get_subject_sentences(self, text: str, subject: str, other_subjects: List[str] = []) -> str:
        """
        获取与特定主体直接相关的句子（主体作为行为主语）
        
        规则：
        - 只要不是以 other_subjects 中的主体为主语的句子，都视为当前主体相关
        - 即：排除其他主体作为主语的句子，其余全部保留
        
        Args:
            text: 待分析的文本
            subject: 当前裁断的主体
            other_subjects: 案卷中的其他主体列表
        """
        # 按句子分割（句号、分号、感叹号、问号）
        sentences = re.split(r'(?<=[。；！？])', text)
        
        subject_sentences = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            
            # 检查是否以其他主体开头（句子或子句）
            is_other_subject_sentence = False
            
            # 按逗号分割为子句
            clauses = re.split(r'[，,]', sent)
            
            for other in other_subjects:
                if not other or other == subject:
                    continue
                # 检查句子开头或任意子句开头是否是其他主体
                if sent.startswith(other) or any(clause.strip().startswith(other) for clause in clauses):
                    is_other_subject_sentence = True
                    break
            
            # 不是其他主体的句子 -> 保留
            if not is_other_subject_sentence:
                subject_sentences.append(sent)
        
        return ''.join(subject_sentences) if subject_sentences else text
    
    def _is_evil_trigger_valid(self, text: str, trigger: str) -> bool:
        """
        检查志恶触发词是否有效
        
        规则（来自system_prompt.md第六章第五节第2条）：
        - 否定词规则仅作用于行为关键词，不作用于动机触发词
        - 动机触发词一经出现，不因否定结构而失效
        
        特殊规则：
        - "谋划"以"主动谋划"形式出现时不触发志恶型动机
        - "主动谋划类"词汇仅作为Q模块内的反向权变判断依据
        """
        return trigger in text

    def judge_E(self, text: str, subject: str) -> Tuple[int, str, Dict, str]:
        """
        判断伦理位阶 E
        返回: (E值, 状态描述, 判定详情, 推导逻辑)
        
        规则（来自system_prompt.md第七章）:
        - 高位伦理 E=5: 君臣、国家、制度稳定等
        - 中位伦理 E=3: 父母、子女、家庭等
        - 低位伦理 E=1: 个人、性命、自保等
        - 未涉伦理 E=0: 未命中任何伦理对象关键词
        
        重要规则（第七章第五节第3条）:
        - 明确标注为【起因】、【结果】部分的伦理对象关键词，
          仅可用于触发E模块启动，不计入任何主体的伦理位阶取值判定
        """
        details = {'found_high': [], 'found_mid': [], 'found_low': [], 'excluded_cause_result': []}
        reasoning_parts = []
        
        subject_text = self._extract_subject_text(text, subject)
        
        # 排除【起因】【结果】部分的文本
        # 规则：这些部分的伦理对象仅用于启动E模块，不计入取值
        subject_text_for_value = self._exclude_cause_result_sections(subject_text)
        
        reasoning_parts.append("字符匹配:")
        
        # 检查高位伦理（在排除【起因】【结果】后的文本中）
        for kw in self.high_ethics:
            if kw in subject_text_for_value:
                details['found_high'].append(kw)
            elif kw in subject_text:
                # 在原文中有，但在排除后没有，说明在【起因】【结果】中
                details['excluded_cause_result'].append(kw)
        
        # 检查中位伦理（需要特殊处理"家"字）
        for kw in self.mid_ethics:
            if kw in subject_text_for_value:
                details['found_mid'].append(kw)
            elif kw in subject_text:
                details['excluded_cause_result'].append(kw)
        
        # 特殊处理：检查"家"字是否作为家庭/家族含义出现
        # 排除"皇家"、"国家"、"专家"等组词
        # has_family, family_names = self._check_family_keyword(subject_text_for_value)
        # if has_family:
        #     for fn in family_names:
        #         if fn not in details['found_mid']:
        #             details['found_mid'].append(fn)
        
        # 检查低位伦理
        for kw in self.low_ethics:
            if kw in subject_text_for_value:
                details['found_low'].append(kw)
            elif kw in subject_text:
                details['excluded_cause_result'].append(kw)
        
        # 汇总所有命中
        all_found = details['found_high'] + details['found_mid'] + details['found_low']
        if all_found:
            reasoning_parts.append(f"  - 行为描述段落中命中「{'、'.join(all_found)}」")
            # 展示第一个命中的原文
            first_ctx = self._extract_keyword_context(subject_text_for_value, all_found[0])
            if first_ctx:
                reasoning_parts.append(f"    原文: 「{first_ctx}」")
        else:
            reasoning_parts.append("  - 行为描述段落中未命中伦理对象关键词")
        
        # 如果有被排除的【起因】【结果】部分的关键词，说明
        if details['excluded_cause_result']:
            reasoning_parts.append(f"  - 【起因】【结果】部分命中「{'、'.join(details['excluded_cause_result'])}」（仅启动，不计入取值）")
        
        if details['found_high']:
            reasoning_parts.append(f"位阶锁定: 命中「{'、'.join(details['found_high'])}」即触及秩序类最高优先")
            reasoning_parts.append("结论: 锁定 E = 5（高位伦理）")
            return 5, "高位伦理", details, '\n'.join(reasoning_parts)
        
        if details['found_mid']:
            reasoning_parts.append(f"位阶锁定: 命中中位伦理对象「{'、'.join(details['found_mid'])}」")
            reasoning_parts.append("结论: 锁定 E = 3（中位伦理）")
            return 3, "中位伦理", details, '\n'.join(reasoning_parts)
        
        if details['found_low']:
            reasoning_parts.append(f"位阶锁定: 命中低位伦理对象「{'、'.join(details['found_low'])}」")
            reasoning_parts.append("结论: 锁定 E = 1（低位伦理）")
            return 1, "低位伦理", details, '\n'.join(reasoning_parts)
        
        reasoning_parts.append("结论: 锁定 E = 0（未涉伦理）")
        return 0, "未涉伦理", details, '\n'.join(reasoning_parts)
    
    def _exclude_cause_result_sections(self, text: str) -> str:
        """
        排除文本中【起因】【结果】部分的内容
        
        规则（来自system_prompt.md第七章第五节第3条）:
        明确标注为【起因】、【结果】部分的伦理对象关键词，
        仅可用于触发E模块启动，不计入任何主体的伦理位阶取值判定。
        
        返回: 排除【起因】【结果】后的文本
        """
        result = text
        
        # 匹配【起因】...【/起因】或【起因】...到下一个【标签】
        # 以及【结果】...【/结果】或【结果】...到下一个【标签】
        patterns = [
            r'【起因】.*?(?:【/起因】|【[^】]+】|$)',
            r'【结果】.*?(?:【/结果】|【[^】]+】|$)',
            r'\[起因\].*?(?:\[/起因\]|\[[^\]]+\]|$)',
            r'\[结果\].*?(?:\[/结果\]|\[[^\]]+\]|$)',
            # 也处理"起因："和"结果："格式
            r'起因[：:].+?(?=\n|$)',
            r'结果[：:].+?(?=\n|$)',
        ]
        
        for pattern in patterns:
            result = re.sub(pattern, '', result, flags=re.DOTALL)
        
        return result
    
    def _check_family_keyword(self, text: str) -> Tuple[bool, List[str]]:
        """
        检查文本中是否存在有效的"家"字（作为家庭/家族含义）
        
        规则：
        - "家"只有在表示家庭/家族含义时才触发中位伦理
        - 排除：皇家、国家、专家、作家等组词中的"家"
        - 有效：X家（如"沈家"、"李家"）表示某个家族
        - 有效：家庭、家族、家人、家中等明确表示家庭的词
        
        返回: (是否有效, 命中的家族名称列表)
        """
        found_families = []
        
        # 先移除所有排除组词
        temp_text = text
        for compound in self.family_excluded_compounds:
            temp_text = temp_text.replace(compound, "██")  # 用占位符替换，保持位置
        
        # 检查是否还有"家"字
        if "家" not in temp_text:
            return False, []
        
        # 检查"家"字是否作为家庭/家族含义出现
        # 模式1：明确的家庭相关词
        family_words = ["家庭", "家族", "家人", "家中", "家里", "家门", "家业", 
                        "家产", "家规", "家风", "家训", "家法", "家教", "家传",
                        "家史", "家谱", "家祠", "家庙", "家宅", "全家", "一家"]
        for word in family_words:
            if word in text:
                return True, [word]
        
        # 模式2：X家（如"沈家"、"李家"）- 姓氏+家，表示某个家族
        # 使用原文检查，找到"X家"模式，然后验证不在排除列表中
        family_pattern = r'([\u4e00-\u9fa5])家'
        matches = re.findall(family_pattern, temp_text)
        for char in matches:
            family_name = char + "家"
            # 验证这个"X家"在原文中确实存在（排除组词后仍然存在）
            if family_name not in self.family_excluded_compounds:
                # 进一步检查是否是姓氏+家的模式（常见姓氏或单字）
                # 这里简单判断：如果前面的字是常见姓氏或者后面跟着家族相关词，则认为有效
                if re.search(rf'{family_name}(?:的|之|人|中|内|里|门|族)?', text):
                    found_families.append(family_name)
        
        if found_families:
            return True, found_families
        
        return False, []

    def _is_anti_trigger_valid(self, text: str, trigger: str) -> bool:
        """
        检查反向表述（Q模块）是否在有效语境中（非否定语境）
        
        例如："绝无任何主动谋划"中的"主动谋划"不应触发反向拦截，不检查否定语境
        """

        return trigger in text
        # if trigger not in text:
        #     return False
        
        # # 查找所有出现trigger的位置
        # idx = 0
        # while True:
        #     idx = text.find(trigger, idx)
        #     if idx == -1:
        #         return False
            
        #     # 获取trigger前面的文本（用于检查否定词）
        #     prefix_start = max(0, idx - 15)
        #     prefix = text[prefix_start:idx]
            
        #     # 检查前面是否有否定词（表示主体否认有此行为）
        #     negation_patterns = [
        #         "绝无", "并无", "没有", "未曾", "无任何", "从未", "不曾",
        #         "毫无", "否认", "并非", "不存在"
        #     ]
            
        #     is_negated = False
        #     for neg in negation_patterns:
        #         if neg in prefix:
        #             is_negated = True
        #             break
            
        #     # # 如果不在否定语境中，则为有效的反向表述
        #     if not is_negated:
        #         return True
            
        #     idx += len(trigger)
        
        # return False

    def judge_modern_law(self, text: str) -> Dict:
        """
        现代法律裁断模块
        返回: 责任识别和程序路径提示
        """
        result = {
            'CR': False, 'AR': False, 'MR': False,
            'investigation': False, 'hearing': False, 'exemption': False,
            'found_criminal': [], 'found_admin': [], 'found_civil': [],
            'found_investigation': [], 'found_hearing': [], 'found_exemption': []
        }
        
        # 刑事责任
        for kw in self.criminal_keywords:
            if kw in text:
                result['CR'] = True
                result['found_criminal'].append(kw)
        for pattern in self.criminal_patterns:
            match = pattern.search(text)
            if match:
                result['CR'] = True
                result['found_criminal'].append(match.group())
        
        # 行政责任
        for kw in self.admin_keywords:
            if kw in text:
                result['AR'] = True
                result['found_admin'].append(kw)
        
        # 民事责任
        for kw in self.civil_keywords:
            if kw in text:
                result['MR'] = True
                result['found_civil'].append(kw)
        
        # 调查/审查程序
        for kw in self.investigation_keywords:
            if kw in text:
                result['investigation'] = True
                result['found_investigation'].append(kw)
        
        # 听证/审理程序
        for kw in self.hearing_keywords:
            if kw in text:
                result['hearing'] = True
                result['found_hearing'].append(kw)
        
        # 免责/减免程序
        for kw in self.exemption_keywords:
            if kw in text:
                result['exemption'] = True
                result['found_exemption'].append(kw)
        
        return result

    def calculate_J(self, M: int, E: int, N: int, Q: int) -> Tuple[int, str]:
        """
        计算春秋裁断值 J 并确定裁断结论
        J = M + E + N - Q
        """
        J = M + E + N - Q
        if J < 0:
            J = 0
        
        if J <= 2:
            verdict = "礼义无罪"
        elif J <= 7:
            verdict = "礼义可原"
        else:
            verdict = "礼义有罪"
        
        return J, verdict

    def format_output(self, results: List[Tuple[str, JudgmentResult]], include_reasoning: bool = True) -> str:
        """
        按要求格式输出裁断结果
        
        参数:
            results: 裁断结果列表
            include_reasoning: 是否包含推导逻辑（默认True）
        """
        output_parts = []
        
        for dossier_id, result in results:
            # 检查是否为要件缺失的情况
            if not result.is_valid:
                output_parts.append(f"卷宗编号{dossier_id} {result.subject}裁断结果")
                output_parts.append("")
                output_parts.append(result.invalid_reason)
                output_parts.append("")
                continue
            
            # 主权裁断部分
            output_parts.append(f"卷宗编号{dossier_id} {result.subject}主权裁断部分")
            output_parts.append("")
            
            # M项
            output_parts.append(f"（1）原心动机（M）项：M = {result.M}（{result.M_state}）")
            if include_reasoning and result.M_reasoning:
                output_parts.append("    【推导逻辑】")
                for line in result.M_reasoning.split('\n'):
                    output_parts.append(f"    {line}")
            output_parts.append("")
            
            # E项
            output_parts.append(f"（2）伦理位阶（E）项：E = {result.E}（{result.E_state}）")
            if include_reasoning and result.E_reasoning:
                output_parts.append("    【推导逻辑】")
                for line in result.E_reasoning.split('\n'):
                    output_parts.append(f"    {line}")
            output_parts.append("")
            
            # N项
            output_parts.append(f"（3）名分正当性（N）项：N = {result.N}（判定：{result.N_state}）")
            if include_reasoning and result.N_reasoning:
                output_parts.append("    【推导逻辑】")
                for line in result.N_reasoning.split('\n'):
                    output_parts.append(f"    {line}")
            output_parts.append("")
            
            # Q项
            if result.Q_note:
                output_parts.append(f"（4）权变修正（Q）项：Q = {result.Q}")
                output_parts.append(f"    说明：{result.Q_note}")
            elif result.Q == 0:
                output_parts.append(f"（4）权变修正（Q）项：Q = {result.Q}（判定：无权变触发）")
            else:
                output_parts.append(f"（4）权变修正（Q）项：Q = {result.Q}")
            if include_reasoning and result.Q_reasoning:
                output_parts.append("    【推导逻辑】")
                for line in result.Q_reasoning.split('\n'):
                    output_parts.append(f"    {line}")
            output_parts.append("")
            
            j_raw = result.M + result.E + result.N - result.Q
            if j_raw < 0:
                output_parts.append(f"（5）数值演算公式项：J = {result.M} + {result.E} + {result.N} - {result.Q} = {j_raw}，修正为 J = 0")
            else:
                output_parts.append(f"（5）数值演算公式项：J = {result.M} + {result.E} + {result.N} - {result.Q} = {result.J}")
            output_parts.append("")
            output_parts.append(f"（6）主权裁断结论项：【{result.verdict}】")
            output_parts.append("")
            
            # 现代法律裁断模块
            output_parts.append(f"卷宗编号{dossier_id}现代法律裁断识别（从属模块）")
            output_parts.append("")
            output_parts.append("（1）责任类型识别项：")
            cr_line = f"    - 刑事责任（CR）：[{'是' if result.CR else '否'}]"
            if result.CR and result.CR_basis:
                cr_line += f"（判别依据：{', '.join(result.CR_basis)}）"
            output_parts.append(cr_line)
            ar_line = f"    - 行政责任（AR）：[{'是' if result.AR else '否'}]"
            if result.AR and result.AR_basis:
                ar_line += f"（判别依据：{', '.join(result.AR_basis)}）"
            output_parts.append(ar_line)
            mr_line = f"    - 民事责任（MR）：[{'是' if result.MR else '否'}]"
            if result.MR and result.MR_basis:
                mr_line += f"（判别依据：{', '.join(result.MR_basis)}）"
            output_parts.append(mr_line)
            output_parts.append("")
            output_parts.append("（2）程序路径提示项：")
            inv_line = f"    - 是否涉及调查或审查程序：[{'是' if result.investigation_procedure else '否'}]"
            if result.investigation_procedure and result.investigation_basis:
                inv_line += f"（判别依据：{', '.join(result.investigation_basis)}）"
            output_parts.append(inv_line)
            if result.investigation_procedure:
                output_parts.append("      提示：存在调查或审查程序路径")
            hear_line = f"    - 是否涉及听证或审理程序：[{'是' if result.hearing_procedure else '否'}]"
            if result.hearing_procedure and result.hearing_basis:
                hear_line += f"（判别依据：{', '.join(result.hearing_basis)}）"
            output_parts.append(hear_line)
            if result.hearing_procedure:
                output_parts.append("      提示：存在听证或审理程序路径")
            exempt_line = f"    - 是否出现免责或减免程序表述：[{'是' if result.exemption_procedure else '否'}]"
            if result.exemption_procedure and result.exemption_basis:
                exempt_line += f"（判别依据：{', '.join(result.exemption_basis)}）"
            output_parts.append(exempt_line)
            if result.exemption_procedure:
                output_parts.append("      提示：存在免责或减免制度空间")
            output_parts.append("")
        
        # 结项声明
        output_parts.append("结项声明")
        output_parts.append("裁断程序已于卷宗世界内闭环终结。")
        
        return '\n'.join(output_parts)

    def _build_full_content(self, dossier_id: str, dossier: dict) -> str:
        """
        从结构化卷宗数据构建完整卷宗内容（用于E伦理位阶启动判定和现代法律模块）
        
        参数:
            dossier_id: 卷宗编号
            dossier: 卷宗字典，支持两种格式:
                - 简单卷宗: {title, subjects, 起因, 主体1, 主体2, ..., 结果}
                - 子页卷宗: {title, subjects, sub_pages: {A: {...}, B: {...}}, 起因, 结果}
        
        返回:
            构建的卷宗完整内容
        """
        parts = []
        
        # 卷宗级起因
        if '起因' in dossier:
            parts.append(dossier['起因'])
        
        # 检查是否有子页结构
        if 'sub_pages' in dossier:
            # 子页卷宗：遍历所有子页
            for page_id, page in dossier['sub_pages'].items():
                # 子页起因
                if '起因' in page:
                    parts.append(page['起因'])
                
                # 子页中各主体的行为描述
                page_subjects = page.get('subjects', [])
                for subj in page_subjects:
                    if subj in page:
                        parts.append(page[subj])
                
                # 子页行为描述补充
                if '行为描述补充' in page:
                    parts.append(page['行为描述补充'])
                
                # 子页结果
                if '结果' in page:
                    parts.append(page['结果'])
        else:
            # 简单卷宗：直接取各主体的行为描述
            subjects = dossier.get('subjects', [])
            for subject in subjects:
                if subject in dossier:
                    parts.append(dossier[subject])
            
            # 行为描述补充
            if '行为描述补充' in dossier:
                parts.append(dossier['行为描述补充'])
        
        # 卷宗级结果
        if '结果' in dossier:
            parts.append(dossier['结果'])
        
        return '\n'.join(parts)
    
    def _get_subject_text(self, dossier: dict, subject: str) -> str:
        """
        获取特定主体的行为描述文本（用于M、N、Q判定）
        
        规则（来自 test_cases.py 中的标准化用例）:
        - 简单卷宗: 直接取 dossier[subject]
        - 子页卷宗: 合并所有包含该主体的子页中的行为描述 + 行为描述补充
        
        参数:
            dossier: 卷宗字典
            subject: 主体名称
        
        返回:
            该主体的完整行为描述文本
        """
        # 检查是否有子页结构
        if 'sub_pages' not in dossier:
            # 简单卷宗
            text = dossier.get(subject, '')
            supplement = dossier.get('行为描述补充', '')
            return f"{text}\n{supplement}" if supplement else text
        
        # 子页卷宗：合并所有包含该主体的子页
        texts = []
        for page_id, page in dossier['sub_pages'].items():
            # 检查该主体是否在此子页中
            if subject in page:
                texts.append(page[subject])
            
            # 如果该主体在此子页的subjects列表中，也获取行为描述补充
            supplement = page.get('行为描述补充', '')
            if supplement and subject in page.get('subjects', []):
                texts.append(supplement)
        
        return '\n'.join(texts)

    def judge_standard(self, test_case: dict) -> Tuple[str, List[Tuple[str, JudgmentResult]]]:
        """
        使用标准化输入格式进行裁断
        
        参数:
            test_case: 标准化测试案例字典，包含:
                - dossiers: 卷宗字典，支持简单卷宗和子页卷宗两种格式
                - judgments: 裁断任务列表 [{dossier_id, subject}]
        
        裁断规则（来自 test_cases.py 和 benchmark rulebook）:
            - M(原心动机): 该主体的行为描述文本（跨子页合并）
              * 多子页M=5全局锁定：若任一子页M=5，则全局M=5
            - E(伦理位阶): 
                * 启动判定 = 全卷宗文本（仅判断是否存在伦理对象）
                * 取值判定 = 仅该主体的行为描述段落
                * 跨子页: 取最高E值
            - N(名分正当性): 该主体的行为描述文本（跨子页取最劣N值）
            - Q(权变修正): 
                * M=5时直接封死
                * 触发词检查 = 该主体的行为描述文本
                * 反向拦截检查 = 全卷宗文本（跨子页穿透）
            - 现代法律模块: 全部卷宗文本（所有卷宗所有子页）
        
        返回:
            (格式化输出字符串, 裁断结果列表)
        """
        dossiers = test_case['dossiers']
        judgment_tasks = test_case['judgments']
        
        # 构建所有卷宗的完整文本（用于现代法律模块）
        all_dossiers_text = '\n'.join([
            self._build_full_content(did, d) for did, d in dossiers.items()
        ])
        
        results = []
        
        for task in judgment_tasks:
            dossier_id = task['dossier_id']
            subject = task['subject']
            
            if dossier_id not in dossiers:
                raise ValueError(f"卷宗 {dossier_id} 不存在")
            
            dossier = dossiers[dossier_id]
            
            # 验证主体是否在卷宗的可裁断主体列表中
            if subject not in dossier['subjects']:
                raise ValueError(f"主体 {subject} 不在卷宗 {dossier_id} 的可裁断主体列表中")
            
            # 获取主体特定文本（用于M、E取值、N、Q触发词判定）
            subject_text = self._get_subject_text(dossier, subject)
            
            # 构建当前卷宗的完整内容（用于E启动判定和Q反向拦截检查）
            full_dossier_content = self._build_full_content(dossier_id, dossier)
            
            # 获取身份信息
            identities = dossier.get('identities', {})
            
            # 提取卷宗中的已知人名（来自subjects和identities字段）
            # 规则（来自system_prompt.md第六章第三节第3条）：具体人名是合法对象
            known_names = list(dossier.get('subjects', []))
            if identities:
                for name in identities.keys():
                    if name not in known_names:
                        known_names.append(name)
            
            # 对于子页卷宗，需要检查多子页穿透规则
            # 规则（来自system_prompt.md第十章第四节）
            sub_page_m_values = None
            sub_page_e_values = None
            sub_page_n_values = None
            sub_page_q_anti = None
            
            # 计算其他主体列表（当前卷宗中除当前 subject 以外的其他主体）
            other_subjects = [s for s in known_names if s != subject]
            
            # 检查卷宗级N模块是否启动（卷宗中是否存在身份/名分要素关键词）
            n_module_activated = self._is_n_module_activated(full_dossier_content, identities)
            
            if 'sub_pages' in dossier:
                # M=5全局锁定规则
                sub_page_m_values = self._check_subpage_M_values(dossier, subject, known_names, other_subjects)
                # E取最高值规则
                sub_page_e_values = self._check_subpage_E_values(dossier, subject)
                # N取最劣值规则
                sub_page_n_values = self._check_subpage_N_values(dossier, subject, identities, other_subjects, n_module_activated)
                # Q全局穿透拦截规则
                sub_page_q_anti = self._check_subpage_Q_anti_triggers(dossier, subject)
            
            # 执行裁断（传入主体文本、完整卷宗内容、所有卷宗文本、身份信息、子页检查结果、已知人名、其他主体）
            result = self.judge_subject_standard(
                subject_text=subject_text,
                subject=subject,
                full_dossier_content=full_dossier_content,
                all_dossiers_text=all_dossiers_text,
                identities=identities,
                sub_page_m_values=sub_page_m_values,
                sub_page_e_values=sub_page_e_values,
                sub_page_n_values=sub_page_n_values,
                sub_page_q_anti=sub_page_q_anti,
                known_names=known_names,
                other_subjects=other_subjects,
                n_module_activated=n_module_activated
            )
            results.append((dossier_id, result))
        
        output = self.format_output(results)
        return output, results
    
    def _check_subpage_M_values(self, dossier: dict, subject: str, known_names: List[str] = None, other_subjects: List[str] = None) -> Dict:
        """
        检查子页卷宗中各子页的M值
        
        规则（来自system_prompt.md第十章第四节第2条）：
        - 若该主人公在任一子页中被判定为M=5（志恶型），则全局M=5
        - 若各子页均为M=0（志善），则M=0
        - 若存在M=2（不明）与M=0并存，则以M=0计
        
        参数:
            dossier: 卷宗字典
            subject: 裁断主体名称
            known_names: 卷宗中已知的人名列表
        
        返回: {'has_evil': bool, 'has_good': bool, 'page_results': {page_id: M}}
        """
        result = {
            'has_evil': False,
            'has_good': False,
            'page_results': {}
        }
        
        if 'sub_pages' not in dossier:
            return result
        
        for page_id, page in dossier['sub_pages'].items():
            # 检查该主体是否在此子页中
            if subject not in page:
                continue
            
            page_text = page[subject]
            supplement = page.get('行为描述补充', '')
            if supplement and subject in page.get('subjects', []):
                page_text = f"{page_text}\n{supplement}"
            
            # 对该子页单独判定M值
            M, M_state, _, _ = self.judge_M(page_text, subject, known_names, other_subjects)
            result['page_results'][page_id] = M
            
            if M == 5:
                result['has_evil'] = True
            elif M == 0:
                result['has_good'] = True
        
        return result
    
    def _check_subpage_E_values(self, dossier: dict, subject: str) -> Dict:
        """
        检查子页卷宗中各子页的E值
        
        规则（来自system_prompt.md第十章第四节第3条）：
        - E（伦理位阶）取最高值：检索所有子页，取该主人公涉及的最高伦理位阶作为最终E值
        
        参数:
            dossier: 卷宗字典
            subject: 裁断主体名称
        
        返回: {'max_E': int, 'page_results': {page_id: E}}
        """
        result = {
            'max_E': 0,
            'page_results': {}
        }
        
        if 'sub_pages' not in dossier:
            return result
        
        for page_id, page in dossier['sub_pages'].items():
            # 检查该主体是否在此子页中
            if subject not in page:
                continue
            
            page_text = page[subject]
            supplement = page.get('行为描述补充', '')
            if supplement and subject in page.get('subjects', []):
                page_text = f"{page_text}\n{supplement}"
            
            # 对该子页单独判定E值
            E, E_state, _, _ = self.judge_E(page_text, subject)
            result['page_results'][page_id] = E
            
            if E > result['max_E']:
                result['max_E'] = E
        
        return result
    
    def _is_n_module_activated(self, full_dossier_content: str, identities: dict = None) -> bool:
        """
        检查N模块是否在卷宗级别启动
        
        规则（来自system_prompt.md第八章第二节）：
        卷宗内必须出现身份/名分要素关键词中的任一词汇，N模块即可启动。
        检查范围包括卷宗全文内容和所有主体的身份字段。
        """
        all_identity_keywords = []
        for cat_ids in self.identity_keywords.values():
            all_identity_keywords.extend(cat_ids)
        
        for kw in all_identity_keywords:
            if kw in full_dossier_content:
                return True
        
        if identities:
            for identity_desc in identities.values():
                for kw in all_identity_keywords:
                    if kw in identity_desc:
                        return True
        
        return False

    def _check_subpage_N_values(self, dossier: dict, subject: str, identities: dict = None, other_subjects: List[str] = None, n_module_activated: bool = False) -> Dict:
        """
        检查子页卷宗中各子页的N值
        
        规则（来自system_prompt.md第十章第四节第3条）：
        - N（名分正当性）取最劣值：若该主人公在任一子页中出现"名分不正"（N=5），则全案N值锁定为5
        
        参数:
            dossier: 卷宗字典
            subject: 裁断主体名称
            identities: 身份信息字典
        
        返回: {'has_improper': bool, 'max_N': int, 'page_results': {page_id: N}}
        """
        result = {
            'has_improper': False,
            'max_N': 0,
            'page_results': {}
        }
        
        if 'sub_pages' not in dossier:
            return result
        
        for page_id, page in dossier['sub_pages'].items():
            # 检查该主体是否在此子页中
            if subject not in page:
                continue
            
            page_text = page[subject]
            supplement = page.get('行为描述补充', '')
            if supplement and subject in page.get('subjects', []):
                page_text = f"{page_text}\n{supplement}"
            
            # 对该子页单独判定N值
            N, N_state, _, _ = self.judge_N_standard(page_text, subject, identities, other_subjects, n_module_activated)
            result['page_results'][page_id] = N
            
            if N == 5:
                result['has_improper'] = True
            if N > result['max_N']:
                result['max_N'] = N
        
        return result
    
    def _check_subpage_Q_anti_triggers(self, dossier: dict, subject: str) -> Dict:
        """
        检查子页卷宗中各子页的Q反向表述
        
        规则（来自system_prompt.md第十章第四节第4条）：
        - 若在任一子页中发现该主人公有"主动谋划"、"预先设计"等反向表述，
          则该主人公在所有子页中表现出的"情势紧急"均为伪装，Q强制锁定为0
        
        参数:
            dossier: 卷宗字典
            subject: 裁断主体名称
        
        返回: {'has_anti_trigger': bool, 'found_triggers': [], 'page_results': {page_id: [triggers]}}
        """
        result = {
            'has_anti_trigger': False,
            'found_triggers': [],
            'page_results': {}
        }
        
        if 'sub_pages' not in dossier:
            return result
        
        for page_id, page in dossier['sub_pages'].items():
            # 检查该主体是否在此子页中
            if subject not in page:
                continue
            
            page_text = page[subject]
            supplement = page.get('行为描述补充', '')
            if supplement and subject in page.get('subjects', []):
                page_text = f"{page_text}\n{supplement}"
            
            page_triggers = []
            
            # 检查主动谋划类反向表述
            for kw in self.anti_urgency_plan:
                if self._is_anti_trigger_valid(page_text, kw):
                    page_triggers.append(kw)
                    if kw not in result['found_triggers']:
                        result['found_triggers'].append(kw)
            
            # 检查从容选择类反向表述
            for kw in self.anti_urgency_choice:
                if self._is_anti_trigger_valid(page_text, kw):
                    page_triggers.append(kw)
                    if kw not in result['found_triggers']:
                        result['found_triggers'].append(kw)
            
            result['page_results'][page_id] = page_triggers
            
            if page_triggers:
                result['has_anti_trigger'] = True
        
        return result
    
    def judge_subject_standard(self, subject_text: str, subject: str, 
                                full_dossier_content: str, all_dossiers_text: str,
                                identities: dict = None,
                                sub_page_m_values: dict = None,
                                sub_page_e_values: dict = None,
                                sub_page_n_values: dict = None,
                                sub_page_q_anti: dict = None,
                                known_names: List[str] = None,
                                other_subjects: List[str] = None,
                                n_module_activated: bool = False) -> JudgmentResult:
        """
        对单一主体进行完整裁断（标准化版本）
        
        参数:
            subject_text: 该主体的行为描述文本（用于M、E取值、N、Q触发词判定）
            subject: 主体名称
            full_dossier_content: 当前卷宗完整内容（用于E启动判定、Q反向拦截检查）
            all_dossiers_text: 所有卷宗的完整文本（用于现代法律模块）
            identities: 卷宗中的身份信息字典 {人名: 身份描述}
            sub_page_m_values: 子页M值检查结果（用于M=5全局锁定）
            sub_page_e_values: 子页E值检查结果（用于E取最高值）
            sub_page_n_values: 子页N值检查结果（用于N取最劣值）
            sub_page_q_anti: 子页Q反向表述检查结果（用于Q全局穿透拦截）
            known_names: 卷宗中已知的人名列表（来自subjects和identities字段）
            other_subjects: 卷宗中的其他主体列表（用于过滤非当前主体的句子）
            n_module_activated: 卷宗级N模块是否已启动
        """
        result = JudgmentResult(subject=subject)
        
        # 判断M - 使用主体特定文本，传递已知人名列表和其他主体列表
        result.M, result.M_state, m_details, result.M_reasoning = self.judge_M(subject_text, subject, known_names, other_subjects)
        
        # 多子页M=5全局锁定规则（来自system_prompt.md第十章第四节第2条）
        # 若该主人公在任一子页中被判定为M=5，则全局M=5
        if sub_page_m_values and sub_page_m_values.get('has_evil'):
            if result.M != 5:
                # 有子页命中志恶，但合并文本未命中，需要强制锁定为M=5
                result.M = 5
                result.M_state = "志恶"
                result.M_reasoning += "\n\n【多子页穿透规则】"
                result.M_reasoning += "\n根据原心穿透原则：主体在某子页中被判定为M=5（志恶型），"
                result.M_reasoning += "全卷宗范围内的动机属性被永久锁定为M=5。"
                for page_id, m_val in sub_page_m_values['page_results'].items():
                    if m_val == 5:
                        result.M_reasoning += f"\n  - 子页{page_id}: M={m_val}（志恶）"
        elif sub_page_m_values and sub_page_m_values.get('has_good') and result.M == 2:
            # 若存在M=2（不明）与M=0并存，则以M=0计
            result.M = 0
            result.M_state = "志善"
            result.M_reasoning += "\n\n【多子页合并规则】"
            result.M_reasoning += "\n根据规则：若存在M=2与M=0并存，则以M=0计。"
        
        # 判断E - 使用主体特定文本进行取值判定
        result.E, result.E_state, e_details, result.E_reasoning = self.judge_E(subject_text, subject)
        
        # 多子页E取最高值规则（来自system_prompt.md第十章第四节第3条）
        if sub_page_e_values and sub_page_e_values.get('max_E', 0) > result.E:
            old_E = result.E
            result.E = sub_page_e_values['max_E']
            # 更新E状态描述
            if result.E == 5:
                result.E_state = "高位伦理"
            elif result.E == 3:
                result.E_state = "中位伦理"
            elif result.E == 1:
                result.E_state = "低位伦理"
            result.E_reasoning += "\n\n【多子页穿透规则】"
            result.E_reasoning += f"\n根据伦理从重原则：取所有子页中该主人公涉及的最高伦理位阶。"
            result.E_reasoning += f"\n合并文本判定E={old_E}，但子页中存在更高E值："
            for page_id, e_val in sub_page_e_values['page_results'].items():
                if e_val == sub_page_e_values['max_E']:
                    result.E_reasoning += f"\n  - 子页{page_id}: E={e_val}"
            result.E_reasoning += f"\n最终锁定 E = {result.E}（{result.E_state}）"
        
        # 判断N - 使用主体特定文本和身份信息，传入卷宗级N模块启动状态
        result.N, result.N_state, n_details, result.N_reasoning = self.judge_N_standard(
            subject_text, subject, identities, other_subjects, n_module_activated
        )
        
        # 多子页N取最劣值规则（来自system_prompt.md第十章第四节第3条）
        # 若该主人公在任一子页中出现"名分不正"（N=5），则全案N值锁定为5
        if sub_page_n_values and sub_page_n_values.get('has_improper'):
            if result.N != 5:
                old_N = result.N
                result.N = 5
                result.N_state = "名分不正"
                result.N_reasoning += "\n\n【多子页穿透规则】"
                result.N_reasoning += "\n根据名分从劣原则：若该主人公在任一子页中出现N=5（名分不正），则全案N值锁定为5。"
                result.N_reasoning += f"\n合并文本判定N={old_N}，但子页中存在N=5："
                for page_id, n_val in sub_page_n_values['page_results'].items():
                    if n_val == 5:
                        result.N_reasoning += f"\n  - 子页{page_id}: N={n_val}（名分不正）"
                result.N_reasoning += f"\n最终锁定 N = 5（名分不正）"
        
        # 判断Q - 使用主体特定文本进行触发词检查，使用完整卷宗内容进行反向拦截检查
        result.Q, result.Q_note, q_details, result.Q_reasoning = self.judge_Q_standard(
            subject_text, full_dossier_content, subject, result.M
        )
        
        # 多子页Q全局穿透拦截规则（来自system_prompt.md第十章第四节第4条）
        # 若在任一子页中发现该主人公有"主动谋划"、"预先设计"等反向表述，则Q强制锁定为0
        if sub_page_q_anti and sub_page_q_anti.get('has_anti_trigger') and result.Q > 0:
            old_Q = result.Q
            result.Q = 0
            result.Q_note = "多子页穿透：命中反向表述，权变修正被拦截"
            result.Q_reasoning += "\n\n【多子页穿透规则】"
            result.Q_reasoning += "\n根据权变修正的全局穿透原则：若在任一子页中发现该主人公有"
            result.Q_reasoning += "\"主动谋划\"、\"预先设计\"等反向表述，则所有子页中的\"情势紧急\"均为伪装，Q强制锁定为0。"
            result.Q_reasoning += f"\n合并文本判定Q={old_Q}，但子页中存在反向表述："
            for page_id, triggers in sub_page_q_anti['page_results'].items():
                if triggers:
                    result.Q_reasoning += f"\n  - 子页{page_id}: 命中「{'、'.join(triggers)}」"
            result.Q_reasoning += f"\n最终锁定 Q = 0"
        
        # 计算J
        result.J, result.verdict = self.calculate_J(result.M, result.E, result.N, result.Q)
        
        # 现代法律模块 - 使用裁断主体所在卷宗的完整文本（纯关键词扫描）
        # 根据system_prompt.md：对裁断主体所在卷宗全局进行法律/制度元素扫描
        modern = self.judge_modern_law(full_dossier_content)
        result.CR = modern['CR']
        result.CR_basis = modern['found_criminal']
        result.AR = modern['AR']
        result.AR_basis = modern['found_admin']
        result.MR = modern['MR']
        result.MR_basis = modern['found_civil']
        result.investigation_procedure = modern['investigation']
        result.investigation_basis = modern['found_investigation']
        result.hearing_procedure = modern['hearing']
        result.hearing_basis = modern['found_hearing']
        result.exemption_procedure = modern['exemption']
        result.exemption_basis = modern['found_exemption']
        
        return result
    
    def judge_N_standard(self, text: str, subject: str, identities: dict = None, other_subjects: List[str] = None, n_module_activated: bool = False) -> Tuple[int, str, Dict, str]:
        """
        判断名分正当性 N（标准化版本）
        返回: (N值, 状态描述, 判定详情, 推导逻辑)
        
        规则（来自system_prompt.md第八章）：
        N=5成立条件：同时满足以下两个条件，且二者处于同一句内：
        （1）身份/名分要素成立（满足任一即可）：
            a. 该句中直接出现身份/名分要素关键词；
            b. 该句主语为当前主体，且其身份字段描述包含身份/名分要素关键词；
        （2）越位/违名行为成立：该句中出现越位/违名行为触发关键词。
        
        其中"同一句"指两个要素之间不存在句号（。）、分号（；）或问号（？）
        
        - N=0: 名分正当（命中"依法履职"等）或N模块未启动
        - N=2: N模块已启动但主体未命中N=0或N=5（名分中性）
        - N=5: 同一句中同时满足身份要素+越位行为（名分不正）
        
        参数:
            text: 主体的行为描述文本
            subject: 主体名称
            identities: 卷宗中的身份信息字典 {人名: 身份描述}
            other_subjects: 其他主体列表
            n_module_activated: 卷宗级N模块是否已启动（卷宗中存在身份/名分要素关键词）
        """
        details = {'found_identity': [], 'found_transgression': [], 'found_legitimate': [], 
                   'matched_sentences': [], 'identity_from_field': None, 'subject_has_identity_role': False}
        reasoning_parts = []
        
        subject_text = self._extract_subject_text(text, subject)
        subject_sentences_text = self._get_subject_sentences(text, subject, other_subjects or [])
        
        # 检查正当名分词（优先判定N=0）
        for kw in self.legitimate_identity:
            if kw in subject_text:
                details['found_legitimate'].append(kw)
                ctx = self._extract_keyword_context(subject_text, kw)
                reasoning_parts.append(f"身份检查: 命中正当名分词「{kw}」")
                if ctx:
                    reasoning_parts.append(f"  原文: 「{ctx}」")
                reasoning_parts.append("结论: N = 0（名分正当）")
                return 0, "名分正当", details, '\n'.join(reasoning_parts)
        
        # 收集所有身份/名分要素关键词
        all_identity_keywords = []
        for cat_ids in self.identity_keywords.values():
            all_identity_keywords.extend(cat_ids)
        
        # 收集所有越位/违名行为触发词
        all_transgressions = self.transgression_strong + self.transgression_mid + self.transgression_weak
        
        # 检查主体在identities字段中的身份是否包含身份关键词
        subject_identity_keywords = []
        if identities and subject in identities:
            identity_desc = identities[subject]
            details['identity_from_field'] = identity_desc
            for kw in all_identity_keywords:
                if kw in identity_desc:
                    subject_identity_keywords.append(kw)
            if subject_identity_keywords:
                details['subject_has_identity_role'] = True
                reasoning_parts.append(f"身份字段检查: 主体「{subject}」的身份「{identity_desc}」包含身份词「{'、'.join(subject_identity_keywords)}」")
        
        # 按句号、分号、问号分割成句子
        sentences = re.split(r'[。；？]', subject_sentences_text)
        
        # 记录全局是否命中身份关键词（用于判定N=2）
        found_identity_in_any = False
        
        reasoning_parts.append("同句检查（身份要素 + 越位行为）:")
        
        # 逐句检查
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            
            # 路径a: 检查该句子中是否直接出现身份关键词
            identity_in_sent_direct = []
            for kw in all_identity_keywords:
                if kw in sent:
                    identity_in_sent_direct.append(kw)
                    found_identity_in_any = True
            
            # 路径b: 检查该句主语是否为当前主体，且主体身份字段包含身份关键词
            identity_from_subject_field = []
            if subject_identity_keywords and subject in sent:
                identity_from_subject_field = subject_identity_keywords
                found_identity_in_any = True
            
            # 合并两条路径的身份要素
            identity_in_sent = list(set(identity_in_sent_direct + identity_from_subject_field))
            
            # 检查该句子中的越位行为关键词
            transgression_in_sent = []
            for kw in all_transgressions:
                if self._match_keyword(sent, kw):
                    transgression_in_sent.append(kw)
            
            # 同一句中同时满足身份要素和越位行为 -> N=5
            if identity_in_sent and transgression_in_sent:
                details['found_identity'].extend(identity_in_sent)
                details['found_transgression'].extend(transgression_in_sent)
                details['matched_sentences'].append(sent)
                
                sent_display = sent if len(sent) <= 60 else sent[:60] + "..."
                reasoning_parts.append(f"  - 句子「{sent_display}」中:")
                if identity_in_sent_direct:
                    reasoning_parts.append(f"    路径a: 句中直接出现身份词「{'、'.join(identity_in_sent_direct)}」")
                if identity_from_subject_field:
                    reasoning_parts.append(f"    路径b: 主体「{subject}」出现在句中，其身份字段包含身份词「{'、'.join(identity_from_subject_field)}」")
                reasoning_parts.append(f"    越位行为词「{'、'.join(transgression_in_sent)}」")
                reasoning_parts.append("结论: 同一句中同时满足身份要素和越位行为，N = 5（名分不正）")
                return 5, "名分不正", details, '\n'.join(reasoning_parts)
        
        # 同句检查未命中N=5，进入同段落检查
        # 规则（system_prompt.md第八章第五节第3条）：
        # 同一行为段落内指两个要素位于同一段文字中，且该段落内未出现段落分隔符或空行分隔
        paragraphs = re.split(r'\n\s*\n', text)
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_identity_direct = []
            for kw in all_identity_keywords:
                if kw in para:
                    para_identity_direct.append(kw)
                    found_identity_in_any = True
            
            para_identity_from_field = []
            if subject_identity_keywords and subject in para:
                para_identity_from_field = subject_identity_keywords
                found_identity_in_any = True
            
            para_identity = list(set(para_identity_direct + para_identity_from_field))
            
            para_transgression = []
            for kw in all_transgressions:
                if self._match_keyword(para, kw):
                    para_transgression.append(kw)
            
            if para_identity and para_transgression:
                details['found_identity'].extend(para_identity)
                details['found_transgression'].extend(para_transgression)
                details['matched_sentences'].append(para)
                
                para_display = para.replace('\n', ' ')
                para_display = para_display if len(para_display) <= 80 else para_display[:80] + "..."
                reasoning_parts.append("")
                reasoning_parts.append("同段落检查（身份要素 + 越位行为）:")
                reasoning_parts.append(f"  - 段落「{para_display}」中:")
                if para_identity_direct:
                    reasoning_parts.append(f"    路径a: 段落中出现身份词「{'、'.join(para_identity_direct)}」")
                if para_identity_from_field:
                    reasoning_parts.append(f"    路径b: 主体「{subject}」出现在段落中，其身份字段包含身份词「{'、'.join(para_identity_from_field)}」")
                reasoning_parts.append(f"    越位行为词「{'、'.join(para_transgression)}」")
                reasoning_parts.append("结论: 同一行为段落中同时满足身份要素和越位行为，N = 5（名分不正）")
                return 5, "名分不正", details, '\n'.join(reasoning_parts)
        
        # 没有同句或同段落命中的情况
        if found_identity_in_any:
            reasoning_parts.append("  - 存在身份要素，但未与越位行为关键词出现在同一句中")
            reasoning_parts.append("结论: N = 2（名分中性）")
            return 2, "名分中性", details, '\n'.join(reasoning_parts)
        
        # 卷宗级N模块已启动，但主体行为描述中未命中身份要素，也未命中N=0或N=5
        if n_module_activated:
            reasoning_parts.append("  - 主体行为描述中未命中身份/名分要素，但卷宗级N模块已启动（卷宗中存在身份/名分要素关键词）")
            reasoning_parts.append("结论: N = 2（名分中性）")
            return 2, "名分中性", details, '\n'.join(reasoning_parts)
        
        reasoning_parts.append("  - 未命中任何身份/名分要素，且卷宗级N模块未启动")
        reasoning_parts.append("结论: N = 0（名分正当（N模块未启动））")
        return 0, "名分正当（N模块未启动）", details, '\n'.join(reasoning_parts)

    def judge_Q_standard(self, subject_text: str, full_dossier_content: str, 
                          subject: str, M: int) -> Tuple[int, str, Dict, str]:
        """
        判断权变修正 Q（标准化版本）
        
        规则（来自system_prompt.md第九章）:
        - M=5时Q封死
        - 触发词检查 = 该主体的行为描述文本
        - 反向拦截检查 = 该主体的行为描述文本（仅作用于发表该言论的主体本人）
        
        重要规则：
        - 反向表述的穿透否定效力，仅作用于发表该言论或实施该预谋的主体本人
        - 严禁跨主体借用反向表述
        - 全卷宗检索必须以"主体一致性"为前提
        
        参数:
            subject_text: 该主体的行为描述文本（用于触发词检查和反向拦截检查）
            full_dossier_content: 完整卷宗内容（不再用于反向拦截，因为需要主体一致性）
            subject: 主体名称
            M: 已判定的M值
        """
        details = {'found_strong': [], 'found_mid': [], 'found_weak': [], 
                   'found_anti_plan': [], 'found_anti_choice': []}
        reasoning_parts = []
        
        # M=5时Q封死
        if M == 5:
            reasoning_parts.append("M = 5（志恶型动机）已成立")
            reasoning_parts.append("结论: 权变通道封死，Q = 0")
            return 0, "命中志恶动机，权变通道封死", details, '\n'.join(reasoning_parts)
        
        # 第一步：检查是否命中权变触发词（Q模块启动前提）
        # 根据system_prompt.md：卷宗中出现至少一个合法权变触发关键词或关键句，否则Q不启动，直接记为Q=0
        reasoning_parts.append("触发词检查（主体行为描述）:")
        
        # 检查强触发
        for kw in self.urgency_strong:
            if self._match_keyword(subject_text, kw):
                details['found_strong'].append(kw)
        
        # 检查中触发
        for kw in self.urgency_mid:
            if self._match_keyword(subject_text, kw):
                details['found_mid'].append(kw)
        
        # 检查弱触发
        for kw in self.urgency_weak:
            if self._match_keyword(subject_text, kw):
                details['found_weak'].append(kw)
        
        # 判断是否有有效触发词（强/中触发）
        has_valid_trigger = bool(details['found_strong'] or details['found_mid'])
        
        if details['found_strong']:
            strong_ctx = self._extract_keyword_context(subject_text, details['found_strong'][0])
            reasoning_parts.append(f"  - 命中强触发词「{'、'.join(details['found_strong'])}」")
            if strong_ctx:
                reasoning_parts.append(f"    原文: 「{strong_ctx}」")
        elif details['found_mid']:
            mid_ctx = self._extract_keyword_context(subject_text, details['found_mid'][0])
            reasoning_parts.append(f"  - 命中中触发词「{'、'.join(details['found_mid'])}」")
            if mid_ctx:
                reasoning_parts.append(f"    原文: 「{mid_ctx}」")
        elif details['found_weak']:
            reasoning_parts.append(f"  - 仅命中弱触发词「{'、'.join(details['found_weak'])}」（不独立成立）")
        else:
            reasoning_parts.append("  - 未命中权变触发词")
        
        # 如果没有有效触发词，Q模块不启动，直接返回Q=0
        if not has_valid_trigger:
            reasoning_parts.append("结论: Q = 0（无权变触发）")
            return 0, "无权变触发", details, '\n'.join(reasoning_parts)
        
        # 第二步：有触发词的情况下，检查反向表述是否拦截
        # 根据system_prompt.md：反向表述的穿透否定效力，仅作用于发表该言论的主体本人
        reasoning_parts.append("")
        reasoning_parts.append("反向拦截检查（主体行为描述）:")
        
        # 主动谋划类
        for kw in self.anti_urgency_plan:
            if self._is_anti_trigger_valid(subject_text, kw):
                details['found_anti_plan'].append(kw)
        
        # 从容选择类
        for kw in self.anti_urgency_choice:
            if self._is_anti_trigger_valid(subject_text, kw):
                details['found_anti_choice'].append(kw)
        
        # 如果有有效的反向表述，则权变被拦截，Q=0
        if details['found_anti_plan'] or details['found_anti_choice']:
            all_anti = details['found_anti_plan'] + details['found_anti_choice']
            anti_ctx = self._extract_keyword_context(subject_text, all_anti[0])
            reasoning_parts.append(f"  - 命中反向表述「{'、'.join(all_anti)}」（非否定语境）")
            if anti_ctx:
                reasoning_parts.append(f"    原文: 「{anti_ctx}」")
            reasoning_parts.append("结论: 命中反向表述，权变修正被拦截，Q = 0")
            return 0, "命中反向表述，权变修正被拦截", details, '\n'.join(reasoning_parts)
        else:
            reasoning_parts.append("  - 未命中有效反向表述（或在否定语境中）")
        
        # 第三步：有触发词且无反向表述拦截，权变成立
        if details['found_strong']:
            reasoning_parts.append("结论: 锁定 Q = 3（强权变成立）")
            return 3, "", details, '\n'.join(reasoning_parts)
        else:
            reasoning_parts.append("结论: 锁定 Q = 1（弱权变成立）")
            return 1, "", details, '\n'.join(reasoning_parts)

    def verify_results(self, results: List[Tuple[str, JudgmentResult]], 
                       expected: dict) -> dict:
        """
        验证裁断结果是否符合预期
        
        参数:
            results: judge_standard返回的裁断结果列表
            expected: expected_results字典 {(dossier_id, subject): {M, E, N, Q, J, ...}}
        
        返回:
            验证报告字典
        """
        report = {
            'total': len(results),
            'passed': 0,
            'failed': 0,
            'details': []
        }
        
        for dossier_id, result in results:
            key = (dossier_id, result.subject)
            
            if key not in expected:
                report['details'].append({
                    'dossier_id': dossier_id,
                    'subject': result.subject,
                    'status': 'SKIP',
                    'message': '无预期结果'
                })
                continue
            
            exp = expected[key]
            errors = []
            
            # 检查主权裁断各项数值
            if result.M != exp.get('M'):
                errors.append(f"M: 期望{exp.get('M')}, 实际{result.M}")
            if result.E != exp.get('E'):
                errors.append(f"E: 期望{exp.get('E')}, 实际{result.E}")
            if result.N != exp.get('N'):
                errors.append(f"N: 期望{exp.get('N')}, 实际{result.N}")
            if result.Q != exp.get('Q'):
                errors.append(f"Q: 期望{exp.get('Q')}, 实际{result.Q}")
            if result.J != exp.get('J'):
                errors.append(f"J: 期望{exp.get('J')}, 实际{result.J}")
            if result.verdict != exp.get('verdict'):
                errors.append(f"verdict: 期望{exp.get('verdict')}, 实际{result.verdict}")
            
            # 检查现代法律裁断识别部分
            if 'CR' in exp and result.CR != exp.get('CR'):
                errors.append(f"CR(刑事责任): 期望{exp.get('CR')}, 实际{result.CR}")
            if 'AR' in exp and result.AR != exp.get('AR'):
                errors.append(f"AR(行政责任): 期望{exp.get('AR')}, 实际{result.AR}")
            if 'MR' in exp and result.MR != exp.get('MR'):
                errors.append(f"MR(民事责任): 期望{exp.get('MR')}, 实际{result.MR}")
            if 'investigation_procedure' in exp and result.investigation_procedure != exp.get('investigation_procedure'):
                errors.append(f"调查程序: 期望{exp.get('investigation_procedure')}, 实际{result.investigation_procedure}")
            if 'hearing_procedure' in exp and result.hearing_procedure != exp.get('hearing_procedure'):
                errors.append(f"听证程序: 期望{exp.get('hearing_procedure')}, 实际{result.hearing_procedure}")
            if 'exemption_procedure' in exp and result.exemption_procedure != exp.get('exemption_procedure'):
                errors.append(f"免责程序: 期望{exp.get('exemption_procedure')}, 实际{result.exemption_procedure}")
            
            if errors:
                report['failed'] += 1
                report['details'].append({
                    'dossier_id': dossier_id,
                    'subject': result.subject,
                    'status': 'FAILED',
                    'errors': errors
                })
            else:
                report['passed'] += 1
                report['details'].append({
                    'dossier_id': dossier_id,
                    'subject': result.subject,
                    'status': 'PASSED'
                })
        
        return report




def generate_rubrics(results: List[Tuple[str, JudgmentResult]]) -> str:
    """
    根据裁断结果生成评判标准(rubrics)
    
    参数:
        results: 裁断结果列表 [(dossier_id, JudgmentResult), ...]
    
    返回:
        rubrics字符串
    """
    rubrics_parts = []
    rubric_num = 1
    
    # 1. 检查是否包含所有主权裁断部分和现代法律裁断部分
    subject_parts = []
    modern_parts = []
    for dossier_id, result in results:
        subject_parts.append(f"卷宗编号{dossier_id} {result.subject}主权裁断部分")
        modern_parts.append(f"卷宗编号{dossier_id}现代法律裁断识别（从属模块）")
    
    all_parts = subject_parts + modern_parts
    parts_str = '、'.join(['"' + p + '"' for p in all_parts])
    # rubrics_parts.append(f"{rubric_num}. 模型回复是否包含{parts_str}部分？")
    # rubric_num += 1
    
    # 2. 为每个主体生成主权裁断部分的rubric
    for dossier_id, result in results:
        # M状态描述
        m_desc = f"M = {result.M}（{result.M_state}）"
        # E状态描述
        e_desc = f"E = {result.E}（{result.E_state}）"
        # N状态描述
        if result.N == 0 and result.N_state == "名分正当（N模块未启动）":
            n_desc = "N = 0（名分正当；表述为N模块未启动或名分要素缺失亦可）"
        else:
            n_desc = f"N = {result.N}（{result.N_state}）"
        # Q描述
        q_desc = f"Q = {result.Q}"
        
        # J公式：若计算结果小于0，须追加"修正为 J = 0"
        j_raw = result.M + result.E + result.N - result.Q
        if j_raw < 0:
            j_formula = f"J = {result.M} + {result.E} + {result.N} - {result.Q} = {j_raw}，修正为 J = 0"
        else:
            j_formula = f"J = {result.M} + {result.E} + {result.N} - {result.Q} = {result.J}"
        
        # Q说明
        q_notes = []
        if result.Q_note:
            q_notes.append(f"{result.Q_note}")
        
        rubric_text = f'{rubric_num}. 模型回复的"卷宗编号{dossier_id} {result.subject}主权裁断部分"中是否判定{m_desc}、{e_desc}、{n_desc}、{q_desc}；数值演算公式项为{j_formula}；主权裁断结论项为"【{result.verdict}】"'
        
        if q_notes:
            q_note = '、'.join(q_notes)
            rubric_text += f'；且权变修正（Q）项中包含"{q_note}"'
        
        rubric_text += '？（注：主权裁断结论须写作带【】方括号的标签，如“【礼义有罪】”；未带方括号视为不满足。）'
        rubrics_parts.append(rubric_text)
        rubric_num += 1
    
    # 3. 为每个卷宗生成现代法律裁断部分的rubric（按卷宗去重，同一卷宗只生成一次）
    processed_dossiers = set()
    for dossier_id, result in results:
        if dossier_id in processed_dossiers:
            continue
        processed_dossiers.add(dossier_id)
        
        cr_str = "是" if result.CR else "否"
        ar_str = "是" if result.AR else "否"
        mr_str = "是" if result.MR else "否"
        inv_str = "是" if result.investigation_procedure else "否"
        hear_str = "是" if result.hearing_procedure else "否"
        exempt_str = "是" if result.exemption_procedure else "否"
        
        # 构建合并的检查文本：责任类型识别 + 程序路径提示
        combined_check = f'{rubric_num}. 模型回复的"卷宗编号{dossier_id}现代法律裁断识别（从属模块）"中责任类型识别项（CR/AR/MR）是否分别判定为"[{cr_str}]"、"[{ar_str}]"、"[{mr_str}]"；程序路径提示项是否包含调查程序为"[{inv_str}]"、听证程序为"[{hear_str}]"、免责程序为"[{exempt_str}]"'
        
        # 添加程序路径提示语句的检查
        procedure_hints = []
        if result.investigation_procedure:
            procedure_hints.append('"存在调查或审查程序路径"')
        if result.hearing_procedure:
            procedure_hints.append('"存在听证或审理程序路径"')
        if result.exemption_procedure:
            procedure_hints.append('"存在免责或减免制度空间"')
        
        if procedure_hints:
            combined_check += f'；且包含提示语句{("、".join(procedure_hints))}'
        
        combined_check += '？'
        rubrics_parts.append(combined_check)
        rubric_num += 1
    
    # 4. 结项声明
    rubrics_parts.append(f'{rubric_num}. 模型回复是否包含"结项声明"且结项声明为"裁断程序已于卷宗世界内闭环终结。"？')
    
    return '\n'.join(rubrics_parts)

def verified_chunqiu(test_case):
    """
    判案手册验证函数
    
    参数:
        test_case: 测试用例
    
    返回:
        str: 验证结果
    """
    judge = ChunqiuJudge()
    case = test_case
    report = []
    # 显示裁断任务
    report.append("\n裁断任务:")
    for task in case['judgments']:
        report.append(f"  - 卷宗: {task['dossier_id']}, 主体: {task['subject']}")
    
    # 执行裁断
    output, results = judge.judge_standard(case)
    report.append("\n裁断结果:")
    report.append("-" * 40)
    report.append(output)
    report.append("-" * 40)
    
    # 生成并输出rubrics
    rubrics = generate_rubrics(results)
    report.append("\n" + "=" * 60)
    report.append("【Checklist】")
    report.append("=" * 60)
    report.append(rubrics)
    report.append("=" * 60)
    
    # 验证结果
    # if 'expected_results' in case:
    #     report_verify = judge.verify_results(results, case['expected_results'])
    #     report.append(f"\n验证结果: 通过 {report_verify['passed']}/{report_verify['total']}")
    #     for detail in report_verify['details']:
    #         if detail['status'] == 'FAILED':
    #             report.append(f"  ❌ {detail['dossier_id']}/{detail['subject']}: {detail['errors']}")
    #         elif detail['status'] == 'PASSED':
    #             report.append(f"  ✓ {detail['dossier_id']}/{detail['subject']}: 通过")
    report_all = '\n'.join(report)
    return report_all

def run_test_standard():
    """运行标准化测试案例（推荐）"""
    try:
        from .test_cases import test_cases_standard, generate_background, generate_question
    except ImportError:
        from test_cases import test_cases_standard, generate_background, generate_question
    
    judge = ChunqiuJudge()
    
    for case_id, case in test_cases_standard.items():
        print(f"\n{'='*60}")
        print(f"测试案例 {case_id}: {case.get('case_name', '')} (标准化格式)")
        print(f"{'='*60}")
        
        # 显示裁断任务
        print("\n裁断任务:")
        for task in case['judgments']:
            print(f"  - 卷宗: {task['dossier_id']}, 主体: {task['subject']}")
        
        # 生成并输出【发送给模型的卷宗原文】
        background = generate_background(case)
        question = generate_question(case)
        
        # print("\n" + "=" * 60)
        # print("【发送给模型的卷宗原文】")
        # print("=" * 60)
        # print(background)
        # print("\n【裁断指令】")
        # print(question)
        # print("=" * 60)
        
        # 执行裁断
        output, results = judge.judge_standard(case)
        
        # print("\n裁断结果:")
        # print("-" * 40)
        # print(output)
        # print("-" * 40)
        
        # # 生成并输出rubrics
        # rubrics = generate_rubrics(results)
        # print("\n" + "=" * 60)
        # print("【生成的Rubrics评判标准】")
        # print("=" * 60)
        # print(rubrics)
        # print("=" * 60)
        
        # 验证结果
        if 'expected_results' in case:
            report = judge.verify_results(results, case['expected_results'])
            print(f"\n验证结果: 通过 {report['passed']}/{report['total']}")
            for detail in report['details']:
                if detail['status'] == 'FAILED':
                    print(f"  ❌ {detail['dossier_id']}/{detail['subject']}: {detail['errors']}")
                elif detail['status'] == 'PASSED':
                    print(f"  ✓ {detail['dossier_id']}/{detail['subject']}: 通过")


if __name__ == "__main__":
    # usage: python -m code_simulation_engines.decision_tree_state_machine.rule_based_adjudication.rule_based_adjudication [question id], e.g. adjudication_1
    import ast
    import json
    import sys
    from pathlib import Path

    qid = sys.argv[1] if len(sys.argv) > 1 else "adjudication_1"
    with open(Path(__file__).resolve().parents[2] / "structured_inputs.jsonl", encoding="utf-8") as f:
        rows = {r["id"]: r for r in map(json.loads, f)}
    raw = rows[qid]["structured_input"]
    try:
        case = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        case = json.loads(raw)
    print(verified_chunqiu(case))
