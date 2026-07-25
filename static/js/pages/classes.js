"use strict";

import { showToast } from '../toast.js';

let pageRoot = null;

export function initClasses(root) {
    pageRoot = root;
    root.innerHTML = `
        <div class="container-fluid py-4 archive-page">
            <div class="archive-content">
                <div class="d-flex flex-column flex-md-row align-items-start align-items-md-center justify-content-between gap-3 mb-4">
                    <div>
                        <h1 class="archive-page-title mb-1">Classes</h1>
                        <p class="text-muted mb-0">Manage your classes and student workspaces.</p>
                    </div>
                </div>
                <ul class="nav nav-pills mb-4" id="classesTabs">
                    <li class="nav-item"><button class="nav-link active" data-tab="teaching">Teaching</button></li>
                    <li class="nav-item"><button class="nav-link" data-tab="enrolled">Enrolled</button></li>
                </ul>
                <div id="classesContent"></div>
            </div>
        </div>
    `;

    root.querySelectorAll('#classesTabs .nav-link').forEach(btn => {
        btn.addEventListener('click', () => {
            root.querySelectorAll('#classesTabs .nav-link').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadClasses(btn.dataset.tab);
        });
    });

    loadClasses('teaching');
}

async function loadClasses(tab) {
    const container = pageRoot.querySelector('#classesContent');
    container.innerHTML = '<div class="text-center py-5"><div class="spinner-border" role="status"></div></div>';

    try {
        const resp = await fetch('/api/classes');
        const data = await resp.json();
        if (!data.status) throw new Error('Failed to load');

        if (tab === 'teaching') {
            renderTeachingView(data.teaching || []);
        } else {
            renderEnrolledView(data.enrolled || []);
        }
    } catch (e) {
        container.innerHTML = '<div class="alert alert-danger">Failed to load classes.</div>';
    }
}

function renderTeachingView(classes) {
    const container = pageRoot.querySelector('#classesContent');
    container.innerHTML = `
        <div class="mb-4">
            <button class="btn btn-primary" id="createClassBtn"><i class="bi bi-plus-lg me-1"></i>Create Class</button>
        </div>
        <div id="classList">${classes.length === 0 ? '<div class="text-muted">No classes yet. Create your first class above.</div>' : ''}</div>
    `;

    container.querySelector('#createClassBtn').addEventListener('click', showCreateClassDialog);

    const list = container.querySelector('#classList');
    classes.forEach(cls => {
        const card = document.createElement('div');
        card.className = 'card surface-wood mb-3';
        card.innerHTML = `
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="mb-1">${escapeHtml(cls.name)}</h5>
                        <p class="text-muted small mb-0">
                            <i class="bi bi-people me-1"></i>${cls.student_count} students
                            <span class="ms-3"><i class="bi bi-key me-1"></i>Code: <strong>${escapeHtml(cls.join_code)}</strong></span>
                        </p>
                    </div>
                    <div class="d-flex gap-2">
                        <button class="btn btn-sm btn-outline-primary view-class-btn" data-class-id="${cls.id}">View</button>
                        <button class="btn btn-sm btn-outline-info analytics-class-btn" data-class-id="${cls.id}">Analytics</button>
                    </div>
                </div>
            </div>
        `;
        card.querySelector('.view-class-btn').addEventListener('click', () => showClassDetail(cls.id));
        card.querySelector('.analytics-class-btn').addEventListener('click', () => showClassAnalytics(cls.id));
        list.appendChild(card);
    });
}

function renderEnrolledView(classes) {
    const container = pageRoot.querySelector('#classesContent');
    container.innerHTML = `
        <div class="mb-4">
            <button class="btn btn-primary" id="joinClassBtn"><i class="bi bi-box-arrow-in-right me-1"></i>Join Class</button>
        </div>
        <div id="enrolledList">${classes.length === 0 ? '<div class="text-muted">Not enrolled in any classes. Use the join button above.</div>' : ''}</div>
    `;

    container.querySelector('#joinClassBtn').addEventListener('click', showJoinClassDialog);

    const list = container.querySelector('#enrolledList');
    classes.forEach(cls => {
        const card = document.createElement('div');
        card.className = 'card surface-wood mb-3';
        card.innerHTML = `
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="mb-1">${escapeHtml(cls.name)}</h5>
                        <p class="text-muted small mb-0">Teacher: ${escapeHtml(cls.teacher_name || 'Unknown')}</p>
                    </div>
                    <a href="/workspace" class="btn btn-sm btn-outline-primary">My Workspaces</a>
                </div>
            </div>
        `;
        list.appendChild(card);
    });
}

function showCreateClassDialog() {
    const dialog = document.createElement('div');
    dialog.className = 'modal fade show d-block';
    dialog.style.backgroundColor = 'rgba(0,0,0,0.5)';
    dialog.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Create Class</h5>
                    <button type="button" class="btn-close" id="createClassClose"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">Class Name</label>
                        <input type="text" class="form-control" id="classNameInput" placeholder="e.g. Year 12 Biology A">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Subject (optional)</label>
                        <select class="form-select" id="classCourseSelect">
                            <option value="">No subject</option>
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" id="createClassCancel">Cancel</button>
                    <button type="button" class="btn btn-primary" id="createClassConfirm">Create</button>
                </div>
            </div>
        </div>`;
    document.body.appendChild(dialog);

    const close = () => dialog.remove();
    dialog.querySelector('#createClassClose').addEventListener('click', close);
    dialog.querySelector('#createClassCancel').addEventListener('click', close);
    dialog.addEventListener('click', (e) => { if (e.target === dialog) close(); });

    const select = dialog.querySelector('#classCourseSelect');
    fetch('/api/nesa/courses').then(r => r.json()).then(data => {
        if (data.status) {
            data.courses.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id;
                opt.textContent = `${c.course_name} (${c.kla})`;
                select.appendChild(opt);
            });
        }
    });

    dialog.querySelector('#createClassConfirm').addEventListener('click', async () => {
        const name = dialog.querySelector('#classNameInput').value.trim();
        const course_id = dialog.querySelector('#classCourseSelect').value || null;
        if (!name) { showToast('Name required', 'warning'); return; }
        const resp = await fetch('/api/classes/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, course_id: course_id ? parseInt(course_id) : null})
        });
        const data = await resp.json();
        if (data.status) {
            showToast(`Class created! Code: ${data.class.join_code}`, 'success');
            close();
            loadClasses('teaching');
        } else {
            showToast(data.error || 'Failed', 'danger');
        }
    });
}

function showJoinClassDialog() {
    const dialog = document.createElement('div');
    dialog.className = 'modal fade show d-block';
    dialog.style.backgroundColor = 'rgba(0,0,0,0.5)';
    dialog.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Join Class</h5>
                    <button type="button" class="btn-close" id="joinClassClose"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">Join Code</label>
                        <input type="text" class="form-control" id="joinCodeInput" placeholder="Enter class code" style="text-transform:uppercase;">
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" id="joinClassCancel">Cancel</button>
                    <button type="button" class="btn btn-primary" id="joinClassConfirm">Join</button>
                </div>
            </div>
        </div>`;
    document.body.appendChild(dialog);

    const close = () => dialog.remove();
    dialog.querySelector('#joinClassClose').addEventListener('click', close);
    dialog.querySelector('#joinClassCancel').addEventListener('click', close);
    dialog.addEventListener('click', (e) => { if (e.target === dialog) close(); });

    dialog.querySelector('#joinClassConfirm').addEventListener('click', async () => {
        const code = dialog.querySelector('#joinCodeInput').value.trim().toUpperCase();
        if (!code) { showToast('Join code required', 'warning'); return; }
        const resp = await fetch('/api/classes/join', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({join_code: code})
        });
        const data = await resp.json();
        if (data.status) {
            showToast('Joined class!', 'success');
            close();
            loadClasses('enrolled');
        } else {
            showToast(data.error || 'Invalid code', 'danger');
        }
    });
}

async function showClassDetail(classId) {
    const container = pageRoot.querySelector('#classesContent');
    container.innerHTML = '<div class="text-center py-5"><div class="spinner-border" role="status"></div></div>';

    try {
        const [studResp, wsResp] = await Promise.all([
            fetch(`/api/classes/${classId}/students`),
            fetch(`/api/classes/${classId}/workspaces`)
        ]);
        const studData = await studResp.json();
        const wsData = await wsResp.json();

        let html = `
            <button class="btn btn-outline-secondary mb-3" id="backToClasses"><i class="bi bi-arrow-left me-1"></i>Back</button>
            <div class="card surface-wood mb-3">
                <div class="card-header"><h5 class="mb-0">Students (${(studData.students || []).length})</h5></div>
                <div class="card-body p-0">
                    <table class="table table-hover mb-0">
                        <thead><tr><th>Name</th><th>Email</th><th>Workspaces</th><th>Sources</th><th>Notes</th><th>Last Active</th></tr></thead>
                        <tbody>
                            ${(wsData.workspaces || []).map(ws => `
                                <tr>
                                    <td>${escapeHtml(ws.student_name)}</td>
                                    <td><small class="text-muted">${escapeHtml((studData.students || []).find(s => s.id === ws.student_id)?.email || '')}</small></td>
                                    <td><a href="/workspace/${ws.workspace_id}" target="_blank">${escapeHtml(ws.workspace_name)}</a></td>
                                    <td>${ws.item_count}</td>
                                    <td>${ws.note_count}</td>
                                    <td><small>${ws.last_active ? new Date(ws.last_active * 1000).toLocaleDateString() : 'N/A'}</small></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="mb-3">
                <button class="btn btn-outline-primary" id="pushTemplateBtn"><i class="bi bi-send me-1"></i>Push Starter Workspace</button>
            </div>
        `;
        container.innerHTML = html;

        container.querySelector('#backToClasses').addEventListener('click', () => loadClasses('teaching'));
        container.querySelector('#pushTemplateBtn').addEventListener('click', () => showPushTemplateDialog(classId));
    } catch (e) {
        container.innerHTML = '<div class="alert alert-danger">Failed to load class details.</div>';
    }
}

function showPushTemplateDialog(classId) {
    const dialog = document.createElement('div');
    dialog.className = 'modal fade show d-block';
    dialog.style.backgroundColor = 'rgba(0,0,0,0.5)';
    dialog.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Push Starter Workspace</h5>
                    <button type="button" class="btn-close" id="pushDialogClose"></button>
                </div>
                <div class="modal-body">
                    <p>Select a template to push to all enrolled students.</p>
                    <div class="mb-3" id="pushTemplateList"></div>
                </div>
            </div>
        </div>`;
    document.body.appendChild(dialog);

    const close = () => dialog.remove();
    dialog.querySelector('#pushDialogClose').addEventListener('click', close);
    dialog.addEventListener('click', (e) => { if (e.target === dialog) close(); });

    const list = dialog.querySelector('#pushTemplateList');
    fetch('/workspace/templates').then(r => r.json()).then(data => {
        if (data.status) {
            data.templates.forEach(t => {
                const btn = document.createElement('button');
                btn.className = 'btn btn-outline-secondary d-block w-100 mb-2 text-start';
                btn.innerHTML = `<strong>${escapeHtml(t.name)}</strong><br><small>${escapeHtml(t.description)}</small>`;
                btn.addEventListener('click', async () => {
                    close();
                    const resp = await fetch(`/api/classes/${classId}/push-workspace`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({template_id: t.id})
                    });
                    const data = await resp.json();
                    if (data.status) {
                        showToast(`Pushed ${data.pushed.length} workspaces`, 'success');
                        showClassDetail(classId);
                    } else {
                        showToast(data.error || 'Failed', 'danger');
                    }
                });
                list.appendChild(btn);
            });
        }
    });
}

async function showClassAnalytics(classId) {
    const container = pageRoot.querySelector('#classesContent');
    container.innerHTML = '<div class="text-center py-5"><div class="spinner-border" role="status"></div></div>';

    try {
        const resp = await fetch(`/api/classes/${classId}/analytics`);
        const data = await resp.json();
        if (!data.status) throw new Error('Failed');

        const a = data.analytics;
        let html = `
            <button class="btn btn-outline-secondary mb-3" id="backToClasses"><i class="bi bi-arrow-left me-1"></i>Back</button>
            <div class="row g-3 mb-4">
                <div class="col-md-3">
                    <div class="card surface-wood text-center p-3">
                        <h3 class="mb-0">${a.total_students}</h3>
                        <small class="text-muted">Students</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card surface-wood text-center p-3">
                        <h3 class="mb-0">${a.total_workspaces}</h3>
                        <small class="text-muted">Workspaces</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card surface-wood text-center p-3">
                        <h3 class="mb-0">${a.total_items}</h3>
                        <small class="text-muted">Total Sources</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card surface-wood text-center p-3">
                        <h3 class="mb-0">${a.total_chats}</h3>
                        <small class="text-muted">AI Chats</small>
                    </div>
                </div>
            </div>
            <div class="card surface-wood">
                <div class="card-header"><h5 class="mb-0">Per-Student Stats</h5></div>
                <div class="card-body p-0">
                    <table class="table table-hover mb-0">
                        <thead><tr><th>Student</th><th>Workspaces</th><th>Sources</th><th>Notes</th><th>Chats</th><th>Last Active</th></tr></thead>
                        <tbody>
                            ${(a.per_student || []).map(s => `
                                <tr>
                                    <td>${escapeHtml(s.student_name || 'Unknown')}</td>
                                    <td>${s.workspace_count}</td>
                                    <td>${s.item_count}</td>
                                    <td>${s.note_count}</td>
                                    <td>${s.chat_count}</td>
                                    <td><small>${s.last_active ? new Date(s.last_active * 1000).toLocaleDateString() : 'N/A'}</small></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
            ${a.activity_timeline && a.activity_timeline.length > 0 ? `
            <div class="card surface-wood mt-3">
                <div class="card-header"><h5 class="mb-0">Activity Timeline (30 days)</h5></div>
                <div class="card-body">
                    <div style="display:flex;align-items:flex-end;gap:2px;height:100px;overflow-x:auto;">
                        ${a.activity_timeline.map(d => `
                            <div title="${d.date}: ${d.count} items" style="flex:none;width:20px;background:var(--bs-primary);height:${Math.min(100, Math.max(3, d.count * 5))}px;"></div>
                        `).join('')}
                    </div>
                </div>
            </div>` : ''}
        `;
        container.innerHTML = html;
        container.querySelector('#backToClasses').addEventListener('click', () => loadClasses('teaching'));
    } catch (e) {
        container.innerHTML = '<div class="alert alert-danger">Failed to load analytics.</div>';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
