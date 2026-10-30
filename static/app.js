const chart = new Chart(document.getElementById('chart'), {
  type: 'line',
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
          title: items => items.length ? fmt(items[0].chart.data.labels[items[0].dataIndex]) : '',
        },
      },
    },
    scales: {
      x: {
        ticks: {
          autoSkip: true,
          maxTicksLimit: context => Math.max(2, Math.min(8, Math.floor(context.chart.width / 100))),
          maxRotation: 0,
          callback(value) {
            return axisLabel(this.getLabelForValue(value));
          },
        },
      },
      y:  { position: 'left',  title: { display: true, text: '温度 (°C)' } },
      y1: { position: 'right', title: { display: true, text: '湿度 (%)' },
            grid: { drawOnChartArea: false } },
    },
  },
});

function fmt(ts) {
  return new Date(ts * 1000).toLocaleString();
}

function axisLabel(ts) {
  const date = new Date(ts * 1000);
  const pad = value => String(value).padStart(2, '0');
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `${pad(date.getHours())}:${pad(date.getMinutes())}`,
  ];
}

let latestLoading = false;

async function loadLatest() {
  if (latestLoading) return;
  latestLoading = true;
  try {
    const r = await fetch('/api/latest');
    const j = await r.json();
    const el = document.getElementById('latest');
    if (j.ok && j.data) {
      el.innerHTML = `最新：温度 <b>${j.data.temperature} °C</b>，` +
                     `湿度 <b>${j.data.humidity} %</b>（${fmt(j.data.ts)}）`;
    } else {
      el.textContent = '暂无数据';
    }
  } catch (e) {
    document.getElementById('latest').textContent = '读取失败：' + e;
  } finally {
    latestLoading = false;
  }
}

let rangeLoading = false;
const rangeButtons = document.querySelectorAll('#range-buttons button');
const chartStatus = document.getElementById('chart-status');

async function loadRange(range) {
  if (rangeLoading) return;
  rangeLoading = true;
  rangeButtons.forEach(btn => { btn.disabled = true; });
  chartStatus.textContent = '正在加载历史数据，请稍候…';
  try {
    const r = await fetch('/api/readings?range=' + encodeURIComponent(range));
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    if (!j.ok || !Array.isArray(j.data)) throw new Error('返回数据格式错误');
    const data = j.data;
    chart.data.labels = data.map(d => d.ts);
    chart.data.datasets[0].data = data.map(d => d.temperature);
    chart.data.datasets[1].data = data.map(d => d.humidity);
    chart.update('none');
    rangeButtons.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.range === range);
    });
    chartStatus.textContent = data.length ? '' : '所选时间范围暂无数据';
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
