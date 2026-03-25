"""
智能匹配引擎

实现多因素加权评分系统，提高匹配准确率和用户满意度。

功能：
- 多因素综合评分（路径、时间、距离、信誉、价格）
- 动态权重配置
- 匹配分数详情展示
- 推荐列表生成
"""

import math
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class MatchScore:
    """匹配分数详情"""
    total_score: float
    route_score: float
    time_score: float
    distance_score: float
    reputation_score: float
    price_score: float


class MatchEngine:
    """智能匹配引擎"""

    def __init__(self, weight_config: Dict[str, float] = None):
        """
        初始化匹配引擎

        Args:
            weight_config: 权重配置字典，如果不提供则使用默认配置
        """
        self.weight_config = weight_config or {
            'route_overlap': 0.40,    # 路径重叠度权重
            'time_preference': 0.20,   # 时间偏好权重
            'distance': 0.15,          # 距离权重
            'reputation': 0.15,         # 信誉权重
            'price': 0.10,             # 价格权重
        }
        self._validate_weights()

    def _validate_weights(self):
        """验证权重配置总和为1.0"""
        total = sum(self.weight_config.values())
        if abs(total - 1.0) > 0.01:
            print(f"警告: 权重总和为{total:.3f}，应该为1.0")

    def calculate_match_score(self, passenger: Dict, vehicle: Dict) -> MatchScore:
        """
        计算综合匹配分数

        Args:
            passenger: 乘客数据字典
            vehicle: 车辆数据字典

        Returns:
            MatchScore对象，包含各维度分数和总分
        """
        # 1. 路径重叠度
        route_score = self._calculate_route_overlap(
            passenger.get('route_path'),
            vehicle.get('route_path')
        )

        # 2. 时间偏好匹配
        time_score = self._calculate_time_match(
            passenger.get('preferred_time'),
            passenger.get('created_at'),
            vehicle.get('created_at')
        )

        # 3. 距离合理性
        distance_score = self._calculate_distance_reasonability(
            passenger.get('start_lng'),
            passenger.get('start_lat'),
            vehicle.get('start_lng'),
            vehicle.get('start_lat')
        )

        # 4. 信誉评分
        reputation_score = self._calculate_reputation_score(vehicle)

        # 5. 价格因素
        price_score = self._calculate_price_match(
            passenger.get('max_price'),
            vehicle.get('price'),
            passenger.get('start'),
            passenger.get('end')
        )

        # 综合加权
        total_score = (
            self.weight_config['route_overlap'] * route_score +
            self.weight_config['time_preference'] * time_score +
            self.weight_config['distance'] * distance_score +
            self.weight_config['reputation'] * reputation_score +
            self.weight_config['price'] * price_score
        )

        return MatchScore(
            total_score=round(total_score, 3),
            route_score=round(route_score, 3),
            time_score=round(time_score, 3),
            distance_score=round(distance_score, 3),
            reputation_score=round(reputation_score, 3),
            price_score=round(price_score, 3)
        )

    def _calculate_route_overlap(self, p_route_path: str, v_route_path: str) -> float:
        """
        计算路径重叠度

        Args:
            p_route_path: 乘客路径JSON字符串
            v_route_path: 车辆路径JSON字符串

        Returns:
            重叠度分数 (0.0 - 1.0)
        """
        try:
            from geo_route import parse_route_path, calculate_route_overlap

            p_path = parse_route_path(p_route_path) if p_route_path else []
            v_path = parse_route_path(v_route_path) if v_route_path else []

            if not p_path or not v_path:
                return 0.3  # 无路径数据时给基础分

            overlap = calculate_route_overlap(p_path, v_path)
            # 提高重叠度的敏感性
            return min(1.0, overlap * 1.5)

        except Exception as e:
            print(f"路径重叠度计算失败: {e}")
            return 0.3

    def _calculate_time_match(self, preferred_time: str, p_created: str, v_created: str) -> float:
        """
        计算时间偏好匹配分数

        Args:
            preferred_time: 乘客偏好时间
            p_created: 乘客注册时间
            v_created: 车辆注册时间

        Returns:
            时间匹配分数 (0.0 - 1.0)
        """
        # 如果没有偏好时间，基于等待时间评分
        if not preferred_time:
            if p_created and v_created:
                # 计算等待时间差异
                try:
                    from datetime import datetime
                    p_time = datetime.fromisoformat(p_created.replace('Z', '+00:00'))
                    v_time = datetime.fromisoformat(v_created.replace('Z', '+00:00'))
                    time_diff = abs((p_time - v_time).total_seconds())

                    # 等待时间越短分数越高（5分钟内最高分）
                    if time_diff < 300:  # 5分钟
                        return 1.0
                    elif time_diff < 900:  # 15分钟
                        return 0.8
                    elif time_diff < 1800:  # 30分钟
                        return 0.6
                    else:
                        return 0.4
                except Exception:
                    return 0.7
            return 0.7

        # 有偏好时间时，基于偏好的匹配程度
        # 简化实现：直接返回中等分数
        return 0.7

    def _calculate_distance_reasonability(self, p_lng: float, p_lat: float,
                                       v_lng: float, v_lat: float) -> float:
        """
        计算距离合理性分数

        Args:
            p_lng, p_lat: 乘客起点坐标
            v_lng, v_lat: 车辆起点坐标

        Returns:
            距离合理性分数 (0.0 - 1.0)
        """
        if not all([p_lng, p_lat, v_lng, v_lat]):
            return 0.5  # 无坐标数据时给中等分

        # 计算两点间距离
        distance = self._haversine_distance(p_lng, p_lat, v_lng, v_lat)

        # 距离越近分数越高（单位：米）
        if distance < 500:  # 500米内
            return 1.0
        elif distance < 1000:  # 1公里内
            return 0.9
        elif distance < 2000:  # 2公里内
            return 0.7
        elif distance < 5000:  # 5公里内
            return 0.5
        else:
            return 0.3

    def _haversine_distance(self, lng1: float, lat1: float,
                           lng2: float, lat2: float) -> float:
        """
        使用Haversine公式计算两点间的大圆距离（米）
        """
        R = 6371000  # 地球半径（米）

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def _calculate_reputation_score(self, vehicle: Dict) -> float:
        """
        计算信誉评分

        Args:
            vehicle: 车辆数据字典

        Returns:
            信誉分数 (0.0 - 1.0)
        """
        # 从vehicle中获取信誉相关数据
        reputation = vehicle.get('reputation', 80)  # 默认80分
        rating = vehicle.get('rating', 4.5)  # 默认4.5星
        total_trips = vehicle.get('total_trips', 10)  # 默认10次

        # 综合评分
        reputation_score = reputation / 100
        rating_score = rating / 5.0

        # 经验加成：完成次数越多，分数越稳定
        experience_bonus = min(0.1, total_trips / 1000)  # 最多0.1的加成

        score = (reputation_score * 0.5 + rating_score * 0.5) + experience_bonus
        return min(1.0, score)

    def _calculate_price_match(self, max_price: float, price: float,
                             start: str, end: str) -> float:
        """
        计算价格匹配分数

        Args:
            max_price: 乘客最高接受价格
            price: 车辆实际价格
            start: 起点
            end: 终点

        Returns:
            价格匹配分数 (0.0 - 1.0)
        """
        if not max_price or not price:
            return 0.7  # 无价格数据时给中等分

        # 计算价格比例
        if price == 0:
            return 0.0

        ratio = price / max_price

        # 价格越低或越接近乘客期望，分数越高
        if ratio <= 0.7:
            return 1.0  # 大幅低于期望
        elif ratio <= 0.9:
            return 0.9
        elif ratio <= 1.0:
            return 0.8
        elif ratio <= 1.1:
            return 0.6
        else:
            return 0.3  # 超出期望太多

    def find_best_matches(self, passenger: Dict, vehicles: List[Dict],
                        threshold: float = 0.5, top_k: int = 3) -> List[Tuple[Dict, MatchScore]]:
        """
        找到最佳匹配的车辆列表

        Args:
            passenger: 乘客数据
            vehicles: 车辆列表
            threshold: 最低匹配阈值
            top_k: 返回前k个最佳匹配

        Returns:
            [(vehicle, MatchScore), ...] 匹配列表，按总分降序排列
        """
        scored_vehicles = []

        for vehicle in vehicles:
            if vehicle.get('seats', 0) < 1:
                continue

            score = self.calculate_match_score(passenger, vehicle)

            if score.total_score >= threshold:
                scored_vehicles.append((vehicle, score))

        # 按总分降序排序
        scored_vehicles.sort(key=lambda x: x[1].total_score, reverse=True)

        # 返回前top_k个
        return scored_vehicles[:top_k]

    def update_weights(self, new_weights: Dict[str, float]):
        """
        更新权重配置

        Args:
            new_weights: 新的权重字典
        """
        self.weight_config = new_weights
        self._validate_weights()


# 全局实例
_match_engine: MatchEngine = None


def get_match_engine(weight_config: Dict[str, float] = None) -> MatchEngine:
    """获取匹配引擎实例（单例）"""
    global _match_engine
    if _match_engine is None or weight_config is not None:
        _match_engine = MatchEngine(weight_config)
    return _match_engine
