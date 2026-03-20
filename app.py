"""
无人驾驶拼车系统 - Flask后端
基于 PSI 隐私保护的共享出行系统
使用 SQLite 数据库持久化
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import hashlib
from database import (
    init_db, reset_db, create_passenger, get_passenger, update_passenger_status,
    create_vehicle, get_vehicle, update_vehicle_status, update_vehicle_seats,
    get_available_vehicles, create_match, get_match_by_passenger,
    get_match_by_vehicle, delete_match_by_passenger, reset_matches
)

app = Flask(__name__)
CORS(app)

# 初始化数据库
init_db()


def route_similarity(route1, route2):
    """路线相似度计算（简化版，未来可替换为PSI）"""
    area1 = route1[:3]
    area2 = route2[:3]
    return 0.9 if area1 == area2 else 0.1


def psi_match(passenger_data, available_vehicles):
    """PSI匹配算法（简化版）"""
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


def generate_match_code(p_id, v_id):
    """生成PSI匹配验证码"""
    raw = f"{p_id}{v_id}"
    return hashlib.md5(raw.encode()).hexdigest()[:6].upper()


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
        match_code = generate_match_code(p_id, v_id)

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

    expected_code = generate_match_code(p_id, v_id)
    if code == expected_code:
        return jsonify({"success": True, "message": "验证成功，可以上车！"})
    else:
        return jsonify({"success": False, "message": "验证失败！"})


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

    return jsonify({
        "success": True,
        "message": "匹配已取消，座位已释放"
    })


@app.route("/reset", methods=["POST"])
def reset_data():
    """重置所有数据（仅用于测试）"""
    reset_db()
    return jsonify({"message": "数据已重置"})


if __name__ == "__main__":
    print("=" * 50)
    print("无人驾驶拼车系统 MVP")
    print("基于 PSI 隐私保护的共享出行系统")
    print("后端服务启动中... http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
