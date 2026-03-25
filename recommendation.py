"""
智能推荐系统

基于用户历史数据和机器学习算法，提供个性化的路线和目的地推荐。

功能：
- 路线聚类分析
- 目的地预测
- 相似用户推荐
- 热门路线推荐
"""

import json
import hashlib
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import math


@dataclass
class RouteFeature:
    """路线特征向量"""
    start_area: str
    end_area: str
    avg_distance: float
    peak_hour_ratio: float
    route_vector: Tuple[float, ...]


@dataclass
class Recommendation:
    """推荐结果"""
    item_type: str
    item_id: str
    item_data: Dict
    score: float
    reason: str


class RecommendationEngine:
    """智能推荐引擎"""

    def __init__(self, min_cluster_size: int = 3, max_clusters: int = 5):
        """
        初始化推荐引擎

        Args:
            min_cluster_size: 最小聚类大小
            max_clusters: 最大聚类数
        """
        self.min_cluster_size = min_cluster_size
        self.max_clusters = max_clusters
        self.user_clusters: Dict[str, int] = {}
        self.clusters: Dict[int, List[Dict]] = {}
        self.popular_routes: Dict[str, int] = defaultdict(int)
        self.destination_frequency: Dict[str, int] = defaultdict(int)
        self.start_frequency: Dict[str, int] = defaultdict(int)

    def _extract_area_code(self, address: str) -> str:
        """提取地址的区域码（用于简化匹配）"""
        if not address:
            return "UNKNOWN"
        address = address.strip()
        if len(address) >= 2:
            return address[:2]
        return address

    def _extract_route_features(self, trip: Dict) -> RouteFeature:
        """提取路线特征"""
        start = trip.get("start", "")
        end = trip.get("end", "")
        
        start_area = self._extract_area_code(start)
        end_area = self._extract_area_code(end)
        
        distance = 0.0
        if trip.get("start_lng") and trip.get("end_lng"):
            distance = math.sqrt(
                (trip.get("start_lng", 0) - trip.get("end_lng", 0)) ** 2 +
                (trip.get("start_lat", 0) - trip.get("end_lat", 0)) ** 2
            )
        
        peak_hour_ratio = 0.0
        if trip.get("created_at"):
            try:
                from datetime import datetime
                if isinstance(trip["created_at"], str):
                    dt = datetime.fromisoformat(trip["created_at"])
                else:
                    dt = trip["created_at"]
                hour = dt.hour
                peak_hour_ratio = 1.0 if 7 <= hour <= 9 or 17 <= hour <= 19 else 0.0
            except:
                peak_hour_ratio = 0.0
        
        route_vector = (distance, peak_hour_ratio, len(start), len(end))
        
        return RouteFeature(
            start_area=start_area,
            end_area=end_area,
            avg_distance=distance,
            peak_hour_ratio=peak_hour_ratio,
            route_vector=route_vector
        )

    def _compute_feature_distance(self, f1: RouteFeature, f2: RouteFeature) -> float:
        """计算特征距离（用于聚类）"""
        dist = 0.0
        
        if f1.start_area == f2.start_area:
            dist += 0.5
        if f1.end_area == f2.end_area:
            dist += 0.5
            
        dist += abs(f1.avg_distance - f2.avg_distance) * 0.1
        dist += abs(f1.peak_hour_ratio - f2.peak_hour_ratio) * 0.2
        
        return dist

    def _simple_kmeans(self, features: List[RouteFeature], k: int) -> List[int]:
        """简化的K-means聚类"""
        if len(features) < k:
            return [0] * len(features)
        
        centroids = features[:k]
        assignments = [0] * len(features)
        
        for _ in range(10):
            new_assignments = []
            for f in features:
                min_dist = float('inf')
                best_cluster = 0
                for i, centroid in enumerate(centroids):
                    d = self._compute_feature_distance(f, centroid)
                    if d < min_dist:
                        min_dist = d
                        best_cluster = i
                new_assignments.append(best_cluster)
            
            if new_assignments == assignments:
                break
            assignments = new_assignments
            
            for i in range(k):
                cluster_features = [features[j] for j in range(len(features)) if assignments[j] == i]
                if cluster_features:
                    centroids[i] = cluster_features[len(cluster_features) // 2]
        
        return assignments

    def analyze_user_routes(self, user_history: List[Dict]) -> Dict:
        """
        分析用户路线模式
        
        Args:
            user_history: 用户历史行程列表
            
        Returns:
            分析结果字典
        """
        if not user_history:
            return {
                "clusters": [],
                "frequent_starts": [],
                "frequent_ends": [],
                "peak_ratio": 0.0
            }
        
        features = [self._extract_route_features(trip) for trip in user_history]
        
        k = min(self.max_clusters, max(1, len(features) // 2))
        if k > 0:
            cluster_assignments = self._simple_kmeans(features, k)
        else:
            cluster_assignments = []
        
        frequent_starts = defaultdict(int)
        frequent_ends = defaultdict(int)
        peak_count = 0
        
        for trip in user_history:
            start = trip.get("start", "")
            end = trip.get("end", "")
            if start:
                frequent_starts[start] += 1
            if end:
                frequent_ends[end] += 1
            
            if trip.get("peak_hour"):
                peak_count += 1
        
        starts_sorted = sorted(frequent_starts.items(), key=lambda x: -x[1])
        ends_sorted = sorted(frequent_ends.items(), key=lambda x: -x[1])
        
        return {
            "clusters": cluster_assignments,
            "frequent_starts": [s[0] for s in starts_sorted[:5]],
            "frequent_ends": [e[0] for e in ends_sorted[:5]],
            "peak_ratio": peak_count / len(user_history) if user_history else 0.0,
            "total_trips": len(user_history)
        }

    def get_similar_routes(self, user_history: List[Dict], current_trip: Dict = None, top_n: int = 5) -> List[Recommendation]:
        """
        获取与用户历史相似的路线推荐
        
        Args:
            user_history: 用户历史行程
            current_trip: 当前行程（可选）
            top_n: 返回数量
            
        Returns:
            推荐列表
        """
        if not user_history:
            return []
        
        analysis = self.analyze_user_routes(user_history)
        recommendations = []
        
        for end in analysis["frequent_ends"][:top_n]:
            recommendations.append(Recommendation(
                item_type="destination",
                item_id=end,
                item_data={"address": end},
                score=0.9,
                reason="您常用的目的地"
            ))
        
        for start in analysis["frequent_starts"][:top_n]:
            recommendations.append(Recommendation(
                item_type="starting_point",
                item_id=start,
                item_data={"address": start},
                score=0.85,
                reason="您常用的出发地"
            ))
        
        return recommendations[:top_n]

    def get_destination_prediction(self, partial_input: str, user_history: List[Dict] = None) -> List[Dict]:
        """
        预测目的地（模糊匹配）
        
        Args:
            partial_input: 部分输入
            user_history: 用户历史
            
        Returns:
            预测目的地列表
        """
        suggestions = []
        partial = partial_input.lower().strip()
        
        if user_history:
            destinations = set()
            for trip in user_history:
                end = trip.get("end", "")
                if end and partial in end.lower():
                    destinations.add(end)
            
            for dest in sorted(destinations)[:5]:
                suggestions.append({
                    "address": dest,
                    "source": "history",
                    "score": 0.9
                })
        
        if len(suggestions) < 5:
            common_destinations = [
                ("市中心", 0.7),
                ("火车站", 0.6),
                ("机场", 0.5),
                ("医院", 0.4),
                ("学校", 0.4),
                ("商场", 0.3),
                ("公园", 0.3),
            ]
            for dest, base_score in common_destinations:
                if partial in dest.lower():
                    suggestions.append({
                        "address": dest,
                        "source": "common",
                        "score": base_score
                    })
        
        return sorted(suggestions, key=lambda x: -x["score"])[:5]

    def get_popular_routes(self, all_trips: List[Dict] = None, top_n: int = 5) -> List[Dict]:
        """
        获取热门路线
        
        Args:
            all_trips: 所有行程数据
            top_n: 返回数量
            
        Returns:
            热门路线列表
        """
        route_counts = defaultdict(int)
        
        if all_trips:
            for trip in all_trips:
                start = trip.get("start", "")
                end = trip.get("end", "")
                if start and end:
                    route_key = f"{start}|{end}"
                    route_counts[route_key] += 1
        
        for key in self.popular_routes:
            route_counts[key] += self.popular_routes[key]
        
        sorted_routes = sorted(route_counts.items(), key=lambda x: -x[1])
        
        results = []
        for route_key, count in sorted_routes[:top_n]:
            parts = route_key.split("|")
            if len(parts) >= 2:
                results.append({
                    "start": parts[0],
                    "end": parts[1],
                    "count": count,
                    "score": min(1.0, count / 10)
                })
        
        return results

    def record_route_usage(self, start: str, end: str):
        """记录路线使用（用于热门推荐）"""
        key = f"{start}|{end}"
        self.popular_routes[key] += 1
        if start:
            self.start_frequency[start] += 1
        if end:
            self.destination_frequency[end] += 1

    def get_similar_users(self, user_history: List[Dict], all_user_histories: Dict[str, List[Dict]], top_n: int = 3) -> List[Dict]:
        """
        查找相似用户
        
        Args:
            user_history: 当前用户历史
            all_user_histories: 所有用户历史 {user_id: history}
            top_n: 返回数量
            
        Returns:
            相似用户列表
        """
        if not user_history or not all_user_histories:
            return []
        
        current_features = self._extract_route_features(user_history[0]) if user_history else None
        if not current_features:
            return []
        
        similarities = []
        for other_id, other_history in all_user_histories.items():
            if not other_history or other_id == "current":
                continue
            
            other_features = self._extract_route_features(other_history[0])
            if other_features:
                dist = self._compute_feature_distance(current_features, other_features)
                similarity = 1.0 / (1.0 + dist)
                similarities.append({
                    "user_id": other_id,
                    "similarity": similarity
                })
        
        similarities.sort(key=lambda x: -x["similarity"])
        return similarities[:top_n]


def get_recommendation_engine() -> RecommendationEngine:
    """获取推荐引擎实例（单例）"""
    global _recommendation_engine
    if _recommendation_engine is None:
        _recommendation_engine = RecommendationEngine()
    return _recommendation_engine


_recommendation_engine: Optional[RecommendationEngine] = None
