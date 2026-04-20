"use strict";

import { showToast } from './main.js';

let quill = null;
let currentNoteId = null;

function loadNotes() {
    fetch('/api/notes')
        .then(response => response.json())
        .then(data => {
            if (data.status) {
                displayNotes(data.notes);
            } else {
                showToast('Failed to load notes', 'danger');
            }
        })
        .catch(error => {
            console.error('Error loading notes:', error);
            showToast('Error loading notes', 'danger');
        });
}

function displayNotes(notes) {
    const container = document.getElementById('notesContainer');
    container.innerHTML = '';

    if (notes.length === 0) {
        container.innerHTML = '<p class="text-muted">No notes yet. Create your first note!</p>';
        return;
    }

    notes.forEach(note => {
        const noteCard = document.createElement('div');
        noteCard.className = 'card mb-3';
        noteCard.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">${note.title}</h5>
                <p class="card-text text-muted small">Updated: ${new Date(note.time_updated * 1000).toLocaleString()}</p>
                <div class="btn-group">
                    <button class="btn btn-sm btn-outline-primary edit-note-btn" data-id="${note.id}">Edit</button>
                    <button class="btn btn-sm btn-outline-danger delete-note-btn" data-id="${note.id}">Delete</button>
                </div>
            </div>
        `;
        container.appendChild(noteCard);
    });

    // Add event listeners
    document.querySelectorAll('.edit-note-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const noteId = e.target.dataset.id;
            editNote(noteId);
        });
    });

    document.querySelectorAll('.delete-note-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const noteId = e.target.dataset.id;
            deleteNote(noteId);
        });
    });
}

function createNote() {
    currentNoteId = null;
    showNoteEditor('', '');
}

function editNote(noteId) {
    fetch(`/api/notes/${noteId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status) {
                currentNoteId = noteId;
                showNoteEditor(data.note.title, data.note.content);
            } else {
                showToast('Failed to load note', 'danger');
            }
        })
        .catch(error => {
            console.error('Error loading note:', error);
            showToast('Error loading note', 'danger');
        });
}

function showNoteEditor(title, content) {
    const container = document.getElementById('notesContainer');
    container.innerHTML = `
        <div class="card">
            <div class="card-header">
                <input type="text" id="noteTitle" class="form-control" placeholder="Note Title" value="${title}">
            </div>
            <div class="card-body">
                <div id="editor" style="height: 400px;"></div>
            </div>
            <div class="card-footer">
                <button class="btn btn-success me-2" id="saveNoteBtn">Save</button>
                <button class="btn btn-secondary" id="cancelNoteBtn">Cancel</button>
            </div>
        </div>
    `;

    // Initialize Quill
    quill = new Quill('#editor', {
        theme: 'snow',
        modules: {
            toolbar: {
                container: [
                    [{ 'header': [1, 2, 3, false] }],
                    ['bold', 'italic', 'underline'],
                    ['link', 'image'],
                    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                    ['blockquote', 'code-block'],
                    [{ 'color': [] }, { 'background': [] }],
                    ['clean']
                ],
                handlers: {
                    image: imageHandler
                }
            }
        }
    });

    if (content) {
        quill.root.innerHTML = content;
    }

    document.getElementById('saveNoteBtn').addEventListener('click', saveNote);
    document.getElementById('cancelNoteBtn').addEventListener('click', () => loadNotes());
}

function saveNote() {
    const title = document.getElementById('noteTitle').value.trim();
    const content = quill.root.innerHTML;

    if (!title) {
        showToast('Title is required', 'warning');
        return;
    }

    const method = currentNoteId ? 'PUT' : 'POST';
    const url = currentNoteId ? `/api/notes/${currentNoteId}` : '/api/notes';

    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: title, content: content })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status) {
            showToast(currentNoteId ? 'Note updated' : 'Note created', 'success');
            loadNotes();
        } else {
            showToast('Failed to save note', 'danger');
        }
    })
    .catch(error => {
        console.error('Error saving note:', error);
        showToast('Error saving note', 'danger');
    });
}

function imageHandler() {
    const input = document.createElement('input');
    input.setAttribute('type', 'file');
    input.setAttribute('accept', 'image/*');
    input.click();

    input.onchange = () => {
        const file = input.files[0];
        if (file) {
            // Upload the file
            const formData = new FormData();
            formData.append('file', file);

            fetch('/api/files/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.status) {
                    const range = quill.getSelection();
                    quill.insertEmbed(range.index, 'image', data.url);
                } else {
                    showToast('Failed to upload image', 'danger');
                }
            })
            .catch(error => {
                console.error('Error uploading image:', error);
                showToast('Error uploading image', 'danger');
            });
        }
    };
}

document.addEventListener('DOMContentLoaded', () => {
    // Only load notes if on notes tab
    const notesTab = document.getElementById('notes-tab');
    if (notesTab) {
        notesTab.addEventListener('shown.bs.tab', loadNotes);
    }

    const createNoteBtn = document.getElementById('createNoteBtn');
    if (createNoteBtn) {
        createNoteBtn.addEventListener('click', createNote);
    }
});