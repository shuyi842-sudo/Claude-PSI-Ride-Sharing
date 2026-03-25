# 基于MP-TPSI的无人驾驶共享出行系统

## 项目简介

本项目是基于**隐私集合求交**的无人驾驶共享出行系统，解决传统拼车在无人驾驶环境下的身份确认和隐私保护问题。
在传统的拼车系统中，用户通常通过与司机的互动来确认身份，但在无人驾驶环境下，这种身份确认方式变得不可行，从而增加了安全隐患，如搭错车的风险、泄漏私人出行路线导致安全风险等。目前的隐私保护拼车系统尚未针对这一问题提出有效的解决方案。本课题拟通过设计新的身份验证机制与隐私保护技术相结合，确保用户在无人驾驶环境中的拼车安全，降低潜在的风险。同时拼车系统需要在匹配乘客的同时确保用户的隐私保护，但当涉及复杂的多方交互和门限条件时，传统的方案可能会面临隐私和效率之间的折中问题。本课题将通过MP-TPSI协议的设计和优化，实现匹配精度与隐私保护的平衡，提高系统的实用性和安全性，确保顺利出行与安全出行。

### 核心问题

1. **身份确认难题**：无人驾驶环境中无法通过司机确认乘客身份
2. **隐私泄露风险**：传统方案可能导致私人出行路线泄露
3. **搭错车风险**：缺乏有效的身份验证机制

### 解决方案

采用 **MP-TPSI（Multi-Party Threshold PSI）协议**：
- PSI隐私计算生成匹配验证码
- 无需传输原始身份信息
- 实现匹配精度与隐私保护的平衡

## 功能特性

### 核心功能

| 功能 | 描述 |
|------|------|
| 乘客注册/匹配 | 发布出行需求，智能匹配合适车辆 |
| 车辆注册/管理 | 注册车辆信息，查看匹配乘客列表 |
| PSI验证码生成 | 基于乘客ID和车辆ID生成隐私保护验证码 |
| 上车验证 | 通过PSI验证码验证乘客身份 |
| 取消匹配 | 取消匹配并释放车辆座位 |
| 实时推送 | WebSocket实时通知乘客匹配/上车/取消 |

### PSI算法支持

- **hash**: MD5哈希（兼容模式）
- **ecc**: ECC双方PSI协议
- **multi**: ECC多方PSI协议
- **threshold**: 门限PSI协议
- **lagrange**: 拉格朗日插值PSI+PFE
- **geo**: 加密空间PSI
- **mptpsi**: MP-TPSI多方门限协议

### 管理后台

- 系统统计数据仪表盘
- 乘客/车辆/匹配数据管理
- PSI模式动态切换
- 系统重置功能

### 安全机制

- JWT令牌认证
- 请求防重放攻击
- 验证码有效期限制
- HTTPS支持

## 项目结构

```
D:\Claude_PSI_project/
├── app_integrated.py      # Flask后端主程序（集成版）
├── database.py            # SQLite数据库操作
├── psi.py                 # MP-TPSI算法实现
├── config.py              # 配置管理
├── lagrange_psi.py        # 拉格朗日插值PSI+PFE
├── mp_tpsi.py             # MP-TPSI多方门限协议
├── geo_route.py           # 加密空间PSI
├── bloom_filter.py        # 布隆过滤器
├── spatial_index.py       # 空间索引
├── match_engine.py        # 匹配引擎
├── recommendation.py      # 推荐算法
├── tracking.py            # 行程追踪
├── privacy.py             # 隐私保护模块
├── test_admin.py          # 管理后台测试
├── test_mptpsi.py         # MP-TPSI测试
├── test_lagrange_psi.py   # 拉格朗日PSI测试
├── requirements.txt       # Python依赖
├── PSI_IMPLEMENTATIONS.md # PSI协议实现文档
├── README.md             # 项目说明（本文件）
├── CLAUDE.md             # 开发规范文档
├── templates/            # HTML模板
│   ├── index.html        # 首页
│   ├── passenger.html    # 乘客端
│   ├── vehicle.html      # 车辆端
│   ├── verify.html       # 验证页面
│   └── admin.html        # 管理后台
└── static/
    └── style.css         # 样式文件
```

## 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
python app_integrated.py
```

服务将运行在 `http://localhost:5000`

### 访问界面

| 界面 | URL |
|------|-----|
| 首页 | http://localhost:5000/ |
| 乘客端 | http://localhost:5000/passenger |
| 车辆端 | http://localhost:5000/vehicle |
| 验证页面 | http://localhost:5000/verify |
| 管理后台 | http://localhost:5000/admin |

## API文档

详细的API文档请参考项目代码中的注释和测试文件。

## PSI算法说明

### 验证码生成

```python
# MD5哈希模式
code = MD5(passenger_id + vehicle_id)[:6].upper()

# ECC双方PSI模式
shared_secret = ECDH(passenger_id, vehicle_id)
code = SHA256("PSI_2P:" + shared_secret)[:6].upper()

# 门限PSI模式
code = SHA256("TH_PSI:" + passenger_id + ":" + vehicle_id + ":threshold")[:6].upper()
```

### 路线匹配

基于Jaccard相似度计算路线匹配度：

```
similarity = 0.7 * Jaccard(route1, route2) + 0.3 * area_match
```

## 测试覆盖

| 模块 | 测试数 | 状态 |
|------|--------|------|
| 管理后台API | 7 | ✅ 全部通过 |
| MP-TPSI | 5 | ✅ 全部通过 |
| 拉格朗日PSI | 6 | ✅ 全部通过 |
| **总计** | **18** | **✅ 全部通过** |

## 技术栈

- **后端**: Flask, Flask-SocketIO, SQLite
- **前端**: HTML5, CSS3, JavaScript (Fetch API, Socket.IO)
- **密码学**: hashlib, cryptography, shamir (PSI算法)
- **安全**: JWT, 防重放攻击
- **空间计算**: geopy, 空间索引

## 开发规范

详见 [CLAUDE.md](CLAUDE.md)

## 许可证

本项目仅用于学习和研究目的。

## 贡献

欢迎提交Issue和Pull Request！

## 作者

无人驾驶拼车系统研究项目
