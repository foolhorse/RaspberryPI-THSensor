# 树莓派上使用温湿度传感器，保存数据，网页展示数据


## 部署

把代码放到项目目录

进入项目目录

下载 Chart.js
在 Pi 上直接下载（Pi 能联网的话）：
```
wget -O static/chart.umd.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js
```
Pi 不能联网就用电脑下载后 `scp` 上去。文件约 200KB，放本地是为了内网/断网时页面也能打开（不要依赖 CDN）。

创建虚拟环境
```
python3 -m venv .venv
```
安装 Adafruit_DHT Bottle 到 venv（必须用 venv 里的 pip）
```
.venv/bin/pip install Adafruit_DHT==1.4.0 bottle
```

使用 SystemD 启动两个服务
```
sudo cp deploy/thsensor.service deploy/thsensor-web.service /etc/systemd/system/
```
```
systemctl daemon-reload
systemctl enable --now thsensor
systemctl enable --now thsensor-web
```

## 使用

查看服务状态
```
systemctl status thsensor --no-pager
systemctl status thsensor-web --no-pager
```

看日志，确认是否正常启动，没有 ModuleNotFoundError / Permission denied
```
journalctl -u thsensor -n 20 --no-pager
journalctl -u thsensor-web -n 20 --no-pager
```

API 是否正常
```
curl -s http://127.0.0.1:8080/api/latest
curl -s 'http://127.0.0.1:8080/api/readings?range=1h' | head -c 300
```

浏览器访问（局域网内任意设备）
```
http://<Pi的IP>:8080/
```
