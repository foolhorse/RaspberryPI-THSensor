import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'data')  # 使用项目绝对路径，避免服务启动目录影响数据库位置。
DB_PATH = os.path.join(DB_DIR, 'sensor.db')


def get_conn():
    """每次调用返回一个新连接。调用方负责 close()。"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('PRAGMA busy_timeout=10000')
    # WAL 让采集进程写入时，Web 进程仍可读取已提交的快照，减少读写互相等待。
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_db():
    """幂等：建目录、建表、建索引。采集和 Web 启动时均可调用。"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_conn()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS readings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          INTEGER NOT NULL,
                temperature REAL,
                humidity    REAL
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts)')
        # 保存总和与有效条数，长期查询才能按样本数加权，而非简单平均小时均值。
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hourly_readings (
                hour_ts INTEGER PRIMARY KEY,
                reading_count INTEGER NOT NULL DEFAULT 0,
                ts_sum INTEGER NOT NULL DEFAULT 0,
                temperature_sum REAL NOT NULL DEFAULT 0,
                temperature_count INTEGER NOT NULL DEFAULT 0,
                humidity_sum REAL NOT NULL DEFAULT 0,
                humidity_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
    finally:
        conn.close()


def store_reading(conn, ts, temperature, humidity):
    """原始记录和小时统计一起提交，任一步失败则一起回滚。"""
    with conn:
        conn.execute(
            'INSERT INTO readings (ts, temperature, humidity) VALUES (?, ?, ?)',
            (ts, temperature, humidity),
        )
        hour = ts // 3600 * 3600  # Unix 秒对应的 UTC 小时起点，不依赖设备本地时区。
        conn.execute('INSERT OR IGNORE INTO hourly_readings (hour_ts) VALUES (?)', (hour,))
        # 空值对总和贡献为 0，也不计入该指标条数；时间戳仍计入所有记录。
        conn.execute('''
            UPDATE hourly_readings SET
                reading_count = reading_count + 1, ts_sum = ts_sum + ?,
                temperature_sum = temperature_sum + ?,
                temperature_count = temperature_count + ?,
                humidity_sum = humidity_sum + ?, humidity_count = humidity_count + ?
            WHERE hour_ts = ?
        ''', (ts, temperature if temperature is not None else 0,
              int(temperature is not None), humidity if humidity is not None else 0,
              int(humidity is not None), hour))
