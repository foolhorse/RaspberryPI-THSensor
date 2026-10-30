
import json
import os
import time

from bottle import route, run, static_file, request, response

from db import get_conn, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

# range 参数 -> 秒数；None 表示全部
RANGES = {
    '1h': 3600,
    '24h': 86400,
    '7d': 7 * 86400,
    '30d': 30 * 86400,
    '1y': 365 * 86400,
    '3y': 3 * 365 * 86400,
    '5y': 5 * 365 * 86400,
    'all': None,
}

MAX_POINTS = 600


def query_readings(conn, seconds, now=None):
    """在 SQLite 内按整数时间桶聚合，最多返回 MAX_POINTS 个点。"""
    if now is None:
        now = int(time.time())
    if seconds is None:
        first = conn.execute(
            'SELECT ts FROM readings ORDER BY ts ASC LIMIT 1'
        ).fetchone()
    else:
        first = conn.execute(
            'SELECT ts FROM readings WHERE ts >= ? ORDER BY ts ASC LIMIT 1',
            (now - seconds,),
        ).fetchone()
    if first is None:
        return []

    # 两次端点查询可利用已有 ts 索引，避免扫描全表计算 MIN/MAX。
    start = first[0]
    end = conn.execute(
        'SELECT ts FROM readings ORDER BY ts DESC LIMIT 1'
    ).fetchone()[0]
    bucket_seconds = max(1, (end - start + 1 + MAX_POINTS - 1) // MAX_POINTS)
    # 固定上下界，避免查询期间新写入的记录扩展桶数。
    return conn.execute(
        """
        SELECT CAST(AVG(ts) AS INTEGER),
               ROUND(AVG(temperature), 2), ROUND(AVG(humidity), 2)
        FROM readings
        WHERE ts >= ? AND ts <= ?
        GROUP BY (ts - ?) / ?
        ORDER BY (ts - ?) / ?
        """,
        (start, end, start, bucket_seconds, start, bucket_seconds),
    ).fetchall()


@route('/')
def index():
    return static_file('index.html', root=STATIC_DIR)


@route('/static/<path:path>')
def static(path):
    return static_file(path, root=STATIC_DIR)


@route('/api/latest')
def api_latest():
    response.content_type = 'application/json'
    conn = get_conn()
    try:
        row = conn.execute(
            'SELECT ts, temperature, humidity FROM readings ORDER BY ts DESC LIMIT 1'
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return json.dumps({'ok': True, 'data': None})
    return json.dumps({'ok': True, 'data': {
        'ts': row[0], 'temperature': row[1], 'humidity': row[2],
    }})


@route('/api/readings')
def api_readings():
    response.content_type = 'application/json'
    rng = request.query.get('range', '24h')
    if rng not in RANGES:
        rng = '24h'
    seconds = RANGES[rng]

    conn = get_conn()
    try:
        rows = query_readings(conn, seconds)
    finally:
        conn.close()

    data = [{'ts': r[0], 'temperature': r[1], 'humidity': r[2]} for r in rows]
    return json.dumps({'ok': True, 'data': data})


if __name__ == '__main__':
    init_db()
    # 老 Pi 单核，wsgiref 单线程完全够用，不要上 gunicorn
    run(host='0.0.0.0', port=8080, server='wsgiref')