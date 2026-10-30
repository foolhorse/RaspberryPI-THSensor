"""停掉采集和 Web 服务后运行：.venv/bin/python backfill_hourly.py。"""
import math
import os

from db import DB_PATH, get_conn, init_db


def verify(conn):
    raw = conn.execute('''
        SELECT COUNT(*), COALESCE(SUM(ts), 0), COUNT(temperature),
               COUNT(humidity), COALESCE(SUM(temperature), 0), COALESCE(SUM(humidity), 0)
        FROM readings
    ''').fetchone()
    summary = conn.execute('''
        SELECT COALESCE(SUM(reading_count), 0), COALESCE(SUM(ts_sum), 0),
               COALESCE(SUM(temperature_count), 0), COALESCE(SUM(humidity_count), 0),
               COALESCE(SUM(temperature_sum), 0), COALESCE(SUM(humidity_sum), 0)
        FROM hourly_readings
    ''').fetchone()
    if raw[:4] != summary[:4] or not all(
        math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)
        for a, b in zip(raw[4:], summary[4:])
    ):
        raise RuntimeError('汇总核对失败，未启用小时查询；请确认服务已停止后重新运行')
    return raw[0]


def backfill(conn, progress=print):
    with conn:
        conn.execute("INSERT OR REPLACE INTO app_metadata VALUES ('hourly_ready', '0')")
    first = conn.execute('SELECT ts FROM readings ORDER BY ts LIMIT 1').fetchone()
    last = conn.execute('SELECT ts FROM readings ORDER BY ts DESC LIMIT 1').fetchone()
    # 每次重算，既支持中断后重跑，也能清除原始数据删除后留下的旧统计。
    with conn:
        conn.execute('DELETE FROM hourly_readings')
    if first is not None:
        day = first[0] // 86400 * 86400
        while day <= last[0]:
            with conn:
                conn.execute('''
                    INSERT INTO hourly_readings
                    (hour_ts, reading_count, ts_sum, temperature_sum,
                     temperature_count, humidity_sum, humidity_count)
                    SELECT (ts / 3600) * 3600, COUNT(*), SUM(ts),
                           COALESCE(SUM(temperature), 0), COUNT(temperature),
                           COALESCE(SUM(humidity), 0), COUNT(humidity)
                    FROM readings WHERE ts >= ? AND ts < ?
                    GROUP BY (ts / 3600) * 3600
                ''', (day, day + 86400))
            progress('已回填 UTC 日起点：{}'.format(day))
            day += 86400
    count = verify(conn)
    with conn:
        conn.execute("INSERT OR REPLACE INTO app_metadata VALUES ('hourly_ready', '1')")
    progress('完成：核对 {} 条原始记录，已启用小时汇总查询。'.format(count))


def main():
    if not os.path.isfile(DB_PATH):
        raise SystemExit('数据库不存在：{}'.format(DB_PATH))
    print('请确保采集和 Web 服务均已停止。正在按天重建小时汇总。', flush=True)
    init_db()
    conn = get_conn()
    try:
        backfill(conn, progress=lambda message: print(message, flush=True))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
