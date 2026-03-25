"""
路径计算缓存系统

使用LRU策略和TTL过期机制缓存路径规划结果，减少高德API调用。
"""

import json
import hashlib
import time
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """缓存条目"""
    route_data: List[List[float]]  # 路径点序列
    timestamp: float  # 创建时间
    access_count: int = 0  # 访问次数
    last_access: float = field(default_factory=time.time)  # 最后访问时间


class RouteCache:
    """
    路径计算缓存系统

    功能：
    - LRU（最近最少使用）策略
    - TTL（生存时间）过期机制
    - 缓存命中率统计
    - 支持持久化存储（可选）
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600,
                 enable_stats: bool = True):
        """
        初始化路径缓存

        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存条目生存时间（秒）
            enable_stats: 是否启用统计
        """
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.enable_stats = enable_stats

        # 缓存存储
        self.cache: Dict[str, CacheEntry] = {}

        # 统计信息
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0
        }

    def _get_cache_key(self, start_lng: float, start_lat: float,
                      end_lng: float, end_lat: float,
                      strategy: int = 1) -> str:
        """
        生成缓存键

        Args:
            start_lng, start_lat: 起点坐标
            end_lng, end_lat: 终点坐标
            strategy: 路径策略（1=最快, 2=最短等）

        Returns:
            缓存键字符串
        """
        # 使用坐标和策略生成唯一键
        key_str = f"{start_lng:.6f},{start_lat:.6f}:{end_lng:.6f},{end_lat:.6f}:{strategy}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, start_lng: float, start_lat: float,
           end_lng: float, end_lat: float,
           strategy: int = 1) -> Optional[List[List[float]]]:
        """
        获取缓存的路径

        Args:
            start_lng, start_lat: 起点坐标
            end_lng, end_lat: 终点坐标
            strategy: 路径策略

        Returns:
            缓存的路径点序列，如果不存在或已过期则返回None
        """
        key = self._get_cache_key(start_lng, start_lat, end_lng, end_lat, strategy)

        if key in self.cache:
            entry = self.cache[key]

            # 检查是否过期
            if time.time() - entry.timestamp < self.ttl:
                # 更新访问信息
                entry.access_count += 1
                entry.last_access = time.time()

                if self.enable_stats:
                    self.stats['hits'] += 1

                return entry.route_data
            else:
                # 过期，删除
                del self.cache[key]
                if self.enable_stats:
                    self.stats['expirations'] += 1

        if self.enable_stats:
            self.stats['misses'] += 1

        return None

    def set(self, start_lng: float, start_lat: float,
           end_lng: float, end_lat: float,
           route_data: List[List[float]], strategy: int = 1):
        """
        缓存路径数据

        Args:
            start_lng, start_lat: 起点坐标
            end_lng, end_lat: 终点坐标
            route_data: 路径点序列
            strategy: 路径策略
        """
        key = self._get_cache_key(start_lng, start_lat, end_lng, end_lat, strategy)

        # 如果缓存已满，使用LRU策略删除最久未访问的条目
        if len(self.cache) >= self.max_size and key not in self.cache:
            self._evict_lru()

        self.cache[key] = CacheEntry(
            route_data=route_data,
            timestamp=time.time()
        )

    def _evict_lru(self):
        """删除最久未访问的缓存条目"""
        if not self.cache:
            return

        # 找到最久未访问的条目
        oldest_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k].last_access
        )

        del self.cache[oldest_key]

        if self.enable_stats:
            self.stats['evictions'] += 1

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def cleanup_expired(self):
        """清理所有过期的缓存条目"""
        now = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now - entry.timestamp >= self.ttl
        ]

        for key in expired_keys:
            del self.cache[key]
            if self.enable_stats:
                self.stats['expirations'] += 1

        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        if not self.enable_stats:
            return {'stats_enabled': False}

        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0

        return {
            'stats_enabled': True,
            'cache_size': len(self.cache),
            'max_size': self.max_size,
            'ttl_seconds': self.ttl,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'evictions': self.stats['evictions'],
            'expirations': self.stats['expirations'],
            'hit_rate': round(hit_rate, 3),
            'total_requests': total_requests
        }

    def get_info(self) -> Dict[str, Any]:
        """
        获取缓存详细信息

        Returns:
            详细信息字典
        """
        now = time.time()

        # 按访问次数排序的条目
        sorted_entries = sorted(
            self.cache.values(),
            key=lambda e: e.access_count,
            reverse=True
        )

        # 统计路径长度
        route_lengths = [len(e.route_data) for e in self.cache.values()]
        avg_route_length = sum(route_lengths) / len(route_lengths) if route_lengths else 0

        return {
            'cache_size': len(self.cache),
            'max_size': self.max_size,
            'ttl_seconds': self.ttl,
            'total_accesses': sum(e.access_count for e in self.cache.values()),
            'most_accessed_count': sorted_entries[0].access_count if sorted_entries else 0,
            'avg_route_points': round(avg_route_length, 1),
            'stats': self.get_stats()
        }

    def save_to_file(self, filename: str):
        """
        将缓存保存到文件

        Args:
            filename: 文件名
        """
        data = {
            'version': 1,
            'timestamp': time.time(),
            'max_size': self.max_size,
            'ttl': self.ttl,
            'stats': self.stats,
            'cache': {
                key: {
                    'route_data': entry.route_data,
                    'timestamp': entry.timestamp,
                    'access_count': entry.access_count,
                    'last_access': entry.last_access
                }
                for key, entry in self.cache.items()
            }
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def load_from_file(self, filename: str, skip_expired: bool = True):
        """
        从文件加载缓存

        Args:
            filename: 文件名
            skip_expired: 是否跳过已过期的条目
        """
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 验证版本
            if data.get('version') != 1:
                print(f"警告: 不支持的缓存版本 {data.get('version')}")

            # 加载缓存
            loaded_count = 0
            skipped_count = 0

            for key, entry_data in data.get('cache', {}).items():
                # 检查是否过期
                if skip_expired and time.time() - entry_data['timestamp'] >= self.ttl:
                    skipped_count += 1
                    continue

                self.cache[key] = CacheEntry(
                    route_data=entry_data['route_data'],
                    timestamp=entry_data['timestamp'],
                    access_count=entry_data.get('access_count', 0),
                    last_access=entry_data.get('last_access', entry_data['timestamp'])
                )
                loaded_count += 1

            # 加载统计
            self.stats.update(data.get('stats', {}))

            print(f"缓存加载完成: {loaded_count}个条目, 跳过{skipped_count}个过期条目")

        except FileNotFoundError:
            print(f"缓存文件不存在: {filename}")
        except json.JSONDecodeError as e:
            print(f"缓存文件解析失败: {e}")
        except Exception as e:
            print(f"缓存加载失败: {e}")

    def __len__(self):
        """返回缓存条目数"""
        return len(self.cache)

    def add_match(self, passenger_id: str, match_data: Dict[str, Any]):
        """
        添加匹配结果到缓存（用于乘客-车辆匹配缓存）

        Args:
            passenger_id: 乘客ID
            match_data: 匹配数据
        """
        key = f"match_{passenger_id}"
        self.cache[key] = CacheEntry(
            route_data=[],  # 匹配结果不是路径数据
            timestamp=time.time()
        )
        if self.enable_stats:
            self.stats['hits'] += 1

    def remove_match(self, passenger_id: str):
        """
        从缓存移除匹配结果

        Args:
            passenger_id: 乘客ID
        """
        key = f"match_{passenger_id}"
        if key in self.cache:
            del self.cache[key]

    @property
    def hits(self):
        """命中次数"""
        return self.stats.get('hits', 0)

    @property
    def misses(self):
        """未命中次数"""
        return self.stats.get('misses', 0)


# 全局实例
_route_cache: Optional[RouteCache] = None


def get_route_cache(max_size: int = 1000, ttl_seconds: int = 3600) -> RouteCache:
    """获取路径缓存实例（单例）"""
    global _route_cache
    if _route_cache is None:
        _route_cache = RouteCache(max_size, ttl_seconds)
    return _route_cache


# 集成到geo_route的装饰器
def cached_route_planner(plan_route_func):
    """
    路径规划缓存装饰器

    Args:
        plan_route_func: 原始路径规划函数

    Returns:
        带有缓存的路径规划函数
    """
    cache = get_route_cache()

    def wrapper(start_lng: float, start_lat: float,
               end_lng: float, end_lat: float,
               strategy: int = 1) -> List[List[float]]:
        # 尝试从缓存获取
        cached = cache.get(start_lng, start_lat, end_lng, end_lat, strategy)
        if cached is not None:
            return cached

        # 缓存未命中，调用原始函数
        route = plan_route_func(start_lng, start_lat, end_lng, end_lat)

        # 存入缓存
        if route:
            cache.set(start_lng, start_lat, end_lng, end_lat, route, strategy)

        return route

    wrapper.cache = cache  # 暴露缓存对象
    return wrapper
