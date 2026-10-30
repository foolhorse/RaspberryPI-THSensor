// 横轴只显示短标签；单独保留对应的 Unix 秒，供悬浮提示展示完整时间。
let chartTimestamps = [];

const chart = new Chart(document.getElementById('chart'), {
  type: 'line',
  plugins: [{
    id: 'readableTimeTicks',
    beforeLayout(chart) {
      // 每次布局（包括窗口缩放）重新计算刻度上限，为两侧纵轴预留空间。
      chart.options.scales.x.ticks.maxTicksLimit = Math.max(2, Math.min(8,
        Math.floor((chart.width - 120) / 90)));
    },
  }],
  data: {
    labels: [],
    datasets: [
      { label: '温度 (°C)', data: [], borderColor: '#e74c3c',
        backgroundColor: 'rgba(231,76,60,0.1)', yAxisID: 'y',
        tension: 0.25, pointRadius: 0, borderWidth: 2 },
      { label: '湿度 (%)', data: [], borderColor: '#3498db',
        backgroundColor: 'rgba(52,152,219,0.1)', yAxisID: 'y1',
        tension: 0.25, pointRadius: 0, borderWidth: 2 },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { position: 'top' },
      tooltip: {
        callbacks: {
          title: items => items.length ? fmt(chartTimestamps[items[0].dataIndex]) : '',
        },
      },
    },
    scales: {
      x: {
        ticks: {
          autoSkip: true,
          maxTicksLimit: 4,
          maxRotation: 0,
          minRotation: 0,
        },
      },
      y:  { position: 'left',  title: { display: true, text: '温度 (°C)' } },
      y1: { position: 'right', title: { display: true, text: '湿度 (%)' },
            grid: { drawOnChartArea: false } },
    },
  },
});

function fmt(ts) {
  return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false });
}

function axisLabel(ts, range) {
  const date = new Date(ts * 1000);
  const pad = value => String(value).padStart(2, '0');
  const day = `${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  // 长时间范围突出年份；短时间范围突出时分。完整时间留在悬浮提示中。
  return ['1y', '3y', '5y', 'all'].includes(range)
    ? [String(date.getFullYear()), day]
    : [day, `${pad(date.getHours())}:${pad(date.getMinutes())}`];
}

let latestLoading = false;

async function loadLatest() {
  // 网络或服务响应慢时，跳过重叠的定时刷新，避免请求积压。
  if (latestLoading) return;
  latestLoading = true;
  try {
    const r = await fetch('/api/latest');
    const j = await r.json();
    if (!r.ok || !j.ok) throw new Error(`HTTP ${r.status}`);
    if (j.data) {
      document.getElementById('latest-temperature').textContent = `${j.data.temperature} °C`;
      document.getElementById('latest-humidity').textContent = `${j.data.humidity} %`;
      document.getElementById('latest-status').textContent = `采集时间：${fmt(j.data.ts)} · 每 30 秒检查更新`;
    } else {
      document.getElementById('latest-temperature').textContent = '— °C';
      document.getElementById('latest-humidity').textContent = '— %';
      document.getElementById('latest-status').textContent = '暂无数据';
    }
  } catch (e) {
    document.getElementById('latest-status').textContent = '最新读数更新失败：' + e.message;
  } finally {
    latestLoading = false;
  }
}

let rangeLoading = false;
const rangeButtons = document.querySelectorAll('#range-buttons button');
const chartStatus = document.getElementById('chart-status');

async function loadRange(range) {
  // 一次只允许一个历史请求；函数内的锁也防止绕过禁用按钮重复调用。
  if (rangeLoading) return;
  rangeLoading = true;
  rangeButtons.forEach(btn => { btn.disabled = true; });
  chartStatus.hidden = false;
  chartStatus.textContent = '正在加载历史数据，请稍候…';
  try {
    const r = await fetch('/api/readings?range=' + encodeURIComponent(range));
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    if (!j.ok || !Array.isArray(j.data)) throw new Error('返回数据格式错误');
    const data = j.data;
    chartTimestamps = data.map(d => d.ts);
    chart.data.labels = data.map(d => axisLabel(d.ts, range));
    chart.data.datasets[0].data = data.map(d => d.temperature);
    chart.data.datasets[1].data = data.map(d => d.humidity);
    chart.update('none');
    // 成功后才切换选中范围，失败时仍与保留的旧曲线对应。
    rangeButtons.forEach(btn => {
      btn.setAttribute('aria-pressed', String(btn.dataset.range === range));
      if (btn.dataset.range === range) {
        document.getElementById('current-range').textContent = btn.textContent;
      }
    });
    chartStatus.textContent = data.length ? '' : '所选时间范围暂无数据';
    chartStatus.hidden = data.length > 0;
    document.getElementById('chart-period').textContent = data.length
      ? `显示数据：${fmt(data[0].ts)} 至 ${fmt(data[data.length - 1].ts)}。轻触或悬停曲线查看详细读数。`
      : '选择其他时间范围查看历史数据。';
  } catch (e) {
    chartStatus.textContent = '历史数据加载失败，请点击时间范围重试：' + e.message;
  } finally {
    rangeLoading = false;
    rangeButtons.forEach(btn => { btn.disabled = false; });
  }
}

rangeButtons.forEach(btn => {
  btn.onclick = () => {
    loadRange(btn.dataset.range);
  };
});

// 初次加载
loadLatest();
loadRange('24h');

// 仅自动刷新最新值；图表在首次加载或点击时间范围时查询。
setInterval(loadLatest, 30000);
