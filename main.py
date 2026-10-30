import time

import Adafruit_DHT

from db import get_conn, init_db, store_reading

DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN = 2  # GPIO 编号，不是排针的物理脚位编号。
INTERVAL = 60  # 每轮结束后的等待秒数，实际采样间隔还包含读取和写入耗时。


def read_and_store():
    """读取一次传感器；读取失败时跳过，成功时同步保存原始记录和小时统计。"""
    humidity, temperature = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
    if humidity is None or temperature is None:
        print("Failed to retrieve data from humidity sensor")
        return

    ts = int(time.time())
    conn = get_conn()
    try:
        store_reading(conn, ts, round(temperature, 2), round(humidity, 2))
    finally:
        conn.close()


def main():
    init_db()
    while True:
        try:
            read_and_store()
        except Exception as e:
            # 单次硬件或数据库错误不终止采集，等待后继续下一轮。
            print("Error:", e)
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
