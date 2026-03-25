"""
管理后台API测试
测试新增的管理后台端点
"""

import requests
import time
import json

BASE_URL = "http://localhost:5000"


def print_result(test_name, success, details=""):
    """打印测试结果"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - {test_name}")
    if details:
        print(f"       {details}")
    return success


def test_admin_passengers():
    """测试获取乘客列表"""
    try:
        response = requests.get(f"{BASE_URL}/admin/passengers")
        data = response.json()
        success = response.status_code == 200 and isinstance(data, list)
        return print_result("获取乘客列表", success, f"返回 {len(data)} 条记录")
    except Exception as e:
        return print_result("获取乘客列表", False, str(e))


def test_admin_vehicles():
    """测试获取车辆列表"""
    try:
        response = requests.get(f"{BASE_URL}/admin/vehicles")
        data = response.json()
        success = response.status_code == 200 and isinstance(data, list)
        return print_result("获取车辆列表", success, f"返回 {len(data)} 条记录")
    except Exception as e:
        return print_result("获取车辆列表", False, str(e))


def test_admin_matches():
    """测试获取匹配记录"""
    try:
        response = requests.get(f"{BASE_URL}/admin/matches")
        data = response.json()
        success = response.status_code == 200 and isinstance(data, list)
        return print_result("获取匹配记录", success, f"返回 {len(data)} 条记录")
    except Exception as e:
        return print_result("获取匹配记录", False, str(e))


def test_psi_config_get():
    """测试获取PSI配置"""
    try:
        response = requests.get(f"{BASE_URL}/psi/config")
        data = response.json()
        success = (response.status_code == 200 and
                   "current_mode" in data and
                   "available_modes" in data)
        return print_result("获取PSI配置", success,
                         f"当前模式: {data.get('current_mode', 'N/A')}")
    except Exception as e:
        return print_result("获取PSI配置", False, str(e))


def test_psi_config_post():
    """测试更新PSI配置"""
    modes = ["hash", "ecc", "multi", "threshold"]
    try:
        # 切换到ecc模式
        response = requests.post(
            f"{BASE_URL}/psi/config",
            json={"mode": "ecc"}
        )
        data = response.json()

        # 切换回hash模式
        requests.post(
            f"{BASE_URL}/psi/config",
            json={"mode": "hash"}
        )

        success = (response.status_code == 200 and
                   data.get("success") == True and
                   "mode" in data)
        return print_result("更新PSI配置", success,
                         f"切换到: {data.get('mode', 'N/A')}")
    except Exception as e:
        return print_result("更新PSI配置", False, str(e))


def test_vehicle_confirm():
    """测试车辆确认上车"""
    # 首先需要创建匹配
    try:
        # 注册乘客
        p_id = f"P{int(time.time()) % 10000:04d}"
        requests.post(f"{BASE_URL}/passenger/register", json={
            "passenger_id": p_id,
            "start": "上海浦东",
            "end": "上海虹桥"  # 使用不同路线避免匹配到现有车辆
        })

        # 注册车辆
        v_id = f"V{int(time.time()) % 1000:03d}"
        requests.post(f"{BASE_URL}/vehicle/register", json={
            "vehicle_id": v_id,
            "start": "上海浦东",
            "end": "上海虹桥",
            "seats": 2
        })

        # 创建匹配
        match_response = requests.post(f"{BASE_URL}/match", json={
            "passenger_id": p_id
        })
        match_data = match_response.json()
        match_success = match_data.get("success") == True

        if not match_success:
            return print_result("车辆确认上车 - 前置匹配失败", False,
                           f"原因: {match_data.get('message', '未知')}")

        # 获取匹配的车辆ID（可能是不同的车辆）
        matched_v_id = match_data.get("vehicle", {}).get("id", v_id)

        # 确认上车 - 使用实际匹配的车辆ID
        response = requests.post(f"{BASE_URL}/vehicle/confirm", json={
            "vehicle_id": matched_v_id,
            "passenger_id": p_id
        })
        data = response.json()

        success = (response.status_code == 200 and
                   data.get("success") == True)

        # 清理
        try:
            requests.post(f"{BASE_URL}/cancel", json={"passenger_id": p_id})
        except:
            pass

        return print_result("车辆确认上车", success,
                         f"乘客 {p_id} 车辆 {matched_v_id}")
    except Exception as e:
        return print_result("车辆确认上车", False, str(e))


def test_unified_response():
    """测试统一响应格式"""
    try:
        # 测试错误响应
        response = requests.post(
            f"{BASE_URL}/vehicle/register",
            json={}
        )
        data = response.json()
        has_error_format = "success" in data and data.get("success") == False

        # 测试成功响应
        response = requests.get(f"{BASE_URL}/stats")
        data = response.json()
        has_success_format = "timestamp" in data

        success = has_error_format or has_success_format
        return print_result("统一响应格式", success,
                         "包含success字段")
    except Exception as e:
        return print_result("统一响应格式", False, str(e))


def main():
    """运行所有测试"""
    print("=" * 50)
    print("管理后台API测试")
    print("=" * 50)
    print()

    tests = [
        ("获取乘客列表", test_admin_passengers),
        ("获取车辆列表", test_admin_vehicles),
        ("获取匹配记录", test_admin_matches),
        ("获取PSI配置", test_psi_config_get),
        ("更新PSI配置", test_psi_config_post),
        ("车辆确认上车", test_vehicle_confirm),
        ("统一响应格式", test_unified_response),
    ]

    results = []
    for name, test_func in tests:
        results.append(test_func())
        time.sleep(0.2)  # 避免请求过快

    print()
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"测试结果: {passed}/{total} 通过")
    print("=" * 50)

    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n测试中断")
        exit(1)
