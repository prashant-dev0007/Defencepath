/**
 * DEFENCE PATH - Student Weakness Analysis & Performance Analytics
 * Visualizes authentic attempt statistics using Chart.js
 */

function renderSubjectChart(canvasId, subjectStats) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const labels = Object.keys(subjectStats);
  const dataAccuracy = labels.map(l => subjectStats[l].accuracy);
  const dataTotal = labels.map(l => subjectStats[l].total);

  const colors = dataAccuracy.map(acc => {
    if (acc >= 70) return '#10B981'; // Green Strong
    if (acc >= 50) return '#F59E0B'; // Amber Practice
    return '#EF4444'; // Red Weak
  });

  new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Subject Accuracy (%)',
        data: dataAccuracy,
        backgroundColor: colors,
        borderColor: '#D4AF37',
        borderWidth: 1,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: function(ctx) {
              const subj = labels[ctx.dataIndex];
              return `Questions Attempted: ${subjectStats[subj].total}`;
            }
          }
        }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { color: '#9CA3AF' },
          grid: { color: 'rgba(255, 255, 255, 0.08)' }
        },
        x: {
          ticks: { color: '#E5E7EB' },
          grid: { display: false }
        }
      }
    }
  });
}

function renderProgressChart(canvasId, attemptsList) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !attemptsList || attemptsList.length === 0) return;

  const labels = attemptsList.map((a, idx) => `Test ${idx + 1}`);
  const scores = attemptsList.map(a => ((a.score / a.max_marks) * 100).toFixed(1));
  const accuracies = attemptsList.map(a => a.accuracy_percent.toFixed(1));

  new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Score %',
          data: scores,
          borderColor: '#D4AF37',
          backgroundColor: 'rgba(212, 175, 55, 0.15)',
          fill: true,
          tension: 0.3,
          pointBackgroundColor: '#D4AF37',
          pointRadius: 5
        },
        {
          label: 'Accuracy %',
          data: accuracies,
          borderColor: '#10B981',
          borderDash: [5, 5],
          tension: 0.2,
          pointBackgroundColor: '#10B981',
          pointRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: '#E5E7EB' }
        }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { color: '#9CA3AF' },
          grid: { color: 'rgba(255, 255, 255, 0.08)' }
        },
        x: {
          ticks: { color: '#9CA3AF' },
          grid: { color: 'rgba(255, 255, 255, 0.04)' }
        }
      }
    }
  });
}
