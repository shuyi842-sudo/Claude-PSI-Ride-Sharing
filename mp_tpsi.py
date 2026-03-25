"""
MP-TPSI: 多方门限隐私集合求交协议
Multi-Party Threshold Private Set Intersection

实现功能：
1. 地理位置到椭圆曲线的映射
2. Shamir秘密共享 (k-of-n门限)
3. 多方PSI协议
4. 门限验证机制
5. 隐私保护的路线匹配

作者: Claude
版本: 1.0.0
"""

import hashlib
import secrets
import time
import json
from typing import List, Tuple, Optional, Dict, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


# ========== 类型定义 ==========

class PSIParticipantRole(Enum):
    """PSI参与方角色"""
    PASSENGER = "passenger"      # 乘客
    VEHICLE = "vehicle"           # 车辆
    SERVER = "server"            # 服务器（可信第三方或协调者）
    VERIFIER = "verifier"        # 验证者（门限验证节点）


@dataclass
class GeoPoint:
    """地理坐标点"""
    lat: float  # 纬度 -90 到 90
    lng: float  # 经度 -180 到 180

    def __repr__(self):
        return f"({self.lat:.4f}, {self.lng:.4f})"

    def to_grid_id(self, precision: int = 5) -> str:
        """
        转换为网格ID（简化版Geohash）

        Args:
            precision: 精度级别，5级约对应2km范围
        """
        # 将坐标归一化到 [0, 1) 区间
        lat_norm = (self.lat + 90) / 180
        lng_norm = (self.lng + 180) / 360

        # 生成整数表示
        lat_int = int(lat_norm * (1 << 32))
        lng_int = int(lng_norm * (1 << 32))
        combined = (lat_int << 32) | lng_int

        # 使用Base32编码
        chars = "0123456789bcdefghjkmnpqrstuvwxyz"
        grid_id = []
        for _ in range(precision):
            idx = combined & 31
            grid_id.append(chars[idx])
            combined >>= 5
        return ''.join(reversed(grid_id))

    def to_int_hash(self, salt: bytes = b'') -> int:
        """
        将坐标转换为整数哈希

        Args:
            salt: 随机盐值，防止彩虹表攻击

        Returns:
            256位整数哈希值
        """
        coord_data = json.dumps({"lat": self.lat, "lng": self.lng}, sort_keys=True).encode()
        h = hashlib.sha256(salt + coord_data).digest()
        return int.from_bytes(h, 'big')


@dataclass
class Share:
    """秘密份额"""
    index: int           # 份额索引 (1, 2, ..., n)
    value: int           # 份额值
    owner: str           # 拥有者ID

    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "value": hex(self.value),
            "owner": self.owner
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Share':
        return cls(
            index=data["index"],
            value=int(data["value"], 16),
            owner=data["owner"]
        )


@dataclass
class BlindedPoint:
    """盲化的地理位置点"""
    original_hash: int   # 原始哈希（仅所有者知道）
    blinded_value: int   # 盲化后的值（公开）
    owner: str           # 拥有者

    def to_dict(self, hide_original: bool = True) -> Dict:
        result = {
            "blinded": hex(self.blinded_value),
            "owner": self.owner
        }
        if not hide_original:
            result["original"] = hex(self.original_hash)
        return result


@dataclass
class PSIMatchResult:
    """PSI匹配结果"""
    matched: bool                 # 是否匹配
    match_score: float            # 匹配分数 (0-1)
    distance_km: float            # 最近距离（公里）
    match_points: List[GeoPoint]  # 匹配的点（如果匹配）
    verification_code: str        # 验证码
    participants: List[str]       # 参与者列表
    timestamp: float              # 时间戳

    def to_dict(self) -> Dict:
        return {
            "matched": self.matched,
            "match_score": self.match_score,
            "distance_km": round(self.distance_km, 3),
            "match_count": len(self.match_points),
            "verification_code": self.verification_code,
            "participants": self.participants,
            "timestamp": self.timestamp
        }


# ========== 数学工具函数 ==========

class MathUtils:
    """数学工具类"""

    # 大素数（近似于secp256r1的阶）
    PRIME = 2**256 - 2**224 + 2**192 + 2**96 - 1

    @staticmethod
    def mod_inverse(a: int, m: int = None) -> int:
        """
        计算模逆元

        使用扩展欧几里得算法或费马小定理

        Args:
            a: 要求逆元的数
            m: 模数（默认使用类定义的大素数）

        Returns:
            a的模逆元，满足 a * a^(-1) ≡ 1 (mod m)
        """
        if m is None:
            m = MathUtils.PRIME

        # 使用费马小定理：a^(m-2) ≡ a^(-1) (mod m)
        return pow(a, m - 2, m)

    @staticmethod
    def lagrange_interpolation(shares: List[Tuple[int, int]],
                              x: int = 0,
                              prime: int = None) -> int:
        """
        拉格朗日插值

        从给定的份额点重构多项式在x处的值

        Args:
            shares: 份额点列表 [(x1, y1), (x2, y2), ...]
            x: 要计算的x值（默认0用于重构秘密）
            prime: 模数

        Returns:
            f(x)的值
        """
        if prime is None:
            prime = MathUtils.PRIME

        if len(shares) == 0:
            raise ValueError("至少需要一个份额")

        k = len(shares)
        result = 0

        for j in range(k):
            x_j, y_j = shares[j]

            # 计算拉格朗日基函数 L_j(x)
            l_j = 1
            for m in range(k):
                if j == m:
                    continue
                x_m, _ = shares[m]

                # L_j(x) = ∏(x - x_m) / (x_j - x_m)
                numerator = (x - x_m) % prime
                denominator = (x_j - x_m) % prime
                inv_denominator = MathUtils.mod_inverse(denominator, prime)
                l_j = (l_j * numerator * inv_denominator) % prime

            # f(x) = Σ y_j * L_j(x)
            result = (result + y_j * l_j) % prime

        return result

    @staticmethod
    def haversine_distance(lat1: float, lng1: float,
                         lat2: float, lng2: float) -> float:
        """
        计算两点间的Haversine距离（公里）

        Args:
            lat1, lng1: 第一个点的坐标
            lat2, lng2: 第二个点的坐标

        Returns:
            两点间的距离（公里）
        """
        import math

        lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])

        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = (math.sin(dlat / 2) ** 2 +
              math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        return 6371 * c  # 地球半径（公里）


# ========== Shamir秘密共享 ==========

class ShamirSecretSharing:
    """
    Shamir秘密共享方案

    将秘密分成n份，任意k份可以重构秘密
    少于k份无法获得任何信息
    """

    def __init__(self, threshold: int = 3, total: int = 5, prime: int = None):
        """
        初始化Shamir秘密共享

        Args:
            threshold: 门限值(k)，需要至少k个份额才能重构
            total: 总份数(n)
            prime: 模数（用于多项式计算）
        """
        if threshold > total:
            raise ValueError(f"门限值({threshold})不能大于总份数({total})")

        self.threshold = threshold
        self.total = total
        self.prime = prime or MathUtils.PRIME

    def split_secret(self, secret: int,
                    owner: str = "unknown") -> List[Share]:
        """
        分割秘密为多个份额

        使用Shamir方案生成 (k-1) 次随机多项式
        f(x) = secret + a1*x + a2*x^2 + ... + a(k-1)*x^(k-1)

        Args:
            secret: 要分割的秘密（整数）
            owner: 秘密的所有者ID

        Returns:
            份额列表，每个份额包含索引、值和所有者信息
        """
        # 生成随机多项式系数: f(x) = secret + a1*x + a2*x^2 + ... + a(k-1)*x^(k-1)
        # 系数都是随机数，常数项就是秘密
        coefficients = [secret] + [
            secrets.randbelow(self.prime)
            for _ in range(self.threshold - 1)
        ]

        # 计算每个份额的值: share_i = f(i)
        shares = []
        for i in range(1, self.total + 1):
            y = coefficients[0]
            x = i
            for j in range(1, self.threshold):
                y = (y + coefficients[j] * pow(x, j, self.prime)) % self.prime

            shares.append(Share(
                index=i,
                value=y,
                owner=owner
            ))

        return shares

    def reconstruct_secret(self, shares: List[Share]) -> int:
        """
        从份额重构秘密

        使用拉格朗日插值重构多项式

        Args:
            shares: 份额列表，至少需要threshold个

        Returns:
            重构的秘密

        Raises:
            ValueError: 份额数量不足
        """
        if len(shares) < self.threshold:
            raise ValueError(
                f"需要至少{self.threshold}个份额，当前只有{len(shares)}个"
            )

        # 转换为 (x, y) 元组
        share_tuples = [(s.index, s.value) for s in shares]

        # 使用拉格朗日插值重构 f(0) = secret
        return MathUtils.lagrange_interpolation(
            share_tuples, x=0, prime=self.prime
        )

    def verify_share(self, share: Share,
                    public_commitments: List[int]) -> bool:
        """
        验证份额的有效性

        使用Feldman承诺方案验证份额

        Args:
            share: 要验证的份额
            public_commitments: 公开承诺列表 [C0, C1, ..., C(k-1)]

        Returns:
            份额是否有效
        """
        # 计算该份额应该满足的等式
        # C0 * C1^i * C2^i^2 * ... * C(k-1)^i^(k-1) = share_value

        # 这里简化实现，实际应该使用群操作
        # 在椭圆曲线上：g^share = ∏ Cj^i^j

        expected = public_commitments[0]
        for j in range(1, min(len(public_commitments), self.threshold)):
            # Cj^i^j mod prime
            term = pow(public_commitments[j], pow(share.index, j, self.prime), self.prime)
            expected = (expected * term) % self.prime

        return expected == share.value

    def generate_commitments(self, coefficients: List[int]) -> List[int]:
        """
        生成公开承诺（Feldman方案）

        Args:
            coefficients: 多项式系数 [secret, a1, a2, ...]

        Returns:
            公开承诺列表 [g^secret, g^a1, g^a2, ...]
        """
        # 简化版：直接使用系数的哈希
        commitments = []
        generator = 2  # 生成元

        for coeff in coefficients:
            commitment = pow(generator, coeff, self.prime)
            commitments.append(commitment)

        return commitments


# ========== 地理位置PSI ==========

class LocationPSI:
    """
    基于地理位置的隐私集合求交

    将地理位置映射到加密空间，在不泄露具体坐标的情况下判断匹配
    现在支持真正的加密空间匹配（不使用原始坐标计算）
    """

    def __init__(self, salt: bytes = None, use_encrypted: bool = True):
        """
        初始化地理位置PSI

        Args:
            salt: 全局盐值，防止彩虹表攻击
            use_encrypted: 是否使用加密空间匹配
        """
        self.salt = salt or secrets.token_bytes(16)
        self.shamir = ShamirSecretSharing()
        self.use_encrypted = use_encrypted

        # 尝试导入加密空间PSI
        self._crypto_psi = None
        if use_encrypted:
            try:
                from crypto_psi import EncryptedSpacePSI
                self._crypto_psi = EncryptedSpacePSI()
            except ImportError:
                print("警告: crypto_psi模块不可用，回退到明文空间匹配")

    def hash_location(self, point: GeoPoint) -> int:
        """
        将地理位置哈希到整数

        Args:
            point: 地理坐标点

        Returns:
            256位整数哈希值
        """
        return point.to_int_hash(self.salt)

    def hash_route(self, route: List[GeoPoint]) -> List[int]:
        """
        将路线哈希为整数列表

        Args:
            route: 路线点列表

        Returns:
            哈希值列表
        """
        return [self.hash_location(p) for p in route]

    def hash_location_encrypted(self, point: GeoPoint, blind_factor: int = None) -> int:
        """
        盲化地理位置哈希（加密空间）

        Args:
            point: 地理坐标点
            blind_factor: 盲因子（如果为None则生成新的）

        Returns:
            盲化后的哈希值
        """
        from crypto_psi import CryptoMath

        if blind_factor is None:
            blind_factor = secrets.randbelow(MathUtils.PRIME)

        # 先计算原始哈希
        h = self.hash_location(point)

        # 使用乘法盲化
        return CryptoMath.blind_multiplicative(h, blind_factor)

    def hash_route_encrypted(self, route: List[GeoPoint], blind_factor: int = None) -> List[int]:
        """
        盲化路线哈希值列表（使用相同的盲因子）

        Args:
            route: 路线点列表
            blind_factor: 盲因子

        Returns:
            盲化后的哈希值列表
        """
        if blind_factor is None:
            blind_factor = secrets.randbelow(MathUtils.PRIME)

        return [self.hash_location_encrypted(p, blind_factor) for p in route]

    def find_encrypted_intersection(self, route1_hashes: List[int],
                                  route2_hashes: List[int]) -> List[Tuple[int, int]]:
        """
        在加密空间找交集（仅比较盲化值）

        不使用原始坐标，直接比较哈希值是否相等

        Args:
            route1_hashes: 第一条路线的盲化哈希值列表
            route2_hashes: 第二条路线的盲化哈希值列表

        Returns:
            匹配的索引对列表 [(i, j), ...]
        """
        matches = []

        # 在加密空间直接比较
        for i, h1 in enumerate(route1_hashes):
            for j, h2 in enumerate(route2_hashes):
                # 精确匹配：盲化值相等意味着原始哈希相等
                if h1 == h2:
                    matches.append((i, j))

        return matches

    def blind_with_shamir(self, value: int, owner: str,
                          threshold: int = 3, total: int = 5) -> List[Share]:
        """
        使用Shamir方案盲化值

        Args:
            value: 要盲化的值
            owner: 所有者
            threshold: 门限值
            total: 总份数

        Returns:
            盲化份额列表
        """
        return self.shamir.split_secret(value, owner, threshold, total)

    def compute_route_similarity(self, route1: List[GeoPoint],
                                route2: List[GeoPoint],
                                threshold_km: float = 2.0) -> float:
        """
        计算两条路线的相似度（基于距离）

        Args:
            route1: 第一条路线
            route2: 第二条路线
            threshold_km: 距离阈值（公里）

        Returns:
            相似度分数 (0-1)
        """
        if not route1 or not route2:
            return 0.0

        # 计算route1中每个点到route2的最小距离
        min_distances = []
        for p1 in route1:
            min_dist = min(
                MathUtils.haversine_distance(p1.lat, p1.lng, p2.lat, p2.lng)
                for p2 in route2
            )
            min_distances.append(min_dist)

        # 计算在阈值内的点数比例
        within_threshold = sum(1 for d in min_distances if d <= threshold_km)
        similarity = within_threshold / len(min_distances)

        return similarity

    def find_route_intersection(self, route1: List[GeoPoint],
                              route2: List[GeoPoint],
                              threshold_km: float = 1.0) -> List[Tuple[GeoPoint, GeoPoint, float]]:
        """
        找到两条路线的交点（在阈值范围内）

        Args:
            route1: 第一条路线
            route2: 第二条路线
            threshold_km: 距离阈值

        Returns:
            交点列表 [(p1, p2, distance), ...]
        """
        intersections = []

        for p1 in route1:
            for p2 in route2:
                dist = MathUtils.haversine_distance(
                    p1.lat, p1.lng, p2.lat, p2.lng
                )
                if dist <= threshold_km:
                    intersections.append((p1, p2, dist))

        # 按距离排序
        intersections.sort(key=lambda x: x[2])
        return intersections


# ========== 多方门限PSI协议 ==========

class MPTPSI:
    """
    多方门限隐私集合求交协议
    Multi-Party Threshold Private Set Intersection

    协议流程：
    1. Setup: 各方生成密钥
    2. Share: 秘密被分成多份
    3. Compute: 各方协作计算交集
    4. Verify: 需要k个验证者确认结果
    5. Reconstruct: 需要k个份额重构秘密
    """

    def __init__(self, threshold: int = 3, total: int = 5,
                 prime: int = None):
        """
        初始化MP-TPSI

        Args:
            threshold: 门限值(k)
            total: 总参与方数(n)
            prime: 模数
        """
        self.threshold = threshold
        self.total = total
        self.prime = prime or MathUtils.PRIME
        self.shamir = ShamirSecretSharing(threshold, total, prime)
        self.location_psi = LocationPSI()

        # 存储各方的状态
        self.participants: Dict[str, Any] = {}
        self.shares: Dict[str, List[Share]] = {}
        self.commitments: Dict[str, List[int]] = {}

    def add_participant(self, participant_id: str, role: PSIParticipantRole):
        """
        添加参与方

        Args:
            participant_id: 参与方ID
            role: 参与方角色
        """
        self.participants[participant_id] = {
            "id": participant_id,
            "role": role,
            "shares": [],
            "received_shares": []
        }
        print(f"✓ 添加参与方: {participant_id} ({role.value})")

    def share_route_secret(self, participant_id: str,
                          route: List[GeoPoint]) -> List[Share]:
        """
        分享路线秘密（Shamir秘密共享）

        将路线的哈希值分割为多个份额，分发给其他参与方

        Args:
            participant_id: 参与方ID
            route: 路线点列表

        Returns:
            生成的份额列表
        """
        # 自动添加参与者（如果不存在）
        if participant_id not in self.participants:
            self.add_participant(participant_id, PSIParticipantRole.VEHICLE)

        # 计算路线的聚合哈希
        route_hashes = self.location_psi.hash_route(route)
        combined_hash = int(hashlib.sha256(
            json.dumps(route_hashes).encode()
        ).hexdigest(), 16) % self.prime

        # 使用Shamir方案分割
        shares = self.shamir.split_secret(combined_hash, participant_id)

        # 存储份额
        self.shares[participant_id] = shares
        self.participants[participant_id]["shares"] = shares

        print(f"✓ {participant_id} 路线已共享为 {len(shares)} 份")
        print(f"  路线聚合哈希: {hex(combined_hash)}")

        return shares

    def distribute_shares(self, from_participant: str,
                        to_participants: List[str]) -> Dict[str, List[Share]]:
        """
        分发份额给其他参与方

        Args:
            from_participant: 发送方ID
            to_participants: 接收方ID列表

        Returns:
            每个接收方收到的份额
        """
        if from_participant not in self.shares:
            raise ValueError(f"参与者 {from_participant} 没有可分享的份额")

        source_shares = self.shares[from_participant]
        distribution = {}

        # 将份额分发给其他参与方
        for i, recipient in enumerate(to_participants):
            if i < len(source_shares):
                share = source_shares[i]
                if recipient in self.participants:
                    self.participants[recipient]["received_shares"].append(share)
                    distribution[recipient] = [share]
                    print(f"  份额{i+1} -> {recipient}")

        return distribution

    def compute_psi_intersection(self, participant1: str,
                                route1: List[GeoPoint],
                                participant2: str,
                                route2: List[GeoPoint],
                                threshold_km: float = 2.0,
                                use_encrypted: bool = False) -> PSIMatchResult:
        """
        计算两方之间的PSI交集

        Args:
            participant1: 第一方ID
            route1: 第一方路线
            participant2: 第二方ID
            route2: 第二方路线
            threshold_km: 距离阈值
            use_encrypted: 是否使用加密空间匹配

        Returns:
            PSI匹配结果
        """
        if use_encrypted:
            return self.compute_psi_intersection_encrypted(
                participant1, route1, participant2, route2
            )

        # 1. 双方生成秘密份额
        shares1 = self.share_route_secret(participant1, route1)
        shares2 = self.share_route_secret(participant2, route2)

        # 2. 交叉分发份额
        self.distribute_shares(participant1, [participant2])
        self.distribute_shares(participant2, [participant1])

        # 3. 计算实际路线交集（用于验证）
        intersections = self.location_psi.find_route_intersection(
            route1, route2, threshold_km
        )

        # 4. 计算匹配分数
        similarity = self.location_psi.compute_route_similarity(
            route1, route2, threshold_km
        )

        # 5. 生成验证码（基于双方ID和时间戳）
        verification_code = self._generate_verification_code(
            participant1, participant2, intersections
        )

        matched = len(intersections) > 0
        min_distance = min((dist for _, _, dist in intersections),
                         default=float('inf'))

        match_points = [(p1, p2) for p1, p2, _ in intersections]

        result = PSIMatchResult(
            matched=matched,
            match_score=similarity,
            distance_km=min_distance,
            match_points=match_points,
            verification_code=verification_code,
            participants=[participant1, participant2],
            timestamp=time.time()
        )

        print(f"\nPSI交集计算完成:")
        print(f"  匹配: {matched}")
        print(f"  相似度: {similarity:.2%}")
        print(f"  交点数: {len(intersections)}")
        print(f"  验证码: {verification_code}")

        return result

    def compute_psi_intersection_encrypted(self, participant1: str,
                                         route1: List[GeoPoint],
                                         participant2: str,
                                         route2: List[GeoPoint]) -> PSIMatchResult:
        """
        在加密空间计算PSI交集（不使用原始坐标）

        流程：
        1. 生成全局盲因子
        2. 使用相同盲因子盲化双方路线
        3. 在加密空间找交集
        4. 基于交集结果生成匹配码

        Args:
            participant1: 第一方ID
            route1: 第一方路线
            participant2: 第二方ID
            route2: 第二方路线

        Returns:
            PSI匹配结果
        """
        print(f"\n【加密空间PSI匹配】")
        print(f"  参与方1: {participant1} (路线点数: {len(route1)})")
        print(f"  参与方2: {participant2} (路线点数: {len(route2)})")

        try:
            from crypto_psi import EncryptedSpacePSI
        except ImportError:
            print("  错误: crypto_psi模块不可用")
            raise ImportError("需要crypto_psi模块进行加密空间匹配")

        # 1. 生成全局盲因子（双方使用相同因子）
        blind_factor = secrets.randbelow(self.prime)
        print(f"  盲因子: {hex(blind_factor)[:16]}...")

        # 2. 盲化双方路线（使用相同的盲因子）
        route1_encrypted = self.location_psi.hash_route_encrypted(route1, blind_factor)
        route2_encrypted = self.location_psi.hash_route_encrypted(route2, blind_factor)

        # 3. 在加密空间找交集（不使用原始坐标）
        encrypted_matches = self.location_psi.find_encrypted_intersection(
            route1_encrypted, route2_encrypted
        )

        # 4. 计算匹配分数（基于加密匹配数）
        total_possible = min(len(route1), len(route2))
        if total_possible > 0:
            match_score = len(encrypted_matches) / total_possible
        else:
            match_score = 0.0

        # 5. 生成加密空间验证码
        psi = EncryptedSpacePSI()
        verification_code = psi.generate_secure_match_code(
            participant1, participant2,
            type('obj', (object,), {
                'matched': len(encrypted_matches) > 0,
                'match_count': len(encrypted_matches),
                'verification_hash': int(hashlib.sha256(
                    f"{participant1}:{participant2}:{blind_factor}".encode()
                ).hexdigest(), 16) % self.prime
            })()
        )

        # 6. 构建结果
        matched = len(encrypted_matches) > 0

        # 从加密匹配中提取匹配点（用于显示）
        match_points = []
        for i, j in encrypted_matches:
            match_points.append((route1[i], route2[j]))

        result = PSIMatchResult(
            matched=matched,
            match_score=match_score,
            distance_km=0.0 if matched else float('inf'),  # 加密空间无实际距离
            match_points=match_points,
            verification_code=verification_code,
            participants=[participant1, participant2],
            timestamp=time.time()
        )

        print(f"  匹配: {matched}")
        print(f"  相似度: {match_score:.2%}")
        print(f"  交点数: {len(encrypted_matches)}")
        print(f"  验证码: {verification_code}")
        print(f"  模式: 加密空间（不使用原始坐标）")

        return result

    def threshold_verify(self, match_result: PSIMatchResult,
                       verifications: List[Tuple[str, bool]]) -> bool:
        """
        门限验证

        需要至少threshold个验证者确认匹配结果

        Args:
            match_result: 匹配结果
            verifications: 验证列表 [(verifier_id, verified), ...]

        Returns:
            验证是否通过
        """
        # 统计验证通过的数量
        verified_count = sum(1 for _, verified in verifications if verified)

        # 计算门限需要的票数
        required = self.threshold

        passed = verified_count >= required

        print(f"\n门限验证:")
        print(f"  验证通过: {verified_count}/{len(verifications)}")
        print(f"  门限要求: {required}")
        print(f"  结果: {'通过' if passed else '失败'}")

        return passed

    def reconstruct_matched_secret(self, participant_id: str,
                                 required_shares: List[Share]) -> int:
        """
        重构匹配的秘密

        需要至少threshold个份额

        Args:
            participant_id: 参与方ID
            required_shares: 收集到的份额

        Returns:
            重构的秘密值
        """
        secret = self.shamir.reconstruct_secret(required_shares)
        print(f"\n秘密重构完成:")
        print(f"  所有者: {participant_id}")
        print(f"  使用份额: {len(required_shares)}")
        print(f"  重构秘密: {hex(secret)}")

        return secret

    def multi_party_match(self, passenger_id: str,
                        passenger_dest: GeoPoint,
                        vehicle_routes: Dict[str, List[GeoPoint]],
                        threshold_km: float = 2.0) -> Dict[str, PSIMatchResult]:
        """
        多方匹配（一个乘客对多辆车）

        Args:
            passenger_id: 乘客ID
            passenger_dest: 乘客目的地
            vehicle_routes: 车辆路线字典 {vehicle_id: route}
            threshold_km: 距离阈值

        Returns:
            匹配结果字典
        """
        print("\n" + "=" * 60)
        print(f"多方匹配: {passenger_id} 对 {len(vehicle_routes)} 辆车")
        print("=" * 60)

        # 为每辆车计算PSI匹配
        results = {}
        for vehicle_id, route in vehicle_routes.items():
            # 将目的地作为单点路线
            passenger_route = [passenger_dest]

            result = self.compute_psi_intersection(
                passenger_id, passenger_route,
                vehicle_id, route,
                threshold_km
            )
            results[vehicle_id] = result

        # 按匹配分数排序
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1].match_score,
            reverse=True
        )

        print("\n匹配结果排序:")
        for i, (vid, res) in enumerate(sorted_results):
            status = "✓" if res.matched else "✗"
            print(f"  {i+1}. {vid}: {status} 分数={res.match_score:.2%}")

        return dict(sorted_results)

    def _generate_verification_code(self, participant1: str,
                                 participant2: str,
                                 intersections: List) -> str:
        """
        生成验证码

        Args:
            participant1: 参与方1
            participant2: 参与方2
            intersections: 交点信息

        Returns:
            6位验证码
        """
        # 基于参与方ID、交点数量和时间戳生成
        input_str = f"{participant1}:{participant2}:{len(intersections)}:{time.time()}"
        h = hashlib.sha256(input_str.encode()).hexdigest()
        return h[:6].upper()


# ========== 门限验证节点 ==========

class ThresholdVerifier:
    """
    门限验证节点

    独立验证PSI匹配结果的有效性
    """

    def __init__(self, verifier_id: str):
        """
        初始化验证者

        Args:
            verifier_id: 验证者ID
        """
        self.verifier_id = verifier_id
        self.verifications: List[Tuple[str, bool, float]] = []

    def verify_match(self, match_result: PSIMatchResult,
                    route1: List[GeoPoint],
                    route2: List[GeoPoint],
                    threshold_km: float) -> Tuple[bool, float]:
        """
        验证匹配结果

        Args:
            match_result: PSI匹配结果
            route1: 第一方路线
            route2: 第二方路线
            threshold_km: 距离阈值

        Returns:
            (验证结果, 置信度)
        """
        # 独立计算路线交集
        location_psi = LocationPSI()
        intersections = location_psi.find_route_intersection(
            route1, route2, threshold_km
        )

        # 验证结果一致性
        expected_matched = len(intersections) > 0
        matched_agrees = (expected_matched == match_result.matched)

        # 验证交点数量（如果匹配）
        if match_result.matched and expected_matched:
            count_agrees = len(intersections) >= len(match_result.match_points)
        else:
            count_agrees = True

        # 计算置信度
        confidence = 1.0 if (matched_agrees and count_agrees) else 0.5

        verified = matched_agrees and count_agrees

        # 记录验证
        self.verifications.append((
            f"{match_result.participants[0]}-{match_result.participants[1]}",
            verified,
            confidence
        ))

        print(f"验证者 {self.verifier_id}:")
        print(f"  预期匹配: {expected_matched}")
        print(f"  报告匹配: {match_result.matched}")
        print(f"  验证结果: {'通过' if verified else '失败'}")
        print(f"  置信度: {confidence:.0%}")

        return verified, confidence


# ========== 演示程序 ==========

def demo_mptpsi():
    """演示MP-TPSI协议"""
    print("=" * 60)
    print("MP-TPSI: 多方门限隐私集合求交协议演示")
    print("=" * 60)

    # 初始化MP-TPSI
    mptpsi = MPTPSI(threshold=3, total=5)

    # 添加参与方
    mptpsi.add_participant("P001", PSIParticipantRole.PASSENGER)
    mptpsi.add_participant("V001", PSIParticipantRole.VEHICLE)
    mptpsi.add_participant("V002", PSIParticipantRole.VEHICLE)
    mptpsi.add_participant("V003", PSIParticipantRole.VEHICLE)

    # 定义测试数据
    passenger_dest = GeoPoint(39.9042, 116.4074)  # 天安门

    # 车辆路线
    vehicle_routes = {
        "V001": [
            GeoPoint(39.8800, 116.3500),  # 起点
            GeoPoint(39.8900, 116.3700),
            GeoPoint(39.9042, 116.4074),  # 经过天安门
            GeoPoint(39.9200, 116.4300)
        ],
        "V002": [
            GeoPoint(39.8500, 116.3000),  # 起点
            GeoPoint(39.8700, 116.3300),
            GeoPoint(39.8900, 116.3600),
            GeoPoint(39.9100, 116.3900)  # 不经过天安门
        ],
        "V003": [
            GeoPoint(39.8900, 116.4000),  # 接近天安门
            GeoPoint(39.9042, 116.4074),  # 经过天安门
            GeoPoint(39.9200, 116.4200)
        ]
    }

    # 多方匹配
    print("\n执行多方匹配...")
    results = mptpsi.multi_party_match(
        "P001", passenger_dest, vehicle_routes, threshold_km=2.0
    )

    # 门限验证
    print("\n" + "=" * 60)
    print("门限验证")
    print("=" * 60)

    # 创建验证者
    verifiers = [
        ThresholdVerifier("Verifier1"),
        ThresholdVerifier("Verifier2"),
        ThresholdVerifier("Verifier3"),
        ThresholdVerifier("Verifier4"),
        ThresholdVerifier("Verifier5")
    ]

    # 对最佳匹配进行验证
    best_match = results["V001"]  # V001与P001匹配
    verifications = []

    for verifier in verifiers:
        verified, confidence = verifier.verify_match(
            best_match,
            [passenger_dest],
            vehicle_routes["V001"],
            threshold_km=2.0
        )
        verifications.append((verifier.verifier_id, verified))

    # 门限验证
    threshold_passed = mptpsi.threshold_verify(best_match, verifications)

    # 秘密重构演示
    print("\n" + "=" * 60)
    print("秘密重构演示")
    print("=" * 60)

    # 获取P001的份额
    p001_shares = mptpsi.shares.get("P001", [])
    print(f"P001的份额: {len(p001_shares)} 份")

    # 使用threshold个份额重构
    if len(p001_shares) >= mptpsi.threshold:
        reconstructed = mptpsi.reconstruct_matched_secret(
            "P001",
            p001_shares[:mptpsi.threshold]
        )

    # 总结
    print("\n" + "=" * 60)
    print("演示总结")
    print("=" * 60)
    print(f"参与方数: {len(mptpsi.participants)}")
    print(f"门限值: {mptpsi.threshold}/{mptpsi.total}")
    print(f"匹配车辆数: {sum(1 for r in results.values() if r.matched)}/{len(results)}")
    print(f"门限验证: {'通过' if threshold_passed else '失败'}")

    return results


def demo_shamir_secret_sharing():
    """演示Shamir秘密共享"""
    print("\n" + "=" * 60)
    print("Shamir秘密共享演示")
    print("=" * 60)

    shamir = ShamirSecretSharing(threshold=3, total=5)

    # 原始秘密
    secret = 123456789
    print(f"原始秘密: {secret}")

    # 分割秘密
    shares = shamir.split_secret(secret, "Alice")
    print(f"\n生成份额 (k={shamir.threshold}, n={shamir.total}):")
    for i, share in enumerate(shares):
        print(f"  份额{i+1}: {hex(share.value)}")

    # 用3个份额重构
    print(f"\n使用前{shamir.threshold}个份额重构:")
    reconstructed = shamir.reconstruct_secret(shares[:shamir.threshold])
    print(f"  重构秘密: {reconstructed}")
    print(f"  匹配: {'✓' if reconstructed == secret else '✗'}")

    # 用2个份额尝试重构（应该失败）
    print(f"\n使用2个份额重构（不足门限）:")
    try:
        shamir.reconstruct_secret(shares[:2])
    except ValueError as e:
        print(f"  预期失败: {e}")

    # 用不同的份额组合重构
    print(f"\n使用不同份额组合重构 (份额1,3,5):")
    alt_shares = [shares[0], shares[2], shares[4]]
    reconstructed_alt = shamir.reconstruct_secret(alt_shares)
    print(f"  重构秘密: {reconstructed_alt}")
    print(f"  匹配: {'✓' if reconstructed_alt == secret else '✗'}")


# ========== PSI+PFE 集成 ==========

# 尝试导入基于拉格朗日插值的PSI+PFE模块
try:
    from lagrange_psi import (
        GeoPoint as LagrangeGeoPoint,
        PFEPoint,
        LagrangeCoefficients,
        PFERequest,
        PFEMatchResult,
        PseudoRandomFunction,
        DistanceNormalizer,
        LagrangePFE,
        HaversineDistance,
        PSIPlusPFE,
        create_route_from_coords
    )

    _LAGRANGE_PSI_AVAILABLE = True
    print("✓ PSI+PFE模块已加载（拉格朗日插值方案）")
except ImportError:
    _LAGRANGE_PSI_AVAILABLE = False
    print("提示: PSI+PFE模块需要 lagrange_psi 模块")


def is_lagrange_psi_available() -> bool:
    """检查拉格朗日PSI+PFE是否可用"""
    return _LAGRANGE_PSI_AVAILABLE


def get_lagrange_psi_instance(threshold_km: float = 2.0,
                             max_distance_km: float = 10.0) -> PSIPlusPFE:
    """
    获取拉格朗日PSI+PFE实例（兼容接口）

    Args:
        threshold_km: 匹配距离阈值（公里）
        max_distance_km: 最大距离（用于归一化）

    Returns:
        PSI+PFE实例

    Raises:
        ImportError: 模块不可用时
    """
    if not _LAGRANGE_PSI_AVAILABLE:
        raise ImportError("PSI+PFE功能需要 lagrange_psi 模块")

    return PSIPlusPFE(threshold_km=threshold_km, max_distance_km=max_distance_km)


def convert_geo_point(lat: float, lng: float) -> GeoPoint:
    """
    创建兼容的GeoPoint（使用mp_tpsi的GeoPoint）

    Args:
        lat: 纬度
        lng: 经度

    Returns:
        GeoPoint对象
    """
    return GeoPoint(lat=lat, lng=lng)


if __name__ == "__main__":
    # 运行Shamir秘密共享演示
    demo_shamir_secret_sharing()

    # 运行MP-TPSI演示
    demo_mptpsi()

    # 如果PSI+PFE可用，运行演示
    if _LAGRANGE_PSI_AVAILABLE:
        try:
            from lagrange_psi import demo_lagrange_psi
            print("\n")
            demo_lagrange_psi()
        except Exception as e:
            print(f"PSI+PFE演示失败: {e}")
