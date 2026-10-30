import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db
from backfill_hourly import backfill, verify
from history import query_readings


class HourlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        folder = Path(self.temp.name)
        with patch.object(db, 'DB_DIR', str(folder)), patch.object(db, 'DB_PATH', str(folder / 'test.db')):
            db.init_db()
            self.conn = db.get_conn()

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_incremental_weighting_nulls_and_partial_boundary(self):
        for row in [(3600, 10, None), (3700, 20, 50), (7200, 40, 70)]:
            db.store_reading(self.conn, *row)
        self.assertEqual(verify(self.conn), 3)
        self.assertEqual(query_readings(self.conn, None), [(3650, 15.0, 50.0), (7200, 40.0, 70.0)])
        # 范围起点 3650，必须排除同小时的 3600 那条。
        self.assertEqual(query_readings(self.conn, 7 * 86400, now=3650 + 7 * 86400),
                         [(3700, 20.0, 50.0), (7200, 40.0, 70.0)])
        self.assertEqual(query_readings(self.conn, 7 * 86400, now=8000 + 7 * 86400), [])

    def test_backfill_rerun_and_unready_fallback(self):
        self.conn.executemany('INSERT INTO readings(ts, temperature, humidity) VALUES (?, ?, ?)',
                              [(0, None, None), (3600, 10, 30), (90000, 20, 50)])
        self.conn.execute("UPDATE app_metadata SET value='0' WHERE key='hourly_ready'")
        self.conn.commit()
        self.assertEqual(len(query_readings(self.conn, None)), 3)
        for _ in range(2):
            backfill(self.conn, progress=lambda _: None)
            self.assertTrue(db.hourly_ready(self.conn))
            self.assertEqual(verify(self.conn), 3)
        db.store_reading(self.conn, 90060, 30, 60)
        self.assertEqual(verify(self.conn), 4)

    def test_atomic_rollback(self):
        self.conn.execute("CREATE TRIGGER fail_summary BEFORE UPDATE ON hourly_readings BEGIN SELECT RAISE(ABORT, 'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            db.store_reading(self.conn, 3600, 20, 50)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM readings').fetchone()[0], 0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM hourly_readings').fetchone()[0], 0)

    def test_point_limit_and_weighted_mean(self):
        # 601 个小时压成 301 桶，首桶两个小时的记录数不相同。
        for hour in range(601):
            db.store_reading(self.conn, hour * 3600, 30, None)
        db.store_reading(self.conn, 1, 0, 50)
        rows = query_readings(self.conn, None)
        self.assertEqual(len(rows), 301)
        self.assertEqual(rows[0], (1200, 20.0, 50.0))
        self.assertEqual(rows[-1][0], 600 * 3600)

    def test_empty_backfill(self):
        backfill(self.conn, progress=lambda _: None)
        self.assertTrue(db.hourly_ready(self.conn))
        self.assertEqual(query_readings(self.conn, None), [])

    def test_empty_partial_hour_does_not_create_phantom_point(self):
        db.store_reading(self.conn, 3600, 10, 40)
        db.store_reading(self.conn, 10800, 20, 60)
        # 起点所在小时没有范围内记录，不能生成空统计点。
        self.assertEqual(query_readings(self.conn, 7 * 86400, now=3650 + 7 * 86400),
                         [(10800, 20.0, 60.0)])
        # 整点起始时，回查区间为空，也不应生成额外数据点。
        self.assertEqual(query_readings(self.conn, 7 * 86400, now=3600 + 7 * 86400),
                         [(3600, 10.0, 40.0), (10800, 20.0, 60.0)])
        self.assertEqual(query_readings(self.conn, 7 * 86400, now=10801 + 7 * 86400), [])


if __name__ == '__main__':
    unittest.main()
