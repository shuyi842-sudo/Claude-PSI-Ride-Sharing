# 项目文件说明

无人驾驶拼车系统 - 基于MP-TPSI协议的共享出行系统

---

## 📁 核心应用文件

| 文件 | 说明 | 优先级 |
|------|------|--------|
| `app_integrated.py` | **主入口** - Flask服务器，集成所有功能模块 | ⭐⭐⭐ |
| `start.py` | 快速启动脚本 | ⭐⭐ |
| `config.py` | 配置管理（环境变量、多环境配置） | ⭐⭐⭐ |
| `database.py` | SQLite数据库操作（表结构、CRUD） | ⭐⭐⭐ |

---

## 🔐 PSI核心模块

| 文件 | 说明 | 优先级 |
|------|------|--------|
| `mp_tpsi.py` | **MP-TPSI主模块** - 多方门限隐私集合求交协议完整实现 | ⭐⭐⭐ |
| `psi.py` | PSI兼容层 - 支持4种模式（hash/ecc/multi/threshold） | ⭐⭐⭐ |
| `lagrange_psi.py` | PSI+PFE集成 - 基于拉格朗日插值的隐私函数求值 | ⭐⭐ |
| `crypto_psi.py` | 加密空间PSI - 真正的加密域匹配 | ⭐⭐ |

---

## 🚗 业务功能模块

| 文件 | 说明 | 优先级 |
|------|------|--------|
| `match_engine.py` | 匹配引擎 - 乘客车辆匹配算法 | ⭐⭐⭐ |
| `geo_route.py` | 地理服务 - 地址编码、路径规划、距离计算 | ⭐⭐⭐ |
| `tracking.py` | 实时追踪 - 行程状态、位置更新、ETA计算 | ⭐⭐ |
| `recommendation.py` | 智能推荐 - 基于历史的路线推荐 | ⭐⭐ |
| `input_handler.py` | 多模态输入 - 语音识别、地址建议、意图解析 | ⭐ |

---

## 🛡️ 安全与隐私

| 文件 | 说明 | 优先级 |
|------|------|--------|
| `auth.py` | 认证授权 - JWT、防重放、验证码管理 | ⭐⭐ |
| `privacy.py` | 隐私保护 - 差分隐私、噪声添加 | ⭐⭐ |
| `bloom_filter.py` | 布隆过滤器 - 快速判断路线是否存在 | ⭐ |
| `spatial_index.py` | 空间索引 - 网格索引加速附近车辆查询 | ⭐ |
| `route_cache.py` | 路线缓存 - 高频路线缓存加速 | ⭐ |

---

## 🧪 测试文件

| 文件 | 说明 | 用途 |
|------|------|------|
| `test_api.py` | API集成测试 | 完整用户流程测试 |
| `test_psi.py` | PSI算法测试 | 4种PSI模式测试 |
| `test_mptpsi.py` | MP-TPSI测试 | 门限PSI协议测试 |
| `test_lagrange_psi.py` | 拉格朗日PSI测试 | PSI+PFE功能测试 |
| `quick_test.py` | 快速测试 | 开发调试用 |
| `demo.py` | 系统演示 | 演示完整流程 |
| `audit.py` | 审计脚本 | 数据完整性检查 |

---

## 📚 文档文件

| 文件 | 说明 |
|------|------|
| `README.md` | 项目说明 |
| `CLAUDE.md` | Claude Code 开发规范 |
| `API.md` | API接口文档 |
| `SECURITY.md` | 安全设计文档 |
| `MPTPSI详解.md` | MP-TPSI协议详解 |
| `requirements.txt` | Python依赖清单 |

---

## 🗂️ 目录结构

```
Claude_PSI_project/
├── 核心应用
│   ├── app_integrated.py    # 主服务器
│   ├── start.py              # 启动脚本
│   ├── config.py            # 配置
│   └── database.py          # 数据库
├── PSI模块
│   ├── mp_tpsi.py          # MP-TPSI主协议
│   ├── psi.py              # PSI兼容层
│   ├── lagrange_psi.py     # PSI+PFE
│   └── crypto_psi.py       # 加密PSI
├── 业务模块
│   ├── match_engine.py      # 匹配引擎
│   ├── geo_route.py        # 地理服务
│   ├── tracking.py         # 实时追踪
│   ├── recommendation.py    # 智能推荐
│   └── input_handler.py    # 多模态输入
├── 安全组件
│   ├── auth.py             # 认证
│   ├── privacy.py          # 隐私保护
│   ├── bloom_filter.py     # 布隆过滤
│   ├── spatial_index.py    # 空间索引
│   └── route_cache.py      # 路线缓存
├── 测试
│   ├── test_api.py
│   ├── test_psi.py
│   ├── test_mptpsi.py
│   ├── test_lagrange_psi.py
│   ├── quick_test.py
│   ├── demo.py
│   └── audit.py
├── 前端
│   ├── templates/          # HTML模板
│   └── static/            # CSS/JS资源
├── 数据
│   └── ride_sharing.db    # SQLite数据库
└── 文档
    ├── README.md
    ├── CLAUDE.md
    ├── API.md
    ├── SECURITY.md
    ├── MPTPSI详解.md
    └── requirements.txt
```

---

## 🚀 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务器
python app_integrated.py
# 或
python start.py

# 运行测试
python test_api.py
python test_mptpsi.py
python demo.py
```

---

## 📊 PSI模式切换

系统支持4种PSI模式，通过 `/psi/config` API动态切换：

| 模式 | 说明 | 安全性 |
|------|------|--------|
| `hash` | 简化哈希模式 | ⭐ |
| `ecc` | 基于ECC的双方PSI | ⭐⭐ |
| `multi` | 基于ECC的多方PSI | ⭐⭐⭐ |
| `threshold` | 门限PSI | ⭐⭐⭐⭐ |
