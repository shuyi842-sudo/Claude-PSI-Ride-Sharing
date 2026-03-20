"""
SQLite 数据库模型和操作
无人驾驶拼车系统 - 数据持久化层
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "ride_sharing.db"


@contextmanager
def get_db():
    """获取数据库连接上下文管理器"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构"""
    with get_db() as conn:
        cursor = conn.cursor()

        # 乘客表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS passengers (
                id TEXT PRIMARY KEY,
                start TEXT NOT NULL,
                end TEXT NOT NULL,
                route TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 车辆表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id TEXT PRIMARY KEY,
                start TEXT NOT NULL,
                end TEXT NOT NULL,
                route TEXT NOT NULL,
                seats INTEGER NOT NULL DEFAULT 4,
                status TEXT NOT NULL DEFAULT 'available',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 匹配关系表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                passenger_id TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                match_code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'matched',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (passenger_id) REFERENCES passengers(id),
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passenger_status ON passengers(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_status ON vehicles(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_passenger ON matches(passenger_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_vehicle ON matches(vehicle_id)")

        print(f"✓ 数据库初始化完成: {DB_PATH}")


def reset_db():
    """重置数据库（清空所有数据）"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM matches")
        cursor.execute("DELETE FROM passengers")
        cursor.execute("DELETE FROM vehicles")
        print("✓ 数据库已重置")


# 乘客操作
def passenger_exists(p_id):
    """检查乘客是否存在"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM passengers WHERE id = ?", (p_id,))
        return cursor.fetchone() is not None


def get_passenger(p_id):
    """获取乘客信息"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM passengers WHERE id = ?", (p_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def create_passenger(p_id, start, end):
    """创建乘客"""
    with get_db() as conn:
        cursor = conn.cursor()
        route = f"{start}-{end}"
        cursor.execute(
            "INSERT OR REPLACE INTO passengers (id, start, end, route, status) VALUES (?, ?, ?, ?, 'waiting')",
            (p_id, start, end, route)
        )
        return {"id": p_id, "start": start, "end": end, "route": route, "status": "waiting"}


def update_passenger_status(p_id, status):
    """更新乘客状态"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE passengers SET status = ? WHERE id = ?", (status, p_id))


def get_all_passengers():
    """获取所有乘客"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM passengers")
        return [dict(row) for row in cursor.fetchall()]


# 车辆操作
def vehicle_exists(v_id):
    """检查车辆是否存在"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM vehicles WHERE id = ?", (v_id,))
        return cursor.fetchone() is not None


def get_vehicle(v_id):
    """获取车辆信息"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vehicles WHERE id = ?", (v_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def create_vehicle(v_id, start, end, seats=4):
    """创建车辆"""
    with get_db() as conn:
        cursor = conn.cursor()
        route = f"{start}-{end}"
        cursor.execute(
            "INSERT OR REPLACE INTO vehicles (id, start, end, route, seats, status) VALUES (?, ?, ?, ?, ?, 'available')",
            (v_id, start, end, route, seats)
        )
        return {"id": v_id, "start": start, "end": end, "route": route, "seats": seats, "status": "available"}


def update_vehicle_status(v_id, status):
    """更新车辆状态"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE vehicles SET status = ? WHERE id = ?", (status, v_id))


def update_vehicle_seats(v_id, seats):
    """更新车辆座位数"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE vehicles SET seats = ? WHERE id = ?", (seats, v_id))


def get_available_vehicles():
    """获取所有可用车辆"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vehicles WHERE status = 'available' AND seats > 0")
        return [dict(row) for row in cursor.fetchall()]


def get_all_vehicles():
    """获取所有车辆"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vehicles")
        return [dict(row) for row in cursor.fetchall()]


# 匹配操作
def create_match(p_id, v_id, match_code):
    """创建匹配记录"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO matches (passenger_id, vehicle_id, match_code) VALUES (?, ?, ?)",
            (p_id, v_id, match_code)
        )
        return cursor.lastrowid


def get_match_by_passenger(p_id):
    """根据乘客ID获取匹配"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE passenger_id = ? ORDER BY created_at DESC LIMIT 1", (p_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_match_by_vehicle(v_id):
    """根据车辆ID获取所有匹配"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT m.*, p.start as passenger_start, p.end as passenger_end
               FROM matches m
               JOIN passengers p ON m.passenger_id = p.id
               WHERE m.vehicle_id = ?""",
            (v_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def delete_match_by_passenger(p_id):
    """删除乘客的匹配记录"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM matches WHERE passenger_id = ?", (p_id,))


def get_all_matches():
    """获取所有匹配"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches")
        return [dict(row) for row in cursor.fetchall()]


def reset_matches():
    """清空匹配表"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM matches")
