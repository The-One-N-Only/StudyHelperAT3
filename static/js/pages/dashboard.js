"use strict";

import { showToast } from '../toast.js';

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadDashboard() {
    try {
        const resp = await fetch('/api/dashboard');
        const data = await resp.json();
        if (!data.status) {
            showToast('Failed to load dashboard', 'danger');
            return;
        }
        renderDashboard(data.dashboard);
    } catch (e) {
        showToast('Failed to load dashboard', 'danger');
    }
}

function renderDashboard(d) {
    const totalWs = document.getElementById('totalWorkspaces');
    const activeWs = document.getElementById('activeWorkspaces');
    const totalSrc = document.getElementById('totalSources');
    const srcAdded7d = document.getElementById('sourcesAdded7d');
    const totalCit = document.getElementById('totalCitations');
    const domainDiv = document.getElementById('domainDiversity');
    const domainCnt = document.getElementById('domainCount');
    const topDomainsContainer = document.getElementById('topDomainsContainer');
    const aiUsageContainer = document.getElementById('aiUsageContainer');

    if (totalWs) totalWs.textContent = d.total_workspaces;
    if (activeWs) activeWs.textContent = `${d.active_workspaces_7d} active this week`;
    if (totalSrc) totalSrc.textContent = d.total_sources;
    if (srcAdded7d) srcAdded7d.textContent = `${d.sources_added_7d} added this week`;
    if (totalCit) totalCit.textContent = d.total_citations;
    if (domainDiv) domainDiv.textContent = d.domain_diversity;
    if (domainCnt) domainCnt.textContent = `${d.domain_count} domains`;

    if (topDomainsContainer) {
        if (d.top_domains && d.top_domains.length > 0) {
            let html = '<div class="list-group list-group-flush">';
            d.top_domains.forEach(([domain, count]) => {
                const maxCount = d.top_domains[0] ? d.top_domains[0][1] : 1;
                const pct = Math.round((count / maxCount) * 100);
                html += `
                    <div class="list-group-item d-flex justify-content-between align-items-center px-0">
                        <span class="small">${escapeHtml(domain)}</span>
                        <div class="d-flex align-items-center gap-2">
                            <div class="progress" style="width:120px;height:8px;">
                                <div class="progress-bar" role="progressbar" style="width:${pct}%" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                            <small class="text-muted">${count}</small>
                        </div>
                    </div>`;
            });
            html += '</div>';
            topDomainsContainer.innerHTML = html;
        } else {
            topDomainsContainer.innerHTML = '<p class="text-muted small mb-0">No domain data yet.</p>';
        }
    }

    if (aiUsageContainer) {
        if (d.ai_usage && d.ai_usage.length > 0) {
            let html = '<div class="table-responsive"><table class="table table-sm"><thead><tr><th>Date</th><th>Endpoint</th><th>Calls</th><th>Cost</th></tr></thead><tbody>';
            d.ai_usage.slice(0, 10).forEach(row => {
                html += `<tr><td>${escapeHtml(row.day)}</td><td>${escapeHtml(row.endpoint)}</td><td>${row.calls}</td><td>$${row.cost.toFixed(6)}</td></tr>`;
            });
            html += '</tbody></table></div>';
            aiUsageContainer.innerHTML = html;
        } else {
            aiUsageContainer.innerHTML = '<p class="text-muted small mb-0">No AI usage data yet.</p>';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    const refreshBtn = document.getElementById('refreshDashboardBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadDashboard);
    }
});
