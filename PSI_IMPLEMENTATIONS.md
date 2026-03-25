# PSI 隐私集合求交协议实现文档

## 概述

本文档详细描述了无人驾驶拼车系统中实现的多种隐私集合求交（PSI）协议。PSI允许两方或多方在不泄露各自集合元素的情况下，计算出集合的交集。

---

## 一、PSI协议类型概览

| 协议类型 | 文件 | 安全级别 | 应用场景 |
|----------|------|----------|----------|
| 简化哈希PSI | `psi.py` | 低 | 兼容旧系统，快速匹配 |
| 基于ECC的双方PSI | `psi.py` | 中 | 乘客-车辆双方匹配 |
| 基于ECC的多方PSI | `psi.py` | 中高 | 多辆车辆协同匹配 |
| 门限PSI | `psi.py` | 高 | 需要多方验证的场景 |
| 拉格朗日插值PSI | `lagrange_psi.py` | 高 | 带距离阈值的模糊匹配 |
| 加密空间PSI | `crypto_psi.py` | 极高 | 完全加密空间的集合求交 |
| MP-TPSI | `mp_tpsi.py` | 极高 | 多方门限隐私集合求交 |

---

## 二、协议详解

### 2.1 简化哈希PSI (Hash PSI)

**特点**：
- 最简单的PSI实现
- 使用MD5哈希生成验证码
- 计算速度快，安全性较低

**原理**：
```
验证码 = MD5(passenger_id + vehicle_id)[:6].upper()
```

**适用场景**：
- 快速原型开发
- 低安全要求的内部系统

**代码示例**：
```python
from psi import generate_match_code

# 生成匹配验证码
code = generate_match_code("P001", "V001", mode="hash")
# 输出: "29903A"
```

---

### 2.2 基于ECC的双方PSI (ECC 2-Party PSI)

**特点**：
- 基于椭圆曲线密码学
- 支持真实ECC（需要cryptography库）
- 提供盲化和共享密钥计算

**核心类**：
```python
class RealECCPSI:
    """基于真实椭圆曲线密码学的PSI实现"""
    def generate_key_pair()          # 生成ECC密钥对
    def blind_element(element, key)   # 对元素进行盲化
    def compute_shared_secret(...)    # 计算ECDH共享密钥
    def generate_ecc_match_code(...) # 使用真实ECC生成验证码
```

**协议流程**：
```
1. 乘客生成密钥对 (p_private, p_public)
2. 车辆生成密钥对 (v_private, v_public)
3. 计算共享密钥: shared = ECDH(p_private, v_public)
4. 生成验证码: code = hash(shared + p_id + v_id)[:6]
```

**使用示例**：
```python
from psi import RealECCPSI

ecc_psi = RealECCPSI()
code = ecc_psi.generate_ecc_match_code("P001", "V001")
```

---

### 2.3 基于ECC的多方PSI (ECC Multi-Party PSI)

**特点**：
- 支持多方参与的PSI
- 使用随机盐值防止预计算攻击
- 添加时间戳防止重放攻击

**实现细节**：
```python
salt = secrets.token_hex(8)  # 随机盐值
multi_input = f"MP_PSI:{p_id}:{v_id}:{salt}:{time.time()}"
code_hash = hashlib.sha256(multi_input.encode()).hexdigest()
code = code_hash[:6].upper()
```

---

### 2.4 门限PSI (Threshold PSI)

**特点**：
- 基于Shamir秘密共享
- 支持k-of-n门限验证
- 多个验证者确认后才能完成匹配

**核心类**：
```python
class MultiPartyPSI:
    """多方隐私集合求交协议"""
    def __init__(self, threshold=3, total=5)
    def generate_secret_shares(secret)   # 生成秘密份额
    def reconstruct_secret(shares)     # 从份额重构秘密
    def compute_multi_party_hash(elements) # 计算多方聚合哈希
    def generate_threshold_match_code(...) # 生成门限匹配码
    def verify_threshold_match(...)      # 验证门限匹配
```

**Shamir秘密共享原理**：
```
给定秘密 S，生成随机多项式:
f(x) = S + a₁·x + a₂·x² + ... + a(k-1)·x^(k-1)

份额 i: Share(i, f(i))

重构: 拉格朗日插值
S = f(0) = Σ y_j · L_j(0)
```

**使用示例**：
```python
from psi import MultiPartyPSI

mp_psi = MultiPartyPSI(threshold=3, total=5)

# 生成门限匹配码
code = mp_psi.generate_threshold_match_code(
    p_id="P001",
    v_id="V001",
    additional_factors=["V002", "V003"]  # 额外门限因子
)

# 验证门限匹配
verified, used = mp_psi.verify_threshold_match(
    p_id="P001",
    v_id="V001",
    code=code,
    additional_factors=["V002", "V003"]
)
```

---

### 2.5 拉格朗日插值PSI (Lagrange PSI)

**特点**：
- 结合PSI和私有函数求值（PFE）
- 支持带距离阈值的模糊匹配
- 车辆无法推断原始距离信息

**核心组件**：

#### 2.5.1 伪随机函数 (PRF)
```python
class PseudoRandomFunction:
    """使用HMAC-SHA256实现的伪随机函数"""
    def generate_shared_seed(size=16) -> bytes
    def generate_x(point_hash, seed) -> int      # 生成自变量x
    def generate_x_batch(point_hashes, seed) -> List[int]
```

#### 2.5.2 距离归一化器
```python
class DistanceNormalizer:
    """将实际距离映射到 [0, 255] 范围"""
    MAX_DISTANCE_KM = 10.0

    def normalize(distance_km) -> int    # 线性归一化
    def denormalize(value) -> float     # 反归一化
```

#### 2.5.3 拉格朗日PFE
```python
class LagrangePFE:
    """基于拉格朗日的私有函数求值"""

    def build_interpolation(points) -> LagrangeCoefficients:
        """
        构建拉格朗日插值多项式
        给定点集 {(x₁,y₁), (x₂,y₂), ..., (xₙ,yₙ)}
        构建多项式 L(x) 满足 L(xᵢ) = yᵢ
        """

    def evaluate(coefficients, x) -> int:
        """
        评估多项式在 x 处的值
        使用霍纳法则高效计算
        """
```

**协议流程**：
```
乘客侧:
1. 对路线每个点计算: PRF值(xᵢ) + 归一化距离(yᵢ)
2. 构建点集 {(xᵢ, yᵢ)}
3. 拉格朗日插值 → 多项式系数 [a₀, a₁, ..., aₙ₋₁]
4. 发送加密地点哈希和多项式系数给车辆

车辆侧:
1. 使用相同PRF生成自己的地点PRF值
2. PSI找出双方地点的交集
3. 对每个交集点，用拉格朗日多项式求值
4. 反归一化得到实际距离
5. 判断距离是否小于阈值
```

**使用示例**：
```python
from lagrange_psi import PSIPlusPFE, GeoPoint, create_route_from_coords

# 创建协议实例
protocol = PSIPlusPFE(threshold_km=2.0, max_distance_km=10.0)

# 乘客数据
passenger_route = create_route_from_coords([
    (39.8800, 116.3500),  # 起点
    (39.9042, 116.4074),  # 天安门
    (39.9100, 116.4200)
])
target_point = GeoPoint(39.9042, 116.4074)

# 乘客准备请求
request = protocol.passenger_prepare_request(
    passenger_route=passenger_route,
    target_point=target_point,
    passenger_id="P001"
)

# 车辆数据
vehicle_route = create_route_from_coords([
    (39.8500, 116.3000),
    (39.9042, 116.4074),  # 经过天安门附近
    (39.9200, 116.4300)
])

# 车辆处理请求
result = protocol.vehicle_process_request(
    request=request,
    vehicle_route=vehicle_route,
    vehicle_id="V001"
)

print(f"匹配: {result.matched}")
print(f"距离: {result.distance_km:.3f} km")
print(f"验证码: {result.verification_code}")
```

---

### 2.6 加密空间PSI (Encrypted Space PSI)

**特点**：
- 在加密空间完成所有匹配计算
- 不接触原始地理坐标
- 支持加法盲化和乘法盲化两种模式

**盲化模式**：
```python
class BlindingMode(Enum):
    ADDITIVE = "additive"       # E(x) = (x + r) mod p
    MULTIPLICATIVE = "multiplicative"  # E(x) = (x * r) mod p
    OPRF = "oprf"              # OPRF盲化
```

**核心类**：

#### 2.6.1 椭圆曲线PSI
```python
class EllipticCurvePSI:
    """基于椭圆曲线的PSI实现"""

    def blind_point(point_hash, blind_factor=None) -> BlindedPoint
    def blind_route(point_hashes, route_id, blind_factor=None) -> BlindedRoute
    def compare_blinded_points(bp1, bp2) -> bool
    def verify_blinding(original_hash, blinded_point) -> bool
```

#### 2.6.2 加密数学工具
```python
class CryptoMath:
    """加密数学工具类"""

    PRIME = 2**256 - 2**224 + 2**192 + 2**96 - 1  # 大素数
    GENERATOR = 2  # 生成元

    @staticmethod
    def mod_inverse(a, m=None):     # 计算模逆元
    @staticmethod
    def hash_to_curve(value):       # 哈希到曲线
    @staticmethod
    def generate_blind_factor():    # 生成随机盲因子
    @staticmethod
    def blind_additive(value, blind_factor):    # 加法盲化
    @staticmethod
    def blind_multiplicative(value, blind_factor):  # 乘法盲化
```

**加密空间交集流程**：
```
1. 乘客和车辆各自生成盲因子 r
2. 对每个地理位置点:
   a. 哈希坐标: h = SHA256(lat, lng)
   b. 盲化: E(h) = (h * r) mod p
3. 交换盲化值
4. 在加密空间比较: E(h₁) == E(h₂)
5. 如相等，则原始坐标相同
6. 双方都不知对方原始坐标
```

**使用示例**：
```python
from crypto_psi import EncryptedSpacePSI, BlindingMode

# 创建加密空间PSI实例
enc_psi = EncryptedSpacePSI(mode=BlindingMode.MULTIPLICATIVE)

# 盲化坐标
blinded_route1 = enc_psi.blind_route_from_coordinates(
    coordinates=[(39.8800, 116.3500), (39.9042, 116.4074)],
    route_id="R001"
)

blinded_route2 = enc_psi.blind_route_from_coordinates(
    coordinates=[(39.8500, 116.3000), (39.9042, 116.4074)],
    route_id="R002"
)

# 在加密空间找交集
intersection = enc_psi.encrypted_intersection(
    route1_blinded=blinded_route1,
    route2_blinded=blinded_route2,
    verify_factor_match=False  # 双方使用不同盲因子
)

print(f"匹配: {intersection.matched}")
print(f"匹配点数: {intersection.match_count}")
print(f"验证码: {intersection.verification_hash}")
```

---

### 2.7 MP-TPSI (多方门限PSI)

**特点**：
- 最完整的PSI实现
- 结合Shamir秘密共享、地理位置PSI、门限验证
- 支持多辆车辆协同匹配

**核心组件**：

#### 2.7.1 Shamir秘密共享
```python
class ShamirSecretSharing:
    """Shamir秘密共享方案"""

    def __init__(self, threshold=3, total=5, prime=None)
    def split_secret(secret, owner) -> List[Share]
    def reconstruct_secret(shares) -> int
    def verify_share(share, public_commitments) -> bool
    def generate_commitments(coefficients) -> List[int]
```

#### 2.7.2 地理位置PSI
```python
class LocationPSI:
    """基于地理位置的隐私集合求交"""

    def hash_location(point) -> int
    def hash_route(route) -> List[int]
    def hash_location_encrypted(point, blind_factor=None) -> int
    def find_route_intersection(route1, route2, threshold_km) -> List
    def compute_route_similarity(route1, route2, threshold_km) -> float
```

#### 2.7.3 多方门限PSI协议
```python
class MPTPSI:
    """多方门限隐私集合求交协议"""

    def add_participant(participant_id, role)
    def share_route_secret(participant_id, route) -> List[Share]
    def distribute_shares(from_participant, to_participants)
    def compute_psi_intersection(p1, route1, p2, route2, ...)
    def threshold_verify(match_result, verifications)
    def reconstruct_matched_secret(participant_id, required_shares)
    def multi_party_match(passenger_id, passenger_dest, vehicle_routes, ...)
```

**完整协议流程**：
```
Setup阶段:
1. 各方生成密钥
2. Shamir配置 k-of-n

Share阶段:
1. 乘客将路线哈希为秘密
2. 使用Shamir分割为n份份额
3. 分发给其他参与方

Compute阶段:
1. 各方协作计算交集
2. 使用地理位置PSI进行路线匹配
3. 计算匹配分数

Verify阶段:
1. 需要k个验证者确认结果
2. 验证结果一致性

Reconstruct阶段:
1. 需要k个份额重构秘密
2. 生成最终验证码
```

**使用示例**：
```python
from mp_tpsi import MPTPSI, GeoPoint, PSIParticipantRole

# 初始化MP-TPSI
mptpsi = MPTPSI(threshold=3, total=5)

# 添加参与方
mptpsi.add_participant("P001", PSIParticipantRole.PASSENGER)
mptpsi.add_participant("V001", PSIParticipantRole.VEHICLE)
mptpsi.add_participant("V002", PSIParticipantRole.VEHICLE)
mptpsi.add_participant("V003", PSIParticipantRole.VEHICLE)

# 定义数据
passenger_dest = GeoPoint(39.9042, 116.4074)  # 天安门

vehicle_routes = {
    "V001": [
        GeoPoint(39.8800, 116.3500),
        GeoPoint(39.9042, 116.4074),  # 经过天安门
        GeoPoint(39.9200, 116.4300)
    ],
    "V002": [
        GeoPoint(39.8500, 116.3000),
        GeoPoint(39.8700, 116.3300),
        GeoPoint(39.9100, 116.3900)
    ],
    "V003": [
        GeoPoint(39.8900, 116.4000),
        GeoPoint(39.9042, 116.4074),  # 经过天安门
        GeoPoint(39.9250, 116.4250)
    ]
}

# 多方匹配
results = mptpsi.multi_party_match(
    passenger_id="P001",
    passenger_dest=passenger_dest,
    vehicle_routes=vehicle_routes,
    threshold_km=2.0
)

# 门限验证
best_match = results["V001"]
verifiers = [
    ThresholdVerifier("Verifier1"),
    ThresholdVerifier("Verifier2"),
    ThresholdVerifier("Verifier3")
]

verifications = []
for verifier in verifiers:
    verified, _ = verifier.verify_match(
        best_match,
        [passenger_dest],
        vehicle_routes["V001"],
        threshold_km=2.0
    )
    verifications.append((verifier.verifier_id, verified))

# 执行门限验证
threshold_passed = mptpsi.threshold_verify(best_match, verifications)
```

---

## 三、安全特性对比

| 安全特性 | Hash | ECC-2P | ECC-MP | Threshold | Lagrange | Encrypted | MP-TPSI |
|----------|------|--------|--------|-----------|----------|-----------|----------|
| 计算不可区分 | ❌ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 抗选择攻击 | ❌ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 抗重放攻击 | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 门限验证 | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| 完全加密 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| 多方协作 | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |

**图例**：
- ❌ 不支持
- ⚠️ 部分支持（需要真实ECC）
- ✅ 完全支持

---

## 四、性能比较

| 协议 | 计算复杂度 | 通信轮次 | 网络开销 | 推荐场景 |
|------|------------|----------|----------|----------|
| Hash PSI | O(1) | 1 | 最低 | 快速匹配 |
| ECC 2-Party PSI | O(n) | 2 | 低 | 双方匹配 |
| ECC Multi-Party PSI | O(n) | 3 | 中 | 多方协作 |
| Threshold PSI | O(n²) | 4 | 中高 | 高安全要求 |
| Lagrange PSI+PFE | O(n²) | 2 | 中 | 模糊匹配 |
| Encrypted Space PSI | O(n²) | 2 | 高 | 高安全要求 |
| MP-TPSI | O(n³) | 5+ | 最高 | 企业级应用 |

---

## 五、统一API接口

### 5.1 基础PSI API

```python
from psi import generate_match_code, route_similarity, PSIMode

# 生成匹配验证码
code = generate_match_code(
    p_id="P001",
    v_id="V001",
    mode="hash"  # 可选: hash, ecc, multi, threshold
)
# 返回: "29903A"

# 计算路线相似度
similarity = route_similarity(
    route1="北京中关村-北京西站",
    route2="北京海淀-北京南站"
)
# 返回: 0.75 (0.0 - 1.0)
```

### 5.2 安全验证码生成

```python
from psi import SecureMatchCode

secure = SecureMatchCode(time_window=60)

code = secure.generate_secure_code(
    p_id="P001",
    v_id="V001",
    mode=PSIMode.ECC_2P,
    use_real_ecc=True
)
```

### 5.3 检查速率限制

```python
from psi import SecureMatchCode

secure = SecureMatchCode()

allowed, count = secure.check_rate_limit(
    identifier="192.168.1.1",  # IP地址或用户ID
    max_attempts=10,
    window_seconds=300
)

# 返回: (True, 1)  # 允许且已尝试1次
```

---

## 六、扩展指南

### 6.1 添加新的PSI协议

1. 创建新的协议类继承基类
2. 实现必要的接口方法
3. 在 `psi.py` 中注册新模式

```python
# 示例: 添加基于同态加密的PSI
class HomomorphicPSI:
    """同态加密PSI实现"""
    def __init__(self):
        # 初始化配置
        pass

    def encrypt_set(self, elements):
        """加密集合"""
        pass

    def compute_intersection(self, encrypted_set1, encrypted_set2):
        """计算交集"""
        pass

    def decrypt_result(self, encrypted_intersection):
        """解密结果"""
        pass
```

### 6.2 修改验证码格式

当前验证码为6位大写字母+数字，可修改：

```python
# 在 psi.py 中修改
def generate_match_code(p_id, v_id, mode="hash"):
    # 修改验证码格式
    code = hashlib.sha256(f"{p_id}{v_id}".encode()).hexdigest()[:8]
    return code.upper()  # 返回8位验证码
```

### 6.3 集成到Flask应用

```python
from flask import Flask, request, jsonify
from psi import generate_match_code

app = Flask(__name__)

@app.route("/match", methods=["POST"])
def match():
    data = request.json
    p_id = data.get("passenger_id")
    v_id = data.get("vehicle_id")
    mode = data.get("mode", "hash")

    code = generate_match_code(p_id, v_id, mode)

    return jsonify({
        "success": True,
        "match_code": code,
        "mode": mode
    })
```

---

## 七、测试验证

### 7.1 运行单元测试

```bash
# 测试MP-TPSI
python mp_tpsi.py

# 测试拉格朗日PSI
python lagrange_psi.py

# 运行所有测试
python test_admin.py
```

### 7.2 验证码验证

```python
from psi import generate_match_code

# 生成验证码
code = generate_match_code("P001", "V001", mode="ecc")
print(f"验证码: {code}")  # 如: "29903A"

# 验证验证码（乘客端发送）
# 车辆端验证逻辑
expected = generate_match_code("P001", "V001", mode="ecc")
if code.upper() == expected.upper():
    print("验证成功")
else:
    print("验证失败")
```

---

## 八、文件结构

```
D:\Claude_PSI_project\
├── psi.py                    # 基础PSI协议
├── mp_tpsi.py                # 多方门限PSI (完整实现)
├── lagrange_psi.py           # 拉格朗日插值PSI+PFE
├── crypto_psi.py             # 加密空间PSI
├── app_integrated.py          # Flask集成应用
├── test_admin.py             # 管理后台测试
├── test_lagrange_psi.py      # 拉格朗日PSI测试
├── test_mptpsi.py            # MP-TPSI测试
└── PSI_IMPLEMENTATIONS.md      # 本文档
```

---

## 九、参考与资源

### 9.1 学术论文

1. **Private Set Intersection (PSI)**
   - Huberman, B. A., Franklin, M. K., & Hogg, T. (2002)
   - Privacy Enhancing Technologies

2. **Threshold PSI**
   - Dachman-Soled, D., et al. (2009)
   - Efficient Threshold Private Set Intersection

3. **Private Function Evaluation**
   - Naor, M., & Pinkas, B. (1999)
   - Oblivious Transfer and Polynomial Evaluation

### 9.2 相关项目

- [Microsoft SEAL](https://github.com/microsoft/SEAL) - 同态加密库
- [OpenMined](https://github.com/OpenMined) - 隐私保护机器学习
- [OPRF](https://datatracker.ietf.org/doc/html/draft-ietf-privacypass-oprf) - IETF OPRF标准

---

## 十、常见问题 (FAQ)

### Q1: 为什么有这么多PSI协议？
A: 不同协议适用于不同的安全级别和性能需求。低安全要求场景使用Hash PSI，高安全要求使用Encrypted Space PSI。

### Q2: 如何选择合适的PSI协议？
A: 根据以下因素选择：
- 安全要求：越高需要越复杂的协议
- 性能要求：简单协议性能更好
- 参与方数量：2方用ECC 2P，多方用MP-TPSI
- 隐私要求：是否需要完全加密

### Q3: 如何验证PSI协议的安全性？
A: 需要进行形式化验证和安全分析。本项目中的协议基于已发表的学术论文实现。

### Q4: 支持哪些编程语言？
A: 当前实现为Python，核心算法可移植到其他语言。

### Q5: 如何在生产环境使用？
A: 建议使用ECC PSI或以上协议，配置正确的密钥管理和速率限制。

---

## 十一、版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.0.0 | 2026-03-25 | 初始版本，包含所有PSI协议实现 |

---

## 十二、许可与版权

本项目仅供学习和研究使用。请在生产环境中进行充分的安全评估和审计。

---

**文档版本**: 1.0.0
**最后更新**: 2026-03-25
**维护者**: Claude Code
