"use strict";

import { showToast } from './main.js';

const CLIENT_ID = "21b089d7-aa3e-478f-a992-9aa757adc73f";
const REDIRECT_URI = `${window.location.origin}/api/oidc/redirect`;

function toggleTheme() {
    const current = document.documentElement.getAttribute("data-bs-theme");
    const newTheme = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-bs-theme", newTheme);
    localStorage.setItem("theme", newTheme);
    updateThemeButton();
}

function updateThemeButton() {
    const themeBtn = document.getElementById("themeToggle");
    const current = document.documentElement.getAttribute("data-bs-theme");
    themeBtn.innerHTML = current === "dark" ? '<i class="bi bi-sun-fill"></i>' : '<i class="bi bi-moon-stars-fill"></i>';
}

function validateJWT(token) {
    // Simple validation - in production, use a library
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    const now = Math.floor(Date.now() / 1000);
    if (payload.exp < now || payload.iat > now || payload.nbf > now) return null;
    if (payload.iss !== "https://login.microsoftonline.com/common/v2.0" || payload.aud !== CLIENT_ID) return null;
    return payload;
}

function login() {
    const state = Math.random().toString(36);
    const nonce = Math.random().toString(36);
    sessionStorage.setItem("oidc_state", state);
    sessionStorage.setItem("oidc_nonce", nonce);
    
    const params = new URLSearchParams({
        client_id: CLIENT_ID,
        response_type: "id_token",
        redirect_uri: REDIRECT_URI,
        scope: "openid profile email",
        state: state,
        nonce: nonce,
        prompt: "none"
    });
    const url = `https://login.microsoftonline.com/common/oauth2/v2.0/authorize?${params}`;
    const popup = window.open(url, "login", "width=500,height=600");
    
    window.addEventListener("message", function handler(event) {
        if (event.origin !== window.location.origin) return;
        const data = event.data;
        if (data.type === "oidc_result") {
            window.removeEventListener("message", handler);
            popup.close();
            if (data.error) {
                if (data.error === "login_required" || data.error === "interaction_required") {
                    // Retry with prompt=login
                    params.set("prompt", "login");
                    const retryUrl = `https://login.microsoftonline.com/common/oauth2/v2.0/authorize?${params}`;
                    const retryPopup = window.open(retryUrl, "login", "width=500,height=600");
                    window.addEventListener("message", function retryHandler(event2) {
                        if (event2.origin !== window.location.origin) return;
                        const data2 = event2.data;
                        if (data2.type === "oidc_result") {
                            window.removeEventListener("message", retryHandler);
                            retryPopup.close();
                            handleLoginResult(data2);
                        }
                    });
                } else {
                    showToast("Login failed", "danger");
                }
            } else {
                handleLoginResult(data);
            }
        }
    });
}

function handleLoginResult(data) {
    if (data.id_token) {
        const payload = validateJWT(data.id_token);
        if (!payload) {
            showToast("Invalid token", "danger");
            return;
        }
        fetch("/api/users/login", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                platform: "ms",
                platform_id: { oid: payload.oid, tid: payload.tid },
                email: payload.email || payload.preferred_username,
                name: payload.name,
                username: payload.preferred_username
            })
        }).then(r => r.json()).then(result => {
            if (result.status) {
                document.getElementById("loginBtn").textContent = "LOGOUT";
                showToast("Logged in successfully", "success");
                // Update UI with saved, etc.
                if (window.updateHomeSections) window.updateHomeSections(result);
            } else {
                showToast("Login failed", "danger");
            }
        });
    } else {
        showToast("Login failed", "danger");
    }
}

function logout() {
    fetch("/api/users/logout").then(() => {
        document.getElementById("loginBtn").textContent = "LOGIN";
        showToast("Logged out", "info");
        window.location.href = "/";
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const loginBtn = document.getElementById("loginBtn");
    const themeBtn = document.getElementById("themeToggle");
    
    if (themeBtn) {
        themeBtn.addEventListener("click", toggleTheme);
        updateThemeButton();
    }
    
    if (loginBtn) {
        loginBtn.addEventListener("click", () => {
            if (loginBtn.textContent === "LOGIN") {
                login();
            } else {
                logout();
            }
        });
    }
});