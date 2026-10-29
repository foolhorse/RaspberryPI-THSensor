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
    plugins: { legend: { position: 'top' } },
    scales: {
      x: { ticks: { maxTicksLimit: 8, maxRotation: 0 } },
      y:  { position: 'left',  title: { display: true, text: '温度 (°C)' } },
      y1: { position: 'right', title: { display: true, text: '湿度 (%)' },
            grid: { drawOnChartArea: false } },
    },
  },
});

function fmt(ts) {
  return new Date(ts * 1000).toLocaleString();
}

async function loadLatest() {
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
  }
}

async function loadRange(range) {
  const r = await fetch('/api/readings?range=' + encodeURIComponent(range));
  const j = await r.json();
  const data = (j && j.data) || [];
  chart.data.labels = data.map(d => fmt(d.ts));
  chart.data.datasets[0].data = data.map(d => d.temperature);
  chart.data.datasets[1].data = data.map(d => d.humidity);
  chart.update('none');
}

document.querySelectorAll('#range-buttons button').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('#range-buttons button')
      .forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    loadRange(btn.dataset.range);
  };
});

// 初次加载
loadLatest();
loadRange('24h');

// 定时刷新：最新值 30s，图表 60s
setInterval(loadLatest, 30000);
setInterval(() => {
  const active = document.querySelector('#range-buttons button.active');
  if (active) loadRange(active.dataset.range);
}, 60000);