"""
配置文件
集中管理系统的各种配置参数
"""

import os


class Config:
    """基础配置"""

    # Flask配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'psi-ride-sharing-secret-2024')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

    # 数据库配置
    DB_PATH = os.getenv('DB_PATH', 'ride_sharing.db')

    # 服务器配置
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))

    # CORS配置
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')

    # PSI配置
    PSI_MODE = os.getenv('PSI_MODE', 'hash')  # hash, ecc, multi, threshold
    PSI_THRESHOLD = int(os.getenv('PSI_THRESHOLD', 3))

    # 安全配置
    JWT_SECRET = os.getenv('JWT_SECRET', 'psi-ride-jwt-secret-2024')
    JWT_EXPIRY_HOURS = int(os.getenv('JWT_EXPIRY_HOURS', 24))
    NONCE_WINDOW_SECONDS = int(os.getenv('NONCE_WINDOW_SECONDS', 300))  # 5分钟
    VERIFICATION_CODE_EXPIRY = int(os.getenv('VERIFICATION_CODE_EXPIRY', 300))  # 5分钟

    # HTTPS配置
    SSL_ENABLED = os.getenv('SSL_ENABLED', 'False').lower() == 'true'
    SSL_CERT = os.getenv('SSL_CERT', '')
    SSL_KEY = os.getenv('SSL_KEY', '')

    # 速率限制
    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 60))

    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')

    # 高德地图API配置
    AMAP_KEY = os.getenv('AMAP_KEY', 'c84d183be79e2f6d4ec4d361596e37b6')  # 高德开发者Web服务API Key
    AMAP_GEOCODE_URL = 'https://restapi.amap.com/v3/geocode/geo'
    AMAP_DRIVING_URL = 'https://restapi.amap.com/v3/direction/driving'


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SSL_ENABLED = False


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    SSL_ENABLED = True
    RATE_LIMIT_ENABLED = True


# 配置映射
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': Config
}


def get_config(env: str = None) -> Config:
    """
    获取配置

    Args:
        env: 环境名称 (development, production)

    Returns:
        配置对象
    """
    if env is None:
        env = os.getenv('FLASK_ENV', 'default')
    return config_map.get(env, Config)()
