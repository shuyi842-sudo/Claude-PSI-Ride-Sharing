"""
基于拉格朗日插值的PSI+PFE拼车匹配方案
Lagrange-based PSI + PFE (Private Function Evaluation) for Ride Matching

结合隐私集合求交(PSI)和私有函数求值(PFE)：
- 支持带距离阈值的模糊匹配
- 通过拉格朗日插值隐藏距离信息
- 双方仅传输加密形式的数据

作者: Claude
版本: 1.0.0
"""

import hashlib
import hmac
import secrets
import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field, asdict
import json


# ========== 数据结构 ==========

@dataclass
class GeoPoint:
    """地理坐标点"""
    lat: float  # 纬度 -90 到 90
    lng: float  # 经度 -180 到 180

    def __repr__(self):
        return f"({self.lat:.4f}, {self.lng:.4f})"

    def to_dict(self) -> Dict:
        return {"lat": self.lat, "lng": self.lng}

    @classmethod
    def from_dict(cls, data: Dict) -> 'GeoPoint':
        return cls(lat=data["lat"], lng=data["lng"])


@dataclass
class PFEPoint:
    """PFE方案的点数据"""
    prf_x: int        # 伪随机值（自变量 x）
    distance_y: int   # 归一化距离（因变量 y），范围 [0, 255]
    original_hash: int  # 原始地点哈希

    def to_dict(self) -> Dict:
        return {
            "prf_x": hex(self.prf_x),
            "distance_y": self.distance_y,
            "original_hash": hex(self.original_hash)
        }


@dataclass
class LagrangeCoefficients:
    """拉格朗日插值系数"""
    coefficients: List[int]  # [a₀, a₁, a₂, ...]
    degree: int             # 多项式次数
    modulus: int = 2**256 - 2**224 + 2**192 + 2**96 - 1  # 大素数

    def to_dict(self) -> Dict:
        return {
            "coefficients": [hex(c) for c in self.coefficients],
            "degree": self.degree,
            "modulus": hex(self.modulus)
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'LagrangeCoefficients':
        return cls(
            coefficients=[int(c, 16) for c in data["coefficients"]],
            degree=data["degree"],
            modulus=int(data["modulus"], 16)
        )


@dataclass
class PFERequest:
    """PFE请求（乘客发送给车辆）"""
    encrypted_points: List[str]  # 加密的地点哈希
    coefficients: LagrangeCoefficients  # 拉格朗日系数
    prf_seed: bytes               # PRF种子
    passenger_id: str             # 乘客ID（可选）
    timestamp: float              # 时间戳

    def to_dict(self, hide_seed: bool = False) -> Dict:
        result = {
            "encrypted_points": self.encrypted_points,
            "coefficients": self.coefficients.to_dict(),
            "passenger_id": self.passenger_id,
            "timestamp": self.timestamp
        }
        if not hide_seed:
            result["prf_seed"] = self.prf_seed.hex()
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> 'PFERequest':
        return cls(
            encrypted_points=data["encrypted_points"],
            coefficients=LagrangeCoefficients.from_dict(data["coefficients"]),
            prf_seed=bytes.fromhex(data["prf_seed"]),
            passenger_id=data.get("passenger_id", ""),
            timestamp=data.get("timestamp", 0)
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class PFEMatchResult:
    """PFE匹配结果"""
    matched: bool              # 是否匹配
    distance_km: float          # 实际距离（公里）
    intersection_count: int     # 交集点数
    verification_code: str      # 验证码
    passenger_id: str           # 乘客ID
    vehicle_id: str            # 车辆ID
    timestamp: float            # 时间戳

    def to_dict(self) -> Dict:
        return {
            "matched": self.matched,
            "distance_km": round(self.distance_km, 3),
            "intersection_count": self.intersection_count,
            "verification_code": self.verification_code,
            "passenger_id": self.passenger_id,
            "vehicle_id": self.vehicle_id,
            "timestamp": self.timestamp
        }


# ========== 核心组件 ==========

class PseudoRandomFunction:
    """
    伪随机函数 (PRF) - Pseudo Random Function

    使用HMAC-SHA256实现伪随机函数
    确保相同输入产生相同输出，不同输入输出不可预测
    """

    def __init__(self, hash_algorithm: str = "sha256"):
        """
        初始化PRF

        Args:
            hash_algorithm: 哈希算法 (sha256, sha512)
        """
        self.hash_algorithm = hash_algorithm

    def generate_shared_seed(self, size: int = 16) -> bytes:
        """
        生成共享的PRF种子

        Args:
            size: 种子大小（字节）

        Returns:
            随机种子
        """
        return secrets.token_bytes(size)

    def generate_x(self, point_hash: int, seed: bytes) -> int:
        """
        对地点哈希生成伪随机值

        这是拉格朗日插值的自变量 x

        Args:
            point_hash: 地点的哈希值（整数）
            seed: PRF种子

        Returns:
            伪随机值（整数）
        """
        # 使用HMAC计算PRF
        # HMAC(key, message) → pseudo-random output
        key = seed
        message = point_hash.to_bytes(32, 'big')

        prf_output = hmac.new(key, message, self.hash_algorithm).digest()

        # 转换为大整数
        return int.from_bytes(prf_output, 'big')

    def generate_x_batch(self, point_hashes: List[int], seed: bytes) -> List[int]:
        """
        批量生成伪随机值

        Args:
            point_hashes: 地点哈希值列表
            seed: PRF种子

        Returns:
            伪随机值列表
        """
        return [self.generate_x(h, seed) for h in point_hashes]


class DistanceNormalizer:
    """
    距离归一化器

    将实际距离映射到固定范围 [0, 255]
    用于拉格朗日插值中的因变量 y
    """

    # 最大考虑距离（公里），超过此值距离归一化为255
    MAX_DISTANCE_KM = 10.0

    # 输出范围 [0, 255]
    MIN_VALUE = 0
    MAX_VALUE = 255

    def __init__(self, max_distance_km: float = None):
        """
        初始化归一化器

        Args:
            max_distance_km: 最大距离阈值（公里）
        """
        self.max_distance_km = max_distance_km or self.MAX_DISTANCE_KM

    def normalize(self, distance_km: float) -> int:
        """
        归一化距离到 [0, 255]

        线性归一化：0km → 0, max_distance_km → 255

        Args:
            distance_km: 实际距离（公里）

        Returns:
            归一化后的值（整数，0-255）
        """
        # 限制在有效范围内
        clamped = min(distance_km, self.max_distance_km)
        clamped = max(clamped, 0)

        # 线性映射
        normalized = (clamped / self.max_distance_km) * self.MAX_VALUE

        return int(normalized)

    def denormalize(self, value: int) -> float:
        """
        反归一化：从 [0, 255] 恢复实际距离

        Args:
            value: 归一化值（0-255）

        Returns:
            实际距离（公里）
        """
        # 限制在有效范围内
        clamped = max(min(value, self.MAX_VALUE), self.MIN_VALUE)

        # 线性反映射
        distance = (clamped / self.MAX_VALUE) * self.max_distance_km

        return distance

    def normalize_batch(self, distances: List[float]) -> List[int]:
        """批量归一化"""
        return [self.normalize(d) for d in distances]

    def denormalize_batch(self, values: List[int]) -> List[float]:
        """批量反归一化"""
        return [self.denormalize(v) for v in values]


class LagrangePFE:
    """
    基于拉格朗日的私有函数求值 (Private Function Evaluation)

    核心思想：
    1. 乘客构建一个函数 f(x) = y，其中 y 是归一化的距离 [0, 255]
    2. 将函数以多项式系数的形式发送给车辆
    3. 车辆使用 PRF(x) 评估多项式，得到归一化距离
    4. 车辆反归一化得到实际距离，判断是否匹配

    车辆无法通过多项式系数推断原始距离信息

    注意：此实现使用浮点数插值，确保精确通过所有点
    """

    def __init__(self):
        """
        初始化拉格朗日PFE
        """
        # 使用大素数作为模数（用于存储系数）
        self.modulus = 2**256 - 2**224 + 2**192 + 2**96 - 1

    def build_interpolation(self, points: List[PFEPoint]) -> LagrangeCoefficients:
        """
        构建拉格朗日插值多项式

        给定点集 {(x₁,y₁), (x₂,y₂), ..., (xₙ,yₙ)}
        构建多项式 L(x) 满足 L(xᵢ) = yᵢ

        使用标准拉格朗日插值方法计算多项式系数

        Args:
            points: 点列表

        Returns:
            拉格朗日系数对象

        Raises:
            ValueError: 点数不足（至少需要1个点）
        """
        if not points:
            raise ValueError("至少需要一个点进行插值")

        n = len(points)

        if n == 1:
            # 单点：常数多项式 f(x) = y₁
            return LagrangeCoefficients(
                coefficients=[points[0].distance_y],
                degree=0,
                modulus=self.modulus
            )

        # 将点转换为 (x, y) 元组，使用浮点数计算
        xy_pairs = [(float(p.prf_x), float(p.distance_y)) for p in points]

        # 使用高斯消元法求解多项式系数（浮点数版本）
        # L(x) = a₀ + a₁·x + a₂·x² + ... + aₙ₋₁·xⁿ⁻¹
        coeffs_float = self._solve_coefficients_float(xy_pairs)

        # 将浮点数系数存储为整数（乘以一个大数并取整）
        SCALE_FACTOR = 10**10
        coefficients = [int(round(c * SCALE_FACTOR)) for c in coeffs_float]

        return LagrangeCoefficients(
            coefficients=coefficients,
            degree=len(coefficients) - 1,
            modulus=self.modulus
        )

    def _solve_coefficients_float(self, points: List[Tuple[float, float]]) -> List[float]:
        """
        使用高斯消元法求解多项式系数（浮点数版本）

        对于 n 个点，构建 n×n 的范德蒙矩阵：
        | 1      x₁    x₁² ... x₁ⁿ⁻¹ | | a₀ |   | y₁ |
        | 1      x₂    x₂² ... x₂ⁿ⁻¹ | | a₁ | = | y₂ |
        | ...    ...   ... ... ...    | | ...|   | ...|
        | 1      xₙ    xₙ² ... xₙⁿ⁻¹ | |aₙ₋₁|   | yₙ |

        Args:
            points: (x, y) 点列表

        Returns:
            多项式系数列表 [a₀, a₁, ..., aₙ₋₁]
        """
        n = len(points)

        # 构建增广矩阵 [A|B]
        matrix = []
        for x, y in points:
            row = []
            for j in range(n):
                row.append(x ** j)
            row.append(y)
            matrix.append(row)

        # 高斯消元（浮点数）
        self._gaussian_elimination_float(matrix, n)

        # 提取系数（最后一列）
        coefficients = [matrix[i][n] for i in range(n)]

        return coefficients

    def _gaussian_elimination_float(self, matrix: List[List[float]], n: int):
        """
        高斯消元法（浮点数版本）

        Args:
            matrix: 增广矩阵
            n: 方程数量
        """
        EPSILON = 1e-10

        # 前向消元
        for i in range(n):
            # 找到主元（最大的非零元素）
            pivot_row = i
            max_abs = abs(matrix[i][i])
            for k in range(i + 1, n):
                if abs(matrix[k][i]) > max_abs:
                    max_abs = abs(matrix[k][i])
                    pivot_row = k

            if max_abs < EPSILON:
                continue  # 这一列全为0，跳过

            # 交换行
            if pivot_row != i:
                matrix[i], matrix[pivot_row] = matrix[pivot_row], matrix[i]

            # 主元
            pivot = matrix[i][i]

            # 归一化主元行
            for j in range(n + 1):
                matrix[i][j] = matrix[i][j] / pivot

            # 消去其他行的这一列
            for k in range(n):
                if k != i and abs(matrix[k][i]) > EPSILON:
                    factor = matrix[k][i]
                    for j in range(n + 1):
                        matrix[k][j] = matrix[k][j] - factor * matrix[i][j]

    def evaluate(self, coefficients: LagrangeCoefficients, x: int) -> int:
        """
        评估多项式在 x 处的值

        L(x) = Σ aᵢ · xⁱ

        使用霍纳法则 (Horner's method) 高效计算

        Args:
            coefficients: 拉格朗日系数对象
            x: 评估点

        Returns:
            多项式的值（整数，在[0, 255]范围内）
        """
        coeffs = coefficients.coefficients
        SCALE_FACTOR = 10**10

        result_float = 0.0
        x_float = float(x)

        # 霍纳法则: a₀ + x(a₁ + x(a₂ + ... + x(aₙ₋₁)))
        for i in range(len(coeffs) - 1, -1, -1):
            coeff_float = coeffs[i] / SCALE_FACTOR
            result_float = result_float * x_float + coeff_float

        # 四舍五入并限制在[0, 255]范围内
        result_int = int(round(result_float))
        result_int = max(0, min(255, result_int))

        return result_int

    def evaluate_batch(self, coefficients: LagrangeCoefficients, x_values: List[int]) -> List[int]:
        """批量评估多项式"""
        return [self.evaluate(coefficients, x) for x in x_values]

    def export_coefficients_to_json(self, coefficients: LagrangeCoefficients) -> str:
        """将系数导出为JSON字符串"""
        return json.dumps(coefficients.to_dict(), ensure_ascii=False)


class HaversineDistance:
    """Haversine距离计算器"""

    EARTH_RADIUS_KM = 6371.0  # 地球半径（公里）

    @staticmethod
    def calculate(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        计算两点间的Haversine距离（公里）

        Args:
            lat1, lng1: 第一个点的坐标
            lat2, lng2: 第二个点的坐标

        Returns:
            两点间的距离（公里）
        """
        # 转换为弧度
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        # Haversine公式
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        return HaversineDistance.EARTH_RADIUS_KM * c


# ========== PSI+PFE组合协议 ==========

class PSIPlusPFE:
    """
    PSI + PFE 组合协议

    完整的隐私保护拼车匹配协议：

    乘客侧流程：
    1. 对路线每个点计算PRF值和到目标地点的距离
    2. 归一化距离到 [0, 255]
    3. 构建拉格朗日插值多项式
    4. 将加密的地点哈希和多项式系数发送给车辆

    车辆侧流程：
    1. 使用相同PRF函数生成自己的地点PRF值
    2. 通过PSI找出双方地点的交集（比较加密哈希）
    3. 对每个交集点，使用拉格朗日多项式求值
    4. 反归一化得到实际距离
    5. 判断距离是否小于阈值，决定是否匹配
    """

    def __init__(self, threshold_km: float = 2.0, max_distance_km: float = 10.0):
        """
        初始化PSI+PFE协议

        Args:
            threshold_km: 匹配距离阈值（公里）
            max_distance_km: 最大距离（用于归一化）
        """
        self.threshold_km = threshold_km
        self.prf = PseudoRandomFunction()
        self.normalizer = DistanceNormalizer(max_distance_km)
        self.lagrange = LagrangePFE()

    def passenger_prepare_request(
        self,
        passenger_route: List[GeoPoint],
        target_point: GeoPoint,
        passenger_id: str = ""
    ) -> PFERequest:
        """
        乘客侧准备PFE请求

        流程：
        1. 生成共享PRF种子
        2. 对乘客路线每个点计算：
           - PRF值 xᵢ
           - 到目标地点的距离 dᵢ
           - 归一化距离 yᵢ
        3. 构建点集 {(xᵢ, yᵢ)}
        4. 拉格朗日插值 → 多项式系数
        5. 计算加密的地点哈希
        6. 打包为PFE请求

        Args:
            passenger_route: 乘客路线点列表
            target_point: 目标地点
            passenger_id: 乘客ID

        Returns:
            PFE请求对象
        """
        # 1. 生成PRF种子
        seed = self.prf.generate_shared_seed()

        # 2. 计算每个点的数据
        pfe_points = []
        encrypted_hashes = []

        for point in passenger_route:
            # 计算原始哈希
            point_hash = self._hash_point(point)

            # 计算PRF值（自变量 x）
            prf_x = self.prf.generate_x(point_hash, seed)

            # 计算到目标地点的距离
            distance_km = HaversineDistance.calculate(
                point.lat, point.lng,
                target_point.lat, target_point.lng
            )

            # 归一化距离（因变量 y）
            distance_y = self.normalizer.normalize(distance_km)

            # 存储点数据
            pfe_points.append(PFEPoint(
                prf_x=prf_x,
                distance_y=distance_y,
                original_hash=point_hash
            ))

            # 计算加密的地点哈希（用于PSI）
            encrypted_hash = self._encrypt_hash(point_hash, seed)
            encrypted_hashes.append(encrypted_hash)

        # 3. 拉格朗日插值
        coefficients = self.lagrange.build_interpolation(pfe_points)

        # 4. 构建请求
        request = PFERequest(
            encrypted_points=encrypted_hashes,
            coefficients=coefficients,
            prf_seed=seed,
            passenger_id=passenger_id,
            timestamp=secrets.token_hex(8) + str(int(__import__('time').time() * 1000))
        )

        return request

    def vehicle_process_request(
        self,
        request: PFERequest,
        vehicle_route: List[GeoPoint],
        vehicle_id: str = ""
    ) -> PFEMatchResult:
        """
        车辆侧处理PFE请求

        流程：
        1. 使用相同PRF函数生成车辆路线点的加密哈希
        2. 执行PSI：找出双方路线的交集（精确匹配）
        3. 对每个交集点，用拉格朗日函数求值
        4. 反归一化得到实际距离
        5. 阈值判断，生成匹配结果

        注意：这是基于精确哈希匹配的PSI协议。
        对于模糊匹配，需要修改协议设计。

        Args:
            request: 乘客发送的PFE请求
            vehicle_route: 车辆路线点列表
            vehicle_id: 车辆ID

        Returns:
            PFE匹配结果
        """
        # 1. 使用请求中的种子处理车辆路线
        vehicle_encrypted = []
        vehicle_prf_x_map = {}  # 存储PRF值用于后续求值

        for point in vehicle_route:
            point_hash = self._hash_point(point)
            encrypted = self._encrypt_hash(point_hash, request.prf_seed)
            vehicle_encrypted.append(encrypted)

            # 计算PRF值（用于拉格朗日求值）
            prf_x = self.prf.generate_x(point_hash, request.prf_seed)
            vehicle_prf_x_map[encrypted] = prf_x

        # 2. PSI: 找出交集（加密哈希相等）
        intersections = set(request.encrypted_points) & set(vehicle_encrypted)

        # 3. 对每个交集点求值
        min_distance = float('inf')
        intersection_count = len(intersections)

        for encrypted_hash in intersections:
            # 获取PRF值（自变量 x）
            prf_x = vehicle_prf_x_map[encrypted_hash]

            # 使用拉格朗日多项式求值
            normalized_distance = self.lagrange.evaluate(
                request.coefficients, prf_x
            )

            # 反归一化得到实际距离
            actual_distance = self.normalizer.denormalize(normalized_distance)

            min_distance = min(min_distance, actual_distance)

        # 4. 判断是否匹配
        matched = (intersection_count > 0) and (min_distance <= self.threshold_km)

        # 5. 生成验证码
        verification_code = self._generate_verification_code(
            request.passenger_id,
            vehicle_id,
            matched,
            intersection_count
        )

        return PFEMatchResult(
            matched=matched,
            distance_km=min_distance if matched else 0.0,
            intersection_count=intersection_count,
            verification_code=verification_code,
            passenger_id=request.passenger_id,
            vehicle_id=vehicle_id,
            timestamp=int(__import__('time').time())
        )

    def batch_vehicle_process(
        self,
        request: PFERequest,
        vehicles_routes: Dict[str, List[GeoPoint]]
    ) -> Dict[str, PFEMatchResult]:
        """
        批量处理多辆车的匹配请求

        Args:
            request: 乘客的PFE请求
            vehicles_routes: 车辆路线字典 {vehicle_id: route}

        Returns:
            每辆车的匹配结果
        """
        results = {}
        for vehicle_id, route in vehicles_routes.items():
            result = self.vehicle_process_request(request, route, vehicle_id)
            results[vehicle_id] = result

        # 按距离排序（优先推荐距离近的）
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1].distance_km if x[1].matched else float('inf')
        )

        return dict(sorted_results)

    def _hash_point(self, point: GeoPoint) -> int:
        """
        将地理坐标点哈希为整数

        Args:
            point: 地理坐标点

        Returns:
            哈希值（整数）
        """
        # 使用SHA-256哈希坐标
        coord_str = f"{point.lat:.6f},{point.lng:.6f}"
        h = hashlib.sha256(coord_str.encode()).digest()
        return int.from_bytes(h, 'big')

    def _encrypt_hash(self, point_hash: int, seed: bytes) -> str:
        """
        加密/盲化地点哈希（用于PSI）

        Args:
            point_hash: 地点哈希
            seed: PRF种子

        Returns:
            加密后的哈希字符串
        """
        # 使用HMAC作为加密/盲化
        h = hmac.new(seed, point_hash.to_bytes(32, 'big'), 'sha256').digest()
        return h.hex()[:16]  # 取前16字符作为哈希标识

    def _generate_verification_code(
        self,
        passenger_id: str,
        vehicle_id: str,
        matched: bool,
        intersection_count: int
    ) -> str:
        """
        生成匹配验证码

        Args:
            passenger_id: 乘客ID
            vehicle_id: 车辆ID
            matched: 是否匹配
            intersection_count: 交集点数

        Returns:
            6位大写验证码
        """
        # 使用时间戳和随机盐增加随机性
        timestamp = int(__import__('time').time() * 1000)
        random_salt = secrets.token_hex(4)

        input_str = f"PFE:{passenger_id}:{vehicle_id}:{matched}:{intersection_count}:{timestamp}:{random_salt}"
        h = hashlib.sha256(input_str.encode()).hexdigest()

        # 取前6个字符，转换为大写
        return h[:6].upper()


# ========== 辅助函数 ==========

def create_route_from_coords(coords: List[Tuple[float, float]]) -> List[GeoPoint]:
    """
    从坐标列表创建路线

    Args:
        coords: 坐标列表 [(lat, lng), ...]

    Returns:
        地理坐标点列表
    """
    return [GeoPoint(lat=lat, lng=lng) for lat, lng in coords]


def parse_route_from_json(json_str: str) -> List[GeoPoint]:
    """
    从JSON字符串解析路线

    Args:
        json_str: JSON格式字符串

    Returns:
        地理坐标点列表
    """
    try:
        data = json.loads(json_str)
        return [GeoPoint(lat=p["lat"], lng=p["lng"]) for p in data]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def format_route_to_json(route: List[GeoPoint]) -> str:
    """
    将路线格式化为JSON字符串

    Args:
        route: 地理坐标点列表

    Returns:
        JSON字符串
    """
    return json.dumps([p.to_dict() for p in route], ensure_ascii=False)


# ========== 演示程序 ==========

def demo_lagrange_psi():
    """演示拉格朗日PSI+PFE协议"""
    print("=" * 70)
    print("基于拉格朗日插值的PSI+PFE拼车匹配协议演示")
    print("=" * 70)

    # 创建协议实例
    protocol = PSIPlusPFE(threshold_km=2.0, max_distance_km=10.0)

    # 乘客数据
    print("\n【乘客侧】")
    passenger_route = create_route_from_coords([
        (39.8800, 116.3500),  # 起点
        (39.8900, 116.3700),
        (39.9000, 116.3900),
        (39.9042, 116.4074),  # 接近天安门
        (39.9100, 116.4200)
    ])
    target_point = GeoPoint(39.9042, 116.4074)  # 目的地：天安门

    print(f"乘客路线: {len(passenger_route)} 个点")
    print(f"目标地点: {target_point}")
    print(f"匹配阈值: {protocol.threshold_km} km")

    # 乘客准备请求
    request = protocol.passenger_prepare_request(
        passenger_route,
        target_point,
        passenger_id="P001"
    )

    print(f"\n✓ 生成PFE请求:")
    print(f"  - PRF种子: {request.prf_seed.hex()[:16]}...")
    print(f"  - 加密点数: {len(request.encrypted_points)}")
    print(f"  - 拉格朗日多项式次数: {request.coefficients.degree}")

    # 车辆数据
    print("\n【车辆侧】")

    vehicle_routes = {
        "V001": create_route_from_coords([
            (39.8500, 116.3000),
            (39.8700, 116.3300),
            (39.9042, 116.4074),  # 经过天安门附近
            (39.9200, 116.4300)
        ]),
        "V002": create_route_from_coords([
            (39.9500, 116.5000),
            (39.9600, 116.5100),
            (39.9700, 116.5200),
            (39.9800, 116.5300)  # 远离天安门
        ]),
        "V003": create_route_from_coords([
            (39.8900, 116.4000),
            (39.9042, 116.4074),  # 接近天安门
            (39.9150, 116.4150),
            (39.9250, 116.4250)
        ])
    }

    print(f"可用车辆: {len(vehicle_routes)} 辆")

    # 批量处理
    print("\n【批量匹配】")
    results = protocol.batch_vehicle_process(request, vehicle_routes)

    print("\n匹配结果:")
    for i, (vehicle_id, result) in enumerate(results.items(), 1):
        status = "✓ 匹配" if result.matched else "✗ 不匹配"
        print(f"  {i}. {vehicle_id}: {status}")
        if result.matched:
            print(f"     距离: {result.distance_km:.3f} km")
            print(f"     交集点数: {result.intersection_count}")
            print(f"     验证码: {result.verification_code}")
        else:
            print(f"     交集点数: {result.intersection_count}")

    # 找出最佳匹配
    print("\n【最佳匹配】")
    matched_results = [(vid, res) for vid, res in results.items() if res.matched]
    if matched_results:
        best_vehicle, best_result = min(
            matched_results,
            key=lambda x: x[1].distance_km
        )
        print(f"推荐车辆: {best_vehicle}")
        print(f"验证码: {best_result.verification_code}")
    else:
        print("没有找到匹配的车辆")

    return results


if __name__ == "__main__":
    demo_lagrange_psi()
