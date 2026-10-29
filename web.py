
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
    'all': None,
}

MAX_POINTS = 600  # 超过就降采样，避免前端画几万个点


def downsample(rows, max_points):
    """按行数分桶取平均。够用，不追求严格等间隔。"""
    if len(rows) <= max_points:
        return rows
    bucket = max(1, len(rows) // max_points)
    result = []
    for i in range(0, len(rows), bucket):
        chunk = rows[i:i + bucket]
        ts_avg = sum(r[0] for r in chunk) // len(chunk)
        t_vals = [r[1] for r in chunk if r[1] is not None]
        h_vals = [r[2] for r in chunk if r[2] is not None]
        t_avg = round(sum(t_vals) / len(t_vals), 2) if t_vals else None
        h_avg = round(sum(h_vals) / len(h_vals), 2) if h_vals else None
        result.append((ts_avg, t_avg, h_avg))
    return result


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
        if seconds is None:
            rows = conn.execute(
                'SELECT ts, temperature, humidity FROM readings ORDER BY ts ASC'
            ).fetchall()
        else:
            start = int(time.time()) - seconds
            rows = conn.execute(
                'SELECT ts, temperature, humidity FROM readings WHERE ts >= ? ORDER BY ts ASC',
                (start,),
            ).fetchall()
    finally:
        conn.close()

    rows = downsample(rows, MAX_POINTS)
    data = [{'ts': r[0], 'temperature': r[1], 'humidity': r[2]} for r in rows]
    return json.dumps({'ok': True, 'data': data})


if __name__ == '__main__':
    init_db()
    # 老 Pi 单核，wsgiref 单线程完全够用，不要上 gunicorn
    run(host='0.0.0.0', port=8080, server='wsgiref')