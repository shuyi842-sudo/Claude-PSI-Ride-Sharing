# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于MP-TPSI（多方门限隐私集合求交）协议的无人驾驶共享出行系统。系统通过PSI密码学技术生成匹配验证码，在不传输原始身份信息的情况下完成乘客-车辆匹配和上车验证。

## 快速命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务器（开发模式）
python app.py

# 运行API测试（需服务器运行）
python test_api.py

# 运行PSI算法测试
python test_psi.py

# 运行系统演示（需服务器运行）
python demo.py

# 单独运行桌面端（需服务器运行）
python passenger.py  # 乘客端Tkinter界面
python vehicle.py   # 车辆端Tkinter界面
```

## 代码架构

### 核心模块

| 模块 | 职责 | 入口文件 |
|------|--------|----------|
| Flask后端 | HTTP路由、WebSocket、业务逻辑 | `app.py` |
| 数据持久化 | SQLite操作、表管理 | `database.py` |
| PSI算法 | 多方门限PSI协议实现 | `psi.py` |
| 安全认证 | JWT、防重放、验证码管理 | `auth.py` |
| 配置管理 | 环境变量、多环境配置 | `config.py` |

### PSI算法模式切换

系统支持4种PSI模式，通过 `/psi/config` API 动态切换：

```python
# app.py 中当前模式
current_psi_mode = "hash"  # hash | ecc | multi | threshold
```

不同模式生成的验证码不同，确保向后兼容的同时提供更强安全性。

### 数据库架构

- `passengers`: 乘客信息（id, start, end, route, status, created_at）
- `vehicles`: 车辆信息（id, start, end, route, seats, status, created_at）
- `matches`: 匹配记录（id, passenger_id, vehicle_id, match_code, status, created_at）

所有数据库操作通过 `database.py` 的函数进行，使用上下文管理器 `get_db()` 自动提交/回滚。

### WebSocket通信

车辆端通过Socket.IO接收实时事件：
- `new_passenger`: 新乘客匹配
- `passenger_boarded`: 乘客已上车
- `passenger_cancelled`: 乘客取消匹配
- `system_reset`: 系统重置

客户端需调用 `socket.emit('join_vehicle', {vehicle_id: 'V001'})` 加入车辆房间。

### 前后端通信

前端使用原生 `fetch()` API 与后端通信，格式：
```javascript
fetch('/api/endpoint', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({...})
})
.then(res => res.json())
.then(data => console.log(data));
```

### 路线匹配算法

`psi.route_similarity()` 使用Jaccard相似度 + 区域前缀权重：
```python
similarity = 0.7 * Jaccard(route1, route2) + 0.3 * area_match
```

匹配阈值默认为0.7，可在 `app.py` 的 `psi_match()` 函数中修改。

## 开发注意事项

1. **PSI模式兼容性**: 修改验证码生成逻辑时需确保所有4种模式正常工作
2. **WebSocket房间**: 车辆相关通知使用 `f"vehicle_{v_id}"` 作为room名称
3. **数据库事务**: 所有写操作应通过 `database.py` 函数，不直接操作
4. **中文界面**: 前端所有用户可见文本使用中文
5. **响应格式**: API统一返回JSON，错误返回 `{error: "...", ...}`

## 测试策略

- `test_api.py`: 测试完整的用户流程（注册→匹配→验证→取消）
- `test_psi.py`: 测试PSI算法各模式的核心逻辑
- 运行测试前需确保服务器已启动（`python app.py`）

## 环境变量

可通过环境变量覆盖默认配置（参考 `config.py`）：
- `FLASK_ENV`: development | production
- `PSI_MODE`: hash | ecc | multi | threshold
- `SECRET_KEY`: Flask密钥
- `JWT_SECRET`: JWT签名密钥
- `SSL_ENABLED`: true/false
