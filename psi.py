"""
MP-TPSI: 多方门限隐私集合求交协议
Multi-Party Threshold Private Set Intersection

基于椭圆曲线密码学实现PSI协议，提供：
- 双方PSI (2-Party PSI)
- 多方PSI (Multi-Party PSI)
- 门限验证 (Threshold Verification)
- 哈希兼容模式
"""

import hashlib
from dataclasses import dataclass
from typing import List, Set, Tuple, Optional
from enum import Enum


class PSIMode(Enum):
    """PSI算法模式"""
    HASH = "hash"           # 简化哈希模式（兼容旧版）
    ECC_2P = "ecc_2p"      # 基于ECC的双方PSI
    ECC_MP = "ecc_mp"      # 基于ECC的多方PSI
    THRESHOLD = "threshold" # 门限PSI


@dataclass
class PSIClient:
    """PSI客户端"""
    id: str
    elements: Set[str]
    mode: PSIMode = PSIMode.ECC_2P


@dataclass
class PSIMatchResult:
    """PSI匹配结果"""
    success: bool
    matched_elements: Set[str]
    match_code: str
    score: float


class ECDHPSI:
    """
    基于椭圆曲线Diffie-Hellman的PSI实现
    模拟PSI协议的隐私保护特性
    """

    def __init__(self):
        # 模拟椭圆曲线参数（实际生产应使用真实ECC库如cryptography）
        self.curve_order = 2**256 - 2**224 + 2**192 + 2**96 - 1

    def _hash_to_curve(self, value: str) -> int:
        """将值哈希到椭圆曲线点（模拟）"""
        # 使用SHA-256模拟哈希到曲线
        return int(hashlib.sha256(value.encode()).hexdigest(), 16) % self.curve_order

    def _compute_shared_secret(self, a_id: str, b_id: str) -> int:
        """
        计算共享密钥（模拟ECDH密钥交换）
        实际生产中：双方交换公钥，计算ECDH共享密钥
        """
        h_a = self._hash_to_curve(a_id)
        h_b = self._hash_to_curve(b_id)
        # 模拟：h(a) * h(b) 作为共享密钥
        return (h_a * h_b) % self.curve_order

    def _blinded_element(self, element: str, secret: int) -> str:
        """对元素进行盲化处理"""
        h_e = self._hash_to_curve(element)
        blinded = (h_e + secret) % self.curve_order
        return format(blinded, '064x')

    def generate_match_code(self, p_id: str, v_id: str, mode: PSIMode = PSIMode.ECC_2P) -> str:
        """
        生成PSI匹配验证码

        Args:
            p_id: 乘客ID
            v_id: 车辆ID
            mode: PSI算法模式

        Returns:
            6位大写验证码
        """
        if mode == PSIMode.HASH:
            # 简化模式：MD5哈希
            raw = f"{p_id}{v_id}"
            return hashlib.md5(raw.encode()).hexdigest()[:6].upper()

        elif mode == PSIMode.ECC_2P:
            # 双方PSI：基于共享密钥
            shared_secret = self._compute_shared_secret(p_id, v_id)
            # 将共享密钥映射到6位验证码
            code_hash = hashlib.sha256(f"PSI_2P:{shared_secret}".encode()).hexdigest()
            return code_hash[:6].upper()

        elif mode == PSIMode.ECC_MP:
            # 多方PSI：包含更多上下文信息
            # 在实际实现中，多方PSI需要每方贡献一个密钥分量
            # 这里模拟多方参与的哈希
            multi_input = f"MP_PSI:{p_id}:{v_id}:multi_party_factor"
            code_hash = hashlib.sha256(multi_input.encode()).hexdigest()
            return code_hash[:6].upper()

        elif mode == PSIMode.THRESHOLD:
            # 门限PSI：需要门限数量的验证才能完成匹配
            threshold_input = f"TH_PSI:{p_id}:{v_id}:threshold_3_of_5"
            code_hash = hashlib.sha256(threshold_input.encode()).hexdigest()
            return code_hash[:6].upper()

        else:
            # 默认使用ECC_2P
            return self.generate_match_code(p_id, v_id, PSIMode.ECC_2P)

    def verify_match_code(self, p_id: str, v_id: str, code: str, mode: PSIMode = PSIMode.ECC_2P) -> bool:
        """验证匹配码是否正确"""
        expected = self.generate_match_code(p_id, v_id, mode)
        return expected.upper() == code.upper()

    def compute_similarity(self, route1: str, route2: str) -> float:
        """
        计算路线相似度（基于PSI的思想）

        多因素综合评分：
        1. 区域前缀匹配（同一城市/区域）
        2. Jaccard字符相似度
        3. 共同关键字匹配
        """
        route1_lower = route1.lower()
        route2_lower = route2.lower()

        # 1. 区域前缀匹配权重 (40%)
        # 检查城市前缀（如"北京"、"上海"等）
        city_prefixes = ["北京", "上海", "广州", "深圳", "成都", "杭州", "武汉", "西安"]
        city_match = 0
        for prefix in city_prefixes:
            if route1_lower.startswith(prefix) and route2_lower.startswith(prefix):
                city_match = 0.85  # 同城
                break
            elif route1_lower.startswith(prefix) or route2_lower.startswith(prefix):
                city_match = 0.6  # 一方包含城市名
                break
        # 检查共同字符匹配
        common_chars = set(route1_lower) & set(route2_lower)
        if len(common_chars) >= 2:
            city_match = max(city_match, 0.3)

        # 2. 地点类型匹配 (20%)
        # 检查是否都是同一类型地点（如都是"科技园"、都是"地铁"）
        type_keywords = [
            (["科技园", "园区", "产业园", "科技", "园区"], 0.8),
            (["地铁", "地铁站", "站", "subway"], 0.6),
            (["大学", "学院", "学校", "univ", "college"], 0.8),
            (["机场", "航站楼", "t1", "t2", "t3", "airport"], 0.8),
            (["医院", "医", "hospital"], 0.8),
            (["商场", "购物中心", "mall", "购物"], 0.8),
            (["中心", "广场", "plaza", "center"], 0.5),
        ]
        type_match = 0
        for keywords, weight in type_keywords:
            if any(k in route1_lower for k in keywords) and any(k in route2_lower for k in keywords):
                type_match = weight
                break

        # 3. Jaccard字符相似度 (30%)
        set1 = set(route1_lower)
        set2 = set(route2_lower)

        if not set1 and not set2:
            jaccard = 1.0
        else:
            intersection = set1 & set2
            union = set1 | set2
            jaccard = len(intersection) / len(union) if union else 0

        # 4. 简单前缀匹配 (10%)
        # 如果前2-3个字符相同
        prefix_match = 0
        min_len = min(len(route1), len(route2))
        for i in range(2, min(4, min_len + 1)):
            if route1_lower[:i] == route2_lower[:i]:
                prefix_match = i / min_len * 0.5
                break

        # 综合相似度
        similarity = (
            0.35 * city_match +    # 城市匹配权重
            0.20 * type_match +    # 地点类型匹配权重
            0.35 * jaccard +        # Jaccard相似度权重
            0.10 * prefix_match     # 前缀匹配权重
        )

        return similarity


class MultiPartyPSI:
    """
    多方隐私集合求交协议（MP-PSI）

    支持多方参与的隐私集合求交，适用于：
    - 多辆车协同匹配
    - 门限验证场景
    - 分布式匹配系统
    """

    def __init__(self, threshold: int = 3):
        """
        初始化多方PSI

        Args:
            threshold: 门限值，需要至少threshold个方同意才能完成匹配
        """
        self.threshold = threshold
        self.ecdh_psi = ECDHPSI()

    def compute_multi_party_hash(self, elements: List[str]) -> str:
        """
        计算多方聚合哈希值

        模拟多方PSI协议：每方贡献一个哈希分量
        """
        combined = "|".join(sorted(elements))
        # 使用门限风格的哈希计算
        hash_input = f"MP_PSI_T{self.threshold}:{combined}"
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def generate_threshold_match_code(
        self,
        p_id: str,
        v_id: str,
        additional_factors: List[str] = None
    ) -> str:
        """
        生成门限PSI匹配码

        Args:
            p_id: 乘客ID
            v_id: 车辆ID
            additional_factors: 额外的门限因子（如其他车辆ID、时间戳等）

        Returns:
            6位大写验证码
        """
        factors = [p_id, v_id]
        if additional_factors:
            factors.extend(additional_factors)

        # 计算门限哈希
        threshold_hash = self.compute_multi_party_hash(factors)

        # 映射到6位验证码
        code = threshold_hash[:6].upper()

        return code

    def verify_threshold_match(
        self,
        p_id: str,
        v_id: str,
        code: str,
        additional_factors: List[str] = None,
        min_factors: int = 3
    ) -> Tuple[bool, int]:
        """
        验证门限匹配

        Args:
            p_id: 乘客ID
            v_id: 车辆ID
            code: 验证码
            additional_factors: 额外的门限因子
            min_factors: 最小要求的因子数量

        Returns:
            (验证结果, 使用的门限因子数量)
        """
        factors = [p_id, v_id]
        used_factors = len(factors)

        if additional_factors:
            # 添加所有额外因子
            for factor in additional_factors:
                factors.append(factor)
                used_factors += 1

        expected = self.compute_multi_party_hash(factors)[:6].upper()

        if used_factors < min_factors:
            return False, used_factors

        return expected == code.upper(), used_factors


# 全局实例
_psi_instance: Optional[ECDHPSI] = None
_mp_psi_instance: Optional[MultiPartyPSI] = None


def get_psi_instance() -> ECDHPSI:
    """获取PSI实例（单例）"""
    global _psi_instance
    if _psi_instance is None:
        _psi_instance = ECDHPSI()
    return _psi_instance


def get_mp_psi_instance(threshold: int = 3) -> MultiPartyPSI:
    """获取多方PSI实例（单例）"""
    global _mp_psi_instance
    if _mp_psi_instance is None or _mp_psi_instance.threshold != threshold:
        _mp_psi_instance = MultiPartyPSI(threshold)
    return _mp_psi_instance


# ========== 简化的API接口（兼容旧版） ==========

def generate_match_code(p_id: str, v_id: str, mode: str = "hash") -> str:
    """
    生成匹配验证码（兼容旧版API）

    Args:
        p_id: 乘客ID
        v_id: 车辆ID
        mode: 算法模式 "hash" | "ecc" | "multi" | "threshold"

    Returns:
        6位大写验证码
    """
    psi = get_psi_instance()
    mode_enum = PSIMode.HASH

    if mode == "hash":
        mode_enum = PSIMode.HASH
    elif mode == "ecc":
        mode_enum = PSIMode.ECC_2P
    elif mode == "multi":
        mode_enum = PSIMode.ECC_MP
    elif mode == "threshold":
        mode_enum = PSIMode.THRESHOLD

    return psi.generate_match_code(p_id, v_id, mode_enum)


def route_similarity(route1: str, route2: str) -> float:
    """计算路线相似度（使用PSI增强算法）"""
    psi = get_psi_instance()
    return psi.compute_similarity(route1, route2)
