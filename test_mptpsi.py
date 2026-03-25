"""
MP-TPSI 完整测试套件
测试多方门限隐私集合求交协议的所有功能
"""

import sys
import time
from mp_tpsi import (
    GeoPoint,
    Share,
    BlindedPoint,
    PSIMatchResult,
    PSIParticipantRole,
    MathUtils,
    ShamirSecretSharing,
    LocationPSI,
    MPTPSI,
    ThresholdVerifier
)


class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def run_test(self, test_func, test_name):
        """运行单个测试"""
        try:
            test_func()
            self.passed += 1
            self.results.append((test_name, True, None))
            print(f"  ✅ {test_name}")
            return True
        except AssertionError as e:
            self.failed += 1
            self.results.append((test_name, False, str(e)))
            print(f"  ❌ {test_name}: {e}")
            return False
        except Exception as e:
            self.failed += 1
            self.results.append((test_name, False, str(e)))
            print(f"  ⚠️  {test_name}: 异常 - {e}")
            return False

    def summary(self):
        """打印测试总结"""
        total = self.passed + self.failed
        print("\n" + "=" * 60)
        print(f"测试完成: {self.passed}/{total} 通过")
        if self.failed > 0:
            print(f"失败: {self.failed}")
            print("\n失败的测试:")
            for name, passed, msg in self.results:
                if not passed:
                    print(f"  - {name}: {msg}")
        print("=" * 60)
        return self.failed == 0


# ========== 测试用例 ==========

def test_geopoint_hash():
    """测试地理点哈希"""
    point = GeoPoint(39.9042, 116.4074)
    h1 = point.to_int_hash()
    h2 = point.to_int_hash()

    assert h1 == h2, "相同坐标应生成相同哈希"
    assert h1 > 0, "哈希值应为正整数"

    # 不同坐标应有不同哈希
    point2 = GeoPoint(39.9050, 116.4080)
    h3 = point2.to_int_hash()
    assert h1 != h3, "不同坐标应生成不同哈希"


def test_geopoint_grid():
    """测试地理点网格编码"""
    point = GeoPoint(39.9042, 116.4074)
    grid_id = point.to_grid_id(precision=5)

    assert isinstance(grid_id, str), "网格ID应为字符串"
    assert len(grid_id) == 5, f"网格ID长度应为5，实际为{len(grid_id)}"


def test_haversine_distance():
    """测试Haversine距离计算"""
    # 北京天安门到北京西站的距离
    tiananmen = GeoPoint(39.9042, 116.4074)
    beijing_west = GeoPoint(39.9045, 116.3219)

    distance = MathUtils.haversine_distance(
        tiananmen.lat, tiananmen.lng,
        beijing_west.lat, beijing_west.lng
    )

    # 实际距离约8公里
    assert 6.0 < distance < 10.0, f"距离应在6-10公里之间，实际{distance:.2f}公里"

    # 相同点距离应为0
    same_dist = MathUtils.haversine_distance(
        tiananmen.lat, tiananmen.lng,
        tiananmen.lat, tiananmen.lng
    )
    assert abs(same_dist) < 0.001, "相同点距离应接近0"


def test_mod_inverse():
    """测试模逆元计算"""
    a = 12345
    mod = 2**256 - 2**224 + 2**192 + 2**96 - 1

    inv = MathUtils.mod_inverse(a, mod)

    # 验证 a * a^(-1) ≡ 1 (mod mod)
    product = (a * inv) % mod
    assert product == 1, f"模逆元验证失败: {a} * {inv} ≡ {product} (mod {mod})"


def test_shamir_split():
    """测试Shamir秘密分割"""
    shamir = ShamirSecretSharing(threshold=3, total=5)
    secret = 987654321

    shares = shamir.split_secret(secret, "Alice")

    assert len(shares) == 5, f"应生成5个份额，实际{len(shares)}"
    assert all(isinstance(s, Share) for s in shares), "所有份额应为Share类型"

    # 检查份额索引
    indices = [s.index for s in shares]
    assert indices == [1, 2, 3, 4, 5], f"份额索引应为1-5，实际{indices}"


def test_shamir_reconstruct():
    """测试Shamir秘密重构"""
    shamir = ShamirSecretSharing(threshold=3, total=5)
    secret = 123456789

    shares = shamir.split_secret(secret, "Alice")

    # 用threshold个份额重构
    reconstructed = shamir.reconstruct_secret(shares[:shamir.threshold])

    assert reconstructed == secret, f"重构秘密不匹配: {reconstructed} != {secret}"


def test_shamir_different_combinations():
    """测试不同份额组合的重构"""
    shamir = ShamirSecretSharing(threshold=3, total=5)
    secret = 555666777

    shares = shamir.split_secret(secret, "Bob")

    # 测试不同组合
    combinations = [
        shares[0:3],  # 1,2,3
        shares[1:4],  # 2,3,4
        shares[2:5],  # 3,4,5
        [shares[0], shares[2], shares[4]]  # 1,3,5
    ]

    for i, combo in enumerate(combinations):
        reconstructed = shamir.reconstruct_secret(combo)
        assert reconstructed == secret, f"组合{i+1}重构失败: {reconstructed} != {secret}"


def test_shamir_threshold():
    """测试门限机制"""
    shamir = ShamirSecretSharing(threshold=3, total=5)
    secret = 111222333

    shares = shamir.split_secret(secret, "Charlie")

    # 用不足的份额应该失败
    try:
        shamir.reconstruct_secret(shares[:2])
        raise AssertionError("使用不足份额应该抛出异常")
    except ValueError as e:
        assert "至少3" in str(e), f"错误消息应包含'至少3'，实际: {e}"


def test_location_psi_hash():
    """测试LocationPSI哈希"""
    lpsi = LocationPSI()
    point = GeoPoint(40.0, 116.0)

    h1 = lpsi.hash_location(point)
    h2 = lpsi.hash_location(point)

    assert h1 == h2, "相同点应生成相同哈希"
    assert 0 < h1 < MathUtils.PRIME, "哈希值应在素数范围内"


def test_location_psi_route():
    """测试LocationPSI路线哈希"""
    lpsi = LocationPSI()
    route = [
        GeoPoint(39.9, 116.3),
        GeoPoint(39.95, 116.35),
        GeoPoint(40.0, 116.4)
    ]

    hashes = lpsi.hash_route(route)

    assert len(hashes) == 3, f"应生成3个哈希，实际{len(hashes)}"
    assert all(isinstance(h, int) for h in hashes), "所有哈希应为整数"


def test_location_psi_similarity():
    """测试路线相似度计算"""
    lpsi = LocationPSI()

    # 相同路线
    route1 = [GeoPoint(39.9, 116.3), GeoPoint(40.0, 116.4)]
    route2 = [GeoPoint(39.9, 116.3), GeoPoint(40.0, 116.4)]

    similarity = lpsi.compute_route_similarity(route1, route2, threshold_km=0.1)

    assert similarity > 0.9, f"相同路线相似度应>0.9，实际{similarity:.2f}"


def test_location_psi_intersection():
    """测试路线交集查找"""
    lpsi = LocationPSI()

    route1 = [GeoPoint(39.9, 116.3), GeoPoint(40.0, 116.4)]
    route2 = [GeoPoint(40.0, 116.4), GeoPoint(40.1, 116.5)]

    intersections = lpsi.find_route_intersection(route1, route2, threshold_km=0.1)

    assert len(intersections) >= 1, "应找到至少一个交点"
    assert intersections[0][2] <= 0.1, "交点距离应在阈值内"


def test_mptpsi_add_participant():
    """测试MPTPSI添加参与方"""
    mptpsi = MPTPSI(threshold=3, total=5)

    mptpsi.add_participant("P001", PSIParticipantRole.PASSENGER)
    mptpsi.add_participant("V001", PSIParticipantRole.VEHICLE)

    assert "P001" in mptpsi.participants, "P001应被添加"
    assert "V001" in mptpsi.participants, "V001应被添加"
    assert mptpsi.participants["P001"]["role"] == PSIParticipantRole.PASSENGER
    assert mptpsi.participants["V001"]["role"] == PSIParticipantRole.VEHICLE


def test_mptpsi_share_route():
    """测试MPTPSI路线共享"""
    mptpsi = MPTPSI(threshold=3, total=5)
    mptpsi.add_participant("P001", PSIParticipantRole.PASSENGER)

    route = [GeoPoint(39.9, 116.3), GeoPoint(40.0, 116.4)]
    shares = mptpsi.share_route_secret("P001", route)

    assert len(shares) == 5, f"应生成5个份额，实际{len(shares)}"
    assert "P001" in mptpsi.shares, "P001的份额应被存储"


def test_mptpsi_compute_intersection():
    """测试MPTPSI交集计算"""
    mptpsi = MPTPSI(threshold=3, total=5)
    mptpsi.add_participant("P001", PSIParticipantRole.PASSENGER)
    mptpsi.add_participant("V001", PSIParticipantRole.VEHICLE)

    # 创建有交集的路线
    common_point = GeoPoint(40.0, 116.4)
    route1 = [common_point]
    route2 = [GeoPoint(39.9, 116.3), common_point, GeoPoint(40.1, 116.5)]

    result = mptpsi.compute_psi_intersection(
        "P001", route1, "V001", route2, threshold_km=1.0
    )

    assert isinstance(result, PSIMatchResult), "结果应为PSIMatchResult类型"
    assert result.matched, "应该找到匹配"
    assert result.match_score > 0, "匹配分数应>0"


def test_mptpsi_threshold_verify():
    """测试MPTPSI门限验证"""
    mptpsi = MPTPSI(threshold=3, total=5)

    # 创建匹配结果
    result = PSIMatchResult(
        matched=True,
        match_score=1.0,
        distance_km=0.5,
        match_points=[],
        verification_code="ABC123",
        participants=["P001", "V001"],
        timestamp=time.time()
    )

    # 测试门限验证
    # 3个验证全部通过
    verifications = [("V1", True), ("V2", True), ("V3", True)]
    passed = mptpsi.threshold_verify(result, verifications)
    assert passed, "3个验证通过应满足门限"

    # 只有2个验证通过
    verifications = [("V1", True), ("V2", True)]
    passed = mptpsi.threshold_verify(result, verifications)
    assert not passed, "2个验证通过不满足门限3"


def test_threshold_verifier():
    """测试ThresholdVerifier验证者"""
    verifier = ThresholdVerifier("Verifier1")

    # 创建匹配结果和路线
    result = PSIMatchResult(
        matched=True,
        match_score=1.0,
        distance_km=0.5,
        match_points=[],
        verification_code="ABC123",
        participants=["P001", "V001"],
        timestamp=time.time()
    )

    route1 = [GeoPoint(40.0, 116.4)]
    route2 = [GeoPoint(40.0, 116.4)]  # 相同点

    verified, confidence = verifier.verify_match(result, route1, route2, 1.0)

    assert isinstance(verified, bool), "验证结果应为布尔值"
    assert 0 <= confidence <= 1.0, "置信度应在0-1之间"


def test_mptpsi_multi_party_match():
    """测试多方匹配（一对多）"""
    mptpsi = MPTPSI(threshold=3, total=5)

    passenger_dest = GeoPoint(40.0, 116.4)

    vehicle_routes = {
        "V001": [GeoPoint(39.9, 116.3), GeoPoint(40.0, 116.4)],
        "V002": [GeoPoint(39.8, 116.2), GeoPoint(39.9, 116.3)],
        "V003": [GeoPoint(40.1, 116.5), GeoPoint(40.2, 116.6)]
    }

    results = mptpsi.multi_party_match(
        "P001", passenger_dest, vehicle_routes, threshold_km=2.0
    )

    assert len(results) == 3, "应返回3个结果"
    assert "V001" in results, "V001应存在于结果中"
    assert "V002" in results, "V002应存在于结果中"
    assert "V003" in results, "V003应存在于结果中"

    # V001应该有更高的匹配分数
    assert results["V001"].match_score >= results["V002"].match_score, \
        "V001匹配分数应>=V002"


def test_share_serialization():
    """测试Share序列化和反序列化"""
    share = Share(index=1, value=123456, owner="Alice")

    # 序列化
    data = share.to_dict()

    assert "index" in data, "序列化数据应包含index"
    assert "value" in data, "序列化数据应包含value"
    assert "owner" in data, "序列化数据应包含owner"

    # 反序列化
    restored = Share.from_dict(data)

    assert restored.index == share.index, "反序列化索引应匹配"
    assert restored.value == share.value, "反序列化值应匹配"
    assert restored.owner == share.owner, "反序列化所有者应匹配"


def test_psimatchresult_serialization():
    """测试PSIMatchResult序列化"""
    result = PSIMatchResult(
        matched=True,
        match_score=0.95,
        distance_km=1.5,
        match_points=[GeoPoint(40.0, 116.4)],
        verification_code="TEST01",
        participants=["P001", "V001"],
        timestamp=time.time()
    )

    data = result.to_dict()

    assert data["matched"] == True
    assert data["match_score"] == 0.95
    assert data["verification_code"] == "TEST01"
    assert len(data["participants"]) == 2


def test_integration_scenario():
    """集成测试：完整的MP-TPSI流程"""
    print("\n  --- 集成测试：完整MP-TPSI流程 ---")

    # 1. 初始化
    mptpsi = MPTPSI(threshold=3, total=5)

    # 2. 添加参与方
    mptpsi.add_participant("Passenger", PSIParticipantRole.PASSENGER)
    mptpsi.add_participant("Vehicle1", PSIParticipantRole.VEHICLE)
    mptpsi.add_participant("Vehicle2", PSIParticipantRole.VEHICLE)

    # 3. 定义路线
    passenger_route = [GeoPoint(39.9, 116.3)]
    vehicle1_route = [GeoPoint(39.85, 116.25), GeoPoint(39.9, 116.3), GeoPoint(39.95, 116.35)]
    vehicle2_route = [GeoPoint(40.0, 116.4), GeoPoint(40.05, 116.45)]

    # 4. 计算PSI交集
    result1 = mptpsi.compute_psi_intersection(
        "Passenger", passenger_route,
        "Vehicle1", vehicle1_route,
        threshold_km=2.0
    )

    result2 = mptpsi.compute_psi_intersection(
        "Passenger", passenger_route,
        "Vehicle2", vehicle2_route,
        threshold_km=2.0
    )

    # 5. 验证结果
    assert result1.matched, "Vehicle1应该匹配"
    assert not result2.matched or result2.distance_km > 1.0, \
        "Vehicle2应该不匹配或距离更远"

    # 6. 门限验证
    verifications = [
        ("Verifier1", result1.matched),
        ("Verifier2", result1.matched),
        ("Verifier3", result1.matched)
    ]
    threshold_passed = mptpsi.threshold_verify(result1, verifications)
    assert threshold_passed, "门限验证应该通过"

    # 7. 秘密重构
    shares = mptpsi.shares.get("Passenger", [])
    if len(shares) >= mptpsi.threshold:
        reconstructed = mptpsi.reconstruct_matched_secret(
            "Passenger", shares[:mptpsi.threshold]
        )
        assert reconstructed > 0, "重构的秘密应为正整数"


# ========== 主程序 ==========

def main():
    """主测试函数"""
    print("=" * 60)
    print("MP-TPSI 完整测试套件")
    print("=" * 60)
    print()

    tests = [
        ("地理点哈希", test_geopoint_hash),
        ("地理点网格编码", test_geopoint_grid),
        ("Haversine距离计算", test_haversine_distance),
        ("模逆元计算", test_mod_inverse),
        ("Shamir秘密分割", test_shamir_split),
        ("Shamir秘密重构", test_shamir_reconstruct),
        ("Shamir不同组合重构", test_shamir_different_combinations),
        ("Shamir门限机制", test_shamir_threshold),
        ("LocationPSI哈希", test_location_psi_hash),
        ("LocationPSI路线哈希", test_location_psi_route),
        ("LocationPSI相似度计算", test_location_psi_similarity),
        ("LocationPSI交集查找", test_location_psi_intersection),
        ("MPTPSI添加参与方", test_mptpsi_add_participant),
        ("MPTPSI路线共享", test_mptpsi_share_route),
        ("MPTPSI交集计算", test_mptpsi_compute_intersection),
        ("MPTPSI门限验证", test_mptpsi_threshold_verify),
        ("ThresholdVerifier验证者", test_threshold_verifier),
        ("MPTPSI多方匹配", test_mptpsi_multi_party_match),
        ("Share序列化", test_share_serialization),
        ("PSIMatchResult序列化", test_psimatchresult_serialization),
        ("集成测试", test_integration_scenario),
    ]

    runner = TestRunner()
    for test_name, test_func in tests:
        runner.run_test(test_func, test_name)

    return runner.summary()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
