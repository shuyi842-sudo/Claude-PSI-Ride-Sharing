# PSI无人驾驶拼车系统 API文档

## 基础信息

- **Base URL**: `http://localhost:5000`
- **响应格式**: JSON
- **字符编码**: UTF-8

---

## 1. 页面路由

### 1.1 首页
```
GET /
```
**响应**: HTML页面 - 身份选择界面

### 1.2 乘客端页面
```
GET /passenger
```
**响应**: HTML页面 - 乘客匹配界面

### 1.3 车辆端页面
```
GET /vehicle
```
**响应**: HTML页面 - 车辆注册与管理界面

### 1.4 验证页面
```
GET /verify
```
**响应**: HTML页面 - 上车验证界面

### 1.5 管理后台页面
```
GET /admin
```
**响应**: HTML页面 - 系统管理后台

---

## 2. 乘客接口

### 2.1 乘客注册
```
POST /passenger/register
```

**请求体**:
```json
{
  "passenger_id": "P001",
  "start": "北京中关村",
  "end": "北京西站"
}
```

**响应示例**:
```json
{
  "message": "乘客注册成功",
  "passenger": {
    "id": "P001",
    "start": "北京中关村",
    "end": "北京西站",
    "route": "北京中关村-北京西站",
    "status": "waiting",
    "created_at": "2024-01-01 12:00:00"
  }
}
```

### 2.2 请求匹配
```
POST /match
```

**请求体**:
```json
{
  "passenger_id": "P001"
}
```

**成功响应**:
```json
{
  "success": true,
  "message": "匹配成功！",
  "vehicle": {
    "id": "V001",
    "start": "北京中关村",
    "end": "北京西站",
    "seats": 3,
    "status": "available"
  },
  "match_code": "A160A5"
}
```

**失败响应**:
```json
{
  "success": false,
  "message": "暂无匹配车辆"
}
```

### 2.3 取消匹配
```
POST /cancel
```

**请求体**:
```json
{
  "passenger_id": "P001"
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "匹配已取消，座位已释放"
}
```

---

## 3. 车辆接口

### 3.1 车辆注册
```
POST /vehicle/register
```

**请求体**:
```json
{
  "vehicle_id": "V001",
  "start": "北京中关村",
  "end": "北京西站",
  "seats": 4
}
```

**响应示例**:
```json
{
  "message": "车辆注册成功",
  "vehicle": {
    "id": "V001",
    "start": "北京中关村",
    "end": "北京西站",
    "seats": 4,
    "status": "available"
  }
}
```

### 3.2 查看匹配乘客
```
GET /vehicle/check?vehicle_id=V001
```

**响应示例**:
```json
{
  "vehicle": {
    "id": "V001",
    "start": "北京中关村",
    "end": "北京西站",
    "seats": 3,
    "status": "available"
  },
  "matched_passengers": [
    {
      "id": "P001",
      "start": "北京中关村",
      "end": "北京西站",
      "status": "matched"
    }
  ]
}
```

---

## 4. 验证接口

### 4.1 上车验证
```
POST /verify
```

**请求体**:
```json
{
  "passenger_id": "P001",
  "vehicle_id": "V001",
  "code": "A160A5"
}
```

**成功响应**:
```json
{
  "success": true,
  "message": "验证成功，可以上车！",
  "psi_mode": "hash"
}
```

**失败响应**:
```json
{
  "success": false,
  "message": "验证失败！",
  "psi_mode": "hash"
}
```

---

## 5. PSI配置接口

### 5.1 获取PSI配置
```
GET /psi/config
```

**响应示例**:
```json
{
  "current_mode": "hash",
  "available_modes": {
    "hash": "MD5哈希（兼容模式）",
    "ecc": "ECC双方PSI",
    "multi": "ECC多方PSI",
    "threshold": "门限PSI"
  },
  "description": "MD5哈希（兼容模式）"
}
```

### 5.2 设置PSI模式
```
POST /psi/config
```

**请求体**:
```json
{
  "mode": "ecc"
}
```

**响应示例**:
```json
{
  "message": "PSI模式已切换为: ECC双方PSI",
  "current_mode": "ecc"
}
```

### 5.3 PSI验证码验证（独立API）
```
POST /psi/verify
```

**请求体**:
```json
{
  "passenger_id": "P001",
  "vehicle_id": "V001",
  "code": "A160A5"
}
```

**响应示例**:
```json
{
  "valid": true,
  "expected": "A160A5",
  "mode": "hash"
}
```

---

## 6. 管理后台接口

### 6.1 获取乘客列表
```
GET /admin/passengers
```

**响应示例**:
```json
[
  {
    "id": "P001",
    "start": "北京中关村",
    "end": "北京西站",
    "route": "北京中关村-北京西站",
    "status": "matched",
    "created_at": "2024-01-01 12:00:00"
  }
]
```

### 6.2 获取车辆列表
```
GET /admin/vehicles
```

**响应示例**:
```json
[
  {
    "id": "V001",
    "start": "北京中关村",
    "end": "北京西站",
    "seats": 3,
    "status": "available",
    "created_at": "2024-01-01 11:00:00"
  }
]
```

### 6.3 获取匹配记录
```
GET /admin/matches
```

**响应示例**:
```json
[
  {
    "id": 1,
    "passenger_id": "P001",
    "vehicle_id": "V001",
    "match_code": "A160A5",
    "status": "matched",
    "created_at": "2024-01-01 12:05:00"
  }
]
```

### 6.4 获取统计数据
```
GET /admin/stats
```

**响应示例**:
```json
{
  "total_passengers": 10,
  "matched_passengers": 5,
  "waiting_passengers": 5,
  "total_vehicles": 5,
  "available_vehicles": 3,
  "full_vehicles": 1,
  "total_matches": 5,
  "psi_mode": "hash"
}
```

---

## 7. 系统接口

### 7.1 重置系统
```
POST /reset
```
**注意**: 此接口仅用于测试，生产环境请谨慎使用。

**响应示例**:
```json
{
  "message": "数据已重置"
}
```

---

## 8. WebSocket事件

### 8.1 客户端事件

#### 加入车辆房间
```javascript
socket.emit('join_vehicle', { vehicle_id: 'V001' })
```

#### 离开车辆房间
```javascript
socket.emit('leave_vehicle')
```

#### 车辆状态更新
```javascript
socket.emit('vehicle_status_update', {
  vehicle_id: 'V001',
  timestamp: 1234567890
})
```

### 8.2 服务端事件

#### 连接成功
```javascript
socket.on('connected', (data) => {
  console.log('连接成功:', data)
})
```

#### 已加入房间
```javascript
socket.on('joined', (data) => {
  console.log('已加入房间:', data)
})
```

#### 新乘客匹配
```javascript
socket.on('new_passenger', (data) => {
  console.log('新乘客:', data.passenger)
})
```

#### 乘客已上车
```javascript
socket.on('passenger_boarded', (data) => {
  console.log('乘客已上车:', data.passenger_id)
})
```

#### 乘客取消匹配
```javascript
socket.on('passenger_cancelled', (data) => {
  console.log('乘客已取消:', data.passenger_id)
})
```

#### 系统重置
```javascript
socket.on('system_reset', (data) => {
  console.log('系统已重置:', data)
})
```

---

## 错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 401 | 未认证 |
| 403 | 权限不足 |
| 500 | 服务器内部错误 |

---

## PSI算法说明

### MD5哈希模式 (hash)
```
code = MD5(passenger_id + vehicle_id)[:6].upper()
```

### ECC双方PSI模式 (ecc)
```
shared_secret = ECDH(passenger_id, vehicle_id)
code = SHA256("PSI_2P:" + shared_secret)[:6].upper()
```

### ECC多方PSI模式 (multi)
```
code = SHA256("MP_PSI:" + passenger_id + ":" + vehicle_id + ":multi")[:6].upper()
```

### 门限PSI模式 (threshold)
```
code = SHA256("TH_PSI:" + passenger_id + ":" + vehicle_id + ":threshold_3_of_5")[:6].upper()
```

---

## 示例代码

### Python示例
```python
import requests

BASE_URL = "http://localhost:5000"

# 注册乘客
requests.post(f"{BASE_URL}/passenger/register", json={
    "passenger_id": "P001",
    "start": "北京中关村",
    "end": "北京西站"
})

# 请求匹配
response = requests.post(f"{BASE_URL}/match", json={
    "passenger_id": "P001"
})
data = response.json()

if data["success"]:
    print(f"验证码: {data['match_code']}")
```

### JavaScript示例
```javascript
// 注册乘客
fetch('http://localhost:5000/passenger/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    passenger_id: 'P001',
    start: '北京中关村',
    end: '北京西站'
  })
})
.then(res => res.json())
.then(data => console.log(data));

// 请求匹配
fetch('http://localhost:5000/match', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ passenger_id: 'P001' })
})
.then(res => res.json())
.then(data => {
  if (data.success) {
    console.log(`验证码: ${data.match_code}`);
  }
});
```
