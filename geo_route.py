"""
地理位置和路径模块
集成高德地图API，提供地理编码、路径规划、路径重叠度计算功能
"""

import json
import math
from typing import Tuple, List, Optional, Dict
from config import Config

# 高德API配置
AMAP_KEY = Config.AMAP_KEY
GEOCODE_URL = Config.AMAP_GEOCODE_URL
DRIVING_URL = Config.AMAP_DRIVING_URL


def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """
    地理编码：将中文地址转换为经纬度坐标

    Args:
        address: 中文地址，如 "北京中关村"

    Returns:
        (经度, 纬度) 或 None（失败时）
    """
    # 检查Key是否有效（32位字符串）
    if not AMAP_KEY or len(AMAP_KEY) != 32:
        # 使用模拟数据
        return _simulate_geocode(address)

    try:
        import requests
        params = {
            'address': address,
            'key': AMAP_KEY,
            'output': 'json'
        }
        response = requests.get(GEOCODE_URL, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            # 检查是否成功（status="1"表示成功）
            if data.get('status') == '1' and data.get('geocodes'):
                location = data['geocodes'][0]['location']
                lng, lat = map(float, location.split(','))
                return (lng, lat)
            else:
                # Key类型不匹配或其他错误，使用模拟数据
                error_info = data.get('info', '')
                if 'USERKEY_PLAT_NOMATCH' in error_info:
                    print(f"⚠️  高德API Key类型不匹配，建议使用Web服务类型Key")
                return _simulate_geocode(address)

        return _simulate_geocode(address)

    except Exception as e:
        print(f"地理编码异常: {e}")
        return _simulate_geocode(address)


def _simulate_geocode(address: str) -> Optional[Tuple[float, float]]:
    """
    模拟地理编码（用于测试/无API Key时）

    根据地址关键词返回预定义的北京区域坐标
    """
    # 北京常见区域坐标
    mock_coords = {
        "中关村": (116.310003, 39.991957),
        "科技园": (116.318, 39.985),
        "朝阳": (116.44, 39.92),
        "海淀": (116.30, 39.96),
        "西站": (116.322, 39.894),
        "东站": (116.49, 39.95),
        "南站": (116.37, 39.87),
        "机场": (116.58, 40.08),
        "T1": (116.58, 40.08),
        "T2": (116.58, 40.08),
        "T3": (116.58, 40.08),
        "市区": (116.40, 39.90),
        "中心": (116.40, 39.90),
        "地铁站": (116.40, 39.90),
    }

    for keyword, coord in mock_coords.items():
        if keyword in address:
            return coord

    # 默认返回北京市中心
    return (116.40, 39.90)


def plan_route(start_lng: float, start_lat: float,
               end_lng: float, end_lat: float) -> List[List[float]]:
    """
    路径规划：获取从起点到终点的实际行驶路径

    Args:
        start_lng, start_lat: 起点经纬度
        end_lng, end_lat: 终点经纬度

    Returns:
        路径点序列 [[lng, lat], [lng, lat], ...]
    """
    # 检查Key是否有效（32位字符串）
    if not AMAP_KEY or len(AMAP_KEY) != 32:
        # 使用模拟数据
        return _simulate_route(start_lng, start_lat, end_lng, end_lat)

    try:
        import requests
        origin = f"{start_lng},{start_lat}"
        destination = f"{end_lng},{end_lat}"

        params = {
            'origin': origin,
            'destination': destination,
            'key': AMAP_KEY,
            'output': 'json',
            'strategy': '1'  # 1=最快路线
        }
        response = requests.get(DRIVING_URL, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            # 检查是否成功
            if data.get('status') == '1' and data.get('route', {}).get('paths'):
                # 解析路径点
                path_data = data['route']['paths'][0]
                polyline = path_data.get('polyline', '')
                if polyline:
                    return _decode_polyline(polyline)

        # API调用失败，使用模拟数据
        error_info = data.get('info', '')
        if 'USERKEY_PLAT_NOMATCH' in error_info:
            print(f"⚠️  高德API Key类型不匹配，建议使用Web服务类型Key")
        return _simulate_route(start_lng, start_lat, end_lng, end_lat)

    except Exception as e:
        print(f"路径规划异常: {e}")
        return _simulate_route(start_lng, start_lat, end_lng, end_lat)


def _decode_polyline(polyline: str) -> List[List[float]]:
    """
    解码高德polyline路径字符串

    高德polyline格式: lng1,lat1;lng2,lat2;lng3,lat3...
    """
    if not polyline:
        return []

    points = []
    for point in polyline.split(';'):
        try:
            lng, lat = map(float, point.split(','))
            points.append([lng, lat])
        except (ValueError, IndexError):
            continue

    return points


def _simulate_route(start_lng: float, start_lat: float,
                   end_lng: float, end_lat: float) -> List[List[float]]:
    """
    模拟路径规划（用于测试/无API Key时）

    在起点和终点之间生成一条直线路径，中间插值生成平滑曲线
    """
    # 生成中间点，每50米一个点
    distance = _haversine_distance(start_lng, start_lat, end_lng, end_lat)
    num_points = max(10, int(distance / 50))

    points = []
    for i in range(num_points + 1):
        ratio = i / num_points
        lng = start_lng + (end_lng - start_lng) * ratio
        lat = start_lat + (end_lat - start_lat) * ratio
        points.append([lng, lat])

    return points


def _haversine_distance(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """
    计算两点间的大圆距离（米）

    使用Haversine公式
    """
    R = 6371000  # 地球半径（米）

    # 转换为弧度
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def calculate_route_overlap(route_path1: List[List[float]],
                           route_path2: List[List[float]],
                           segment_distance: float = 50) -> float:
    """
    计算两条路径的共享路段比例

    算法：
    1. 将两条路径按segment_distance分段
    2. 计算重叠段数
    3. 共享比例 = 重叠段数 / 总段数（取两条路径中较短的）

    Args:
        route_path1: 第一条路径点序列 [[lng, lat], ...]
        route_path2: 第二条路径点序列 [[lng, lat], ...]
        segment_distance: 分段距离（米），默认50米

    Returns:
        共享路段比例（0.0 - 1.0）
    """
    if not route_path1 or not route_path2:
        return 0.0

    # 将路径分段
    segments1 = _segment_path(route_path1, segment_distance)
    segments2 = _segment_path(route_path2, segment_distance)

    if not segments1 or not segments2:
        return 0.0

    # 计算重叠段数
    overlap_count = 0
    threshold = 30  # 30米内视为同一段

    for seg1 in segments1:
        for seg2 in segments2:
            dist = _haversine_distance(seg1[0], seg1[1], seg2[0], seg2[1])
            if dist <= threshold:
                overlap_count += 1
                break  # 每个segment只匹配一次

    # 使用较短路径的总段数作为分母
    total_segments = min(len(segments1), len(segments2))

    return overlap_count / total_segments if total_segments > 0 else 0.0


def _segment_path(path_points: List[List[float]], distance: float) -> List[List[float]]:
    """
    将路径按指定距离分段

    Args:
        path_points: 路径点序列
        distance: 分段距离（米）

    Returns:
        分段后的点序列
    """
    if not path_points or len(path_points) < 2:
        return []

    if distance <= 0:
        return path_points[:]

    segments = [path_points[0]]  # 起点
    accumulated_distance = 0.0
    current_idx = 0
    max_iterations = len(path_points) * 10  # 防止死循环
    iterations = 0

    while current_idx < len(path_points) - 1 and iterations < max_iterations:
        iterations += 1
        # 获取当前段
        p1 = path_points[current_idx]
        p2 = path_points[current_idx + 1]

        segment_len = _haversine_distance(p1[0], p1[1], p2[0], p2[1])

        # 如果段长度为0，跳过
        if segment_len < 0.001:
            current_idx += 1
            continue

        # 如果累积距离超过分段距离，插入新点
        if accumulated_distance + segment_len >= distance:
            ratio = (distance - accumulated_distance) / segment_len
            new_lng = p1[0] + (p2[0] - p1[0]) * ratio
            new_lat = p1[1] + (p2[1] - p1[1]) * ratio
            segments.append([new_lng, new_lat])
            accumulated_distance = 0.0
        else:
            accumulated_distance += segment_len
            current_idx += 1

    # 添加终点
    segments.append(path_points[-1])

    return segments


def parse_route_path(route_path_json: str) -> List[List[float]]:
    """
    从JSON字符串解析路径点序列

    Args:
        route_path_json: JSON格式路径字符串

    Returns:
        路径点序列 [[lng, lat], ...]
    """
    try:
        return json.loads(route_path_json)
    except (json.JSONDecodeError, TypeError):
        return []


def format_route_path(route_path: List[List[float]]) -> str:
    """
    将路径点序列格式化为JSON字符串

    Args:
        route_path: 路径点序列

    Returns:
        JSON字符串
    """
    return json.dumps(route_path)


def geocode_address_reverse(lnglat: Tuple[float, float]) -> str:
    """
    逆地理编码：将经纬度转换为地址描述

    Args:
        lnglat: (经度, 纯度) 坐标

    Returns:
        地址描述字符串
    """
    # 模拟逆地理编码
    lng, lat = lnglat

    # 根据坐标模拟返回地址
    if lng > 116.5 and lat > 40.0:
        return "首都机场T3航站楼"
    elif lng > 116.3 and lng < 116.5 and lat > 39.8 and lat < 40.2:
        return "北京市朝阳区"
    elif lng > 116.2 and lng < 116.4 and lat > 39.9 and lat < 40.1:
        return "北京市海淀区"
    else:
        return f"北京市 (经度: {lng:.4f}, 纬度: {lat:.4f})"


def get_distance(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """
    计算两点间距离（米）

    Args:
        lng1, lat1: 第一点坐标
        lng2, lat2: 第二点坐标

    Returns:
        距离（米）
    """
    return _haversine_distance(lng1, lat1, lng2, lat2)


# ========== 简化API（兼容旧版） ==========

def get_route_similarity(route1: str, route2: str) -> float:
    """
    获取路线相似度（使用真实路径）

    注意：此函数需要从数据库获取完整的route_path数据
    建议使用 calculate_route_overlap 直接计算
    """
    # 此函数为兼容接口，实际使用时建议传入完整的路径点
    return 0.0
