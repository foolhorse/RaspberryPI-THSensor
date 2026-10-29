# /home/pi/file/RaspberryPI-THSensor/import_csv.py
import csv
import os
from datetime import datetime

from db import get_conn, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'log.csv')

BATCH = 50000  # 每 5 万条提交一次，兼顾速度与内存


def parse_row(row):
    # CSV 格式: Date(%m/%d/%y),Time(%H:%M),Temperature,Humidity
    dt = datetime.strptime(
        '{} {}'.format(row[0].strip(), row[1].strip()),
        '%m/%d/%y %H:%M',
    )
    return int(dt.timestamp()), float(row[2]), float(row[3])


def clean_lines(f, stats):
    """逐行清理 NUL 字节，统计数量。内存占用 = 单行大小。"""
    for line in f:
        if '\x00' in line:
            stats['nul'] += line.count('\x00')
            line = line.replace('\x00', '')
        yield line


def main():
    init_db()
    conn = get_conn()
    try:
        existing = conn.execute('SELECT COUNT(*) FROM readings').fetchone()[0]
        if existing > 0:
            print('readings 表已有 {} 条数据，为避免重复导入，脚本退出。'.format(existing))
            print('如需重新导入，请先手动清空表：')
            print('  sqlite3 data/sensor.db "DELETE FROM readings;"')
            return

        stats = {'nul': 0}
        imported = skipped = 0
        batch = []

        # 流式读取：不用一次性读入内存
        with open(CSV_PATH, 'r', encoding='utf-8', errors='replace', newline='') as f:
            reader = csv.reader(clean_lines(f, stats))
            next(reader, None)  # 跳过表头
            for row in reader:
                if not row or len(row) < 4:
                    skipped += 1
                    continue
                try:
                    ts, temp, hum = parse_row(row)
                except Exception as e:
                    skipped += 1
                    if skipped <= 20:
                        print('跳过异常行:', row, '->', e)
                    continue

                batch.append((ts, temp, hum))
                imported += 1
                if len(batch) >= BATCH:
                    conn.executemany(
                        'INSERT INTO readings (ts, temperature, humidity) VALUES (?, ?, ?)',
                        batch,
                    )
                    conn.commit()
                    batch.clear()
                    print('  已写入 {} 条…'.format(imported), flush=True)

            if batch:
                conn.executemany(
                    'INSERT INTO readings (ts, temperature, humidity) VALUES (?, ?, ?)',
                    batch,
                )
                conn.commit()
                batch.clear()
    finally:
        conn.close()

    print('导入完成: 成功 {} 条, 跳过 {} 条, 清理 NUL {} 个'.format(
        imported, skipped, stats['nul']))


if __name__ == '__main__':
    main()