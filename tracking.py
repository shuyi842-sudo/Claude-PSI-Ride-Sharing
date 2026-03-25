"""
实时行程追踪系统

支持实时位置更新、行程状态追踪和WebSocket事件推送。
"""

import time
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class TripStatus(Enum):
    """行程状态枚举"""
    PENDING = "pending"          # 等待中
    MATCHED = "matched"          # 已匹配
    ARRIVED_PICKUP = "arrived_pickup"  # 到达上车点
    BOARDING = "boarding"        # 上车中
    IN_TRANSIT = "in_transit"    # 行驶中
    ARRIVED_DESTINATION = "arrived_destination"  # 到达目的地
    COMPLETED = "completed"       # 已完成
    CANCELLED = "cancelled"      # 已取消


@dataclass
class LocationUpdate:
    """位置更新"""
    passenger_id: str
    lng: float
    lat: float
    timestamp: float
    accuracy: float = 10.0  # 精度（米）


@dataclass
class TripEvent:
    """行程事件"""
    trip_id: str
    event_type: str
    status: str
    message: str
    timestamp: float
    data: dict = None


@dataclass
class ActiveTrip:
    """活跃行程"""
    trip_id: str
    passenger_id: str
    vehicle_id: str
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    status: str
    created_at: float
    updated_at: float
    events: List[TripEvent]
    passenger_location: Optional[LocationUpdate] = None
    vehicle_location: Optional[LocationUpdate] = None


class TripTracker:
    """
    实时行程追踪系统

    功能：
    - 实时位置更新和广播
    - 行程状态追踪
    - 历史轨迹记录
    - ETA估算
    """

    def __init__(self, socketio=None):
        """
        初始化行程追踪系统

        Args:
            socketio: Flask-SocketIO实例，用于推送实时事件
        """
        self.socketio = socketio
        self.active_trips: Dict[str, ActiveTrip] = {}
        self.passenger_locations: Dict[str, LocationUpdate] = {}
        self.vehicle_locations: Dict[str, LocationUpdate] = {}

    def set_socketio(self, socketio):
        """
        设置SocketIO实例

        Args:
            socketio: Flask-SocketIO实例
        """
        self.socketio = socketio

    def create_trip(self, trip_id: str, passenger_id: str, vehicle_id: str,
                   start_lat: float, start_lng: float,
                   end_lat: float, end_lng: float) -> ActiveTrip:
        """
        创建新行程

        Args:
            trip_id: 行程ID
            passenger_id: 乘客ID
            vehicle_id: 车辆ID
            start_lat, start_lng: 起点坐标
            end_lat, end_lng: 终点坐标

        Returns:
            创建的行程对象
        """
        now = time.time()

        trip = ActiveTrip(
            trip_id=trip_id,
            passenger_id=passenger_id,
            vehicle_id=vehicle_id,
            start_lat=start_lat,
            start_lng=start_lng,
            end_lat=end_lat,
            end_lng=end_lng,
            status=TripStatus.MATCHED.value,
            created_at=now,
            updated_at=now,
            events=[]
        )

        # 添加创建事件
        self._add_trip_event(trip, "trip_created", "行程已创建")

        self.active_trips[trip_id] = trip

        # 推送事件
        self._emit_trip_event(trip)

        return trip

    def update_trip_status(self, trip_id: str, status: TripStatus,
                          message: str = None, data: dict = None):
        """
        更新行程状态

        Args:
            trip_id: 行程ID
            status: 新状态
            message: 状态描述
            data: 附加数据
        """
        if trip_id not in self.active_trips:
            return

        trip = self.active_trips[trip_id]
        old_status = trip.status
        trip.status = status.value
        trip.updated_at = time.time()

        # 生成默认消息
        status_messages = {
            TripStatus.PENDING: "等待中",
            TripStatus.MATCHED: "已匹配车辆",
            TripStatus.ARRIVED_PICKUP: "车辆已到达上车点",
            TripStatus.BOARDING: "乘客上车中",
            TripStatus.IN_TRANSIT: "行驶中",
            TripStatus.ARRIVED_DESTINATION: "已到达目的地",
            TripStatus.COMPLETED: "行程完成",
            TripStatus.CANCELLED: "行程已取消"
        }

        msg = message or status_messages.get(status, "状态更新")

        # 添加事件
        self._add_trip_event(trip, f"status_change:{status.value}", msg, data)

        # 推送事件
        self._emit_trip_event(trip, additional_data={
            'old_status': old_status,
            'new_status': status.value
        })

    def _add_trip_event(self, trip: ActiveTrip, event_type: str,
                       message: str, data: dict = None):
        """
        添加行程事件

        Args:
            trip: 行程对象
            event_type: 事件类型
            message: 事件消息
            data: 附加数据
        """
        event = TripEvent(
            trip_id=trip.trip_id,
            event_type=event_type,
            status=trip.status,
            message=message,
            timestamp=time.time(),
            data=data
        )
        trip.events.append(event)

    def _emit_trip_event(self, trip: ActiveTrip, additional_data: dict = None):
        """推送行程事件到客户端"""
        if not self.socketio:
            return

        event_data = {
            'trip_id': trip.trip_id,
            'passenger_id': trip.passenger_id,
            'vehicle_id': trip.vehicle_id,
            'status': trip.status,
            'message': trip.events[-1].message if trip.events else '',
            'timestamp': trip.updated_at
        }

        if additional_data:
            event_data.update(additional_data)

        # 发送给乘客
        self.socketio.emit('trip_status', event_data, room=f"passenger_{trip.passenger_id}")

        # 发送给车辆
        self.socketio.emit('trip_status', event_data, room=f"vehicle_{trip.vehicle_id}")

    def update_passenger_location(self, passenger_id: str, lng: float, lat: float,
                               accuracy: float = 10.0):
        """
        更新乘客实时位置

        Args:
            passenger_id: 乘客ID
            lng, lat: 位置坐标
            accuracy: 位置精度（米）
        """
        now = time.time()
        location = LocationUpdate(
            passenger_id=passenger_id,
            lng=lng,
            lat=lat,
            timestamp=now,
            accuracy=accuracy
        )

        self.passenger_locations[passenger_id] = location

        # 更新相关行程
        for trip in self.active_trips.values():
            if trip.passenger_id == passenger_id:
                trip.passenger_location = location
                trip.updated_at = now

        # 推送给车辆
        self._emit_location_update('passenger_location', location)

    def update_vehicle_location(self, vehicle_id: str, lng: float, lat: float,
                              accuracy: float = 10.0):
        """
        更新车辆实时位置

        Args:
            vehicle_id: 车辆ID
            lng, lat: 位置坐标
            accuracy: 位置精度（米）
        """
        now = time.time()
        location = LocationUpdate(
            passenger_id=vehicle_id,  # 复用字段存储vehicle_id
            lng=lng,
            lat=lat,
            timestamp=now,
            accuracy=accuracy
        )

        self.vehicle_locations[vehicle_id] = location

        # 更新相关行程
        for trip in self.active_trips.values():
            if trip.vehicle_id == vehicle_id:
                trip.vehicle_location = location
                trip.updated_at = now

        # 推送给乘客
        self._emit_location_update('vehicle_location', location)

    def _emit_location_update(self, event_type: str, location: LocationUpdate):
        """推送位置更新"""
        if not self.socketio:
            return

        data = {
            'entity_id': location.passenger_id,
            'lng': location.lng,
            'lat': location.lat,
            'timestamp': location.timestamp,
            'accuracy': location.accuracy
        }

        # 判断是乘客还是车辆
        if 'passenger' in event_type:
            # 发送给该乘客匹配的车辆
            for trip in self.active_trips.values():
                if trip.passenger_id == location.passenger_id:
                    self.socketio.emit(event_type, data, room=f"vehicle_{trip.vehicle_id}")
        else:
            # 发送给该车辆服务的乘客
            for trip in self.active_trips.values():
                if trip.vehicle_id == location.passenger_id:  # 此时passenger_id存的是vehicle_id
                    self.socketio.emit(event_type, data, room=f"passenger_{trip.passenger_id}")

    def calculate_eta(self, trip_id: str) -> Optional[float]:
        """
        计算预计到达时间（ETA）

        Args:
            trip_id: 行程ID

        Returns:
            预计到达时间戳，如果无法计算则返回None
        """
        trip = self.active_trips.get(trip_id)
        if not trip:
            return None

        # 简化估算：基于距离和平均速度
        if trip.status == TripStatus.IN_TRANSIT.value and trip.vehicle_location:
            # 计算到终点的距离
            remaining_distance = self._haversine_distance(
                trip.vehicle_location.lng, trip.vehicle_location.lat,
                trip.end_lng, trip.end_lat
            )

            # 假设平均速度30km/h = 8.33m/s
            avg_speed = 8.33  # 米/秒
            eta_seconds = remaining_distance / avg_speed

            return time.time() + eta_seconds

        # 没有位置信息，无法计算
        return None

    def _haversine_distance(self, lng1: float, lat1: float,
                           lng2: float, lat2: float) -> float:
        """计算两点间距离（米）"""
        import math
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

    def get_trip(self, trip_id: str) -> Optional[ActiveTrip]:
        """获取行程"""
        return self.active_trips.get(trip_id)

    def get_passenger_trips(self, passenger_id: str) -> List[ActiveTrip]:
        """获取乘客的所有行程"""
        return [trip for trip in self.active_trips.values()
                if trip.passenger_id == passenger_id]

    def get_vehicle_trips(self, vehicle_id: str) -> List[ActiveTrip]:
        """获取车辆的所有行程"""
        return [trip for trip in self.active_trips.values()
                if trip.vehicle_id == vehicle_id]

    def complete_trip(self, trip_id: str):
        """完成行程"""
        self.update_trip_status(trip_id, TripStatus.COMPLETED, "行程完成")

    def cancel_trip(self, trip_id: str, reason: str = ""):
        """取消行程"""
        self.update_trip_status(
            trip_id,
            TripStatus.CANCELLED,
            f"行程已取消: {reason}" if reason else "行程已取消"
        )

    def cleanup_old_trips(self, max_age_hours: int = 24):
        """
        清理旧行程

        Args:
            max_age_hours: 最大保留时间（小时）
        """
        now = time.time()
        max_age_seconds = max_age_hours * 3600

        old_trips = [
            trip_id for trip_id, trip in self.active_trips.items()
            if now - trip.updated_at > max_age_seconds
        ]

        for trip_id in old_trips:
            trip = self.active_trips[trip_id]
            # 只清理已完成的行程
            if trip.status in [TripStatus.COMPLETED.value, TripStatus.CANCELLED.value]:
                del self.active_trips[trip_id]

        return len(old_trips)

    def get_stats(self) -> dict:
        """获取统计信息"""
        now = time.time()
        active_count = len([
            trip for trip in self.active_trips.values()
            if trip.status in [TripStatus.MATCHED.value, TripStatus.IN_TRANSIT.value]
        ])

        return {
            'total_trips': len(self.active_trips),
            'active_trips': active_count,
            'passenger_locations': len(self.passenger_locations),
            'vehicle_locations': len(self.vehicle_locations)
        }

    def get_trip_summary(self, trip_id: str) -> Optional[dict]:
        """
        获取行程摘要

        Args:
            trip_id: 行程ID

        Returns:
            行程摘要字典
        """
        trip = self.active_trips.get(trip_id)
        if not trip:
            return None

        return {
            'trip_id': trip.trip_id,
            'passenger_id': trip.passenger_id,
            'vehicle_id': trip.vehicle_id,
            'status': trip.status,
            'created_at': trip.created_at,
            'updated_at': trip.updated_at,
            'eta': self.calculate_eta(trip_id),
            'event_count': len(trip.events),
            'start': {'lat': trip.start_lat, 'lng': trip.start_lng},
            'end': {'lat': trip.end_lat, 'lng': trip.end_lng}
        }


# 全局实例
_trip_tracker: Optional[TripTracker] = None


def get_trip_tracker(socketio=None) -> TripTracker:
    """获取行程追踪器实例（单例）"""
    global _trip_tracker
    if _trip_tracker is None:
        _trip_tracker = TripTracker(socketio)
    elif socketio is not None and _trip_tracker.socketio is None:
        _trip_tracker.set_socketio(socketio)
    return _trip_tracker
