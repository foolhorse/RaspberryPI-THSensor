# 树莓派上使用温湿度传感器，保存数据，网页展示数据

使用 DHT22 采集温湿度，保存到 SQLite，并通过局域网网页查看最新值和历史曲线。业务流程详见 [业务流程说明](docs/business-flow.md)。

## 技术栈

- 采集：Python 3、Adafruit_DHT（DHT22，GPIO 2）。
- 存储：SQLite（Python 标准库 `sqlite3`，WAL 模式）。
- Web：Bottle，使用 Python 内置 wsgiref 服务提供页面和 JSON API。
- 前端：HTML、CSS、原生 JavaScript、Chart.js（部署时下载 4.4.0 到本地）。
- 运行环境：树莓派、Python venv、systemd 双服务。

## 项目结构

```text
.
├── main.py                 # 定时采集温湿度并入库
├── db.py                   # 数据库连接、建表和索引
├── web.py                  # 静态页面与数据查询 API
├── history.py              # 原始数据及小时汇总查询
├── backfill_hourly.py      # 历史小时汇总回填及核对
├── tests/                  # 汇总与事务测试
├── static/
│   ├── index.html          # 监控页面
│   └── app.js              # 最新值、历史曲线和定时刷新
├── deploy/
│   ├── thsensor.service    # 采集服务
│   └── thsensor-web.service # Web 服务
├── docs/
│   └── business-flow.md    # 业务流程说明
└── data/sensor.db          # 运行时自动生成的 SQLite 数据库
```

`static/chart.umd.min.js` 需要按下方步骤下载。部署前需将 `deploy/` 中的用户和项目路径改为实际环境配置。

## 部署

把代码放到项目目录

进入项目目录

下载 Chart.js
在 Pi 上直接下载（Pi 能联网的话）：
```bash
wget -O static/chart.umd.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js
wget -O static/chart.umd.js.map https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js.map
```
第二个文件是同版本的源码映射，供浏览器开发者工具调试使用；缺失时可能产生 `chart.umd.js.map` 的 404，但不影响图表功能。
Pi 不能联网就用电脑下载后 `scp` 上去。文件约 200KB，放本地是为了内网/断网时页面也能打开（不要依赖 CDN）。

创建虚拟环境
```bash
python3 -m venv .venv
```bash
安装 Adafruit_DHT Bottle 到 venv（必须用 venv 里的 pip）
```bash
.venv/bin/pip install Adafruit_DHT==1.4.0 bottle
```

使用 SystemD 启动两个服务
```bash
sudo cp deploy/thsensor.service deploy/thsensor-web.service /etc/systemd/system/
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now thsensor
sudo systemctl enable --now thsensor-web
```

## 使用

历史图表支持 1 小时、24 小时、7 天、30 天、1 年、3 年、5 年及全部（一年按 365 天计算），1 小时和 24 小时查询原始表，7 天及更长范围查询小时汇总表，再按时间桶加权平均，最多返回 600 个点。图表仅在首次加载或点击范围时查询，顶部最新值每 30 秒刷新。

停止服务
```bash
sudo systemctl stop thsensor
sudo systemctl stop thsensor-web
```

重启服务（修改 Python 代码后执行）：
```bash
sudo systemctl restart thsensor
sudo systemctl restart thsensor-web
```

也可以同时重启：
```bash
sudo systemctl restart thsensor thsensor-web
```

如果修改了 `deploy/` 下的服务配置，先重新复制到 `/etc/systemd/system/`，执行 `sudo systemctl daemon-reload`，再重启对应服务。仅修改前端静态文件时，浏览器强制刷新即可。

查看服务状态
```bash
systemctl status thsensor --no-pager
systemctl status thsensor-web --no-pager
```

看日志，确认是否正常启动，没有 ModuleNotFoundError / Permission denied
```bash
journalctl -u thsensor -n 20 --no-pager
journalctl -u thsensor-web -n 20 --no-pager
```

API 是否正常
```bash
curl -s http://127.0.0.1:8080/api/latest
curl -s 'http://127.0.0.1:8080/api/readings?range=1h' | head -c 300
```

浏览器访问（局域网内任意设备）
```bash
http://<Pi的IP>:8080/
```


## 已有数据库升级到小时汇总

在树莓派项目目录执行。先部署新版代码，停止两个服务，再备份数据库并回填。回填期间暂停采集，完成时间取决于设备和数据量。

```bash
sudo systemctl stop thsensor thsensor-web
.venv/bin/python - <<'PYTHON'
import sqlite3
from datetime import datetime
from db import DB_PATH
backup = DB_PATH + '.backup-' + datetime.now().strftime('%Y%m%d-%H%M%S')
source = sqlite3.connect(DB_PATH)
target = sqlite3.connect(backup)
try:
    source.backup(target)
finally:
    target.close()
    source.close()
print('备份完成：', backup)
PYTHON
.venv/bin/python backfill_hourly.py
```

确认脚本输出“完成：核对……条原始记录，已启用小时汇总查询”后，再启动服务：

```bash
sudo systemctl start thsensor thsensor-web
```

脚本按 UTC 日分批提交，每小时保存记录数、时间戳总和、温湿度总和及各自有效条数，最后核对原始表和汇总表的总条数、时间戳总和、温湿度有效条数及总和。原始表不会修改。脚本可重复运行，每次清空并重建汇总；中途失败可保持服务停止后重新执行。失败或未回填时，历史接口回退到原始表查询，避免展示不完整汇总，速度仍可能较慢。

新建空数据库不需要回填。新版采集程序在同一个事务中写入原始表并更新小时统计，无需额外定时任务。7 天以上范围按小时加权展示；查询起点不足一小时的部分会回查原始表，避免包含范围外记录。分桶边界与旧版原始数据分桶可能略有差异。

运行测试（无需传感器或 Bottle）：

```bash
python3 -m unittest discover -s tests -v
```
