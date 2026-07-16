"use strict";

import { showToast } from '../toast.js';

let pageRoot = null;
let selectedFile = null;

export function initUpload(root) {
    pageRoot = root;
    pageRoot.innerHTML = `
        <div class="archive-page archive-page-upload">
            <span class="archive-illustration illustration-compass" aria-hidden="true"></span>
            <span class="archive-illustration illustration-sextant" aria-hidden="true"></span>
            <span class="archive-illustration illustration-flourish" aria-hidden="true"></span>
            <div class="container py-4 archive-content upload-content" style="max-width: 700px;">
                <div class="card p-0 mb-4 upload-panel">
                    <div class="card-body text-center p-5 surface-leather upload-zone" id="uploadZone">
                        <i class="bi bi-cloud-upload display-4 text-muted archive-upload-icon" aria-hidden="true"></i>
                        <h6 class="mt-3">Drag files here or click to browse</h6>
                        <p class="small text-muted">Maximum 10MB</p>
                        <input type="file" id="fileInput" accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.gif,.webp,.xlsx,.xls" style="display: none;">
                    </div>
                    <div class="p-3 pt-0 upload-actions">
                        <div class="mb-3">
                            <p class="mb-2"><strong>Selected:</strong> <span id="selectedFile">No file selected</span></p>
                        </div>
                        <div class="progress mb-3" style="display: none;" id="progressBar">
                            <div class="progress-bar" role="progressbar" style="width: 0%"></div>
                        </div>
                        <button class="btn btn-primary btn-brass w-100" id="uploadBtn" disabled>Upload File</button>
                    </div>
                </div>
                <div class="card surface-leather file-list-panel">
                    <div class="card-header d-flex align-items-center">
                        <i class="bi bi-files me-2" aria-hidden="true"></i>
                        <h5 class="mb-0">Your Files</h5>
                        <span class="badge bg-primary archive-count-badge ms-2" id="fileCountBadge">0</span>
                    </div>
                    <div class="card-body p-0">
                        <ul class="list-group list-group-flush" id="filesList"></ul>
                    </div>
                </div>
            </div>
        </div>
    `;

    setupUploadZone();
    loadUploadedFiles();
}

function setupUploadZone() {
    const uploadZone = pageRoot.querySelector('#uploadZone');
    const fileInput = pageRoot.querySelector('#fileInput');
    const uploadBtn = pageRoot.querySelector('#uploadBtn');

    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length) handleFile(files[0]);
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleFile(e.target.files[0]);
    });

    uploadBtn.addEventListener('click', uploadFile);
}

function handleFile(file) {
    const allowedTypes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'application/x-msexcel',
        'application/x-excel'
    ];

    if (!allowedTypes.includes(file.type)) {
        showToast('Invalid file type', 'danger');
        return;
    }
    if (file.size > 10 * 1024 * 1024) {
        showToast('File too large (max 10MB)', 'danger');
        return;
    }

    selectedFile = file;
    pageRoot.querySelector('#selectedFile').textContent = file.name;
    pageRoot.querySelector('#uploadBtn').disabled = false;
}

function uploadFile() {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);

    const progressBar = pageRoot.querySelector('#progressBar');
    progressBar.style.display = 'block';
    progressBar.querySelector('.progress-bar').style.width = '0%';

    fetch('/api/files/upload', {
        method: 'POST',
        body: formData
    })
        .then((r) => r.json())
        .then((result) => {
            progressBar.style.display = 'none';
            if (result.status) {
                showToast('Uploaded successfully', 'success');
                selectedFile = null;
                pageRoot.querySelector('#selectedFile').textContent = 'No file selected';
                pageRoot.querySelector('#uploadBtn').disabled = true;
                pageRoot.querySelector('#fileInput').value = '';
                loadUploadedFiles();
            } else {
                showToast(result.error, 'danger');
            }
        })
        .catch(() => {
            progressBar.style.display = 'none';
            showToast('Upload failed', 'danger');
        });
}

function loadUploadedFiles() {
    fetch('/api/files/list')
        .then((r) => r.json())
        .then((result) => {
            const container = pageRoot.querySelector('#filesList');
            const countBadge = pageRoot.querySelector('#fileCountBadge');
            container.innerHTML = '';
            countBadge.textContent = result.files.length;

            result.files.forEach((file) => {
                let icon = 'file-earmark';
                if (file.file_type === 'pdf') icon = 'file-earmark-pdf';
                else if (file.file_type === 'docx') icon = 'file-earmark-word';
                else if (file.file_type === 'txt') icon = 'file-earmark-text';
                else if (file.file_type === 'xlsx' || file.file_type === 'xls') icon = 'file-earmark-spreadsheet';
                else if (file.file_type === 'image') icon = 'image';

                const item = document.createElement('li');
                item.className = 'list-group-item d-flex align-items-center gap-3';
                item.innerHTML = `
                    <i class="bi bi-${icon} file-icon file-icon-${file.file_type} text-muted" aria-hidden="true"></i>
                    <div class="flex-grow-1">
                        <div class="fw-semibold text-truncate">${file.filename}</div>
                        <small class="text-muted file-size">${(file.file_size / 1024).toFixed(1)} KB</small>
                    </div>
                    <button class="btn btn-outline-danger btn-sm icon-button icon-button-danger delete-btn" data-id="${file.id}" type="button" aria-label="Delete file">
                        <i class="bi bi-trash" aria-hidden="true"></i>
                    </button>
                `;
                item.querySelector('.delete-btn').addEventListener('click', () => deleteFile(file.id));
                container.appendChild(item);
            });
        });
}

function deleteFile(id) {
    if (!confirm('Delete file?')) return;

    fetch(`/api/files/${id}`, { method: 'DELETE' })
        .then((r) => r.json())
        .then((result) => {
            if (result.status) {
                showToast('Deleted', 'success');
                loadUploadedFiles();
            }
        });
}
