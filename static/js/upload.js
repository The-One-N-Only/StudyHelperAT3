"use strict";

import { showToast } from './main.js';

document.addEventListener('DOMContentLoaded', () => {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const progressBar = document.getElementById('progressBar');
    
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
    
    loadUploadedFiles();
});

function handleFile(file) {
    // Validate
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
    
    document.getElementById('selectedFile').textContent = file.name;
    uploadBtn.disabled = false;
}

function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    const progressBar = document.getElementById('progressBar');
    progressBar.style.display = 'block';
    
    fetch('/api/files/upload', {
        method: 'POST',
        body: formData
    }).then(r => r.json()).then(result => {
        progressBar.style.display = 'none';
        if (result.status) {
            showToast('Uploaded successfully', 'success');
            document.getElementById('selectedFile').textContent = 'No file selected';
            document.getElementById('uploadBtn').disabled = true;
            document.getElementById('fileInput').value = '';
            loadUploadedFiles();
        } else {
            showToast(result.error, 'danger');
        }
    }).catch(() => {
        progressBar.style.display = 'none';
        showToast('Upload failed', 'danger');
    });
}

function loadUploadedFiles() {
    fetch('/api/files/list')
        .then(r => r.json())
        .then(result => {
            const container = document.getElementById('filesList');
            const countBadge = document.getElementById('fileCountBadge');
            container.innerHTML = '';
            countBadge.textContent = result.files.length;
            
            result.files.forEach(file => {
                let icon = 'file-earmark';
                if (file.file_type === 'pdf') icon = 'file-earmark-pdf';
                else if (file.file_type === 'docx') icon = 'file-earmark-word';
                else if (file.file_type === 'txt') icon = 'file-earmark-text';
                else if (file.file_type === 'xlsx' || file.file_type === 'xls') icon = 'file-earmark-spreadsheet';
                else if (file.file_type === 'image') icon = 'image';
                
                const item = document.createElement('li');
                item.className = 'list-group-item d-flex align-items-center gap-3';
                item.innerHTML = `
                    <i class="bi bi-${icon} text-muted"></i>
                    <div class="flex-grow-1">
                        <div class="fw-semibold text-truncate">${file.filename}</div>
                        <small class="text-muted">${(file.file_size / 1024).toFixed(1)} KB</small>
                    </div>
                    <button class="btn btn-outline-danger btn-sm delete-btn" data-id="${file.id}">
                        <i class="bi bi-trash"></i>
                    </button>
                `;
                item.querySelector('.delete-btn').addEventListener('click', () => deleteFile(file.id));
                container.appendChild(item);
            });
        });
}

function deleteFile(id) {
    if (confirm('Delete file?')) {
        fetch(`/api/files/${id}`, {method: 'DELETE'})
            .then(r => r.json())
            .then(result => {
                if (result.status) {
                    showToast('Deleted', 'success');
                    loadUploadedFiles();
                }
            });
    }
}