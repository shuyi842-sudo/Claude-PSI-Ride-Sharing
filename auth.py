"""
安全认证模块
包含JWT令牌、请求防重放、验证码有效期等功能
"""

import hashlib
import hmac
import time
import json
from functools import wraps
from typing import Optional, Dict, Callable, Any
from collections import defaultdict


# ========== JWT令牌管理 ==========

class JWTManager:
    """简化版JWT令牌管理（生产环境应使用PyJWT库）"""

    def __init__(self, secret: str = "psi-ride-jwt-secret-2024", expiry_hours: int = 24):
        self.secret = secret
        self.expiry_hours = expiry_hours

    def generate_token(self, user_id: str, role: str = "user") -> str:
        """
        生成JWT令牌

        Args:
            user_id: 用户ID
            role: 用户角色 (user, admin, vehicle)

        Returns:
            JWT令牌字符串
        """
        header = {
            "alg": "HS256",
            "typ": "JWT"
        }

        payload = {
            "user_id": user_id,
            "role": role,
            "iat": int(time.time()),
            "exp": int(time.time()) + (self.expiry_hours * 3600)
        }

        # 简化版JWT：header.payload.signature
        header_b64 = self._base64url_encode(json.dumps(header, separators=(',', ':')))
        payload_b64 = self._base64url_encode(json.dumps(payload, separators=(',', ':')))

        message = f"{header_b64}.{payload_b64}"
        signature = self._hmac_sha256(message, self.secret)
        signature_b64 = self._base64url_encode(signature)

        return f"{message}.{signature_b64}"

    def verify_token(self, token: str) -> tuple[bool, Optional[Dict]]:
        """
        验证JWT令牌

        Returns:
            (是否有效, payload字典)
        """
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return False, None

            header_b64, payload_b64, signature_b64 = parts
            message = f"{header_b64}.{payload_b64}"

            # 验证签名
            expected_signature = self._hmac_sha256(message, self.secret)
            expected_signature_b64 = self._base64url_encode(expected_signature)

            if not hmac.compare_digest(signature_b64, expected_signature_b64):
                return False, None

            # 解析payload
            payload_json = self._base64url_decode(payload_b64)
            payload = json.loads(payload_json)

            # 检查过期
            if payload.get("exp", 0) < int(time.time()):
                return False, None

            return True, payload

        except Exception:
            return False, None

    @staticmethod
    def _base64url_encode(data: str) -> str:
        """Base64 URL编码"""
        import base64
        return base64.urlsafe_b64encode(data.encode()).decode().rstrip('=')

    @staticmethod
    def _base64url_decode(data: str) -> str:
        """Base64 URL解码"""
        import base64
        # 添加填充
        padding = 4 - len(data) % 4
        if padding != 4:
            data += '=' * padding
        return base64.urlsafe_b64decode(data).decode()

    @staticmethod
    def _hmac_sha256(message: str, secret: str) -> str:
        """HMAC-SHA256签名"""
        return hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()


# ========== 请求防重放攻击 ==========

class ReplayProtection:
    """请求防重放攻击保护"""

    def __init__(self, window_seconds: int = 300):
        """
        初始化防重放保护

        Args:
            window_seconds: 时间窗口（秒），默认5分钟
        """
        self.window_seconds = window_seconds
        # 存储已使用的nonce: {nonce: timestamp}
        self._used_nonces: Dict[str, float] = defaultdict(float)
        self._cleanup_interval = 60
        self._last_cleanup = time.time()

    def generate_nonce(self) -> str:
        """生成唯一的nonce"""
        import uuid
        return f"{int(time.time())}-{uuid.uuid4().hex[:16]}"

    def validate_nonce(self, nonce: str, timestamp: float) -> bool:
        """
        验证nonce

        Args:
            nonce: 请求的nonce值
            timestamp: 请求的时间戳

        Returns:
            是否有效
        """
        current_time = time.time()

        # 定期清理过期nonce
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup()

        # 检查时间戳是否在有效窗口内
        if abs(current_time - timestamp) > self.window_seconds:
            return False

        # 检查nonce是否已使用
        if nonce in self._used_nonces:
            return False

        # 记录已使用的nonce
        self._used_nonces[nonce] = current_time
        return True

    def _cleanup(self):
        """清理过期的nonce"""
        current_time = time.time()
        expired = [
            nonce for nonce, ts in self._used_nonces.items()
            if current_time - ts > self.window_seconds
        ]
        for nonce in expired:
            del self._used_nonces[nonce]
        self._last_cleanup = current_time


# ========== 验证码管理 ==========

class VerificationCodeManager:
    """验证码管理器 - 支持有效期和防重放"""

    def __init__(self, expiry_seconds: int = 300):
        """
        初始化验证码管理器

        Args:
            expiry_seconds: 验证码有效期（秒），默认5分钟
        """
        self.expiry_seconds = expiry_seconds
        # 存储验证码: {code: (timestamp, p_id, v_id, used)}
        self._codes: Dict[str, tuple] = {}
        self.replay_protection = ReplayProtection(expiry_seconds)

    def generate(self, p_id: str, v_id: str) -> str:
        """
        生成验证码

        Returns:
            验证码字符串
        """
        nonce = self.replay_protection.generate_nonce()
        raw = f"{p_id}{v_id}{nonce}"
        code = hashlib.md5(raw.encode()).hexdigest()[:6].upper()

        timestamp = time.time()
        self._codes[code] = (timestamp, p_id, v_id, False)

        return code

    def verify(self, code: str, p_id: str, v_id: str) -> tuple[bool, str]:
        """
        验证码验证

        Returns:
            (是否有效, 错误消息)
        """
        if code not in self._codes:
            return False, "验证码不存在"

        timestamp, stored_p_id, stored_v_id, used = self._codes[code]

        # 检查是否已使用
        if used:
            return False, "验证码已使用"

        # 检查是否过期
        if time.time() - timestamp > self.expiry_seconds:
            return False, "验证码已过期"

        # 检查乘客和车辆ID是否匹配
        if stored_p_id != p_id or stored_v_id != v_id:
            return False, "验证码与乘客/车辆不匹配"

        # 标记为已使用
        self._codes[code] = (timestamp, stored_p_id, stored_v_id, True)

        return True, "验证成功"

    def cleanup_expired(self):
        """清理过期的验证码"""
        current_time = time.time()
        expired = [
            code for code, (ts, _, _, _) in self._codes.items()
            if current_time - ts > self.expiry_seconds
        ]
        for code in expired:
            del self._codes[code]


# ========== Flask装饰器 ==========

def require_auth(jwt_manager: JWTManager, allowed_roles: list = None):
    """
    需要认证的装饰器

    Args:
        jwt_manager: JWT管理器实例
        allowed_roles: 允许的角色列表，None表示所有角色
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request, jsonify

            # 从请求头获取token
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return jsonify({"error": "缺少认证令牌"}), 401

            token = auth_header[7:]  # 移除 'Bearer ' 前缀

            # 验证token
            is_valid, payload = jwt_manager.verify_token(token)
            if not is_valid:
                return jsonify({"error": "无效或过期的令牌"}), 401

            # 检查角色
            if allowed_roles and payload.get("role") not in allowed_roles:
                return jsonify({"error": "权限不足"}), 403

            # 将用户信息附加到请求上下文
            request.user = payload

            return f(*args, **kwargs)

        return decorated_function
    return decorator


# ========== 全局实例 ==========

_jwt_manager: Optional[JWTManager] = None
_replay_protection: Optional[ReplayProtection] = None
_verification_manager: Optional[VerificationCodeManager] = None


def get_jwt_manager() -> JWTManager:
    """获取JWT管理器（单例）"""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


def get_replay_protection() -> ReplayProtection:
    """获取防重放保护（单例）"""
    global _replay_protection
    if _replay_protection is None:
        _replay_protection = ReplayProtection()
    return _replay_protection


def get_verification_manager() -> VerificationCodeManager:
    """获取验证码管理器（单例）"""
    global _verification_manager
    if _verification_manager is None:
        _verification_manager = VerificationCodeManager()
    return _verification_manager
