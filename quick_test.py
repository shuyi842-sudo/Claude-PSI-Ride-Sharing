#!/usr/bin/env python3
"""
快速端到端测试
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_passenger_registration():
    """测试乘客注册"""
    print("\n=== 测试1: 乘客注册 ===")
    data = {
        "passenger_id": "P001",
        "start": "北京中关村",
        "end": "北京国贸",
        "current_lng": 116.308,
        "current_lat": 39.983
    }

    r = requests.post(f"{BASE_URL}/passenger/register", json=data)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        result = r.json()
        print(f"✅ 注册成功: {result.get('message')}")
        return result.get("passenger", {}).get("id")
    else:
        print(f"❌ 注册失败: {r.text}")
        return None

def test_vehicle_registration():
    """测试车辆注册"""
    print("\n=== 测试2: 车辆注册 ===")
    data = {
        "vehicle_id": "V001",
        "start": "北京国贸",
        "end": "北京中关村",
        "seats": 4
    }

    r = requests.post(f"{BASE_URL}/vehicle/register", json=data)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        result = r.json()
        print(f"✅ 注册成功: {result.get('message')}")
        return result.get("vehicle", {}).get("id")
    else:
        print(f"❌ 注册失败: {r.text}")
        return None

def test_matching():
    """测试匹配功能"""
    print("\n=== 测试3: 匹配功能 ===")
    data = {
        "passenger_id": "P001"
    }

    r = requests.post(f"{BASE_URL}/match", json=data)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        result = r.json()
        if result.get("success"):
            print(f"✅ 匹配成功")
            print(f"   匹配车辆: {len(result.get('matches', []))}辆")
            for match in result.get('matches', [])[:3]:  # 只显示前3个
                print(f"   - {match['vehicle_id']}: {match['similarity']:.2f}")
            return True
        else:
            print(f"❌ 匹配失败: {result.get('error')}")
            return False
    else:
        print(f"❌ 请求失败: {r.text}")
        return False

def test_psi_code():
    """测试PSI验证码生成"""
    print("\n=== 测试4: PSI验证码 ===")
    data = {
        "passenger_id": "P001",
        "vehicle_id": "V001"
    }

    r = requests.post(f"{BASE_URL}/psi/generate", json=data)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        result = r.json()
        if result.get("success"):
            codes = result.get("codes", {})
            print(f"✅ PSI验证码生成成功:")
            for mode, code in codes.items():
                print(f"   {mode}: {code}")
            return True
        else:
            print(f"❌ 生成失败: {result.get('error')}")
            return False
    else:
        print(f"❌ 请求失败: {r.text}")
        return False

def test_verification():
    """测试验证功能"""
    print("\n=== 测试5: 验证功能 ===")
    data = {
        "passenger_id": "P001",
        "vehicle_id": "V001",
        "match_code": "A160A5"  # 使用hash模式的验证码
    }

    r = requests.post(f"{BASE_URL}/verify", json=data)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        result = r.json()
        if result.get("success"):
            print(f"✅ 验证成功: {result.get('message')}")
            return True
        else:
            print(f"❌ 验证失败: {result.get('error')}")
            return False
    else:
        print(f"❌ 请求失败: {r.text}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("无人驾驶拼车系统 - 快速端到端测试")
    print("=" * 60)

    # 测试各功能
    passenger_id = test_passenger_registration()
    if not passenger_id:
        print("\n❌ 乘客注册失败，终止测试")
        return

    vehicle_id = test_vehicle_registration()
    if not vehicle_id:
        print("\n❌ 车辆注册失败，终止测试")
        return

    # 测试匹配
    if test_matching():
        # 测试PSI
        if test_psi_code():
            # 测试验证
            test_verification()

    print("\n" + "=" * 60)
    print("测试完成")

if __name__ == "__main__":
    main()