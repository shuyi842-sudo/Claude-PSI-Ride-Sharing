# 无人驾驶共享出行系统（基于PSI隐私集合求交）

## 项目概述

基于隐私集合求交（PSI）技术的无人驾驶共享出行系统，解决无人驾驶环境下乘客身份确认和隐私保护问题。

### 核心问题

1. **身份确认难题**：无人驾驶环境中无法通过司机确认乘客身份
2. **隐私泄露风险**：传统方案可能导致私人出行路线泄露
3. **搭错车风险**：缺乏有效的身份验证机制

### 解决方案

采用 **MP-TPSI（Multi-Party Threshold PSI）协议**：
- PSI隐私计算生成匹配验证码
- 无需传输原始身份信息
- 实现匹配精度与隐私保护的平衡

## 项目结构

```
D:\Claude_PSI_project/
├── app.py                 # Flask后端主程序
├── test_api.py            # API测试套件（15个测试用例）
├── templates/             # HTML模板
│   ├── index.html         # 首页（身份选择）
│   ├── passenger.html     # 乘客端（匹配+验证码）
│   ├── vehicle.html      # 车辆端（注册+查看乘客）
│   └── verify.html       # 上车验证页面
└── static/
    └── style.css         # 响应式样式
```

## API 接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 首页 |
| `/passenger` | GET | 乘客端页面 |
| `/vehicle` | GET | 车辆端页面 |
| `/verify` | GET | 验证页面 |
| `/passenger/register` | POST | 乘客注册 |
| `/vehicle/register` | POST | 车辆注册 |
| `/match` | POST | 乘客请求匹配 |
| `/vehicle/check` | GET | 车辆查看匹配乘客 |
| `/verify` | POST | 上车验证码验证 |
| `/cancel` | POST | 取消匹配 |
| `/reset` | POST | 重置数据（仅测试） |

## 运行方式

```bash
# 安装依赖
pip install flask flask-cors requests

# 启动服务
python app.py

# 访问
http://localhost:5000

# 运行测试
python test_api.py
```

## PSI 验证码生成

验证码基于乘客ID和车辆ID通过哈希计算：
```python
def generate_match_code(p_id, v_id):
    raw = f"{p_id}{v_id}"
    return hashlib.md5(raw.encode()).hexdigest()[:6].upper()
```

## 路线匹配算法

基于区域相似度的简化匹配（未来可替换为真正的PSI算法）：
```python
def route_similarity(route1, route2):
    area1 = route1[:3]
    area2 = route2[:3]
    return 0.9 if area1 == area2 else 0.1
```

## 开发规范

- 使用中文进行代码注释和用户界面
- 保持前后端分离，使用 fetch API 通信
- 新功能需添加对应测试用例
- 使用 git 提交代码，遵循约定式提交格式
