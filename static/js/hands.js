(function () {
        const dataEl = document.getElementById('hands-data');
        if (!dataEl) return;
        let rows = [];
        try { rows = JSON.parse(dataEl.textContent || '[]'); } catch (e) { rows = []; }
        if (!rows.length) return;
        const labels = rows.map(h => h[1]);
        const ptsA = rows.map(h => h[6]);
        const ptsB = rows.map(h => h[7]);
        const cumA = [], cumB = [];
        let sa = 0, sb = 0;
        for (let i = 0; i < labels.length; i++) {
          sa += Number(ptsA[i] || 0);
          sb += Number(ptsB[i] || 0);
          cumA.push(sa);
          cumB.push(sb);
        }
        const ctx = document.getElementById('scoreProgress');
        if (!ctx) return;
        new Chart(ctx, {
          type: 'line',
          data: {
            labels: labels.map(n => 'Manche ' + n),
            datasets: [
              {
                label: 'Équipe A',
                data: cumA,
                borderColor: 'rgb(13, 110, 253)',
                backgroundColor: 'rgba(13, 110, 253, 0.2)',
                tension: 0.2
              },
              {
                label: 'Équipe B',
                data: cumB,
                borderColor: 'rgb(220, 53, 69)',
                backgroundColor: 'rgba(220, 53, 69, 0.2)',
                tension: 0.2
              }
            ]
          },
          options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'top' } },
            scales: {
              y: { beginAtZero: true, title: { display: true, text: 'Points cumulés' } },
              x: { title: { display: true, text: 'Manche' } }
            }
          }
        });
      })();