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
        conn.commit()
    finally:
        conn.close()