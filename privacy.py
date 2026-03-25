"""
差分隐私保护模块

实现差分隐私机制，保护用户敏感信息。

功能：
- 拉普拉斯噪声添加
- 位置匿名化
- 查询隐私保护
"""

import math
import random
from typing import Tuple, List, Optional
from dataclasses import dataclass


class DifferentialPrivacy:
    """
    差分隐私保护

    使用拉普拉斯机制实现差分隐私，通过添加噪声保护隐私。
    """

    def __init__(self, epsilon: float = 1.0, delta: float = 1e-5):
        """
        初始化差分隐私保护

        Args:
            epsilon: 隐私预算，越大隐私保护越弱但数据可用性越高
                      通常值在0.1-10之间，1.0是常用值
            delta: 失败概率，用于(epsilon, delta)-差分隐私
        """
        self.epsilon = epsilon
        self.delta = delta

    def add_laplace_noise(self, value: float, sensitivity: float = 1.0) -> float:
        """
        添加拉普拉斯噪声实现差分隐私

        拉普拉斯分布: f(x) = (1/(2b)) * exp(-|x|/b)
        其中 b = sensitivity / epsilon

        Args:
            value: 原始值
            sensitivity: 数据敏感度（单个记录变化对查询结果的最大影响）

        Returns:
            添加噪声后的值
        """
        scale = sensitivity / self.epsilon

        # 使用指数分布生成拉普拉斯噪声
        # 如果 U ~ Uniform(0,1)，则 -scale * ln(U) ~ Exp(1/scale)
        u1 = random.random()
        u2 = random.random()

        # 生成拉普拉斯噪声
        noise = scale * math.log(u1 / u2)

        return value + noise

    def add_gaussian_noise(self, value: float, sensitivity: float = 1.0) -> float:
        """
        添加高斯噪声实现(epsilon, delta)-差分隐私

        高斯分布的标准差: sigma = sqrt(2 * ln(1.25/delta)) * sensitivity / epsilon

        Args:
            value: 原始值
            sensitivity: 数据敏感度

        Returns:
            添加噪声后的值
        """
        sigma = math.sqrt(2 * math.log(1.25 / self.delta)) * sensitivity / self.epsilon

        # 使用Box-Muller变换生成高斯噪声
        u1 = random.random()
        u2 = random.random()
        noise = sigma * math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)

        return value + noise

    def anonymize_location(self, lng: float, lat: float,
                         noise_level: float = 0.001) -> Tuple[float, float]:
        """
        位置匿名化（添加噪声）

        通过在经纬度上添加随机噪声，模糊精确位置。

        Args:
            lng: 经度
            lat: 纬度
            noise_level: 噪声水平（度），0.001度约等于100米

        Returns:
            (noisy_lng, noisy_lat) 匿名化后的坐标
        """
        # 经纬度各添加拉普拉斯噪声
        # 1度经度在赤道约等于111公里
        # 0.001度约等于111米
        noisy_lng = self.add_laplace_noise(lng, sensitivity=noise_level)
        noisy_lat = self.add_laplace_noise(lat, sensitivity=noise_level)

        return (noisy_lng, noisy_lat)

    def privatize_count(self, count: int, sensitivity: int = 1) -> int:
        """
        对计数值进行差分隐私保护

        Args:
            count: 原始计数值
            sensitivity: 敏感度（每次查询最多影响多少计数）

        Returns:
            私有化后的计数值（四舍五入为整数）
        """
        noisy_count = self.add_laplace_noise(count, sensitivity)
        return max(0, int(round(noisy_count)))

    def privatize_sum(self, values: List[float], min_value: float = 0,
                     max_value: float = 100) -> float:
        """
        对求和结果进行差分隐私保护

        Args:
            values: 原始数值列表
            min_value: 单个值的最小可能值
            max_value: 单个值的最大可能值

        Returns:
            私有化后的和
        """
        total = sum(values)
        sensitivity = max_value - min_value
        return self.add_laplace_noise(total, sensitivity)

    def privatize_average(self, values: List[float], min_value: float = 0,
                         max_value: float = 100) -> float:
        """
        对平均值进行差分隐私保护

        Args:
            values: 原始数值列表
            min_value: 单个值的最小可能值
            max_value: 单个值的最大可能值

        Returns:
            私有化后的平均值
        """
        if not values:
            return 0

        total = sum(values)
        n = len(values)

        # 平均值的敏感度
        sensitivity = (max_value - min_value) / n

        noisy_total = self.add_laplace_noise(total, n * sensitivity)
        return noisy_total / n

    def create_histogram(self, items: List[str], bins: List[str]) -> dict:
        """
        创建差分隐私的直方图

        Args:
            items: 要统计的项列表
            bins: 统计桶列表

        Returns:
            私有化后的直方图 {bin: count}
        """
        # 计算原始直方图
        histogram = {bin_name: 0 for bin_name in bins}
        for item in items:
            if item in histogram:
                histogram[item] += 1

        # 对每个计数添加噪声
        privatized = {}
        for bin_name, count in histogram.items():
            privatized[bin_name] = self.privatize_count(count)

        return privatized

    def exponential_mechanism(self, options: List, utility_func: callable,
                             sensitivity: float = 1.0) -> str:
        """
        指数机制：从选项中选择满足差分隐私的输出

        Args:
            options: 选项列表
            utility_func: 效用函数，计算每个选项的效用值
            sensitivity: 效用函数的敏感度

        Returns:
            被选中的选项
        """
        # 计算每个选项的效用值
        utilities = [utility_func(opt) for opt in options]
        max_utility = max(utilities)

        # 计算每个选项的概率权重
        weights = []
        for u in utilities:
            weight = math.exp(self.epsilon * (u - max_utility) / (2 * sensitivity))
            weights.append(weight)

        # 根据权重随机选择
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(options)

        r = random.uniform(0, total_weight)
        cumulative = 0

        for i, weight in enumerate(weights):
            cumulative += weight
            if r <= cumulative:
                return options[i]

        return options[-1]

    def set_epsilon(self, new_epsilon: float):
        """
        更新隐私预算

        Args:
            new_epsilon: 新的隐私预算
        """
        if new_epsilon <= 0:
            raise ValueError("epsilon必须大于0")
        self.epsilon = new_epsilon


@dataclass
class PrivateLocation:
    """私有化位置数据"""
    original_lng: float
    original_lat: float
    noisy_lng: float
    noisy_lat: float
    radius_meters: float  # 误差半径（米）
    timestamp: float


class LocationPrivacy:
    """
    位置隐私保护

    提供位置匿名化和轨迹隐私保护。
    """

    def __init__(self, dp: DifferentialPrivacy = None):
        """
        初始化位置隐私保护

        Args:
            dp: DifferentialPrivacy实例，如果不提供则创建默认实例
        """
        self.dp = dp or DifferentialPrivacy()

    def anonymize_point(self, lng: float, lat: float,
                      precision_meters: float = 100) -> PrivateLocation:
        """
        匿名化单个位置点

        Args:
            lng: 经度
            lat: 纬度
            precision_meters: 隐私精度（米），值越大隐私保护越强

        Returns:
            PrivateLocation对象
        """
        # 1度约等于111公里
        noise_level = precision_meters / 111000

        noisy_lng, noisy_lat = self.dp.anonymize_location(lng, lat, noise_level)

        return PrivateLocation(
            original_lng=lng,
            original_lat=lat,
            noisy_lng=noisy_lng,
            noisy_lat=noisy_lat,
            radius_meters=precision_meters,
            timestamp=time.time()
        )

    def anonymize_trajectory(self, trajectory: List[Tuple[float, float]],
                           precision_meters: float = 100) -> List[PrivateLocation]:
        """
        匿名化轨迹（位置序列）

        Args:
            trajectory: 轨迹点列表 [(lng, lat), ...]
            precision_meters: 隐私精度

        Returns:
            匿名化后的轨迹点列表
        """
        privatized = []
        for lng, lat in trajectory:
            privatized.append(self.anonymize_point(lng, lat, precision_meters))
        return privatized

    def calculate_private_distance(self, point1: Tuple[float, float],
                                 point2: Tuple[float, float],
                                 sensitivity: float = 100) -> float:
        """
        计算私有化距离

        Args:
            point1: 第一个点 (lng, lat)
            point2: 第二个点 (lng, lat)
            sensitivity: 距离计算的敏感度

        Returns:
            添加噪声后的距离（米）
        """
        import time  # 避免循环导入

        # 计算真实距离
        lng1, lat1 = point1
        lng2, lat2 = point2

        R = 6371000  # 地球半径（米）

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        distance = R * c

        # 添加差分隐私噪声
        return self.dp.add_laplace_noise(distance, sensitivity)


# 全局实例
_dp_instance: Optional[DifferentialPrivacy] = None
_location_privacy: Optional[LocationPrivacy] = None


def get_dp_instance(epsilon: float = 1.0) -> DifferentialPrivacy:
    """获取差分隐私实例（单例）"""
    global _dp_instance
    if _dp_instance is None or _dp_instance.epsilon != epsilon:
        _dp_instance = DifferentialPrivacy(epsilon)
    return _dp_instance


def get_location_privacy(epsilon: float = 1.0) -> LocationPrivacy:
    """获取位置隐私实例（单例）"""
    global _location_privacy
    if _location_privacy is None:
        dp = get_dp_instance(epsilon)
        _location_privacy = LocationPrivacy(dp)
    return _location_privacy


# 导入time模块（延迟导入以避免循环）
import time
