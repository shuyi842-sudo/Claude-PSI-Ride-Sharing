"""
布隆过滤器快速筛选

使用布隆过滤器快速判断路线是否可能匹配，减少不必要的计算。
布隆过滤器可能产生假阳性，但不会有假阴性。
"""

import hashlib
import secrets
from typing import List, Set, Optional
from bitarray import bitarray


class BloomFilter:
    """
    布隆过滤器

    特点：
    - 空间效率高
    - 查询速度快 O(k)，k为哈希函数数量
    - 无假阴性，可能有假阳性
    - 不支持删除操作（标准版本）
    """

    def __init__(self, size: int = 100000, hash_count: int = 5,
                 use_bitarray: bool = True):
        """
        初始化布隆过滤器

        Args:
            size: 布隆过滤器大小（位数）
            hash_count: 哈希函数数量
            use_bitarray: 是否使用bitarray库（需要安装 bitarray）
        """
        self.size = size
        self.hash_count = hash_count
        self.use_bitarray = use_bitarray

        # 使用bitarray或bytearray存储位图
        if use_bitarray:
            try:
                from bitarray import bitarray
                self.bit_array = bitarray(size)
                self.bit_array.setall(0)
            except ImportError:
                print("警告: bitarray未安装，回退到bytearray")
                self.use_bitarray = False
                self.bit_array = bytearray(size // 8 + 1)
        else:
            self.bit_array = bytearray(size // 8 + 1)

        # 使用不同的哈希函数种子
        self.hash_seeds = [secrets.randbelow(2**32) for _ in range(hash_count)]

        # 统计信息
        self.added_count = 0

    def _hash(self, value: str, seed: int) -> int:
        """
        计算哈希值

        Args:
            value: 要哈希的值
            seed: 哈希种子

        Returns:
            哈希值
        """
        # 使用MD5哈希 + 种子
        hash_input = f"{value}:{seed}"
        hash_result = hashlib.md5(hash_input.encode()).hexdigest()

        # 转换为整数
        hash_int = int(hash_result, 16)

        return hash_int % self.size

    def add(self, route_key: str):
        """
        添加路线到过滤器

        Args:
            route_key: 路线键（通常是起终点组合）
        """
        for seed in self.hash_seeds:
            position = self._hash(route_key, seed)
            self._set_bit(position)

        self.added_count += 1

    def _set_bit(self, position: int):
        """设置指定位"""
        if self.use_bitarray:
            self.bit_array[position] = 1
        else:
            byte_index = position // 8
            bit_offset = position % 8
            self.bit_array[byte_index] |= (1 << bit_offset)

    def _get_bit(self, position: int) -> bool:
        """获取指定位的值"""
        if self.use_bitarray:
            return self.bit_array[position]
        else:
            byte_index = position // 8
            bit_offset = position % 8
            return (self.bit_array[byte_index] & (1 << bit_offset)) != 0

    def possibly_contains(self, route_key: str) -> bool:
        """
        判断路线是否可能存在（可能有假阳性）

        Args:
            route_key: 路线键

        Returns:
            True=可能存在, False=肯定不存在
        """
        for seed in self.hash_seeds:
            position = self._hash(route_key, seed)
            if not self._get_bit(position):
                return False
        return True

    def definitely_not_contains(self, route_key: str) -> bool:
        """
        判断路线肯定不存在（无假阴性）

        Args:
            route_key: 路线键

        Returns:
            True=肯定不存在, False=可能存在
        """
        return not self.possibly_contains(route_key)

    def add_multiple(self, route_keys: List[str]):
        """
        批量添加路线

        Args:
            route_keys: 路线键列表
        """
        for key in route_keys:
            self.add(key)

    def estimate_size(self) -> int:
        """
        估计布隆过滤器中的元素数量

        使用公式: n = -m/k * ln(1 - x/m)
        其中 m=size, k=hash_count, x=设置的位数

        Returns:
            估计的元素数量
        """
        # 计算设置的位数
        set_bits = 0
        if self.use_bitarray:
            set_bits = self.bit_array.count(1)
        else:
            for byte in self.bit_array:
                set_bits += bin(byte).count('1')

        # 估计元素数量
        if set_bits == 0:
            return 0

        n = -self.size / self.hash_count * math.log(1 - set_bits / self.size)
        return int(n)

    def get_false_positive_rate(self) -> float:
        """
        计算假阳性率

        使用公式: (1 - e^(-kn/m))^k
        其中 n=元素数量, k=hash_count, m=size

        Returns:
            假阳性率
        """
        n = self.estimate_size()
        if n == 0:
            return 0.0

        exponent = -self.hash_count * n / self.size
        base = 1 - math.exp(exponent)
        return base ** self.hash_count

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'size': self.size,
            'hash_count': self.hash_count,
            'added_count': self.added_count,
            'estimated_elements': self.estimate_size(),
            'false_positive_rate': round(self.get_false_positive_rate(), 4),
            'memory_usage_bytes': len(self.bit_array),
            'usage_bitarray': self.use_bitarray
        }

    def clear(self):
        """清空布隆过滤器"""
        if self.use_bitarray:
            self.bit_array.setall(0)
        else:
            self.bit_array = bytearray(self.size // 8 + 1)
        self.added_count = 0

    def __contains__(self, item: str) -> bool:
        """支持 'in' 操作符"""
        return self.possibly_contains(item)

    def __len__(self) -> int:
        """返回添加的元素数量（精确值）"""
        return self.added_count


class RouteBloomFilter:
    """
    专用于路线匹配的布隆过滤器

    基于起终点生成路线键，用于快速筛选可能匹配的路线。
    """

    def __init__(self, size: int = 100000, hash_count: int = 5):
        """
        初始化路线布隆过滤器

        Args:
            size: 布隆过滤器大小
            hash_count: 哈希函数数量
        """
        self.bloom = BloomFilter(size, hash_count)
        self.route_to_ids = {}  # {route_key: [id1, id2, ...]}

    def _generate_route_key(self, start: str, end: str) -> str:
        """
        生成路线键

        Args:
            start: 起点
            end: 终点

        Returns:
            路线键
        """
        return f"{start}>>{end}"

    def add_route(self, id: str, start: str, end: str):
        """
        添加路线

        Args:
            id: 路线ID（乘客ID或车辆ID）
            start: 起点
            end: 终点
        """
        route_key = self._generate_route_key(start, end)
        self.bloom.add(route_key)

        if route_key not in self.route_to_ids:
            self.route_to_ids[route_key] = []
        self.route_to_ids[route_key].append(id)

    def check_route_exists(self, start: str, end: str) -> bool:
        """
        检查路线是否存在

        Args:
            start: 起点
            end: 终点

        Returns:
            True=可能存在, False=肯定不存在
        """
        route_key = self._generate_route_key(start, end)
        return self.bloom.possibly_contains(route_key)

    def get_potential_matches(self, start: str, end: str) -> List[str]:
        """
        获取可能匹配的ID列表

        注意：由于布隆过滤器可能有假阳性，
        需要进一步验证这些ID是否真实匹配。

        Args:
            start: 起点
            end: 终点

        Returns:
            可能匹配的ID列表
        """
        if not self.check_route_exists(start, end):
            return []

        route_key = self._generate_route_key(start, end)
        return self.route_to_ids.get(route_key, [])

    def clear(self):
        """清空过滤器和映射"""
        self.bloom.clear()
        self.route_to_ids.clear()

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = self.bloom.get_stats()
        stats['unique_routes'] = len(self.route_to_ids)
        stats['total_mappings'] = sum(len(ids) for ids in self.route_to_ids.values())
        return stats


import math


# 全局实例
_bloom_filter: Optional[RouteBloomFilter] = None


def get_bloom_filter(size: int = 100000, hash_count: int = 5) -> RouteBloomFilter:
    """获取路线布隆过滤器实例（单例）"""
    global _bloom_filter
    if _bloom_filter is None:
        _bloom_filter = RouteBloomFilter(size, hash_count)
    return _bloom_filter
