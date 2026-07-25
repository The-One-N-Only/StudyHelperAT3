"use strict";

let usageLineChart = null;
let usagePieChart = null;

document.addEventListener('DOMContentLoaded', () => {
    const daysSelect = document.getElementById('usageDaysSelect');
    if (daysSelect) {
        daysSelect.addEventListener('change', fetchUsageData);
        fetchUsageData();
    }
});

async function fetchUsageData() {
    const days = document.getElementById('usageDaysSelect')?.value || 30;
    try {
        const resp = await fetch(`/api/usage/dashboard?days=${days}`);
        const data = await resp.json();
        if (data.status) {
            renderUsageCards(data);
            renderLineChart(data.aggregates);
            renderPieChart(data.model_distribution);
            renderBreakdownTable(data.aggregates);
        }
    } catch (e) {
        console.error('Failed to fetch usage data:', e);
    }
}

function renderUsageCards(data) {
    const totalCost = document.getElementById('totalCost');
    const totalCalls = document.getElementById('totalCalls');
    const totalInputTokens = document.getElementById('totalInputTokens');
    const totalOutputTokens = document.getElementById('totalOutputTokens');

    if (totalCost) totalCost.textContent = `$${data.total_cost.toFixed(4)}`;
    if (totalCalls) {
        const calls = (data.aggregates || []).reduce((sum, r) => sum + r.calls, 0);
        totalCalls.textContent = calls;
    }
    if (totalInputTokens) {
        const inputTokens = (data.aggregates || []).reduce((sum, r) => sum + r.input_tokens, 0);
        totalInputTokens.textContent = inputTokens.toLocaleString();
    }
    if (totalOutputTokens) {
        const outputTokens = (data.aggregates || []).reduce((sum, r) => sum + r.output_tokens, 0);
        totalOutputTokens.textContent = outputTokens.toLocaleString();
    }
}

function renderLineChart(aggregates) {
    const canvas = document.getElementById('usageLineChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (usageLineChart) usageLineChart.destroy();

    const dailyData = {};
    (aggregates || []).forEach(row => {
        if (!dailyData[row.day]) {
            dailyData[row.day] = { input: 0, output: 0 };
        }
        dailyData[row.day].input += row.input_tokens;
        dailyData[row.day].output += row.output_tokens;
    });

    const labels = Object.keys(dailyData).sort();
    const inputData = labels.map(d => dailyData[d].input);
    const outputData = labels.map(d => dailyData[d].output);

    usageLineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label: 'Input Tokens', data: inputData, borderColor: '#0d6efd', fill: false, tension: 0.3 },
                { label: 'Output Tokens', data: outputData, borderColor: '#dc3545', fill: false, tension: 0.3 },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: { y: { beginAtZero: true } },
        },
    });
}

function renderPieChart(modelDistribution) {
    const canvas = document.getElementById('usagePieChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (usagePieChart) usagePieChart.destroy();

    const colors = ['#0d6efd', '#dc3545', '#198754', '#ffc107', '#6f42c1', '#fd7e14'];

    usagePieChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: (modelDistribution || []).map(m => m.model),
            datasets: [{
                data: (modelDistribution || []).map(m => m.calls),
                backgroundColor: colors.slice(0, (modelDistribution || []).length),
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
        },
    });
}

function renderBreakdownTable(aggregates) {
    const tbody = document.getElementById('usageBreakdownBody');
    if (!tbody) return;

    tbody.innerHTML = '';
    (aggregates || []).forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${escapeHtml(row.day)}</td>
            <td><span class="badge bg-secondary">${escapeHtml(row.endpoint)}</span></td>
            <td>${row.calls}</td>
            <td>${row.input_tokens.toLocaleString()}</td>
            <td>${row.output_tokens.toLocaleString()}</td>
            <td>$${row.cost.toFixed(6)}</td>
        `;
        tbody.appendChild(tr);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
