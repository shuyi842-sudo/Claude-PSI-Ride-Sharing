"""
安全审计日志系统

记录系统中的敏感操作、可疑活动和PSI操作，用于安全审计和问题追踪。
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import os
import time


@dataclass
class AuditEvent:
    """审计事件"""
    timestamp: str
    event_type: str
    severity: str  # INFO, WARNING, ERROR, CRITICAL
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    result: Optional[str] = None  # SUCCESS, FAILURE


class SecurityAuditLogger:
    """
    安全审计日志系统

    功能：
    - 记录敏感操作
    - 检测可疑活动
    - 记录PSI操作
    - 日志轮转和归档
    """

    def __init__(self, log_file: str = 'security_audit.log'):
        """
        初始化安全审计日志系统

        Args:
            log_file: 日志文件路径
        """
        self.log_file = log_file
        self.logger = self._setup_logger()
        self.suspicious_threshold = {
            'failed_login': 5,      # 5次失败登录
            'failed_verification': 10, # 10次验证失败
            'api_rate_limit': 100     # 100次/分钟
        }
        self.suspicious_activities = {}  # {ip_or_id: {event_type: [timestamps]}}
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        """确保日志目录存在"""
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('security_audit')
        logger.setLevel(logging.INFO)

        # 避免重复添加handler
        if not logger.handlers:
            # 文件handler
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)

            # JSON格式formatter
            json_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(json_formatter)

            # 控制台handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)

            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

        return logger

    def log_event(self, event: AuditEvent):
        """
        记录审计事件

        Args:
            event: 审计事件对象
        """
        log_data = asdict(event)
        log_message = json.dumps(log_data, ensure_ascii=False)

        # 根据严重性选择日志级别
        severity_map = {
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }

        log_level = severity_map.get(event.severity, logging.INFO)
        self.logger.log(log_level, log_message)

    def log_sensitive_operation(self, operation: str, user_id: str,
                               details: Dict[str, Any] = None,
                               result: str = 'SUCCESS'):
        """
        记录敏感操作

        Args:
            operation: 操作类型（如 passenger_register, vehicle_register, match）
            user_id: 用户ID
            details: 操作详情
            result: 操作结果
        """
        event = AuditEvent(
            timestamp=datetime.now().isoformat(),
            event_type=f"sensitive_operation_{operation}",
            severity='INFO' if result == 'SUCCESS' else 'WARNING',
            user_id=user_id,
            details=details,
            result=result
        )
        self.log_event(event)

    def log_suspicious_activity(self, event_type: str, identifier: str,
                               details: str, ip_address: str = None):
        """
        记录可疑活动

        Args:
            event_type: 可疑活动类型（如 failed_login, api_abuse）
            identifier: 用户ID或IP地址
            details: 活动详情
            ip_address: IP地址
        """
        # 记录到可疑活动追踪
        key = identifier
        if key not in self.suspicious_activities:
            self.suspicious_activities[key] = {}

        now = time.time()
        if event_type not in self.suspicious_activities[key]:
            self.suspicious_activities[key][event_type] = []

        # 添加时间戳（保留最近100个）
        self.suspicious_activities[key][event_type].append(now)
        if len(self.suspicious_activities[key][event_type]) > 100:
            self.suspicious_activities[key][event_type] = \
                self.suspicious_activities[key][event_type][-100:]

        # 检查是否超过阈值
        is_threshold_exceeded = self._check_suspicious_threshold(
            key, event_type, self.suspicious_threshold.get(event_type, 10)
        )

        severity = 'CRITICAL' if is_threshold_exceeded else 'WARNING'

        event = AuditEvent(
            timestamp=datetime.now().isoformat(),
            event_type=f"suspicious_{event_type}",
            severity=severity,
            user_id=identifier if '@' in str(identifier) else None,
            ip_address=ip_address or (identifier if not '@' in str(identifier) else None),
            details={'message': details, 'count': len(self.suspicious_activities[key][event_type])}
        )
        self.log_event(event)

    def log_psi_operation(self, mode: str, participants: List[str],
                          result: str, user_id: str = None):
        """
        记录PSI操作

        Args:
            mode: PSI模式（hash, ecc, multi, threshold）
            participants: 参与方ID列表
            result: 操作结果
            user_id: 用户ID
        """
        event = AuditEvent(
            timestamp=datetime.now().isoformat(),
            event_type='psi_operation',
            severity='INFO' if result == 'SUCCESS' else 'WARNING',
            user_id=user_id,
            details={
                'mode': mode,
                'participants': participants,
                'participant_count': len(participants)
            },
            result=result
        )
        self.log_event(event)

    def log_authentication(self, user_id: str, method: str,
                         success: bool, ip_address: str = None):
        """
        记录认证操作

        Args:
            user_id: 用户ID
            method: 认证方式（password, token, code）
            success: 是否成功
            ip_address: IP地址
        """
        if success:
            self.log_sensitive_operation(
                'authentication_success',
                user_id,
                {'method': method},
                'SUCCESS'
            )
        else:
            self.log_suspicious_activity(
                'failed_login',
                user_id if '@' in str(user_id) else ip_address or user_id,
                f'Authentication failed using {method}',
                ip_address
            )

    def log_api_call(self, endpoint: str, method: str,
                    user_id: str = None, ip_address: str = None,
                    status_code: int = 200, response_time: float = 0):
        """
        记录API调用

        Args:
            endpoint: API端点
            method: HTTP方法
            user_id: 用户ID
            ip_address: IP地址
            status_code: HTTP状态码
            response_time: 响应时间（秒）
        """
        # 记录慢请求和错误
        is_slow = response_time > 2.0
        is_error = status_code >= 400

        if is_slow or is_error:
            event = AuditEvent(
                timestamp=datetime.now().isoformat(),
                event_type=f'api_call_{"slow" if is_slow else "error"}',
                severity='WARNING' if is_slow else 'ERROR',
                user_id=user_id,
                ip_address=ip_address,
                details={
                    'endpoint': endpoint,
                    'method': method,
                    'status_code': status_code,
                    'response_time': response_time
                }
            )
            self.log_event(event)

    def log_data_access(self, data_type: str, record_id: str,
                       user_id: str, access_type: str = 'read'):
        """
        记录数据访问

        Args:
            data_type: 数据类型（passenger, vehicle, match）
            record_id: 记录ID
            user_id: 访问用户ID
            access_type: 访问类型（read, write, delete）
        """
        event = AuditEvent(
            timestamp=datetime.now().isoformat(),
            event_type='data_access',
            severity='WARNING' if access_type == 'delete' else 'INFO',
            user_id=user_id,
            details={
                'data_type': data_type,
                'record_id': record_id,
                'access_type': access_type
            }
        )
        self.log_event(event)

    def _check_suspicious_threshold(self, identifier: str, event_type: str,
                                   threshold: int, time_window: int = 300) -> bool:
        """
        检查是否超过可疑活动阈值

        Args:
            identifier: 用户ID或IP
            event_type: 事件类型
            threshold: 阈值
            time_window: 时间窗口（秒）

        Returns:
            是否超过阈值
        """
        if identifier not in self.suspicious_activities:
            return False

        if event_type not in self.suspicious_activities[identifier]:
            return False

        timestamps = self.suspicious_activities[identifier][event_type]
        now = time.time()

        # 统计时间窗口内的事件数
        recent_count = sum(1 for t in timestamps if now - t <= time_window)

        return recent_count >= threshold

    def get_suspicious_report(self, time_window: int = 3600) -> Dict[str, Any]:
        """
        获取可疑活动报告

        Args:
            time_window: 时间窗口（秒）

        Returns:
            可疑活动报告字典
        """
        now = time.time()
        report = {
            'timestamp': datetime.now().isoformat(),
            'time_window_seconds': time_window,
            'suspicious_entities': []
        }

        for identifier, events in self.suspicious_activities.items():
            for event_type, timestamps in events.items():
                recent_count = sum(1 for t in timestamps if now - t <= time_window)
                if recent_count > 0:
                    report['suspicious_entities'].append({
                        'identifier': identifier,
                        'event_type': event_type,
                        'recent_count': recent_count,
                        'is_critical': recent_count >= self.suspicious_threshold.get(event_type, 10)
                    })

        # 按数量降序排序
        report['suspicious_entities'].sort(
            key=lambda x: x['recent_count'],
            reverse=True
        )

        return report

    def clear_old_activities(self, time_threshold: int = 86400):
        """
        清理旧的可疑活动记录

        Args:
            time_threshold: 时间阈值（秒），默认24小时
        """
        now = time.time()
        for identifier in list(self.suspicious_activities.keys()):
            for event_type in list(self.suspicious_activities[identifier].keys()):
                # 保留最近的记录
                self.suspicious_activities[identifier][event_type] = [
                    t for t in self.suspicious_activities[identifier][event_type]
                    if now - t <= time_threshold
                ]

                # 如果没有记录了，删除
                if not self.suspicious_activities[identifier][event_type]:
                    del self.suspicious_activities[identifier][event_type]

            # 如果没有事件类型了，删除标识符
            if not self.suspicious_activities[identifier]:
                del self.suspicious_activities[identifier]


# 全局实例
_audit_logger: Optional[SecurityAuditLogger] = None


def get_audit_logger(log_file: str = 'security_audit.log') -> SecurityAuditLogger:
    """获取安全审计日志实例（单例）"""
    global _audit_logger
    if _audit_logger is None or _audit_logger.log_file != log_file:
        _audit_logger = SecurityAuditLogger(log_file)
    return _audit_logger
