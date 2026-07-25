"use strict";

document.addEventListener('DOMContentLoaded', function () {
    const revokeForms = document.querySelectorAll('#sessionsTable form');
    revokeForms.forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!confirm('Are you sure you want to revoke this session?')) {
                e.preventDefault();
            }
        });
    });
});
