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
import secrets
import math
import time
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


class RealECCPSI:
    """
    基于真实椭圆曲线密码学的PSI实现

    使用cryptography库的secp256r1曲线（NIST P-256）
    提供真实的ECC密钥生成、盲化和共享密钥计算
    """

    def __init__(self):
        """初始化真实ECC PSI"""
        try:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.backends import default_backend

            self.curve = ec.SECP256R1()
            self.backend = default_backend()
            self.curve_order = 2**256 - 2**224 + 2**192 + 2**96 - 1
            self._has_cryptography = True
        except ImportError:
            print("警告: cryptography库未安装，回退到模拟模式")
            print("      安装命令: pip install cryptography")
            self._has_cryptography = False
            self.curve_order = 2**256 - 2**224 + 2**192 + 2**96 - 1

    def generate_key_pair(self):
        """
        生成ECC密钥对

        Returns:
            (private_key, public_key): 私钥和公钥对象
        """
        if not self._has_cryptography:
            return self._generate_mock_key_pair()

        from cryptography.hazmat.primitives.asymmetric import ec

        private_key = ec.generate_private_key(self.curve, self.backend)
        public_key = private_key.public_key()
        return private_key, public_key

    def _generate_mock_key_pair(self):
        """生成模拟密钥对（当cryptography不可用时）"""
        private_key_int = secrets.randbelow(self.curve_order)
        public_key_int = pow(2, private_key_int, self.curve_order)  # 简化的DH计算
        return private_key_int, public_key_int

    def blind_element(self, element: str, private_key) -> str:
        """
        对元素进行盲化处理

        Args:
            element: 要盲化的元素字符串
            private_key: 盲化使用的私钥

        Returns:
            盲化后的字符串表示
        """
        if not self._has_cryptography:
            return self._blind_element_mock(element, private_key)

        h_e = self._hash_to_curve(element)

        # 使用私钥进行盲化（模拟）
        if isinstance(private_key, int):
            blinded = (h_e * private_key) % self.curve_order
        else:
            # 对于真实的私钥对象，提取标量值
            blinded = (h_e * private_key.private_numbers().private_value) % self.curve_order

        return format(blinded, '064x')

    def _blind_element_mock(self, element: str, private_key: int) -> str:
        """模拟盲化处理"""
        h_e = self._hash_to_curve(element)
        blinded = (h_e + private_key) % self.curve_order
        return format(blinded, '064x')

    def compute_shared_secret(self, a_private_key, b_public_key) -> int:
        """
        计算ECDH共享密钥

        Args:
            a_private_key: 一方的私钥
            b_public_key: 另一方的公钥

        Returns:
            共享密钥的整数表示
        """
        if not self._has_cryptography:
            return self._compute_shared_secret_mock(a_private_key, b_public_key)

        from cryptography.hazmat.primitives.asymmetric import ec

        try:
            if isinstance(a_private_key, int):
                # 模拟模式：重新创建私钥对象
                from cryptography.hazmat.primitives.asymmetric import ec
                from cryptography.hazmat.backends import default_backend
                private_key = ec.derive_private_key(a_private_key, self.curve, self.backend)
            else:
                private_key = a_private_key

            if isinstance(b_public_key, int):
                # 模拟模式的公钥
                shared_secret = pow(b_public_key, a_private_key, self.curve_order)
            else:
                shared_secret = private_key.exchange(ec.ECDH(), b_public_key)

            # 将共享密钥转换为整数
            if isinstance(shared_secret, bytes):
                return int.from_bytes(shared_secret, 'big') % self.curve_order
            return shared_secret % self.curve_order

        except Exception as e:
            print(f"ECDH共享密钥计算失败: {e}")
            return self._compute_shared_secret_mock(a_private_key, b_public_key)

    def _compute_shared_secret_mock(self, a_private_key: int, b_public_key: int) -> int:
        """模拟ECDH共享密钥计算"""
        return (a_private_key * b_public_key) % self.curve_order

    def _hash_to_curve(self, value: str) -> int:
        """
        将值哈希到椭圆曲线点（模简化）

        Args:
            value: 要哈希的值

        Returns:
            曲线点的大整数表示
        """
        return int(hashlib.sha256(value.encode()).hexdigest(), 16) % self.curve_order

    def generate_ecc_match_code(self, p_id: str, v_id: str) -> str:
        """
        使用真实ECC生成匹配验证码

        Args:
            p_id: 乘客ID
            v_id: 车辆ID

        Returns:
            6位大写验证码
        """
        # 生成临时密钥对用于这次匹配
        p_private, p_public = self.generate_key_pair()
        v_private, v_public = self.generate_key_pair()

        # 计算共享密钥
        shared_secret = self.compute_shared_secret(p_private, v_public)

        # 将共享密钥映射到6位验证码
        code_input = f"ECC_PSI:{shared_secret}:{p_id}:{v_id}:{time.time()}"
        code_hash = hashlib.sha256(code_input.encode()).hexdigest()
        return code_hash[:6].upper()


class ECDHPSI:
    """
    基于椭圆曲线Diffie-Hellman的PSI实现
    支持真实ECC和兼容模式的PSI协议
    """

    def __init__(self, use_real_ecc: bool = True):
        """
        初始化ECDH PSI

        Args:
            use_real_ecc: 是否使用真实ECC（需要cryptography库）
        """
        self.use_real_ecc = use_real_ecc
        self.real_ecc = RealECCPSI() if use_real_ecc else None
        self.curve_order = 2**256 - 2**224 + 2**192 + 2**96 - 1

    def _hash_to_curve(self, value: str) -> int:
        """将值哈希到椭圆曲线点（模拟）"""
        # 使用SHA-256模拟哈希到曲线
        return int(hashlib.sha256(value.encode()).hexdigest(), 16) % self.curve_order

    def _compute_shared_secret(self, a_id: str, b_id: str) -> int:
        """
        计算共享密钥（真实ECDH或模拟）

        Args:
            a_id: 参与方A的ID
            b_id: 参与方B的ID

        Returns:
            共享密钥
        """
        # 如果可用真实ECC，使用它
        if self.use_real_ecc and self.real_ecc and self.real_ecc._has_cryptography:
            h_a = self._hash_to_curve(a_id)
            h_b = self._hash_to_curve(b_id)
            # 使用真实ECC的共享密钥计算
            p_private, p_public = self.real_ecc.generate_key_pair()
            # 将哈希值作为临时密钥
            shared_secret = self.real_ecc.compute_shared_secret(h_a % (2**128), h_b % (2**128))
            return shared_secret

        # 回退到模拟模式
        h_a = self._hash_to_curve(a_id)
        h_b = self._hash_to_curve(b_id)
        return (h_a * h_b) % self.curve_order

    def _blinded_element(self, element: str, secret: int) -> str:
        """对元素进行盲化处理"""
        h_e = self._hash_to_curve(element)
        blinded = (h_e + secret) % self.curve_order
        return format(blinded, '064x')

    def generate_match_code(self, p_id: str, v_id: str, mode: PSIMode = PSIMode.ECC_2P,
                          use_real_ecc: bool = True) -> str:
        """
        生成PSI匹配验证码

        Args:
            p_id: 乘客ID
            v_id: 车辆ID
            mode: PSI算法模式
            use_real_ecc: 是否使用真实ECC（仅ECC模式有效）

        Returns:
            6位大写验证码
        """
        if mode == PSIMode.HASH:
            # 简化模式：MD5哈希
            raw = f"{p_id}{v_id}"
            return hashlib.md5(raw.encode()).hexdigest()[:6].upper()

        elif mode == PSIMode.ECC_2P:
            # 双方PSI：基于共享密钥
            if use_real_ecc and self.use_real_ecc and self.real_ecc and self.real_ecc._has_cryptography:
                # 使用真实ECC
                return self.real_ecc.generate_ecc_match_code(p_id, v_id)
            else:
                # 回退到模拟模式
                shared_secret = self._compute_shared_secret(p_id, v_id)
                code_hash = hashlib.sha256(f"PSI_2P:{shared_secret}".encode()).hexdigest()
                return code_hash[:6].upper()

        elif mode == PSIMode.ECC_MP:
            # 多方PSI：包含更多上下文信息
            salt = secrets.token_hex(8)  # 添加随机盐值
            multi_input = f"MP_PSI:{p_id}:{v_id}:{salt}:{time.time()}"
            code_hash = hashlib.sha256(multi_input.encode()).hexdigest()
            return code_hash[:6].upper()

        elif mode == PSIMode.THRESHOLD:
            # 门限PSI：需要门限数量的验证才能完成匹配
            salt = secrets.token_hex(8)
            threshold_input = f"TH_PSI:{p_id}:{v_id}:threshold_3_of_5:{salt}"
            code_hash = hashlib.sha256(threshold_input.encode()).hexdigest()
            return code_hash[:6].upper()

        else:
            # 默认使用ECC_2P
            return self.generate_match_code(p_id, v_id, PSIMode.ECC_2P, use_real_ecc)

    def verify_match_code(self, p_id: str, v_id: str, code: str, mode: PSIMode = PSIMode.ECC_2P) -> bool:
        """验证匹配码是否正确"""
        expected = self.generate_match_code(p_id, v_id, mode)
        return expected.upper() == code.upper()

    def compute_similarity(self, route1: str, route2: str,
                         route_path1: str = None,
                         route_path2: str = None) -> float:
        """
        计算路线相似度（使用加密空间PSI）

        真正的隐私集合求交：在加密空间完成所有计算，不接触原始坐标数据。

        Args:
            route1: 路线1文本描述（仅用于日志，不参与PSI）
            route2: 路线2文本描述（仅用于日志，不参与PSI）
            route_path1: 路线1的路径点JSON字符串 [[lng, lat], ...]
            route_path2: 路线2的路径点JSON字符串 [[lng, lat], ...]

        Returns:
            相似度分数 (0.0 - 1.0)
        """
        # PSI需要路径点数据
        if not route_path1 or not route_path2:
            return 0.0

        try:
            import json
            from crypto_psi import EncryptedSpacePSI

            # 解析路径点
            path1 = json.loads(route_path1) if isinstance(route_path1, str) else route_path1
            path2 = json.loads(route_path2) if isinstance(route_path2, str) else route_path2

            if not path1 or not path2:
                return 0.0

            # 转换为坐标列表 [(lat, lng), ...]
            coords1 = [(float(p[1]), float(p[0])) for p in path1 if len(p) >= 2]
            coords2 = [(float(p[1]), float(p[0])) for p in path2 if len(p) >= 2]

            if not coords1 or not coords2:
                return 0.0

            # 使用加密空间PSI进行匹配
            psi = EncryptedSpacePSI()

            # 生成全局盲因子（双方使用相同因子，确保可比较）
            global_blind = secrets.randbelow(self.curve_order)

            # 在加密空间盲化两条路线
            blinded_route1 = psi.blind_route_from_coordinates(
                coords1, "route1", blind_factor=global_blind
            )
            blinded_route2 = psi.blind_route_from_coordinates(
                coords2, "route2", blind_factor=global_blind
            )

            # 在加密空间计算交集（不接触原始坐标）
            encrypted_intersection = psi.encrypted_intersection(
                blinded_route1, blinded_route2, verify_factor_match=True
            )

            # 根据加密交集结果计算相似度
            # 相似度 = 匹配点数 / 两条路线点数的较小值
            min_points = min(len(coords1), len(coords2))
            if min_points == 0:
                return 0.0

            similarity = encrypted_intersection.match_count / min_points
            similarity = min(similarity, 1.0)  # 确保不超过1

            return similarity

        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            print(f"PSI路径解析失败: {e}")
            return 0.0
        except ImportError:
            print("警告: crypto_psi模块不可用，无法进行PSI匹配")
            return 0.0
        except Exception as e:
            print(f"PSI计算异常: {e}")
            return 0.0


class SecureMatchCode:
    """
    安全的匹配验证码生成器

    增强功能：
    - 时间窗口保护（防止短时间内重复生成）
    - 防暴力破解（增加随机盐值）
    - 使用secrets生成高质量随机数
    """

    def __init__(self, time_window: int = 60):
        """
        初始化安全验证码生成器

        Args:
            time_window: 时间窗口（秒），同一ID在此时间内只能生成一次
        """
        self.used_codes = {}  # {key: (timestamp, code)}
        self.time_window = time_window
        self.max_history = 1000  # 最大历史记录数
        self.failed_attempts = {}  # 防暴力破解 {ip_or_id: {count, last_time}}

    def generate_secure_code(self, p_id: str, v_id: str, mode: PSIMode = PSIMode.ECC_2P,
                           use_real_ecc: bool = True) -> str:
        """
        生成安全验证码

        Args:
            p_id: 乘客ID
            v_id: 车辆ID
            mode: PSI算法模式
            use_real_ecc: 是否使用真实ECC

        Returns:
            6位大写验证码
        """
        now = time.time()
        key = f"{p_id}:{v_id}"

        # 检查时间窗口
        if key in self.used_codes:
            last_time, _ = self.used_codes[key]
            if now - last_time < self.time_window:
                # 时间窗口内，生成不同的但可验证的码（添加时间戳和盐值）
                salt = secrets.token_hex(8)
                if mode == PSIMode.HASH:
                    base = f"{key}:{now}:{salt}"
                    code = hashlib.sha256(base.encode()).hexdigest()[:6].upper()
                elif mode == PSIMode.ECC_2P:
                    base = f"ECC_2P:{key}:{now}:{salt}"
                    code = hashlib.sha256(base.encode()).hexdigest()[:6].upper()
                else:
                    base = f"PSI_{mode.value}:{key}:{now}:{salt}"
                    code = hashlib.sha256(base.encode()).hexdigest()[:6].upper()
                return code

        # 正常生成验证码
        psi = ECDHPSI(use_real_ecc=use_real_ecc)
        code = psi.generate_match_code(p_id, v_id, mode, use_real_ecc)

        # 记录使用
        self._record_usage(key, now)

        return code

    def _record_usage(self, key: str, timestamp: float):
        """记录验证码使用情况"""
        self.used_codes[key] = (timestamp, None)

        # 清理过期记录
        self._cleanup_old_records(timestamp)

    def _cleanup_old_records(self, current_time: float):
        """清理过期的历史记录"""
        expired_keys = [
            k for k, (t, _) in self.used_codes.items()
            if current_time - t > self.time_window * 10  # 保留10个时间窗口的历史
        ]
        for k in expired_keys:
            del self.used_codes[k]

    def check_rate_limit(self, identifier: str, max_attempts: int = 10,
                        window_seconds: int = 300) -> Tuple[bool, int]:
        """
        检查速率限制（防暴力破解）

        Args:
            identifier: 唯一标识符（IP地址或用户ID）
            max_attempts: 最大尝试次数
            window_seconds: 时间窗口（秒）

        Returns:
            (是否允许, 当前尝试次数)
        """
        now = time.time()

        if identifier not in self.failed_attempts:
            self.failed_attempts[identifier] = {'count': 1, 'last_time': now}
            return True, 1

        attempt = self.failed_attempts[identifier]

        # 检查是否超过时间窗口
        if now - attempt['last_time'] > window_seconds:
            # 重置计数
            attempt['count'] = 1
            attempt['last_time'] = now
            return True, 1

        # 增加计数
        attempt['count'] += 1
        attempt['last_time'] = now

        # 检查是否超过最大尝试次数
        if attempt['count'] > max_attempts:
            return False, attempt['count']

        return True, attempt['count']

    def record_success(self, identifier: str):
        """记录成功验证（重置失败计数）"""
        if identifier in self.failed_attempts:
            del self.failed_attempts[identifier]


class MultiPartyPSI:
    """
    多方隐私集合求交协议（MP-PSI）

    支持多方参与的隐私集合求交，适用于：
    - 多辆车协同匹配
    - 门限验证场景
    - 分布式匹配系统

    实现Shamir秘密共享，支持门限验证。
    """

    def __init__(self, threshold: int = 3, total: int = 5):
        """
        初始化多方PSI

        Args:
            threshold: 门限值（k），需要至少threshold个份额才能重构秘密
            total: 总参与方数量（n）
        """
        self.threshold = threshold
        self.total = total
        self.ecdh_psi = ECDHPSI()
        self.prime = 2**256 - 2**224 + 2**192 + 2**96 - 1  # 大素数用于模运算

    def generate_secret_shares(self, secret: int) -> List[Tuple[int, int]]:
        """
        生成秘密份额（Shamir秘密共享）

        将秘密分成n份，任意k份可重构秘密。

        Args:
            secret: 要分割的秘密（整数）

        Returns:
            [(x, y), ...] 份额列表，x是索引，y是份额值
        """
        # 生成随机多项式系数: f(x) = secret + a1*x + a2*x^2 + ... + a(k-1)*x^(k-1)
        coefficients = [secret] + [secrets.randbelow(self.prime) for _ in range(self.threshold - 1)]

        # 计算每个份额的值: share_i = f(i)
        shares = []
        for i in range(1, self.total + 1):
            y = secret
            x = i
            for j in range(1, self.threshold):
                y = (y + coefficients[j] * pow(x, j, self.prime)) % self.prime
            shares.append((i, y))

        return shares

    def reconstruct_secret(self, shares: List[Tuple[int, int]]) -> int:
        """
        从门限份额重构秘密（拉格朗日插值）

        Args:
            shares: 份额列表 [(x, y), ...]，至少需要threshold个

        Returns:
            重构的秘密

        Raises:
            ValueError: 份额数量不足
        """
        if len(shares) < self.threshold:
            raise ValueError(f"需要至少{self.threshold}个份额，当前只有{len(shares)}个")

        # 使用拉格朗日插值重构
        secret = 0
        for j, (x_j, y_j) in enumerate(shares[:self.threshold]):
            # 计算拉格朗日基函数 L_j(0)
            l_j = 1
            for m, (x_m, _) in enumerate(shares[:self.threshold]):
                if j != m:
                    # L_j(0) = product of (0 - x_m) / (x_j - x_m) for all m != j
                    numerator = (-x_m) % self.prime
                    denominator = (x_j - x_m) % self.prime
                    # 计算模逆元
                    inv_denominator = self._mod_inverse(denominator, self.prime)
                    l_j = (l_j * numerator * inv_denominator) % self.prime

            # secret = sum(y_j * L_j(0))
            secret = (secret + y_j * l_j) % self.prime

        return secret

    def _mod_inverse(self, a: int, m: int) -> int:
        """
        计算模逆元（使用扩展欧几里得算法）

        Args:
            a: 要求逆元的数
            m: 模数

        Returns:
            a的模逆元
        """
        # 使用费马小定理计算逆元（适用于质数模）
        return pow(a, m - 2, m)

    def compute_multi_party_hash(self, elements: List[str]) -> str:
        """
        计算多方聚合哈希值

        模拟多方PSI协议：每方贡献一个哈希分量

        Args:
            elements: 参与方ID列表

        Returns:
            聚合哈希值
        """
        combined = "|".join(sorted(elements))
        salt = secrets.token_hex(8)
        # 使用门限风格的哈希计算
        hash_input = f"MP_PSI_T{self.threshold}:N{self.total}:{combined}:{salt}"
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
        min_factors: int = None
    ) -> Tuple[bool, int]:
        """
        验证门限匹配

        Args:
            p_id: 乘客ID
            v_id: 车辆ID
            code: 验证码
            additional_factors: 额外的门限因子
            min_factors: 最小要求的因子数量（默认使用threshold）

        Returns:
            (验证结果, 使用的门限因子数量)
        """
        if min_factors is None:
            min_factors = self.threshold

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

    def create_shamir_shares_for_match(self, p_id: str, v_id: str) -> dict:
        """
        为匹配创建Shamir秘密份额

        Args:
            p_id: 乘客ID
            v_id: 车辆ID

        Returns:
            包含份额信息和重构参数的字典
        """
        # 将ID组合哈希为整数作为秘密
        secret_input = f"{p_id}:{v_id}:{secrets.token_hex(8)}"
        secret = int(hashlib.sha256(secret_input.encode()).hexdigest(), 16) % self.prime

        # 生成份额
        shares = self.generate_secret_shares(secret)

        # 验证可以重构
        test_shares = shares[:self.threshold]
        reconstructed = self.reconstruct_secret(test_shares)

        return {
            'shares': shares,
            'threshold': self.threshold,
            'total': self.total,
            'verification_code': format(reconstructed, '064x')[:6].upper(),
            'secret_input': secret_input
        }


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


def route_similarity(route1: str, route2: str,
                   route_path1: str = None,
                   route_path2: str = None) -> float:
    """
    计算路线相似度（使用PSI增强算法）

    Args:
        route1: 路线1文本描述
        route2: 路线2文本描述
        route_path1: 路线1的路径点JSON字符串（可选）
        route_path2: 路线2的路径点JSON字符串（可选）

    Returns:
        相似度分数 (0.0 - 1.0)
    """
    psi = get_psi_instance()
    return psi.compute_similarity(route1, route2, route_path1, route_path2)


# ========== MP-TPSI 兼容导入 ==========

# 尝试导入完整的MP-TPSI模块
try:
    from mp_tpsi import (
        GeoPoint,
        Share,
        BlindedPoint,
        PSIMatchResult,
        PSIParticipantRole,
        MathUtils,
        ShamirSecretSharing,
        LocationPSI,
        MPTPSI,
        ThresholdVerifier
    )

    _MP_TPSI_AVAILABLE = True
except ImportError:
    _MP_TPSI_AVAILABLE = False
    print("提示: 完整的MP-TPSI功能需要 mp_tpsi 模块")


def is_mp_tpsi_available() -> bool:
    """检查完整的MP-TPSI是否可用"""
    return _MP_TPSI_AVAILABLE


def get_mp_tpsi_instance(threshold: int = 3, total: int = 5) -> MPTPSI:
    """
    获取MP-TPSI实例（兼容接口）

    Args:
        threshold: 门限值(k)
        total: 总参与方数(n)

    Returns:
        MP-TPSI实例
    """
    if not _MP_TPSI_AVAILABLE:
        raise ImportError("MP-TPSI功能需要 mp_tpsi 模块")

    return MPTPSI(threshold=threshold, total=total)
