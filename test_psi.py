"""
PSI算法测试套件
测试MP-TPSI协议的各种模式
"""

import hashlib
from psi import (
    generate_match_code,
    route_similarity,
    get_psi_instance,
    get_mp_psi_instance,
    PSIMode,
    ECDHPSI,
    MultiPartyPSI
)


def test_hash_mode():
    """测试哈希模式（兼容旧版）"""
    print("测试1: 哈希模式兼容性...")

    # 测试MD5哈希
    code = generate_match_code("P001", "V001", "hash")
    assert len(code) == 6, "验证码长度应为6位"
    assert code.isalnum(), "验证码应为字母数字"

    # 验证一致性
    code2 = generate_match_code("P001", "V001", "hash")
    assert code == code2, "相同输入应生成相同验证码"

    # 验证不同性
    code3 = generate_match_code("P002", "V001", "hash")
    assert code2 != code3, "不同输入应生成不同验证码"

    print("  ✅ 哈希模式测试通过")
    return True


def test_ecc_mode():
    """测试ECC双方PSI模式"""
    print("测试2: ECC双方PSI模式...")

    psi = get_psi_instance()

    # 测试ECC模式验证码
    code = psi.generate_match_code("P001", "V001", PSIMode.ECC_2P)
    assert len(code) == 6, "验证码长度应为6位"
    assert code.isalnum(), "验证码应为字母数字"

    # 测试验证功能
    assert psi.verify_match_code("P001", "V001", code, PSIMode.ECC_2P), "验证应成功"
    assert not psi.verify_match_code("P001", "V001", "WRONG", PSIMode.ECC_2P), "错误验证码应失败"

    print("  ✅ ECC双方PSI测试通过")
    return True


def test_multi_party_mode():
    """测试多方PSI模式"""
    print("测试3: 多方PSI模式...")

    psi = get_psi_instance()

    # 测试多方模式验证码
    code = psi.generate_match_code("P001", "V001", PSIMode.ECC_MP)
    assert len(code) == 6, "验证码长度应为6位"
    assert code.isalnum(), "验证码应为字母数字"

    # 验证功能
    assert psi.verify_match_code("P001", "V001", code, PSIMode.ECC_MP), "验证应成功"

    # 模式应产生不同结果
    hash_code = psi.generate_match_code("P001", "V001", PSIMode.HASH)
    ecc_code = psi.generate_match_code("P001", "V001", PSIMode.ECC_2P)
    multi_code = psi.generate_match_code("P001", "V001", PSIMode.ECC_MP)

    # 确保不同模式产生不同结果（增加安全性）
    assert hash_code != ecc_code != multi_code, "不同模式应产生不同验证码"

    print("  ✅ 多方PSI测试通过")
    return True


def test_threshold_mode():
    """测试门限PSI模式"""
    print("测试4: 门限PSI模式...")

    mp_psi = get_mp_psi_instance(threshold=3)

    # 基本测试（低于门限）
    code = mp_psi.generate_threshold_match_code("P001", "V001")
    assert len(code) == 6, "验证码长度应为6位"

    # 验证失败（因子数低于门限）
    valid, count = mp_psi.verify_threshold_match("P001", "V001", code)
    assert valid == False, "低于门限验证应失败"
    assert count == 2, "应使用2个基础因子"

    # 带额外因子测试（达到门限）
    factors = ["factor_A", "factor_B"]  # 2个额外因子 + 2个基础 = 4个，满足门限3
    code_with_factors = mp_psi.generate_threshold_match_code("P001", "V001", factors)
    assert len(code_with_factors) == 6, "验证码长度应为6位"

    # 验证成功（使用相同因子达到门限）
    valid, count = mp_psi.verify_threshold_match("P001", "V001", code_with_factors, factors)
    assert valid == True, "达到门限验证应成功"
    assert count == 4, "应使用4个因子"

    # 测试门限检查（使用相同因子但提高门限到5）
    valid_high, count_high = mp_psi.verify_threshold_match(
        "P001", "V001", code_with_factors, factors, min_factors=5
    )
    assert valid_high == False, "因子数低于更高门限应验证失败"

    # 测试不同因子验证失败
    valid_wrong, _ = mp_psi.verify_threshold_match(
        "P001", "V001", code_with_factors, ["wrong_factor"]
    )
    assert valid_wrong == False, "使用不同因子应验证失败"

    print("  ✅ 门限PSI测试通过")
    return True


def test_route_similarity():
    """测试路线相似度计算"""
    print("测试5: 路线相似度计算...")

    psi = get_psi_instance()

    # 相同路线
    score1 = psi.compute_similarity("北京中关村", "北京中关村")
    assert score1 > 0.9, "相同路线应返回高分"

    # 前缀相同的路线（北京开头的短路线）
    score2 = psi.compute_similarity("中关村A", "中关村B")
    assert score2 >= 0.5, "相同地点应返回较高分"

    # 相似度高（有重叠字符）
    score3 = psi.compute_similarity("科技园A区", "科技园B区")
    assert score3 >= 0.3, "重叠较多应返回中等分"

    # 不同区域
    score4 = psi.compute_similarity("中关村", "陆家嘴")
    assert score4 < 0.5, "不同区域应返回较低分"

    # 验证相似度范围
    assert 0 <= score4 <= 1, "相似度应在0-1之间"

    print("  ✅ 路线相似度测试通过")
    return True


def test_ecdh_operations():
    """测试ECDH基础操作"""
    print("测试6: ECDH基础操作...")

    psi = ECDHPSI()

    # 测试哈希到曲线
    point = psi._hash_to_curve("test_element")
    assert 0 <= point < psi.curve_order, "点应在曲线范围内"

    # 测试共享密钥计算
    secret = psi._compute_shared_secret("Alice", "Bob")
    assert 0 <= secret < psi.curve_order, "共享密钥应在曲线范围内"

    # 测试盲化元素
    blinded = psi._blinded_element("element123", secret)
    assert len(blinded) == 64, "盲化元素应为64位十六进制"

    print("  ✅ ECDH基础操作测试通过")
    return True


def test_mode_comparison():
    """测试各模式验证码差异"""
    print("测试7: 各模式验证码差异分析...")

    psi = get_psi_instance()
    test_pairs = [
        ("P001", "V001"),
        ("P002", "V002"),
        ("PASS123", "VEHICLE456"),
    ]

    for p_id, v_id in test_pairs:
        codes = {
            "hash": psi.generate_match_code(p_id, v_id, PSIMode.HASH),
            "ecc": psi.generate_match_code(p_id, v_id, PSIMode.ECC_2P),
            "multi": psi.generate_match_code(p_id, v_id, PSIMode.ECC_MP),
            "threshold": psi.generate_match_code(p_id, v_id, PSIMode.THRESHOLD),
        }

        # 确保每个模式产生不同结果
        unique_codes = set(codes.values())
        assert len(unique_codes) == 4, f"{p_id}-{v_id}: 各模式应产生不同验证码"

        print(f"    {p_id}-{v_id}: hash={codes['hash']}, ecc={codes['ecc']}, multi={codes['multi']}, threshold={codes['threshold']}")

    print("  ✅ 模式差异测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("MP-TPSI 算法测试套件")
    print("=" * 60)
    print()

    tests = [
        test_hash_mode,
        test_ecc_mode,
        test_multi_party_mode,
        test_threshold_mode,
        test_route_similarity,
        test_ecdh_operations,
        test_mode_comparison,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"  ❌ 测试失败: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ 测试异常: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"测试完成: {passed}/{len(tests)} 通过")
    if failed > 0:
        print(f"失败: {failed}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_all_tests() else 1)
