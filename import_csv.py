
import csv
import os
from datetime import datetime

from db import get_conn, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'log.csv')


def parse_row(row):
    # CSV 格式: Date(%m/%d/%y),Time(%H:%M),Temperature,Humidity
    dt = datetime.strptime(
        '{} {}'.format(row[0].strip(), row[1].strip()),
        '%m/%d/%y %H:%M',
    )
    return int(dt.timestamp()), float(row[2]), float(row[3])


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

        imported = skipped = 0
        with open(CSV_PATH, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # 跳过表头
            for row in reader:
                if not row or len(row) < 4:
                    skipped += 1
                    continue
                try:
                    ts, temp, hum = parse_row(row)
                except Exception as e:
                    skipped += 1
                    print('跳过异常行:', row, '->', e)
                    continue
                conn.execute(
                    'INSERT INTO readings (ts, temperature, humidity) VALUES (?, ?, ?)',
                    (ts, temp, hum),
                )
                imported += 1
        conn.commit()
    finally:
        conn.close()

    print('导入完成: 成功 {} 条, 跳过 {} 条'.format(imported, skipped))


if __name__ == '__main__':
    main()