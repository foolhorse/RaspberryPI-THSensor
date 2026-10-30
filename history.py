import time

MAX_POINTS = 600  # 限制接口返回量，避免浏览器绘图负担随历史数据量增长。


def query_raw_readings(conn, seconds, now=None):
    """在 SQLite 内按整数时间桶聚合，最多返回 MAX_POINTS 个点。"""
    if now is None:
        now = int(time.time())
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
    # 闭区间跨度加 1，再向上取整，保证末端记录不会落入第 601 个桶。
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


def query_readings(conn, seconds, now=None):
    """短范围查原始表；长期查小时统计，起点不足一小时部分精确回查。"""
    # 短期保留原始采样细节，长期只扫描小时统计；None 表示全部历史。
    if seconds is not None and seconds <= 86400:
        return query_raw_readings(conn, seconds, now)
    if now is None:
        now = int(time.time())
    start = None if seconds is None else now - seconds
    # 小时内的起点不能直接使用整小时统计，否则会包含范围外数据。
    if start is None:
        first = conn.execute('SELECT hour_ts FROM hourly_readings ORDER BY hour_ts LIMIT 1').fetchone()
        if first is None:
            return []
        start = first[0]
    # [start, full_start) 从原始表读取；[full_start, last] 从汇总表读取，互不重叠。
    first_hour = start // 3600 * 3600
    full_start = ((start + 3599) // 3600) * 3600
    last = conn.execute('SELECT hour_ts FROM hourly_readings ORDER BY hour_ts DESC LIMIT 1').fetchone()
    if last is None or last[0] < first_hour:
        return []
    bucket_hours = max(1, ((last[0] - first_hour) // 3600 + MAX_POINTS) // MAX_POINTS)
    # UNION 中每行都是可加权统计，避免对小时平均值再做简单平均。
    # 空的边界查询也会产生一行 COUNT(*)=0，外层将其过滤；NULLIF 处理指标全为空的桶。
    return conn.execute('''
        WITH stats AS (
            SELECT hour_ts, ts_sum, reading_count, temperature_sum,
                   temperature_count, humidity_sum, humidity_count
            FROM hourly_readings WHERE hour_ts >= ? AND hour_ts <= ?
            UNION ALL
            SELECT ?, COALESCE(SUM(ts), 0), COUNT(*),
                   COALESCE(SUM(temperature), 0), COUNT(temperature),
                   COALESCE(SUM(humidity), 0), COUNT(humidity)
            FROM readings WHERE ts >= ? AND ts < ?
        )
        SELECT CAST(SUM(ts_sum) / SUM(reading_count) AS INTEGER),
               ROUND(SUM(temperature_sum) / NULLIF(SUM(temperature_count), 0), 2),
               ROUND(SUM(humidity_sum) / NULLIF(SUM(humidity_count), 0), 2)
        FROM stats
        WHERE reading_count > 0
        GROUP BY (hour_ts - ?) / ?
        ORDER BY MIN(hour_ts)
    ''', (full_start, last[0], first_hour, start, full_start,
          first_hour, bucket_hours * 3600)).fetchall()
