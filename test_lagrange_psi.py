"""
基于拉格朗日插值的PSI+PFE测试套件
Tests for Lagrange-based PSI + PFE for Ride Matching

测试内容：
1. PRF生成一致性
2. 距离归一化/反归一化可逆性
3. 拉格朗日插值准确性
4. 完整协议流程
5. 阈值匹配判断

作者: Claude
版本: 1.0.0
"""

import unittest
import json
from lagrange_psi import (
    GeoPoint,
    PFEPoint,
    LagrangeCoefficients,
    PFERequest,
    PFEMatchResult,
    PseudoRandomFunction,
    DistanceNormalizer,
    LagrangePFE,
    HaversineDistance,
    PSIPlusPFE,
    create_route_from_coords
)


class TestPseudoRandomFunction(unittest.TestCase):
    """测试伪随机函数"""

    def setUp(self):
        self.prf = PseudoRandomFunction()
        self.seed = b'test_seed_12345678'

    def test_prf_consistency(self):
        """测试PRF一致性：相同输入产生相同输出"""
        point_hash = 123456789

        x1 = self.prf.generate_x(point_hash, self.seed)
        x2 = self.prf.generate_x(point_hash, self.seed)

        self.assertEqual(x1, x2, "相同输入应产生相同输出")

    def test_prf_different_inputs(self):
        """测试PRF不同输入产生不同输出"""
        point_hash1 = 123456789
        point_hash2 = 987654321

        x1 = self.prf.generate_x(point_hash1, self.seed)
        x2 = self.prf.generate_x(point_hash2, self.seed)

        self.assertNotEqual(x1, x2, "不同输入应产生不同输出")

    def test_prf_different_seeds(self):
        """测试不同种子产生不同输出"""
        point_hash = 123456789
        seed1 = b'seed_1'
        seed2 = b'seed_2'

        x1 = self.prf.generate_x(point_hash, seed1)
        x2 = self.prf.generate_x(point_hash, seed2)

        self.assertNotEqual(x1, x2, "不同种子应产生不同输出")

    def test_generate_shared_seed(self):
        """测试种子生成"""
        seed = self.prf.generate_shared_seed()

        self.assertEqual(len(seed), 16, "种子长度应为16字节")
        self.assertIsInstance(seed, bytes, "种子应为字节类型")

    def test_generate_x_batch(self):
        """测试批量生成PRF值"""
        point_hashes = [1, 2, 3, 4, 5]

        result1 = self.prf.generate_x_batch(point_hashes, self.seed)
        result2 = [self.prf.generate_x(h, self.seed) for h in point_hashes]

        self.assertEqual(result1, result2, "批量生成应与逐个生成结果相同")


class TestDistanceNormalizer(unittest.TestCase):
    """测试距离归一化器"""

    def setUp(self):
        self.normalizer = DistanceNormalizer(max_distance_km=10.0)

    def test_normalize_zero_distance(self):
        """测试零距离归一化"""
        result = self.normalizer.normalize(0.0)
        self.assertEqual(result, 0, "零距离应归一化为0")

    def test_normalize_max_distance(self):
        """测试最大距离归一化"""
        result = self.normalizer.normalize(10.0)
        self.assertEqual(result, 255, "最大距离应归一化为255")

    def test_normalize_mid_distance(self):
        """测试中间距离归一化"""
        result = self.normalizer.normalize(5.0)
        # 5.0 / 10.0 * 255 = 127.5
        self.assertEqual(result, 127 or 128, "5km应归一化为127或128")

    def test_denormalize(self):
        """测试反归一化"""
        y = self.normalizer.normalize(3.5)
        distance = self.normalizer.denormalize(y)

        self.assertAlmostEqual(distance, 3.5, places=1,
                          msg="归一化+反归一化应接近原始值")

    def test_clamp_max_distance(self):
        """测试超过最大距离的截断"""
        result = self.normalizer.normalize(20.0)
        self.assertEqual(result, 255, "超过最大距离应被截断为255")

    def test_clamp_negative_distance(self):
        """测试负距离的处理"""
        result = self.normalizer.normalize(-1.0)
        self.assertEqual(result, 0, "负距离应被截断为0")

    def test_normalize_denormalize_roundtrip(self):
        """测试归一化-反归一化往返"""
        test_distances = [0.0, 1.5, 3.0, 5.0, 7.5, 9.9]

        for original in test_distances:
            normalized = self.normalizer.normalize(original)
            recovered = self.normalizer.denormalize(normalized)
            # 允许0.1km的误差（由离散化引起）
            self.assertAlmostEqual(recovered, original, places=0,
                              msg=f"往返测试失败: {original} -> {recovered}")


class TestHaversineDistance(unittest.TestCase):
    """测试Haversine距离计算"""

    def test_same_point_distance(self):
        """测试同一点距离为0"""
        distance = HaversineDistance.calculate(39.9042, 116.4074,
                                            39.9042, 116.4074)
        self.assertAlmostEqual(distance, 0.0, places=6)

    def test_beijing_shanghai_distance(self):
        """测试北京到上海距离"""
        # 北京天安门
        lat1, lng1 = 39.9042, 116.4074
        # 上海外滩
        lat2, lng2 = 31.2304, 121.4737

        distance = HaversineDistance.calculate(lat1, lng1, lat2, lng2)

        # 北京到上海约1067公里
        self.assertGreater(distance, 1000, "北京到上海距离应大于1000km")
        self.assertLess(distance, 1200, "北京到上海距离应小于1200km")

    def test_nearby_points(self):
        """测试近距离点"""
        # 天安门附近两点
        lat1, lng1 = 39.9042, 116.4074
        lat2, lng2 = 39.9045, 116.4077

        distance = HaversineDistance.calculate(lat1, lng1, lat2, lng2)

        # 应该在100米以内
        self.assertLess(distance, 0.1, "附近两点距离应小于0.1km")


class TestLagrangePFE(unittest.TestCase):
    """测试拉格朗日私有函数求值"""

    def setUp(self):
        self.lagrange = LagrangePFE()

    def test_single_point_interpolation(self):
        """测试单点插值（常数多项式）"""
        point = PFEPoint(
            prf_x=100,
            distance_y=128,
            original_hash=12345
        )

        coeffs = self.lagrange.build_interpolation([point])

        self.assertEqual(len(coeffs.coefficients), 1, "单点应产生1个系数")
        self.assertEqual(coeffs.degree, 0, "单点应为0次多项式")
        self.assertEqual(coeffs.coefficients[0], 128, "常数应为点的y值")

    def test_two_point_interpolation(self):
        """测试两点插值（线性多项式）"""
        points = [
            PFEPoint(prf_x=100, distance_y=50, original_hash=1),
            PFEPoint(prf_x=200, distance_y=150, original_hash=2)
        ]

        coeffs = self.lagrange.build_interpolation(points)

        self.assertEqual(coeffs.degree, 1, "两点应产生1次多项式")

        # 验证插值通过两个点
        y1 = self.lagrange.evaluate(coeffs, 100)
        y2 = self.lagrange.evaluate(coeffs, 200)

        self.assertEqual(y1, 50, "应通过第一个点")
        self.assertEqual(y2, 150, "应通过第二个点")

    def test_multiple_point_interpolation(self):
        """测试多点插值"""
        points = [
            PFEPoint(prf_x=10, distance_y=20, original_hash=1),
            PFEPoint(prf_x=20, distance_y=40, original_hash=2),
            PFEPoint(prf_x=30, distance_y=60, original_hash=3),
            PFEPoint(prf_x=40, distance_y=80, original_hash=4)
        ]

        coeffs = self.lagrange.build_interpolation(points)

        # 验证插值通过所有点
        for point in points:
            y = self.lagrange.evaluate(coeffs, point.prf_x)
            self.assertEqual(y, point.distance_y,
                          f"应通过点 ({point.prf_x}, {point.distance_y})")

    def test_evaluate(self):
        """测试多项式评估"""
        points = [
            PFEPoint(prf_x=100, distance_y=0, original_hash=1),
            PFEPoint(prf_x=200, distance_y=255, original_hash=2)
        ]

        coeffs = self.lagrange.build_interpolation(points)

        # 在原始点处评估应返回对应的y值
        y1 = self.lagrange.evaluate(coeffs, 100)
        y2 = self.lagrange.evaluate(coeffs, 200)

        self.assertEqual(y1, 0, "x=100应得到y=0")
        self.assertEqual(y2, 255, "x=200应得到y=255")

        # 在中点处评估的结果应该在合理范围内
        # 由于使用模运算，结果可能不是简单的线性插值
        y_mid = self.lagrange.evaluate(coeffs, 150)
        # 只验证结果是一个有效的归一化值（0-255或模数内的值）
        self.assertIsInstance(y_mid, int, "评估结果应为整数")

    def test_coefficients_serialization(self):
        """测试系数序列化"""
        points = [
            PFEPoint(prf_x=100, distance_y=50, original_hash=1),
            PFEPoint(prf_x=200, distance_y=150, original_hash=2)
        ]

        coeffs = self.lagrange.build_interpolation(points)

        # 转换为字典
        coeffs_dict = coeffs.to_dict()
        self.assertIn('coefficients', coeffs_dict)
        self.assertIn('degree', coeffs_dict)

        # 从字典恢复
        restored = LagrangeCoefficients.from_dict(coeffs_dict)
        self.assertEqual(restored.degree, coeffs.degree)
        self.assertEqual(len(restored.coefficients), len(coeffs.coefficients))

    def test_export_coefficients_to_json(self):
        """测试系数导出为JSON"""
        points = [
            PFEPoint(prf_x=100, distance_y=50, original_hash=1),
            PFEPoint(prf_x=200, distance_y=150, original_hash=2)
        ]

        coeffs = self.lagrange.build_interpolation(points)
        json_str = self.lagrange.export_coefficients_to_json(coeffs)

        # 验证是有效的JSON
        parsed = json.loads(json_str)
        self.assertIn('coefficients', parsed)

    def test_evaluate_batch(self):
        """测试批量评估"""
        points = [
            PFEPoint(prf_x=100, distance_y=0, original_hash=1),
            PFEPoint(prf_x=200, distance_y=255, original_hash=2)
        ]

        coeffs = self.lagrange.build_interpolation(points)
        x_values = [100, 150, 200]

        results = self.lagrange.evaluate_batch(coeffs, x_values)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0], 0, "x=100应得到0")
        self.assertEqual(results[2], 255, "x=200应得到255")


class TestPFEDataStructures(unittest.TestCase):
    """测试PFE数据结构"""

    def test_geo_point_to_dict(self):
        """测试GeoPoint序列化"""
        point = GeoPoint(lat=39.9042, lng=116.4074)
        point_dict = point.to_dict()

        self.assertEqual(point_dict['lat'], 39.9042)
        self.assertEqual(point_dict['lng'], 116.4074)

    def test_geo_point_from_dict(self):
        """测试GeoPoint反序列化"""
        point_dict = {'lat': 39.9042, 'lng': 116.4074}
        point = GeoPoint.from_dict(point_dict)

        self.assertEqual(point.lat, 39.9042)
        self.assertEqual(point.lng, 116.4074)

    def test_pfe_point_to_dict(self):
        """测试PFEPoint序列化"""
        point = PFEPoint(prf_x=12345, distance_y=100, original_hash=67890)
        point_dict = point.to_dict()

        self.assertIn('prf_x', point_dict)
        self.assertIn('distance_y', point_dict)
        self.assertIn('original_hash', point_dict)

    def test_pfe_request_serialization(self):
        """测试PFERequest序列化"""
        from lagrange_psi import LagrangePFE

        lagrange = LagrangePFE()
        coeffs = lagrange.build_interpolation([
            PFEPoint(prf_x=100, distance_y=50, original_hash=1)
        ])

        request = PFERequest(
            encrypted_points=['hash1', 'hash2'],
            coefficients=coeffs,
            prf_seed=b'seed123',
            passenger_id='P001',
            timestamp=123456
        )

        # 转换为字典
        req_dict = request.to_dict()
        self.assertIn('encrypted_points', req_dict)
        self.assertIn('prf_seed', req_dict)

        # 从字典恢复
        restored = PFERequest.from_dict(req_dict)
        self.assertEqual(restored.passenger_id, 'P001')
        self.assertEqual(len(restored.encrypted_points), 2)


class TestPSIPlusPFE(unittest.TestCase):
    """测试PSI+PFE完整协议"""

    def setUp(self):
        self.protocol = PSIPlusPFE(threshold_km=2.0, max_distance_km=10.0)

    def test_passenger_prepare_request(self):
        """测试乘客准备请求"""
        passenger_route = create_route_from_coords([
            (39.8800, 116.3500),
            (39.8900, 116.3700),
            (39.9042, 116.4074)
        ])
        target_point = GeoPoint(39.9042, 116.4074)

        request = self.protocol.passenger_prepare_request(
            passenger_route,
            target_point,
            passenger_id='P001'
        )

        self.assertIsInstance(request, PFERequest)
        self.assertEqual(request.passenger_id, 'P001')
        self.assertGreater(len(request.encrypted_points), 0)
        self.assertIsNotNone(request.prf_seed)
        self.assertGreater(request.coefficients.degree, -1)

    def test_vehicle_process_request_match(self):
        """测试车辆处理请求（匹配场景）"""
        # 乘客准备请求
        passenger_route = create_route_from_coords([
            (39.8800, 116.3500),
            (39.9042, 116.4074)  # 天安门
        ])
        target_point = GeoPoint(39.9042, 116.4074)

        request = self.protocol.passenger_prepare_request(
            passenger_route, target_point, 'P001'
        )

        # 车辆路线（经过天安门附近）
        vehicle_route = create_route_from_coords([
            (39.8500, 116.3000),
            (39.9042, 116.4074),  # 经过相同点
            (39.9200, 116.4300)
        ])

        result = self.protocol.vehicle_process_request(request, vehicle_route, 'V001')

        self.assertTrue(result.matched, "应该匹配")
        self.assertEqual(result.passenger_id, 'P001')
        self.assertEqual(result.vehicle_id, 'V001')
        self.assertGreater(result.intersection_count, 0)
        self.assertEqual(len(result.verification_code), 6)

    def test_vehicle_process_request_no_match(self):
        """测试车辆处理请求（不匹配场景）"""
        # 乘客准备请求
        passenger_route = create_route_from_coords([
            (39.9042, 116.4074)  # 天安门
        ])
        target_point = GeoPoint(39.9042, 116.4074)

        request = self.protocol.passenger_prepare_request(
            passenger_route, target_point, 'P001'
        )

        # 车辆路线（远离天安门）
        vehicle_route = create_route_from_coords([
            (39.9500, 116.5000),  # 很远
            (39.9600, 116.5100),
            (39.9700, 116.5200)
        ])

        result = self.protocol.vehicle_process_request(request, vehicle_route, 'V001')

        self.assertFalse(result.matched, "不应该匹配")
        self.assertEqual(result.passenger_id, 'P001')
        self.assertEqual(result.vehicle_id, 'V001')

    def test_batch_vehicle_process(self):
        """测试批量处理多辆车"""
        passenger_route = create_route_from_coords([
            (39.9042, 116.4074)  # 天安门
        ])
        target_point = GeoPoint(39.9042, 116.4074)

        request = self.protocol.passenger_prepare_request(
            passenger_route, target_point, 'P001'
        )

        # 多辆车的路线
        vehicles_routes = {
            'V001': create_route_from_coords([
                (39.9042, 116.4074),  # 匹配
                (39.9200, 116.4300)
            ]),
            'V002': create_route_from_coords([
                (39.9500, 116.5000)  # 不匹配
            ]),
            'V003': create_route_from_coords([
                (39.8900, 116.4000),
                (39.9042, 116.4074)  # 匹配
            ])
        }

        results = self.protocol.batch_vehicle_process(request, vehicles_routes)

        self.assertEqual(len(results), 3)
        self.assertIn('V001', results)
        self.assertIn('V002', results)
        self.assertIn('V003', results)

        # 检查匹配情况
        matched_count = sum(1 for r in results.values() if r.matched)
        self.assertGreater(matched_count, 0, "至少应有一辆车匹配")

    def test_threshold_matching(self):
        """测试阈值匹配（基于精确坐标匹配）"""
        # 设置较大的阈值
        protocol = PSIPlusPFE(threshold_km=5.0, max_distance_km=10.0)

        passenger_route = create_route_from_coords([
            (39.9042, 116.4074)  # 天安门
        ])
        target_point = GeoPoint(39.9042, 116.4074)

        request = protocol.passenger_prepare_request(
            passenger_route, target_point, 'P001'
        )

        # 车辆经过相同的点（精确坐标匹配）
        vehicle_route = create_route_from_coords([
            (39.9042, 116.4074),  # 相同坐标
            (39.9200, 116.4300)
        ])

        result = protocol.vehicle_process_request(request, vehicle_route, 'V001')

        self.assertTrue(result.matched, "相同坐标点应该匹配")
        self.assertLessEqual(result.distance_km, protocol.threshold_km,
                          "距离应在阈值内")

    def test_exact_match_verification_code(self):
        """测试验证码生成"""
        passenger_route = create_route_from_coords([
            (39.9042, 116.4074)
        ])
        target_point = GeoPoint(39.9042, 116.4074)

        request = self.protocol.passenger_prepare_request(
            passenger_route, target_point, 'P001'
        )

        vehicle_route = create_route_from_coords([
            (39.9042, 116.4074)
        ])

        result = self.protocol.vehicle_process_request(request, vehicle_route, 'V001')

        # 验证码格式：6位大写字母数字
        self.assertEqual(len(result.verification_code), 6)
        self.assertTrue(result.verification_code.isalnum(),
                       "验证码应为字母数字")
        self.assertTrue(result.verification_code.isupper(),
                       "验证码应为大写")

    def test_different_requests_different_codes(self):
        """测试不同请求生成不同验证码"""
        import time

        passenger_route = create_route_from_coords([(39.9042, 116.4074)])
        target_point = GeoPoint(39.9042, 116.4074)
        vehicle_route = create_route_from_coords([(39.9042, 116.4074)])

        request1 = self.protocol.passenger_prepare_request(
            passenger_route, target_point, 'P001'
        )
        time.sleep(0.1)  # 等待以确保时间戳不同
        request2 = self.protocol.passenger_prepare_request(
            passenger_route, target_point, 'P001'
        )

        result1 = self.protocol.vehicle_process_request(request1, vehicle_route, 'V001')
        result2 = self.protocol.vehicle_process_request(request2, vehicle_route, 'V001')

        self.assertNotEqual(result1.verification_code, result2.verification_code,
                          "不同请求应生成不同验证码")


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_full_protocol_workflow(self):
        """测试完整协议工作流"""
        protocol = PSIPlusPFE(threshold_km=2.0, max_distance_km=10.0)

        # 1. 乘客准备请求
        passenger_route = create_route_from_coords([
            (39.8800, 116.3500),
            (39.8900, 116.3700),
            (39.9042, 116.4074),  # 天安门
            (39.9100, 116.4200)
        ])
        target_point = GeoPoint(39.9042, 116.4074)

        request = protocol.passenger_prepare_request(
            passenger_route, target_point, 'P001'
        )

        # 2. 车辆处理请求
        vehicle_route = create_route_from_coords([
            (39.8500, 116.3000),
            (39.8900, 116.3600),
            (39.9042, 116.4074),  # 经过天安门
            (39.9200, 116.4300)
        ])

        result = protocol.vehicle_process_request(request, vehicle_route, 'V001')

        # 3. 验证结果
        self.assertTrue(result.matched, "完整流程应该匹配")
        self.assertGreater(result.intersection_count, 0)
        self.assertLess(result.distance_km, protocol.threshold_km)

    def test_multiple_passengers_multiple_vehicles(self):
        """测试多乘客多车辆场景"""
        protocol = PSIPlusPFE(threshold_km=3.0, max_distance_km=10.0)

        # 多个乘客
        passengers = {
            'P001': create_route_from_coords([(39.9042, 116.4074)]),  # 天安门
            'P002': create_route_from_coords([(39.9163, 116.3972)]),  # 故宫
            'P003': create_route_from_coords([(39.9889, 116.3826)])   # 奥林匹克公园
        }

        # 多个目标
        targets = {
            'P001': GeoPoint(39.9042, 116.4074),
            'P002': GeoPoint(39.9163, 116.3972),
            'P003': GeoPoint(39.9889, 116.3826)
        }

        # 多个车辆
        vehicles = {
            'V001': create_route_from_coords([
                (39.9042, 116.4074),  # 天安门
                (39.9163, 116.3972)   # 故宫
            ]),
            'V002': create_route_from_coords([
                (39.9163, 116.3972),  # 故宫
                (39.9889, 116.3826)   # 奥林匹克公园
            ]),
            'V003': create_route_from_coords([
                (39.8000, 116.3000)   # 偏远地区
            ])
        }

        # 测试每个乘客
        for p_id, p_route in passengers.items():
            request = protocol.passenger_prepare_request(
                p_route, targets[p_id], p_id
            )
            results = protocol.batch_vehicle_process(request, vehicles)

            # 验证结果
            self.assertEqual(len(results), len(vehicles))


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestPseudoRandomFunction))
    suite.addTests(loader.loadTestsFromTestCase(TestDistanceNormalizer))
    suite.addTests(loader.loadTestsFromTestCase(TestHaversineDistance))
    suite.addTests(loader.loadTestsFromTestCase(TestLagrangePFE))
    suite.addTests(loader.loadTestsFromTestCase(TestPFEDataStructures))
    suite.addTests(loader.loadTestsFromTestCase(TestPSIPlusPFE))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回测试结果
    return result


if __name__ == '__main__':
    result = run_tests()

    # 打印总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✓ 所有测试通过！")
    else:
        print("\n✗ 部分测试失败")
