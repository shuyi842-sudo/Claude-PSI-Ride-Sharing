from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import hashlib
import random

app = Flask(__name__)
CORS(app)

passengers = {}
vehicles = {}
matches = {}
vehicles_passengers = {}

def route_similarity(route1, route2):
    area1 = route1[:3]
    area2 = route2[:3]
    return 0.9 if area1 == area2 else 0.1

def psi_match(passenger_data, available_vehicles):
    best_match = None
    best_score = 0
    for v_id, v_data in available_vehicles.items():
        if v_data["seats"] < 1:
            continue
        score = route_similarity(passenger_data["route"], v_data["route"])
        if score > best_score and score >= 0.7:
            best_score = score
            best_match = v_id
    return best_match

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

@app.route("/passenger/register", methods=["POST"])
def passenger_register():
    data = request.json
    p_id = data.get("passenger_id")
    if not p_id:
        return jsonify({"error": "缺少passenger_id"}), 400
    passengers[p_id] = {
        "id": p_id,
        "start": data.get("start"),
        "end": data.get("end"),
        "route": f"{data.get('start')}-{data.get('end')}",
        "status": "waiting"
    }
    return jsonify({"message": "乘客注册成功", "passenger": passengers[p_id]})

@app.route("/vehicle/register", methods=["POST"])
def vehicle_register():
    data = request.json
    v_id = data.get("vehicle_id")
    if not v_id:
        return jsonify({"error": "缺少vehicle_id"}), 400
    vehicles[v_id] = {
        "id": v_id,
        "start": data.get("start"),
        "end": data.get("end"),
        "route": f"{data.get('start')}-{data.get('end')}",
        "seats": data.get("seats", 4),
        "status": "available"
    }
    vehicles_passengers[v_id] = []
    return jsonify({"message": "车辆注册成功", "vehicle": vehicles[v_id]})

@app.route("/match", methods=["POST"])
def match():
    data = request.json
    p_id = data.get("passenger_id")
    if p_id not in passengers:
        return jsonify({"error": "乘客未注册"}), 404
    passenger = passengers[p_id]
    available_vehicles = {v_id: v for v_id, v in vehicles.items() if v["status"] == "available"}
    matched_vehicle_id = psi_match(passenger, available_vehicles)
    if matched_vehicle_id:
        matches[p_id] = matched_vehicle_id
        vehicles_passengers[matched_vehicle_id].append(p_id)
        passengers[p_id]["status"] = "matched"
        vehicles[matched_vehicle_id]["seats"] -= 1
        if vehicles[matched_vehicle_id]["seats"] == 0:
            vehicles[matched_vehicle_id]["status"] = "full"
        return jsonify({
            "success": True,
            "message": "匹配成功！",
            "vehicle": vehicles[matched_vehicle_id],
            "match_code": generate_match_code(p_id, matched_vehicle_id)
        })
    else:
        return jsonify({"success": False, "message": "暂无匹配车辆"})

@app.route("/vehicle/check", methods=["GET"])
def vehicle_check():
    v_id = request.args.get("vehicle_id")
    if v_id not in vehicles:
        return jsonify({"error": "车辆未注册"}), 404
    matched_passengers = [passengers[p_id] for p_id in vehicles_passengers.get(v_id, [])]
    return jsonify({"vehicle": vehicles[v_id], "matched_passengers": matched_passengers})

@app.route("/verify", methods=["POST"])
def verify():
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
    if p_id not in passengers:
        return jsonify({"error": "乘客未注册"}), 404
    if passengers[p_id]["status"] != "matched":
        return jsonify({"error": "乘客未处于匹配状态"}), 400
    if p_id not in matches:
        return jsonify({"error": "无匹配记录"}), 404
    v_id = matches[p_id]
    # 释放座位
    vehicles[v_id]["seats"] += 1
    if vehicles[v_id]["seats"] > 0:
        vehicles[v_id]["status"] = "available"
    # 移除匹配关系
    if p_id in vehicles_passengers[v_id]:
        vehicles_passengers[v_id].remove(p_id)
    del matches[p_id]
    passengers[p_id]["status"] = "waiting"
    return jsonify({
        "success": True,
        "message": "匹配已取消，座位已释放"
    })

def generate_match_code(p_id, v_id):
    raw = f"{p_id}{v_id}"
    return hashlib.md5(raw.encode()).hexdigest()[:6].upper()

@app.route("/reset", methods=["POST"])
def reset_data():
    """重置所有数据（仅用于测试）"""
    global passengers, vehicles, matches, vehicles_passengers
    passengers.clear()
    vehicles.clear()
    matches.clear()
    vehicles_passengers.clear()
    return jsonify({"message": "数据已重置"})

if __name__ == "__main__":
    print("=" * 50)
    print("无人驾驶拼车系统 MVP")
    print("后端服务启动中... http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
