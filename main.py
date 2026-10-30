import time

import Adafruit_DHT

from db import get_conn, init_db, store_reading

DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN = 2
INTERVAL = 60


def read_and_store():
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
            # 原代码 except Error 是 NameError 的坑，这里改成 Exception
            print("Error:", e)
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()