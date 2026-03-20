"""
无人驾驶拼车系统 API 测试
基于 PSI 隐私保护的共享出行系统测试用例
"""

import requests
import hashlib

BASE_URL = "http://localhost:5000"


class TestPSIRideSharing:
    """PSI 拼车系统测试套件"""

    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.test_counter = 0
        # 测试开始前重置数据
        self.session.post(f"{BASE_URL}/reset")

    def log_test(self, name, passed, message=""):
        """记录测试结果"""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = f"{status} - {name}"
        if message:
            result += f": {message}"
        print(result)
        self.test_results.append((name, passed, message))
        return passed

    def get_unique_id(self, prefix):
        """生成唯一测试ID"""
        self.test_counter += 1
        return f"{prefix}_{self.test_counter}"

    def setup_vehicle_and_passenger(self):
        """设置测试数据：返回车辆ID和乘客ID"""
        self.session.post(f"{BASE_URL}/reset")  # 每次测试前重置
        v_id = self.get_unique_id("V_TEST")
        p_id = self.get_unique_id("P_TEST")

        self.session.post(
            f"{BASE_URL}/vehicle/register",
            json={"vehicle_id": v_id, "start": "北京中关村", "end": "北京西站", "seats": 4}
        )
        self.session.post(
            f"{BASE_URL}/passenger/register",
            json={"passenger_id": p_id, "start": "北京中关村", "end": "北京西站"}
        )
        return v_id, p_id

    def test_01_homepage(self):
        """测试1：首页访问"""
        try:
            r = self.session.get(BASE_URL)
            passed = r.status_code == 200 and "无人驾驶拼车系统" in r.text
            return self.log_test("首页访问", passed)
        except Exception as e:
            return self.log_test("首页访问", False, str(e))

    def test_02_pages_access(self):
        """测试2：所有页面访问"""
        try:
            pages = ["/passenger", "/vehicle", "/verify"]
            passed = all(
                self.session.get(f"{BASE_URL}{p}").status_code == 200
                for p in pages
            )
            return self.log_test("所有页面访问", passed)
        except Exception as e:
            return self.log_test("所有页面访问", False, str(e))

    def test_03_vehicle_register(self):
        """测试3：车辆注册"""
        try:
            v_id = self.get_unique_id("V_REG")
            r = self.session.post(
                f"{BASE_URL}/vehicle/register",
                json={"vehicle_id": v_id, "start": "北京中关村", "end": "北京西站", "seats": 4}
            )
            data = r.json()
            passed = r.status_code == 200 and data.get("vehicle", {}).get("id") == v_id
            return self.log_test("车辆注册", passed)
        except Exception as e:
            return self.log_test("车辆注册", False, str(e))

    def test_04_passenger_register(self):
        """测试4：乘客注册"""
        try:
            p_id = self.get_unique_id("P_REG")
            r = self.session.post(
                f"{BASE_URL}/passenger/register",
                json={"passenger_id": p_id, "start": "北京中关村", "end": "北京西站"}
            )
            data = r.json()
            passed = r.status_code == 200 and data.get("passenger", {}).get("id") == p_id
            return self.log_test("乘客注册", passed)
        except Exception as e:
            return self.log_test("乘客注册", False, str(e))

    def test_05_match_same_area(self):
        """测试5：同区域匹配成功"""
        try:
            v_id, p_id = self.setup_vehicle_and_passenger()

            r = self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p_id}
            )
            data = r.json()
            passed = r.status_code == 200 and data.get("success") == True and data.get("match_code")
            return self.log_test("同区域匹配成功", passed)
        except Exception as e:
            return self.log_test("同区域匹配成功", False, str(e))

    def test_06_match_cross_area(self):
        """测试6：跨区域匹配失败"""
        try:
            self.session.post(f"{BASE_URL}/reset")
            # 先注册车辆
            v_id = self.get_unique_id("V_CROSS")
            self.session.post(
                f"{BASE_URL}/vehicle/register",
                json={"vehicle_id": v_id, "start": "北京中关村", "end": "北京西站", "seats": 4}
            )
            # 注册跨区域乘客
            p_id = self.get_unique_id("P_CROSS")
            self.session.post(
                f"{BASE_URL}/passenger/register",
                json={"passenger_id": p_id, "start": "上海浦东", "end": "上海虹桥"}
            )
            r = self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p_id}
            )
            data = r.json()
            passed = r.status_code == 200 and data.get("success") == False
            return self.log_test("跨区域匹配失败", passed)
        except Exception as e:
            return self.log_test("跨区域匹配失败", False, str(e))

    def test_07_vehicle_check(self):
        """测试7：查看车辆乘客列表"""
        try:
            v_id, p_id = self.setup_vehicle_and_passenger()
            # 执行匹配
            self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p_id}
            )

            r = self.session.get(f"{BASE_URL}/vehicle/check?vehicle_id={v_id}")
            data = r.json()
            passengers = data.get("matched_passengers", [])
            passed = r.status_code == 200 and len(passengers) > 0 and passengers[0]["id"] == p_id
            return self.log_test("查看乘客列表", passed)
        except Exception as e:
            return self.log_test("查看乘客列表", False, str(e))

    def test_08_verify_code_correct(self):
        """测试8：正确验证码"""
        try:
            v_id, p_id = self.setup_vehicle_and_passenger()
            # 获取验证码
            r = self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p_id}
            )
            match_data = r.json()
            code = match_data.get("match_code")

            # 验证
            r = self.session.post(
                f"{BASE_URL}/verify",
                json={"passenger_id": p_id, "vehicle_id": v_id, "code": code}
            )
            data = r.json()
            passed = r.status_code == 200 and data.get("success") == True
            return self.log_test("验证码正确", passed)
        except Exception as e:
            return self.log_test("验证码正确", False, str(e))

    def test_09_verify_code_wrong(self):
        """测试9：错误验证码"""
        try:
            v_id, p_id = self.setup_vehicle_and_passenger()
            self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p_id}
            )

            r = self.session.post(
                f"{BASE_URL}/verify",
                json={"passenger_id": p_id, "vehicle_id": v_id, "code": "WRONG"}
            )
            data = r.json()
            passed = r.status_code == 200 and data.get("success") == False
            return self.log_test("验证码错误", passed)
        except Exception as e:
            return self.log_test("验证码错误", False, str(e))

    def test_10_cancel_match(self):
        """测试10：取消匹配"""
        try:
            v_id, p_id = self.setup_vehicle_and_passenger()
            # 执行匹配
            self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p_id}
            )

            r = self.session.post(
                f"{BASE_URL}/cancel",
                json={"passenger_id": p_id}
            )
            data = r.json()
            passed = r.status_code == 200 and data.get("success") == True
            return self.log_test("取消匹配", passed)
        except Exception as e:
            return self.log_test("取消匹配", False, str(e))

    def test_11_seats_full(self):
        """测试11：座位满载场景"""
        try:
            self.session.post(f"{BASE_URL}/reset")
            v_id = self.get_unique_id("V_FULL")
            # 注册只有1个座位的车辆
            self.session.post(
                f"{BASE_URL}/vehicle/register",
                json={"vehicle_id": v_id, "start": "北京中关村", "end": "北京西站", "seats": 1}
            )
            # 第一个乘客
            p1 = self.get_unique_id("P_FULL")
            self.session.post(
                f"{BASE_URL}/passenger/register",
                json={"passenger_id": p1, "start": "北京中关村", "end": "北京西站"}
            )
            r1 = self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p1}
            )
            # 第二个乘客
            p2 = self.get_unique_id("P_FULL")
            self.session.post(
                f"{BASE_URL}/passenger/register",
                json={"passenger_id": p2, "start": "北京中关村", "end": "北京西站"}
            )
            r2 = self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p2}
            )
            # 第一个成功，第二个失败
            passed = r1.json().get("success") == True and r2.json().get("success") == False
            return self.log_test("座位满载", passed)
        except Exception as e:
            return self.log_test("座位满载", False, str(e))

    def test_12_error_handling(self):
        """测试12：错误处理"""
        try:
            # 乘客未注册
            r1 = self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": "P_NOT_EXISTS_12345"}
            )
            # 车辆未注册
            r2 = self.session.get(f"{BASE_URL}/vehicle/check?vehicle_id=V_NOT_EXISTS_12345")

            passed = r1.status_code == 404 and r2.status_code == 404
            return self.log_test("错误处理(404)", passed)
        except Exception as e:
            return self.log_test("错误处理(404)", False, str(e))

    def test_13_psi_code_format(self):
        """测试13：PSI验证码格式正确"""
        try:
            v_id, p_id = self.setup_vehicle_and_passenger()

            # 计算预期的验证码
            raw = f"{p_id}{v_id}"
            expected = hashlib.md5(raw.encode()).hexdigest()[:6].upper()

            # 执行匹配获取验证码
            r = self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p_id}
            )
            actual = r.json().get("match_code")

            passed = actual == expected and len(expected) == 6 and expected.isalnum()
            return self.log_test("PSI验证码格式", passed)
        except Exception as e:
            return self.log_test("PSI验证码格式", False, str(e))

    def test_14_multi_match_same_vehicle(self):
        """测试14：同一车辆多乘客匹配"""
        try:
            self.session.post(f"{BASE_URL}/reset")
            v_id = self.get_unique_id("V_MULTI")
            # 注册3座车辆
            self.session.post(
                f"{BASE_URL}/vehicle/register",
                json={"vehicle_id": v_id, "start": "北京中关村", "end": "北京西站", "seats": 3}
            )
            # 三个乘客匹配
            passengers = [
                self.get_unique_id("P_MULTI"),
                self.get_unique_id("P_MULTI"),
                self.get_unique_id("P_MULTI")
            ]
            results = []
            for p_id in passengers:
                self.session.post(
                    f"{BASE_URL}/passenger/register",
                    json={"passenger_id": p_id, "start": "北京中关村", "end": "北京西站"}
                )
                r = self.session.post(
                    f"{BASE_URL}/match",
                    json={"passenger_id": p_id}
                )
                results.append(r.json().get("success", False))

            passed = all(results)
            return self.log_test("同一车辆多乘客匹配", passed)
        except Exception as e:
            return self.log_test("同一车辆多乘客匹配", False, str(e))

    def test_15_code_uniqueness(self):
        """测试15：不同组合生成不同验证码"""
        try:
            self.session.post(f"{BASE_URL}/reset")
            v1, p1 = self.setup_vehicle_and_passenger()
            # reset 后再注册第二组
            self.session.post(f"{BASE_URL}/reset")
            v2, p2 = self.setup_vehicle_and_passenger()

            r1 = self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p1}
            )
            r2 = self.session.post(
                f"{BASE_URL}/match",
                json={"passenger_id": p2}
            )

            code1 = r1.json().get("match_code")
            code2 = r2.json().get("match_code")

            passed = code1 != code2
            return self.log_test("不同组合不同验证码", passed)
        except Exception as e:
            return self.log_test("不同组合不同验证码", False, str(e))

    def run_all(self):
        """运行所有测试"""
        print("=" * 60)
        print("无人驾驶拼车系统 API 测试")
        print("基于 PSI 隐私保护的共享出行系统")
        print("=" * 60)
        print()

        tests = [
            self.test_01_homepage,
            self.test_02_pages_access,
            self.test_03_vehicle_register,
            self.test_04_passenger_register,
            self.test_05_match_same_area,
            self.test_06_match_cross_area,
            self.test_07_vehicle_check,
            self.test_08_verify_code_correct,
            self.test_09_verify_code_wrong,
            self.test_10_cancel_match,
            self.test_11_seats_full,
            self.test_12_error_handling,
            self.test_13_psi_code_format,
            self.test_14_multi_match_same_vehicle,
            self.test_15_code_uniqueness,
        ]

        for test in tests:
            test()

        print()
        print("=" * 60)
        total = len(self.test_results)
        passed = sum(1 for _, p, _ in self.test_results if p)
        failed = total - passed
        print(f"测试完成: {passed}/{total} 通过")
        if failed > 0:
            print(f"失败: {failed}")
            print()
            print("失败的测试:")
            for name, p, msg in self.test_results:
                if not p:
                    print(f"  - {name}: {msg}")
        print("=" * 60)


if __name__ == "__main__":
    tester = TestPSIRideSharing()
    tester.run_all()
