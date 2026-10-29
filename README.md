# 树莓派上使用温湿度传感器，保存数据，网页展示数据


## 部署

先确认时区正确（迁移前必做）
timedatectl

停掉旧采集服务，防止迁移过程中 CSV 还在变
sudo systemctl stop thsensor

备份现有 CSV
cp /home/pi/file/RaspberryPI-THSensor/log.csv \
   /home/pi/file/RaspberryPI-THSensor/log.csv.bak.$(date +%Y%m%d)

部署代码：把 db.py / main.py / web.py / import_csv.py
和 static/ 下的三个文件放到项目目录

创建虚拟环境
python3 -m venv .venv

安装 Adafruit_DHT Bottle 到 venv（必须用 venv 里的 pip！）
.venv/bin/pip install Adafruit_DHT==1.4.0
.venv/bin/pip install bottle


下载 Chart.js
在 Pi 上直接下载（Pi 能联网的话）：
cd static
wget -O chart.umd.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js

Pi 不能联网就用电脑下载后 `scp` 上去。文件约 200KB，放本地是为了内网/断网时页面也能打开（不要依赖 CDN）。

跑迁移脚本
.venv/bin/python3 import_csv.py

验证数据已入库
sqlite3 data/sensor.db "SELECT COUNT(*), datetime(MIN(ts),'unixepoch','localtime'), datetime(MAX(ts),'unixepoch','localtime') FROM readings;"

安装并启动两个服务
sudo cp deploy/thsensor.service deploy/thsensor-web.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now thsensor
systemctl enable --now thsensor-web




查看服务状态
systemctl status thsensor --no-pager
systemctl status thsensor-web --no-pager

看日志，确认没有 ModuleNotFoundError / Permission denied
journalctl -u thsensor -n 20 --no-pager
journalctl -u thsensor-web -n 20 --no-pager

采集进程是否在写新数据（等 60~90 秒后再查）
sqlite3 /home/pi/file/RaspberryPI-THSensor/data/sensor.db \
  "SELECT datetime(ts,'unixepoch','localtime'), temperature, humidity FROM readings ORDER BY ts DESC LIMIT 5;"

API 是否正常
curl -s http://127.0.0.1:8080/api/latest
curl -s 'http://127.0.0.1:8080/api/readings?range=1h' | head -c 300

浏览器访问（局域网内任意设备）
http://<Pi的IP>:8080/

