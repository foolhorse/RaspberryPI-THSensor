
import json
import os
import time

from bottle import route, run, static_file, request, response

from db import get_conn, init_db
from history import query_readings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

# range 参数 -> 秒数；年按 365 天计算，None 表示全部历史。
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



@route('/')
def index():
    return static_file('index.html', root=STATIC_DIR)


@route('/static/<path:path>')
def static(path):
    return static_file(path, root=STATIC_DIR)


@route('/api/latest')
def api_latest():
    """供页面顶部独立刷新最新读数，不执行历史聚合。"""
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
    """统一返回原始或小时统计聚合后的曲线数据，由查询层选择数据源。"""
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
    # 使用轻量的单线程服务；同一时刻的其他请求需要等待当前查询完成。
    run(host='0.0.0.0', port=8080, server='wsgiref')
