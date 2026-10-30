import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DB_DIR, 'sensor.db')


def get_conn():
    """每次调用返回一个新连接。调用方负责 close()。"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('PRAGMA busy_timeout=10000')
    # WAL 模式：写不阻塞读，对「采集进程写 + Web 进程读」很关键
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_db():
    """幂等：建目录、建表、建索引。main/web/import 启动时都可以调。"""
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
        conn.execute('CREATE TABLE IF NOT EXISTS app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        # 新空库可直接使用汇总；旧库必须完成回填后才切换。
        if conn.execute('SELECT 1 FROM readings LIMIT 1').fetchone() is None:
            conn.execute("INSERT OR IGNORE INTO app_metadata VALUES ('hourly_ready', '1')")
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
        hour = ts // 3600 * 3600
        conn.execute('INSERT OR IGNORE INTO hourly_readings (hour_ts) VALUES (?)', (hour,))
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


def hourly_ready(conn):
    return conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'hourly_ready'"
    ).fetchone() == ('1',)
