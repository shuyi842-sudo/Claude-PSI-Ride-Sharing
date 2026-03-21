# PSI拼车系统 - 安全配置指南

## 概述

本系统实现了多层安全机制，确保无人驾驶拼车环境下的安全性和隐私保护。

## 安全功能

### 1. PSI隐私保护
- **MP-TPSI协议**: 多方门限隐私集合求交
- **算法模式**:
  - `hash`: MD5哈希（兼容模式）
  - `ecc`: ECC双方PSI
  - `multi`: ECC多方PSI
  - `threshold`: 门限PSI

### 2. JWT令牌认证
- 基于HMAC-SHA256的JWT实现
- 支持角色权限控制 (user, admin, vehicle)
- 可配置的过期时间（默认24小时）

### 3. 请求防重放攻击
- 使用Nonce机制防止重放攻击
- 时间窗口验证（默认5分钟）
- 自动清理过期nonce

### 4. 验证码保护
- 验证码有效期（默认5分钟）
- 防重复使用
- 绑定乘客/车辆ID

## 环境变量配置

### 基础配置
```bash
# Flask密钥（生产环境必须修改）
export SECRET_KEY="your-secret-key-here"

# JWT密钥
export JWT_SECRET="your-jwt-secret-here"

# 数据库路径
export DB_PATH="ride_sharing.db"
```

### HTTPS/SSL配置
```bash
# 启用HTTPS
export SSL_ENABLED="true"
export SSL_CERT="/path/to/cert.pem"
export SSL_KEY="/path/to/key.pem"
```

### PSI算法配置
```bash
# PSI模式选择
export PSI_MODE="ecc"  # hash, ecc, multi, threshold

# 门限PSI阈值
export PSI_THRESHOLD="3"
```

### 安全配置
```bash
# JWT过期时间（小时）
export JWT_EXPIRY_HOURS="24"

# 防重放时间窗口（秒）
export NONCE_WINDOW_SECONDS="300"

# 验证码有效期（秒）
export VERIFICATION_CODE_EXPIRY="300"
```

## HTTPS部署

### 使用自签名证书（开发/测试）
```bash
# 生成自签名证书
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# 启动HTTPS服务
export SSL_ENABLED="true"
export SSL_CERT="cert.pem"
export SSL_KEY="key.pem"
python app.py
```

### 使用Let's Encrypt证书（生产环境）
```bash
# 安装certbot
sudo apt-get install certbot

# 获取证书
sudo certbot certonly --standalone -d yourdomain.com

# 配置环境变量
export SSL_ENABLED="true"
export SSL_CERT="/etc/letsencrypt/live/yourdomain.com/fullchain.pem"
export SSL_KEY="/etc/letsencrypt/live/yourdomain.com/privkey.pem"
```

### 使用Nginx反向代理（推荐）

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /socket.io {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## API认证

### 获取JWT令牌
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'
```

### 使用令牌访问受保护API
```bash
curl -X GET http://localhost:5000/admin/stats \
  -H "Authorization: Bearer <your-jwt-token>"
```

## 安全检查清单

- [ ] 修改默认SECRET_KEY
- [ ] 修改默认JWT_SECRET
- [ ] 启用HTTPS
- [ ] 配置防火墙规则
- [ ] 启用日志记录
- [ ] 定期备份数据库
- [ ] 限制管理员访问IP
- [ ] 配置速率限制
- [ ] 监控异常访问

## 常见安全问题

### 1. SQL注入
系统使用SQLite参数化查询，有效防止SQL注入。

### 2. XSS攻击
所有用户输入都经过验证，前端使用textContent而非innerHTML（除必要位置）。

### 3. CSRF攻击
建议在生产环境配置CSRF保护。

### 4. 中间人攻击
使用HTTPS加密通信，防止中间人攻击。

## 故障排查

### 证书错误
```
SSL: CERTIFICATE_VERIFY_FAILED
```
确保SSL_CERT和SSL_KEY路径正确。

### 令牌过期
```
无效或过期的令牌
```
检查JWT_EXPIRY_HOURS配置，或刷新令牌。

### 防重放验证失败
```
请求被重放
```
检查客户端时间同步，确保时间戳准确。
