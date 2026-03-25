"""
空间索引加速查询

使用网格索引或R树实现空间索引，加速附近车辆查询。
"""

import math
from typing import List, Tuple, Dict, Optional, Set
from dataclasses import dataclass


@dataclass
class Point:
    """地理点"""
    lng: float
    lat: float
    id: str = None
    data: dict = None

    def __hash__(self):
        """使Point对象可哈希"""
        return hash((self.lng, self.lat, self.id))

    def __eq__(self, other):
        """比较Point对象是否相等"""
        if not isinstance(other, Point):
            return False
        return (self.lng == other.lng and
                self.lat == other.lat and
                self.id == other.id)


@dataclass
class BoundingBox:
    """边界框"""
    min_lng: float
    min_lat: float
    max_lng: float
    max_lat: float

    def contains(self, point: Point) -> bool:
        """检查点是否在边界框内"""
        return (self.min_lng <= point.lng <= self.max_lng and
                self.min_lat <= point.lat <= self.max_lat)

    def intersects(self, other: 'BoundingBox') -> bool:
        """检查两个边界框是否相交"""
        return not (self.max_lng < other.min_lng or other.max_lng < self.min_lng or
                    self.max_lat < other.min_lat or other.max_lat < self.min_lat)

    def expand(self, radius_km: float) -> 'BoundingBox':
        """扩展边界框"""
        # 1度约等于111公里
        degree_radius = radius_km / 111.0
        return BoundingBox(
            min_lng=self.min_lng - degree_radius,
            min_lat=self.min_lat - degree_radius,
            max_lng=self.max_lng + degree_radius,
            max_lat=self.max_lat + degree_radius
        )


class GridIndex:
    """
    简单网格空间索引

    将空间划分为网格，每个格子存储该区域内的点。
    查询时只检查相关格子。
    """

    def __init__(self, cell_size_km: float = 1.0):
        """
        初始化网格索引

        Args:
            cell_size_km: 网格单元大小（公里）
        """
        self.cell_size_km = cell_size_km
        self.cell_size_deg = cell_size_km / 111.0  # 转换为度
        self.grid: Dict[Tuple[int, int], Set[Point]] = {}
        self.points: Dict[str, Point] = {}  # {id: Point}

    def _get_cell_key(self, lng: float, lat: float) -> Tuple[int, int]:
        """
        获取网格单元键

        Args:
            lng, lat: 坐标

        Returns:
            (grid_x, grid_y)
        """
        grid_x = int(lng / self.cell_size_deg)
        grid_y = int(lat / self.cell_size_deg)
        return (grid_x, grid_y)

    def insert_point(self, point: Point):
        """
        插入点

        Args:
            point: 点对象
        """
        if point.id is None:
            raise ValueError("点必须有ID")

        # 删除旧的位置（如果存在）
        if point.id in self.points:
            self.remove_point(point.id)

        # 添加到网格
        cell_key = self._get_cell_key(point.lng, point.lat)
        if cell_key not in self.grid:
            self.grid[cell_key] = set()

        self.grid[cell_key].add(point)
        self.points[point.id] = point

    def remove_point(self, point_id: str) -> bool:
        """
        移除点

        Args:
            point_id: 点ID

        Returns:
            是否成功移除
        """
        if point_id not in self.points:
            return False

        point = self.points[point_id]
        cell_key = self._get_cell_key(point.lng, point.lat)

        if cell_key in self.grid:
            self.grid[cell_key].discard(point)
            # 如果格子为空，删除格子
            if not self.grid[cell_key]:
                del self.grid[cell_key]

        del self.points[point_id]
        return True

    def update_point(self, point_id: str, new_lng: float, new_lat: float,
                    new_data: dict = None):
        """
        更新点的位置

        Args:
            point_id: 点ID
            new_lng, new_lat: 新坐标
            new_data: 新数据
        """
        if point_id not in self.points:
            return

        point = self.points[point_id]
        point.lng = new_lng
        point.lat = new_lat
        if new_data is not None:
            point.data = new_data

        # 重新插入到正确的格子
        self.insert_point(point)

    def query_nearby(self, lng: float, lat: float,
                    radius_km: float = 5) -> List[Point]:
        """
        查询附近的点

        Args:
            lng, lat: 查询中心坐标
            radius_km: 查询半径（公里）

        Returns:
            附近的点列表（按距离排序）
        """
        # 计算需要检查的格子范围
        radius_deg = radius_km / 111.0
        center_cell = self._get_cell_key(lng, lat)

        # 计算格子范围
        cells_to_check = []
        cell_radius = int(radius_deg / self.cell_size_deg) + 1

        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                cell_key = (center_cell[0] + dx, center_cell[1] + dy)
                cells_to_check.append(cell_key)

        # 收集候选点
        candidates = []
        for cell_key in cells_to_check:
            if cell_key in self.grid:
                candidates.extend(self.grid[cell_key])

        # 计算距离并过滤
        results = []
        for point in candidates:
            dist = self._haversine_distance(lng, lat, point.lng, point.lat)
            if dist <= radius_km:
                results.append((point, dist))

        # 按距离排序
        results.sort(key=lambda x: x[1])
        return [point for point, _ in results]

    def query_in_box(self, bbox: BoundingBox) -> List[Point]:
        """
        查询边界框内的点

        Args:
            bbox: 边界框

        Returns:
            边界框内的点列表
        """
        # 计算格子范围
        min_cell = self._get_cell_key(bbox.min_lng, bbox.min_lat)
        max_cell = self._get_cell_key(bbox.max_lng, bbox.max_lat)

        results = []
        for grid_x in range(min_cell[0], max_cell[0] + 1):
            for grid_y in range(min_cell[1], max_cell[1] + 1):
                cell_key = (grid_x, grid_y)
                if cell_key in self.grid:
                    for point in self.grid[cell_key]:
                        if bbox.contains(point):
                            results.append(point)

        return results

    def get_point(self, point_id: str) -> Optional[Point]:
        """获取指定ID的点"""
        return self.points.get(point_id)

    def get_all_points(self) -> List[Point]:
        """获取所有点"""
        return list(self.points.values())

    def clear(self):
        """清空索引"""
        self.grid.clear()
        self.points.clear()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'total_points': len(self.points),
            'total_cells': len(self.grid),
            'cell_size_km': self.cell_size_km,
            'avg_points_per_cell': len(self.points) / len(self.grid) if self.grid else 0
        }

    def _haversine_distance(self, lng1: float, lat1: float,
                           lng2: float, lat2: float) -> float:
        """
        计算两点间的大圆距离（米）

        使用Haversine公式
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


class RTreeIndex:
    """
    R树空间索引（简化版）

    使用边界框层次结构进行空间查询。
    注意：完整R树实现较为复杂，这里提供一个简化版本。
    """

    def __init__(self, max_children: int = 4):
        """
        初始化R树

        Args:
            max_children: 每个节点的最大子节点数
        """
        self.max_children = max_children
        self.points: Dict[str, Point] = {}
        self.bboxes: Dict[str, BoundingBox] = {}  # {id: bbox}

    def insert_point(self, point: Point):
        """
        插入点（简化版：仅存储，不构建R树）

        Args:
            point: 点对象
        """
        if point.id is None:
            raise ValueError("点必须有ID")

        self.points[point.id] = point
        # 点的边界框就是点本身
        self.bboxes[point.id] = BoundingBox(
            min_lng=point.lng, min_lat=point.lat,
            max_lng=point.lng, max_lat=point.lat
        )

    def remove_point(self, point_id: str) -> bool:
        """移除点"""
        if point_id in self.points:
            del self.points[point_id]
            del self.bboxes[point_id]
            return True
        return False

    def query_nearby(self, lng: float, lat: float,
                    radius_km: float = 5) -> List[Point]:
        """
        查询附近的点（简化版：线性搜索）

        Args:
            lng, lat: 查询中心坐标
            radius_km: 查询半径（公里）

        Returns:
            附近的点列表
        """
        # 计算查询边界框
        radius_deg = radius_km / 111.0
        query_bbox = BoundingBox(
            min_lng=lng - radius_deg,
            min_lat=lat - radius_deg,
            max_lng=lng + radius_deg,
            max_lat=lat + radius_deg
        )

        # 线性搜索（简化实现）
        results = []
        for point in self.points.values():
            dist = self._haversine_distance(lng, lat, point.lng, point.lat)
            if dist <= radius_km:
                results.append((point, dist))

        results.sort(key=lambda x: x[1])
        return [point for point, _ in results]

    def _haversine_distance(self, lng1: float, lat1: float,
                           lng2: float, lat2: float) -> float:
        """计算两点间距离"""
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

    def get_point(self, point_id: str) -> Optional[Point]:
        """获取指定ID的点"""
        return self.points.get(point_id)

    def clear(self):
        """清空索引"""
        self.points.clear()
        self.bboxes.clear()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'total_points': len(self.points),
            'max_children': self.max_children,
            'type': 'simplified_rtree'
        }


# 智能选择索引类型
class SpatialIndex:
    """
    空间索引门面

    根据可用库和配置选择最佳的索引实现。
    """

    def __init__(self, index_type: str = 'auto', cell_size_km: float = 1.0):
        """
        初始化空间索引

        Args:
            index_type: 索引类型 ('grid', 'rtree', 'auto')
            cell_size_km: 网格单元大小（仅网格索引有效）
        """
        self.index_type = index_type

        if index_type == 'auto':
            # 尝试使用rtree库
            try:
                import rtree
                self._use_rtree = True
            except ImportError:
                self._use_rtree = False
        elif index_type == 'rtree':
            self._use_rtree = True
        else:
            self._use_rtree = False

        if self._use_rtree:
            try:
                from rtree import index as rtree_index
                self.rtree = rtree_index.Index()
                self.points: Dict[str, Point] = {}
                print("使用R树空间索引")
            except ImportError:
                print("rtree未安装，回退到网格索引")
                self._use_rtree = False

        if not self._use_rtree:
            self.grid = GridIndex(cell_size_km)
            print(f"使用网格空间索引 (单元大小: {cell_size_km}km)")

    def insert_point(self, point_id: str, lng: float, lat: float, data: dict = None):
        """插入点"""
        point = Point(lng=lng, lat=lat, id=point_id, data=data)

        if self._use_rtree:
            # 使用R树
            left = right = lng
            bottom = top = lat
            self.rtree.insert(point_id, (left, bottom, right, top))
            self.points[point_id] = point
        else:
            # 使用网格
            self.grid.insert_point(point)

    def query_nearby(self, lng: float, lat: float,
                    radius_km: float = 5) -> List[str]:
        """
        查询附近车辆ID

        Args:
            lng, lat: 查询中心坐标
            radius_km: 查询半径（公里）

        Returns:
            附近的ID列表
        """
        if self._use_rtree:
            # R树范围查询
            min_lng = lng - radius_km / 111.0
            max_lng = lng + radius_km / 111.0
            min_lat = lat - radius_km / 111.0
            max_lat = lat + radius_km / 111.0

            results = list(self.rtree.intersection((min_lng, min_lat, max_lng, max_lat)))

            # 精确距离过滤
            filtered = []
            for point_id in results:
                point = self.points.get(point_id)
                if point:
                    dist = self.grid._haversine_distance(lng, lat, point.lng, point.lat)
                    if dist <= radius_km:
                        filtered.append(point_id)

            return filtered
        else:
            # 网格查询
            points = self.grid.query_nearby(lng, lat, radius_km)
            return [p.id for p in points]

    def remove_point(self, point_id: str) -> bool:
        """移除点"""
        if self._use_rtree:
            if point_id in self.points:
                point = self.points[point_id]
                self.rtree.delete(point_id, (point.lng, point.lat, point.lng, point.lat))
                del self.points[point_id]
                return True
            return False
        else:
            return self.grid.remove_point(point_id)

    def update_point(self, point_id: str, lng: float, lat: float, data: dict = None):
        """更新点位置"""
        self.remove_point(point_id)
        self.insert_point(point_id, lng, lat, data)

    def clear(self):
        """清空索引"""
        if self._use_rtree:
            from rtree import index as rtree_index
            self.rtree = rtree_index.Index()
            self.points.clear()
        else:
            self.grid.clear()

    def get_stats(self) -> dict:
        """获取统计信息"""
        if self._use_rtree:
            return {
                'type': 'rtree',
                'total_points': len(self.points)
            }
        else:
            stats = self.grid.get_stats()
            stats['type'] = 'grid'
            return stats


# 全局实例
_spatial_index: Optional[SpatialIndex] = None


def get_spatial_index(index_type: str = 'auto',
                     cell_size_km: float = 1.0) -> SpatialIndex:
    """获取空间索引实例（单例）"""
    global _spatial_index
    if _spatial_index is None:
        _spatial_index = SpatialIndex(index_type, cell_size_km)
    return _spatial_index
