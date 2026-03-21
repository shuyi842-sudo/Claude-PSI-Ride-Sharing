"""
PSI无人驾驶拼车系统演示脚本
展示系统的完整流程
"""

import requests
import time
import hashlib


class Demo:
    """系统演示"""

    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()

    def print_section(self, title):
        """打印章节标题"""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print('='*60)

    def print_result(self, label, data):
        """打印结果"""
        print(f"\n{label}:")
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"  {k}: {v}")
        else:
            print(f"  {data}")

    def reset_system(self):
        """重置系统"""
        self.print_section("1. 重置系统")
        response = self.session.post(f"{self.base_url}/reset")
        print(f"✓ 系统已重置")

    def register_vehicles(self):
        """注册车辆"""
        self.print_section("2. 注册车辆")

        vehicles = [
            {"id": "V001", "start": "北京中关村", "end": "北京西站", "seats": 4},
            {"id": "V002", "start": "上海浦东", "end": "上海虹桥", "seats": 2},
            {"id": "V003", "start": "广州天河", "end": "广州白云", "seats": 3},
        ]

        for v in vehicles:
            response = self.session.post(
                f"{self.base_url}/vehicle/register",
                json={"vehicle_id": v["id"], "start": v["start"], "end": v["end"], "seats": v["seats"]}
            )
            self.print_result(f"注册车辆 {v['id']}", response.json())

    def register_passengers(self):
        """注册乘客"""
        self.print_section("3. 注册乘客")

        passengers = [
            {"id": "P001", "start": "北京中关村", "end": "北京西站"},
            {"id": "P002", "start": "北京中关村", "end": "北京西站"},
            {"id": "P003", "start": "上海浦东", "end": "上海虹桥"},
        ]

        for p in passengers:
            response = self.session.post(
                f"{self.base_url}/passenger/register",
                json={"passenger_id": p["id"], "start": p["start"], "end": p["end"]}
            )
            self.print_result(f"注册乘客 {p['id']}", response.json())

    def match_passengers(self):
        """乘客匹配"""
        self.print_section("4. 乘客请求匹配")

        passengers = ["P001", "P002", "P003"]
        results = {}

        for p_id in passengers:
            response = self.session.post(
                f"{self.base_url}/match",
                json={"passenger_id": p_id}
            )
            data = response.json()
            results[p_id] = data

            if data.get("success"):
                print(f"\n✓ 乘客 {p_id} 匹配成功！")
                print(f"  匹配车辆: {data['vehicle']['id']}")
                print(f"  验证码: {data['match_code']}")
            else:
                print(f"\n✗ 乘客 {p_id} 匹配失败: {data.get('message')}")

        return results

    def check_vehicle_passengers(self):
        """车辆查看乘客"""
        self.print_section("5. 车辆查看匹配乘客")

        vehicle_id = "V001"
        response = self.session.get(f"{self.base_url}/vehicle/check", params={"vehicle_id": vehicle_id})
        data = response.json()

        print(f"\n车辆 {vehicle_id} 的匹配乘客:")
        print(f"  路线: {data['vehicle']['start']} → {data['vehicle']['end']}")
        print(f"  剩余座位: {data['vehicle']['seats']}")
        print(f"  匹配乘客数: {len(data['matched_passengers'])}")

        for p in data['matched_passengers']:
            print(f"    - {p['id']}: {p['start']} → {p['end']} ({p['status']})")

    def verify_boarding(self, match_results):
        """上车验证"""
        self.print_section("6. 上车验证")

        # 模拟乘客P001上车验证
        p_id = "P001"
        v_id = "V001"
        match_data = match_results.get(p_id, {})
        code = match_data.get("match_code")

        print(f"\n乘客 {p_id} 在车辆 {v_id} 处验证上车...")
        print(f"  验证码: {code}")

        response = self.session.post(
            f"{self.base_url}/verify",
            json={"passenger_id": p_id, "vehicle_id": v_id, "code": code}
        )
        data = response.json()

        if data.get("success"):
            print(f"  ✓ 验证成功！乘客 {p_id} 可以上车")
        else:
            print(f"  ✗ 验证失败: {data.get('message')}")

        # 测试错误验证码
        print(f"\n测试错误验证码...")
        response = self.session.post(
            f"{self.base_url}/verify",
            json={"passenger_id": p_id, "vehicle_id": v_id, "code": "WRONG"}
        )
        data = response.json()
        print(f"  ✗ 验证失败（预期）: {data.get('message')}")

    def switch_psi_mode(self):
        """切换PSI模式"""
        self.print_section("7. PSI模式切换")

        modes = ["hash", "ecc", "multi", "threshold"]
        mode_names = {
            "hash": "MD5哈希（兼容）",
            "ecc": "ECC双方PSI",
            "multi": "ECC多方PSI",
            "threshold": "门限PSI"
        }

        current_mode = self.session.get(f"{self.base_url}/psi/config").json().get("current_mode")
        print(f"当前PSI模式: {mode_names.get(current_mode, current_mode)}")

        for mode in modes:
            if mode == current_mode:
                continue
            print(f"\n切换到 {mode_names[mode]}...")
            response = self.session.post(
                f"{self.base_url}/psi/config",
                json={"mode": mode}
            )
            data = response.json()
            print(f"  {data.get('message')}")
            time.sleep(0.5)

        # 切换回默认模式
        self.session.post(
            f"{self.base_url}/psi/config",
            json={"mode": "hash"}
        )

    def get_system_stats(self):
        """获取系统统计"""
        self.print_section("8. 系统统计")

        response = self.session.get(f"{self.base_url}/admin/stats")
        data = response.json()

        print("\n📊 系统统计:")
        print(f"  总乘客数: {data['total_passengers']}")
        print(f"  已匹配乘客: {data['matched_passengers']}")
        print(f"  等待中乘客: {data['waiting_passengers']}")
        print(f"  总车辆数: {data['total_vehicles']}")
        print(f"  可用车辆: {data['available_vehicles']}")
        print(f"  满载车辆: {data['full_vehicles']}")
        print(f"  总匹配数: {data['total_matches']}")
        print(f"  PSI模式: {data['psi_mode']}")

    def run(self):
        """运行完整演示"""
        self.print_section("PSI无人驾驶拼车系统演示")
        print("基于隐私集合求交(PSI)技术的安全拼车系统")
        print("支持MP-TPSI多方门限协议")

        try:
            self.reset_system()
            time.sleep(0.5)

            self.register_vehicles()
            time.sleep(0.5)

            self.register_passengers()
            time.sleep(0.5)

            match_results = self.match_passengers()
            time.sleep(0.5)

            self.check_vehicle_passengers()
            time.sleep(0.5)

            self.verify_boarding(match_results)
            time.sleep(0.5)

            self.switch_psi_mode()
            time.sleep(0.5)

            self.get_system_stats()

            self.print_section("演示完成")
            print("所有功能演示完毕！")
            print("\n访问 Web 界面:")
            print("  - 首页: http://localhost:5000/")
            print("  - 乘客端: http://localhost:5000/passenger")
            print("  - 车辆端: http://localhost:5000/vehicle")
            print("  - 验证页面: http://localhost:5000/verify")
            print("  - 管理后台: http://localhost:5000/admin")

        except Exception as e:
            print(f"\n演示过程中出错: {e}")
            print("请确保服务器正在运行: python app.py")


def main():
    """主函数"""
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    print(f"连接到服务器: {url}")

    demo = Demo(url)
    demo.run()


if __name__ == "__main__":
    main()
