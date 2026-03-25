"""
无人驾驶拼车系统 - 完整集成版
基于 MP-TPSI 协议的共享出行系统
集成多模态输入、空间索引、布隆过滤器等高级功能
"""

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import hashlib
import time
import json
import math
import random
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

# 导入所有模块
from database import (
    init_db, reset_db, create_passenger, get_passenger, update_passenger_status,
    create_vehicle, get_vehicle, update_vehicle_status, update_vehicle_seats,
    get_available_vehicles, create_match, get_match_by_passenger,
    get_match_by_vehicle, delete_match_by_passenger, reset_matches,
    get_all_passengers, get_all_vehicles, get_all_matches
)
from psi import generate_match_code, route_similarity
from geo_route import (
    geocode_address, plan_route, calculate_route_overlap,
    geocode_address_reverse, get_distance, _haversine_distance
)
from bloom_filter import get_bloom_filter
from input_handler import (
    get_input_handler, VoiceInput, DestinationPrediction,
    AddressSuggestion
)
from tracking import (
    get_trip_tracker, TripStatus, LocationUpdate,
    ActiveTrip
)
from spatial_index import SpatialIndex
from bloom_filter import BloomFilter
from route_cache import RouteCache
from privacy import DifferentialPrivacy
from recommendation import RecommendationEngine, get_recommendation_engine

app = Flask(__name__)
app.config['SECRET_KEY'] = 'psi-ride-sharing-secret-2024-integrated'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化各个组件
init_db()

# ========== 统一响应函数 ==========

def success_response(message: str, **data) -> dict:
    """统一成功响应格式"""
    return jsonify({
        "success": True,
        "message": message,
        **data
    })

def error_response(message: str, status: int = 400, **data) -> tuple:
    """统一错误响应格式"""
    return jsonify({
        "success": False,
        "error": message,
        **data
    }), status

# 初始化高级组件
input_handler = get_input_handler()
trip_tracker = get_trip_tracker(socketio)
spatial_index = SpatialIndex()
bloom_filter = get_bloom_filter(1000)  # 初始容量1000
route_cache = RouteCache()
recommendation_engine = get_recommendation_engine()

# 当前PSI模式
current_psi_mode = "hash"

# 距离阈值（米）
MAX_DISTANCE_THRESHOLD = 5000
ROUTE_SIMILARITY_THRESHOLD = 0.7


def emit_to_vehicle(v_id, event, data):
    """向特定车辆发送实时消息"""
    socketio.emit(event, data, room=f"vehicle_{v_id}")


def emit_to_passenger(p_id, event, data):
    """向特定乘客发送实时消息"""
    socketio.emit(event, data, room=f"passenger_{p_id}")


# ========== 页面路由 ==========

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/passenger")
def passenger_page():
    return render_template("passenger.html")


@app.route("/vehicle")
def vehicle_page():
    return render_template("vehicle.html")


@app.route("/admin")
def admin_page():
    """管理后台页面"""
    return render_template("admin.html")


# ========== 管理后台API ==========

@app.route("/admin/passengers", methods=["GET"])
def admin_get_passengers():
    """获取所有乘客列表"""
    passengers = get_all_passengers()
    return jsonify(passengers)


@app.route("/admin/vehicles", methods=["GET"])
def admin_get_vehicles():
    """获取所有车辆列表"""
    vehicles = get_all_vehicles()
    return jsonify(vehicles)


@app.route("/admin/matches", methods=["GET"])
def admin_get_matches():
    """获取所有匹配记录"""
    matches = get_all_matches()
    return jsonify(matches)


@app.route("/verify")
def verify_page():
    """上车验证页面"""
    return render_template("verify.html")


# ========== 核心API ==========

@app.route("/passenger/register", methods=["POST"])
def passenger_register():
    """乘客注册（增强版）"""
    data = request.json
    p_id = data.get("passenger_id")
    if not p_id:
        return error_response("缺少passenger_id")

    start = data.get("start")
    end = data.get("end")
    current_lng = data.get("current_lng")
    current_lat = data.get("current_lat")

    # 地理编码
    start_coords = geocode_address(start) if start else None
    end_coords = geocode_address(end) if end else None

    # 路径规划
    route_path = []
    if start_coords and end_coords:
        route_path = plan_route(
            start_coords[0], start_coords[1],
            end_coords[0], end_coords[1]
        )

    # 创建乘客记录
    passenger = create_passenger(p_id, start, end)
    if passenger:
        passenger["route_path"] = route_path
        passenger["start_coords"] = start_coords
        passenger["end_coords"] = end_coords

    # 添加到空间索引
    if start_coords:
        spatial_index.insert_point(p_id, start_coords[0], start_coords[1])

    # 添加到布隆过滤器
    bloom_filter.add_route(p_id, start, end)

    # 获取地址建议
    suggestions = []
    if current_lng and current_lat:
        suggestions = input_handler.get_suggestions(
            end or "", p_id, current_lng, current_lat
        )

    return jsonify({
        "message": "乘客注册成功",
        "passenger": passenger,
        "suggestions": suggestions[:5],  # 返回前5个建议
        "psi_mode": current_psi_mode
    })


@app.route("/vehicle/register", methods=["POST"])
def vehicle_register():
    """车辆注册（增强版）"""
    data = request.json
    v_id = data.get("vehicle_id")
    if not v_id:
        return error_response("缺少vehicle_id")

    start = data.get("start")
    end = data.get("end")
    seats = data.get("seats", 4)
    current_lng = data.get("current_lng")
    current_lat = data.get("current_lat")

    # 地理编码
    start_coords = geocode_address(start) if start else None
    end_coords = geocode_address(end) if end else None

    # 路径规划
    route_path = []
    if start_coords and end_coords:
        route_path = plan_route(
            start_coords[0], start_coords[1],
            end_coords[0], end_coords[1]
        )

    # 创建车辆记录
    vehicle = create_vehicle(v_id, start, end, seats)
    if vehicle:
        vehicle["route_path"] = route_path
        vehicle["start_coords"] = start_coords
        vehicle["end_coords"] = end_coords

    # 添加到空间索引
    if start_coords:
        spatial_index.insert_point(v_id, start_coords[0], start_coords[1])

    # 添加到布隆过滤器
    bloom_filter.add_route(v_id, start, end)

    return jsonify({
        "message": "车辆注册成功",
        "vehicle": vehicle,
        "psi_mode": current_psi_mode
    })


@app.route("/match", methods=["POST"])
def match():
    """智能匹配（使用多种算法）"""
    data = request.json
    p_id = data.get("passenger_id")

    passenger = get_passenger(p_id)
    if not passenger:
        return error_response("乘客未注册", 404)

    # 检查布隆过滤器
    passenger_route_key = f"{passenger.get('start', '')}>>{passenger.get('end', '')}"
    if not bloom_filter.check_route_exists(passenger.get('start', ''), passenger.get('end', '')):
        return jsonify({"error": "该路线暂无可用车辆"}), 404

    # 获取可用车辆
    available_vehicles = get_available_vehicles()

    # 1. 空间索引快速筛选
    passenger_coords = passenger.get("start_coords")
    nearby_vehicles = []
    if passenger_coords:
        nearby_vehicle_ids = spatial_index.query_nearby(
            passenger_coords[0], passenger_coords[1], MAX_DISTANCE_THRESHOLD / 1000
        )
        # 获取车辆对象
        nearby_vehicles = [get_vehicle(v_id) for v_id in nearby_vehicle_ids if get_vehicle(v_id)]

    # 2. 路径相似度匹配
    best_match = None
    best_score = 0

    # 优先检查附近的车辆
    vehicles_to_check = available_vehicles
    if nearby_vehicles:
        # 创建ID到车辆的映射
        vehicle_map = {v["id"]: v for v in available_vehicles}
        vehicles_to_check = [vehicle_map[v_id] for v_id in nearby_vehicles
                           if v_id in vehicle_map]

    for vehicle in vehicles_to_check:
        if vehicle["seats"] > 0:
            # 计算路径相似度
            passenger_route = passenger.get("route_path", [])
            vehicle_route = vehicle.get("route_path", [])
            score = route_similarity(
                passenger.get("start", "") + " to " + passenger.get("end", ""),
                vehicle.get("start", "") + " to " + vehicle.get("end", ""),
                json.dumps(passenger_route) if passenger_route else None,
                json.dumps(vehicle_route) if vehicle_route else None
            )

            # 确保分数在0-1之间
            score = max(0, min(1, score))

            # 使用隐私保护距离计算
            if passenger_coords and vehicle.get("start_coords"):
                dist_calc = DifferentialPrivacy()
                distance = dist_calc.calculate_distance(
                    passenger_coords[0], passenger_coords[1],
                    vehicle["start_coords"][0], vehicle["start_coords"][1]
                )
                # 距离权重
                distance_weight = max(0, 1 - distance / MAX_DISTANCE_THRESHOLD)
                score = score * 0.7 + distance_weight * 0.3

            if score > best_score:
                best_score = score
                best_match = vehicle

    if best_match:
        v_id = best_match["id"]
        match_code = generate_match_code(p_id, v_id, current_psi_mode)

        # 创建匹配记录
        create_match(p_id, v_id, match_code)

        # 更新状态
        update_passenger_status(p_id, "matched")
        update_vehicle_seats(v_id, best_match["seats"] - 1)

        # 检查是否满载
        if best_match["seats"] - 1 == 0:
            update_vehicle_status(v_id, "full")

        # 创建行程追踪
        trip_id = f"trip_{p_id}_{v_id}_{int(time.time())}"
        if passenger_coords and best_match.get("start_coords"):
            trip = trip_tracker.create_trip(
                trip_id, p_id, v_id,
                passenger_coords[1], passenger_coords[0],
                best_match["start_coords"][1], best_match["start_coords"][0]
            )

        # 返回更新后的车辆信息
        best_match["seats"] -= 1
        if best_match["seats"] == 0:
            best_match["status"] = "full"

        # 缓存匹配结果
        route_cache.add_match(p_id, {
            "vehicle": best_match,
            "match_code": match_code,
            "timestamp": time.time()
        })

        # 通知车辆端
        emit_to_vehicle(v_id, "new_passenger", {
            "passenger": passenger,
            "vehicle": best_match,
            "match_code": match_code,
            "trip_id": trip_id
        })

        return jsonify({
            "success": True,
            "message": f"匹配成功！相似度: {best_score:.2f}",
            "vehicle": best_match,
            "match_code": match_code,
            "trip_id": trip_id,
            "psi_mode": current_psi_mode
        })
    else:
        return jsonify({
            "success": False,
            "message": "暂无匹配车辆",
            "nearby_count": len(nearby_vehicles),
            "available_count": len(available_vehicles)
        })


@app.route("/vehicle/check", methods=["GET"])
def vehicle_check():
    """查询车辆匹配的乘客列表"""
    v_id = request.args.get("vehicle_id")
    if not v_id:
        return error_response("缺少vehicle_id")

    # 获取车辆信息
    vehicle = get_vehicle(v_id)

    # 获取匹配的乘客
    matches = get_match_by_vehicle(v_id)

    # 获取乘客详细信息
    matched_passengers = []
    for match in matches:
        passenger = get_passenger(match["passenger_id"])
        if passenger:
            matched_passengers.append({
                "id": passenger["id"],
                "start": passenger["start"],
                "end": passenger["end"],
                "status": passenger["status"],
                "match_code": match["match_code"],
                "created_at": match["created_at"]
            })

    return jsonify({
        "vehicle": vehicle,
        "matched_passengers": matched_passengers,
        "count": len(matched_passengers)
    })


@app.route("/vehicle/confirm", methods=["POST"])
def vehicle_confirm_boarding():
    """车辆端确认乘客上车"""
    data = request.json
    v_id = data.get("vehicle_id")
    p_id = data.get("passenger_id")

    # 验证车辆存在
    vehicle = get_vehicle(v_id)
    if not vehicle:
        return error_response("车辆不存在", 404)

    # 验证匹配记录
    match_record = get_match_by_passenger(p_id)
    if not match_record or match_record["vehicle_id"] != v_id:
        return error_response("未找到匹配记录", 404)

    # 更新乘客状态为 boarded
    update_passenger_status(p_id, "boarded")

    # 通知乘客端
    emit_to_passenger(p_id, "boarding_confirmed", {
        "vehicle_id": v_id,
        "message": "车辆已确认您上车",
        "timestamp": time.time()
    })

    return success_response("已确认乘客上车",
                         passenger_id=p_id,
                         vehicle_id=v_id,
                         timestamp=time.time())


@app.route("/verify", methods=["POST"])
def verify():
    """上车验证码验证（增强版）"""
    data = request.json
    p_id = data.get("passenger_id")
    v_id = data.get("vehicle_id")
    code = data.get("code")

    # 验证匹配码
    expected_code = generate_match_code(p_id, v_id, current_psi_mode)
    print(f"Debug: 验证码输入={code.upper()}, 期望={expected_code.upper()}")

    # 获取匹配记录
    match_record = get_match_by_passenger(p_id)
    if match_record and match_record["vehicle_id"] == v_id and code.upper() == expected_code.upper():
        # 更新行程状态（created_at是字符串，使用hash作为标识）
        trip_hash = hashlib.md5(str(match_record['created_at']).encode()).hexdigest()[:8]
        trip_id = f"trip_{p_id}_{v_id}_{trip_hash}"
        trip_tracker.update_trip_status(
            trip_id,
            TripStatus.BOARDING,
            "乘客正在上车"
        )

        # 通知车辆端乘客已上车
        emit_to_vehicle(v_id, "passenger_boarded", {
            "passenger_id": p_id,
            "timestamp": str(hashlib.md5(str(time.time()).encode()).hexdigest())[:8],
            "psi_mode": current_psi_mode,
            "trip_id": trip_id
        })

        # 通知乘客车辆已确认
        emit_to_passenger(p_id, "vehicle_confirmed", {
            "vehicle_id": v_id,
            "message": "车辆已确认，请准备上车",
            "trip_id": trip_id
        })

        return jsonify({
            "success": True,
            "message": "验证成功，可以上车！",
            "psi_mode": current_psi_mode,
            "trip_id": trip_id
        })
    else:
        return jsonify({
            "success": False,
            "message": "验证失败！",
            "psi_mode": current_psi_mode
        })


@app.route("/cancel", methods=["POST"])
def cancel_match():
    """取消乘客匹配（增强版）"""
    data = request.json
    p_id = data.get("passenger_id")

    passenger = get_passenger(p_id)
    if not passenger:
        return error_response("乘客未注册", 404)

    if passenger["status"] != "matched":
        return error_response("乘客未处于匹配状态")

    match_record = get_match_by_passenger(p_id)
    if not match_record:
        return error_response("无匹配记录", 404)

    v_id = match_record["vehicle_id"]
    vehicle = get_vehicle(v_id)

    # 释放座位
    if vehicle:
        update_vehicle_seats(v_id, vehicle["seats"] + 1)
        if vehicle["seats"] + 1 > 0:
            update_vehicle_status(v_id, "available")

    # 移除匹配关系
    delete_match_by_passenger(p_id)
    update_passenger_status(p_id, "waiting")

    # 取消行程追踪（created_at是字符串，使用hash作为标识）
    import hashlib
    trip_hash = hashlib.md5(str(match_record['created_at']).encode()).hexdigest()[:8]
    trip_id = f"trip_{p_id}_{v_id}_{trip_hash}"
    trip_tracker.cancel_trip(trip_id, "乘客取消")

    # 通知车辆端
    emit_to_vehicle(v_id, "passenger_cancelled", {
        "passenger_id": p_id,
        "timestamp": time.time()
    })

    # 从缓存移除
    route_cache.remove_match(p_id)

    return jsonify({
        "success": True,
        "message": "匹配已取消，座位已释放",
        "trip_id": trip_id
    })


# ========== 多模态输入API ==========

@app.route("/input/voice", methods=["POST"])
def voice_input():
    """语音输入处理"""
    data = request.json
    audio_data = data.get("audio_data")  # Base64编码的音频数据
    user_id = data.get("user_id")
    language = data.get("language", "zh-CN")

    # 这里应该解码Base64音频数据
    # 简化实现：直接处理文本
    if data.get("text"):
        text = data.get("text")

        # 解析路线命令
        route_cmd = input_handler.parse_route_command(text)
        if route_cmd:
            return jsonify({
                "success": True,
                "type": "route",
                "data": route_cmd,
                "suggestions": input_handler.predict_destination(
                    route_cmd.get("to", ""), user_id
                )
            })

        # 获取地址建议
        suggestions = input_handler.get_suggestions(text, user_id)
        return jsonify({
            "success": True,
            "type": "suggestion",
            "suggestions": suggestions[:10]
        })

    # 模拟语音识别
    voice_result = input_handler.voice_to_text(audio_data, language)
    return jsonify({
        "success": True,
        "type": "voice",
        "text": voice_result.text,
        "confidence": voice_result.confidence,
        "language": voice_result.language
    })


@app.route("/input/map-select", methods=["POST"])
def map_select():
    """地图选点处理"""
    data = request.json
    lng = float(data.get("lng"))
    lat = float(data.get("lat"))
    user_id = data.get("user_id")

    # 逆地理编码
    address = geocode_address_reverse((lng, lat))

    # 添加到收藏
    if user_id and address:
        input_handler.add_user_favorite(user_id, address, lng, lat)

    return jsonify({
        "success": True,
        "address": address,
        "lng": lng,
        "lat": lat,
        "is_favorite": user_id is not None
    })


@app.route("/input/predict", methods=["POST"])
def predict_destination():
    """目的地预测"""
    data = request.json
    partial_input = data.get("partial_input")
    user_id = data.get("user_id")
    context = data.get("context", {})

    predictions = input_handler.predict_destination(partial_input, user_id, context)

    return jsonify({
        "success": True,
        "predictions": predictions[:10]
    })


@app.route("/input/stats", methods=["POST"])
def get_user_stats():
    """获取用户输入统计"""
    data = request.json
    user_id = data.get("user_id")

    stats = input_handler.get_user_stats(user_id)

    return jsonify({
        "success": True,
        "stats": stats
    })


# ========== 实时追踪API ==========

@app.route("/tracking/update", methods=["POST"])
def update_location():
    """更新位置信息"""
    data = request.json
    entity_type = data.get("type")  # "passenger" or "vehicle"
    entity_id = data.get("id")
    lng = float(data.get("lng"))
    lat = float(data.get("lat"))
    accuracy = float(data.get("accuracy", 10.0))

    if entity_type == "passenger":
        # 更新乘客位置
        trip_tracker.update_passenger_location(entity_id, lng, lat, accuracy)

        # 添加到历史记录
        passenger = get_passenger(entity_id)
        if passenger:
            input_handler.add_user_history(entity_id, {
                "start": passenger.get("start"),
                "end": passenger.get("end"),
                "start_lng": passenger.get("start_coords", [0, 0])[0] if passenger.get("start_coords") else 0,
                "start_lat": passenger.get("start_coords", [0, 0])[1] if passenger.get("start_coords") else 0,
                "end_lng": passenger.get("end_coords", [0, 0])[0] if passenger.get("end_coords") else 0,
                "end_lat": passenger.get("end_coords", [0, 0])[1] if passenger.get("end_coords") else 0,
                "timestamp": time.time()
            })
    elif entity_type == "vehicle":
        # 更新车辆位置
        trip_tracker.update_vehicle_location(entity_id, lng, lat, accuracy)
    else:
        return jsonify({"error": "无效的实体类型"}), 400

    return jsonify({"success": True, "timestamp": time.time()})


@app.route("/tracking/eta/<trip_id>", methods=["GET"])
def get_eta(trip_id):
    """获取预计到达时间"""
    eta = trip_tracker.calculate_eta(trip_id)
    if eta:
        return jsonify({
            "success": True,
            "eta": eta,
            "eta_formatted": datetime.fromtimestamp(eta).strftime("%H:%M:%S")
        })
    else:
        return jsonify({"success": False, "message": "无法计算ETA"})


@app.route("/tracking/trip/<trip_id>", methods=["GET"])
def get_trip_info(trip_id):
    """获取行程信息"""
    summary = trip_tracker.get_trip_summary(trip_id)
    if summary:
        return jsonify({"success": True, "trip": summary})
    else:
        return jsonify({"success": False, "message": "行程不存在"})


# ========== 系统管理API ==========

@app.route("/psi/config", methods=["GET"])
def get_psi_config():
    """获取PSI配置信息"""
    PSI_MODES = {
        "hash": "MD5哈希（兼容模式）",
        "ecc": "ECC双方PSI",
        "multi": "ECC多方PSI",
        "threshold": "门限PSI"
    }

    return jsonify({
        "current_mode": current_psi_mode,
        "description": PSI_MODES.get(current_psi_mode, ""),
        "available_modes": PSI_MODES
    })


@app.route("/psi/config", methods=["POST"])
def update_psi_config():
    """更新PSI模式配置"""
    global current_psi_mode
    data = request.json
    new_mode = data.get("mode")

    if new_mode in ["hash", "ecc", "multi", "threshold"]:
        old_mode = current_psi_mode
        current_psi_mode = new_mode

        # 广播模式变更
        socketio.emit("psi_mode_changed", {
            "old_mode": old_mode,
            "new_mode": new_mode,
            "timestamp": time.time()
        })

        return success_response(f"PSI模式已更新为 {new_mode}", mode=new_mode)
    else:
        return error_response("无效的PSI模式")


@app.route("/stats", methods=["GET"])
def get_system_stats():
    """获取系统统计信息"""
    # 数据库统计
    passenger_count = len(get_all_passengers())
    vehicle_count = len(get_all_vehicles())

    # 追踪器统计
    tracker_stats = trip_tracker.get_stats()

    # 空间索引统计
    spatial_stats = spatial_index.get_stats()

    return jsonify({
        "timestamp": time.time(),
        "passenger_count": passenger_count,
        "vehicle_count": vehicle_count,
        "tracker": tracker_stats,
        "spatial_index": spatial_stats,
        "current_psi_mode": current_psi_mode,
        "route_cache_hits": route_cache.hits,
        "route_cache_misses": route_cache.misses
    })


@app.route("/reset", methods=["POST"])
def reset_data():
    """重置所有数据（增强版）"""
    # 重置数据库
    reset_db()

    # 重置高级组件
    spatial_index.clear()
    bloom_filter.clear()
    route_cache.clear()
    trip_tracker.cleanup_old_trips(0)  # 清理所有行程

    # 广播系统重置
    socketio.emit("system_reset", {
        "message": "系统已重置",
        "timestamp": time.time()
    })

    return jsonify({
        "success": True,
        "message": "数据已重置",
        "timestamp": time.time()
    })


@app.route("/debug/coordinates", methods=["POST"])
def debug_coordinates():
    """调试坐标转换"""
    data = request.json
    address = data.get("address")

    coords = geocode_address(address)
    reverse = None
    if coords:
        reverse = geocode_address_reverse(coords)

    return jsonify({
        "address": address,
        "coordinates": coords,
        "reverse": reverse,
        "timestamp": time.time()
    })


# ========== WebSocket 事件 ==========

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    print(f"客户端连接: {request.sid}")
    emit('connected', {
        'message': '连接成功',
        'timestamp': time.time(),
        'psi_mode': current_psi_mode
    })


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    print(f"客户端断开: {request.sid}")


@socketio.on('join_vehicle')
def handle_join_vehicle(data):
    """加入车辆房间"""
    v_id = data.get('vehicle_id')
    if v_id:
        room = f"vehicle_{v_id}"
        from flask_socketio import join_room
        join_room(room)
        print(f"客户端 {request.sid} 加入车辆房间: {v_id}")
        emit('joined', {
            'vehicle_id': v_id,
            'timestamp': time.time()
        }, room=request.sid)


@socketio.on('join_passenger')
def handle_join_passenger(data):
    """加入乘客房间"""
    p_id = data.get('passenger_id')
    if p_id:
        room = f"passenger_{p_id}"
        from flask_socketio import join_room
        join_room(room)
        print(f"客户端 {request.sid} 加入乘客房间: {p_id}")
        emit('joined', {
            'passenger_id': p_id,
            'timestamp': time.time()
        }, room=request.sid)


@socketio.on('location_update')
def handle_location_update(data):
    """处理位置更新"""
    entity_type = data.get('type')
    entity_id = data.get('id')
    lng = data.get('lng')
    lat = data.get('lat')

    if entity_type and entity_id and lng is not None and lat is not None:
        # 调用相应的位置更新函数
        if entity_type == 'passenger':
            trip_tracker.update_passenger_location(entity_id, lng, lat)
        elif entity_type == 'vehicle':
            trip_tracker.update_vehicle_location(entity_id, lng, lat)

        print(f"收到位置更新: {entity_type}_{entity_id} ({lng}, {lat})")


# ========== 智能推荐API ==========

@app.route("/recommend/routes", methods=["POST"])
def recommend_routes():
    """获取路线推荐"""
    data = request.json
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"error": "缺少user_id"}), 400
    
    history = input_handler.user_history.get(user_id, [])
    
    recommendations = recommendation_engine.get_similar_routes(history, top_n=5)
    
    return jsonify({
        "success": True,
        "recommendations": [
            {
                "type": r.item_type,
                "item": r.item_data,
                "score": r.score,
                "reason": r.reason
            }
            for r in recommendations
        ]
    })


@app.route("/recommend/predict", methods=["POST"])
def recommend_predict_destination():
    """预测目的地"""
    data = request.json
    partial_input = data.get("input", "")
    user_id = data.get("user_id")
    
    history = input_handler.user_history.get(user_id, []) if user_id else None
    
    predictions = recommendation_engine.get_destination_prediction(
        partial_input, history
    )
    
    return jsonify({
        "success": True,
        "predictions": predictions
    })


@app.route("/recommend/popular", methods=["GET"])
def get_popular_routes():
    """获取热门路线"""
    all_trips = input_handler.user_history.get("all", [])
    popular = recommendation_engine.get_popular_routes(all_trips, top_n=5)
    
    return jsonify({
        "success": True,
        "popular_routes": popular
    })


if __name__ == "__main__":
    import socket

    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    local_ip = get_local_ip()

    print("=" * 60)
    print("无人驾驶拼车系统 - 完整集成版")
    print("多模态输入、空间索引、实时追踪已启用")
    print("PSI模式:", current_psi_mode)
    print("=" * 60)
    print("后端服务启动中...")
    print(f"  本机访问: http://localhost:5000")
    print(f"  局域网访问: http://{local_ip}:5000")
    print("=" * 60)

    # 监听0.0.0.0让局域网可访问
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)