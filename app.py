"""
无人驾驶拼车系统 - Flask后端
基于 PSI 隐私保护的共享出行系统
使用 SQLite 数据库持久化 + WebSocket 实时更新 + MP-TPSI协议
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import hashlib
import time
from database import (
    init_db, reset_db, create_passenger, get_passenger, update_passenger_status,
    create_vehicle, get_vehicle, update_vehicle_status, update_vehicle_seats,
    get_available_vehicles, create_match, get_match_by_passenger,
    get_match_by_vehicle, delete_match_by_passenger, reset_matches,
    get_all_passengers, get_all_vehicles, get_all_matches
)
from psi import generate_match_code, route_similarity, get_psi_instance

app = Flask(__name__)
app.config['SECRET_KEY'] = 'psi-ride-sharing-secret-2024'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化数据库
init_db()

# PSI实例
_psi = get_psi_instance()


def psi_match(passenger_data, available_vehicles):
    """
    PSI匹配算法（增强版）

    基于PSI思想的路线相似度计算，支持：
    - 区域匹配
    - Jaccard相似度
    - 可配置的匹配阈值
    """
    best_match = None
    best_score = 0
    for vehicle in available_vehicles:
        if vehicle["seats"] < 1:
            continue
        score = route_similarity(passenger_data["route"], vehicle["route"])
        if score > best_score and score >= 0.7:
            best_score = score
            best_match = vehicle
    return best_match


# ========== PSI模式配置 ==========

PSI_MODES = {
    "hash": "MD5哈希（兼容模式）",
    "ecc": "ECC双方PSI",
    "multi": "ECC多方PSI",
    "threshold": "门限PSI"
}

# 当前PSI模式（可通过API切换）
current_psi_mode = "hash"


def emit_to_vehicle(v_id, event, data):
    """向特定车辆发送实时消息"""
    socketio.emit(event, data, room=f"vehicle_{v_id}")


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


@app.route("/verify")
def verify_page():
    return render_template("verify.html")


@app.route("/admin")
def admin_page():
    return render_template("admin.html")


# ========== API 接口 ==========

@app.route("/passenger/register", methods=["POST"])
def passenger_register():
    """乘客注册"""
    data = request.json
    p_id = data.get("passenger_id")
    if not p_id:
        return jsonify({"error": "缺少passenger_id"}), 400

    passenger = create_passenger(p_id, data.get("start"), data.get("end"))
    return jsonify({"message": "乘客注册成功", "passenger": passenger})


@app.route("/vehicle/register", methods=["POST"])
def vehicle_register():
    """车辆注册"""
    data = request.json
    v_id = data.get("vehicle_id")
    if not v_id:
        return jsonify({"error": "缺少vehicle_id"}), 400

    vehicle = create_vehicle(
        v_id,
        data.get("start"),
        data.get("end"),
        data.get("seats", 4)
    )
    return jsonify({"message": "车辆注册成功", "vehicle": vehicle})


@app.route("/match", methods=["POST"])
def match():
    """乘客请求匹配"""
    data = request.json
    p_id = data.get("passenger_id")

    passenger = get_passenger(p_id)
    if not passenger:
        return jsonify({"error": "乘客未注册"}), 404

    # 获取可用车辆
    available_vehicles = get_available_vehicles()

    # PSI匹配
    matched_vehicle = psi_match(passenger, available_vehicles)

    if matched_vehicle:
        v_id = matched_vehicle["id"]
        match_code = generate_match_code(p_id, v_id, current_psi_mode)

        # 创建匹配记录
        create_match(p_id, v_id, match_code)

        # 更新状态
        update_passenger_status(p_id, "matched")
        update_vehicle_seats(v_id, matched_vehicle["seats"] - 1)

        # 检查是否满载
        if matched_vehicle["seats"] - 1 == 0:
            update_vehicle_status(v_id, "full")

        # 返回更新后的车辆信息
        matched_vehicle["seats"] -= 1
        if matched_vehicle["seats"] == 0:
            matched_vehicle["status"] = "full"

        # 通知车辆端有新乘客匹配
        emit_to_vehicle(v_id, "new_passenger", {
            "passenger": passenger,
            "vehicle": matched_vehicle
        })

        return jsonify({
            "success": True,
            "message": "匹配成功！",
            "vehicle": matched_vehicle,
            "match_code": match_code
        })
    else:
        return jsonify({"success": False, "message": "暂无匹配车辆"})


@app.route("/vehicle/check", methods=["GET"])
def vehicle_check():
    """车辆查看匹配的乘客列表"""
    v_id = request.args.get("vehicle_id")

    vehicle = get_vehicle(v_id)
    if not vehicle:
        return jsonify({"error": "车辆未注册"}), 404

    # 获取匹配的乘客
    matches = get_match_by_vehicle(v_id)
    matched_passengers = []
    for m in matches:
        passenger = get_passenger(m["passenger_id"])
        if passenger:
            matched_passengers.append(passenger)

    return jsonify({"vehicle": vehicle, "matched_passengers": matched_passengers})


@app.route("/verify", methods=["POST"])
def verify():
    """上车验证码验证"""
    data = request.json
    p_id = data.get("passenger_id")
    v_id = data.get("vehicle_id")
    code = data.get("code")

    expected_code = generate_match_code(p_id, v_id, current_psi_mode)
    if code.upper() == expected_code.upper():
        # 通知车辆端乘客已上车
        emit_to_vehicle(v_id, "passenger_boarded", {
            "passenger_id": p_id,
            "timestamp": str(hashlib.md5(str(time.time()).encode()).hexdigest())[:8],
            "psi_mode": current_psi_mode
        })
        return jsonify({
            "success": True,
            "message": "验证成功，可以上车！",
            "psi_mode": current_psi_mode
        })
    else:
        return jsonify({
            "success": False,
            "message": "验证失败！",
            "psi_mode": current_psi_mode
        })


@app.route("/cancel", methods=["POST"])
def cancel_match():
    """取消乘客匹配，释放车辆座位"""
    data = request.json
    p_id = data.get("passenger_id")

    passenger = get_passenger(p_id)
    if not passenger:
        return jsonify({"error": "乘客未注册"}), 404

    if passenger["status"] != "matched":
        return jsonify({"error": "乘客未处于匹配状态"}), 400

    match_record = get_match_by_passenger(p_id)
    if not match_record:
        return jsonify({"error": "无匹配记录"}), 404

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

    # 通知车辆端有乘客取消
    emit_to_vehicle(v_id, "passenger_cancelled", {
        "passenger_id": p_id
    })

    return jsonify({
        "success": True,
        "message": "匹配已取消，座位已释放"
    })


@app.route("/reset", methods=["POST"])
def reset_data():
    """重置所有数据（仅用于测试）"""
    reset_db()
    socketio.emit("system_reset", {"message": "系统已重置"}, broadcast=True)
    return jsonify({"message": "数据已重置"})


# ========== PSI配置API ==========

@app.route("/psi/config", methods=["GET"])
def get_psi_config():
    """获取PSI配置"""
    return jsonify({
        "current_mode": current_psi_mode,
        "available_modes": PSI_MODES,
        "description": PSI_MODES.get(current_psi_mode, "")
    })


@app.route("/psi/config", methods=["POST"])
def set_psi_config():
    """设置PSI模式"""
    global current_psi_mode
    data = request.json
    mode = data.get("mode", "hash")

    if mode not in PSI_MODES:
        return jsonify({"error": f"无效的PSI模式，可选: {list(PSI_MODES.keys())}"}), 400

    current_psi_mode = mode
    return jsonify({
        "message": f"PSI模式已切换为: {PSI_MODES[mode]}",
        "current_mode": current_psi_mode
    })


@app.route("/psi/verify", methods=["POST"])
def psi_verify():
    """PSI验证码验证（独立API）"""
    data = request.json
    p_id = data.get("passenger_id")
    v_id = data.get("vehicle_id")
    code = data.get("code")

    expected = generate_match_code(p_id, v_id, current_psi_mode)
    is_valid = expected.upper() == code.upper()

    return jsonify({
        "valid": is_valid,
        "expected": expected if is_valid else None,
        "mode": current_psi_mode
    })


# ========== 管理后台API ==========

@app.route("/admin/passengers", methods=["GET"])
def admin_get_passengers():
    """获取所有乘客列表"""
    return jsonify(get_all_passengers())


@app.route("/admin/vehicles", methods=["GET"])
def admin_get_vehicles():
    """获取所有车辆列表"""
    return jsonify(get_all_vehicles())


@app.route("/admin/matches", methods=["GET"])
def admin_get_matches():
    """获取所有匹配记录"""
    return jsonify(get_all_matches())


@app.route("/admin/stats", methods=["GET"])
def admin_get_stats():
    """获取系统统计数据"""
    passengers = get_all_passengers()
    vehicles = get_all_vehicles()
    matches = get_all_matches()

    matched_passengers = len([p for p in passengers if p["status"] == "matched"])
    waiting_passengers = len([p for p in passengers if p["status"] == "waiting"])
    available_vehicles = len([v for v in vehicles if v["status"] == "available"])
    full_vehicles = len([v for v in vehicles if v["status"] == "full"])

    return jsonify({
        "total_passengers": len(passengers),
        "matched_passengers": matched_passengers,
        "waiting_passengers": waiting_passengers,
        "total_vehicles": len(vehicles),
        "available_vehicles": available_vehicles,
        "full_vehicles": full_vehicles,
        "total_matches": len(matches),
        "psi_mode": current_psi_mode
    })


# ========== SocketIO 事件 ==========

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    print(f"客户端连接: {request.sid}")
    emit('connected', {'message': '连接成功'})


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
        join_room(room)
        print(f"客户端 {request.sid} 加入车辆房间: {v_id}")
        emit('joined', {'vehicle_id': v_id}, room=request.sid)


@socketio.on('leave_vehicle')
def handle_leave_vehicle():
    """离开车辆房间"""
    leave_room()
    print(f"客户端 {request.sid} 离开车辆房间")


@socketio.on('vehicle_status_update')
def handle_vehicle_status(data):
    """车辆状态更新（用于心跳）"""
    v_id = data.get('vehicle_id')
    emit('vehicle_status', {'vehicle_id': v_id, 'timestamp': data.get('timestamp')},
         room=f"vehicle_{v_id}", include_self=False)


def join_room(room):
    """加入房间"""
    from flask_socketio import join_room
    join_room(room)


def leave_room():
    """离开所有房间"""
    from flask_socketio import leave_room, rooms
    client_rooms = rooms(request.sid)
    for room in client_rooms:
        leave_room(room)


if __name__ == "__main__":
    import socket
    import platform

    # 获取本机IP地址
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

    print("=" * 50)
    print("无人驾驶拼车系统 MVP")
    print("基于 PSI 隐私保护的共享出行系统")
    print("WebSocket 实时推送已启用")
    print("=" * 50)
    print(f"后端服务启动中...")
    print(f"  本机访问: http://localhost:5000")
    print(f"  局域网访问: http://{local_ip}:5000")
    print()
    print("手机访问步骤:")
    print(f"1. 确保手机和电脑在同一WiFi网络")
    print(f"2. 在手机浏览器输入: http://{local_ip}:5000")
    print("=" * 50)

    # 监听0.0.0.0让局域网可访问
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
