"use strict";

export const DEFAULT_BROWSE_SUMMARY_ERROR = "Unable to create overview. Try again.";

export async function fetchBrowseSummary(payload, signal) {
    let response;
    try {
        response = await fetch('/api/browse/summary', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal,
        });
    } catch (error) {
        if (error?.name === 'AbortError') throw error;
        throw new Error(DEFAULT_BROWSE_SUMMARY_ERROR);
    }

    let data = null;
    try {
        data = await response.json();
    } catch (_err) {
        throw new Error(DEFAULT_BROWSE_SUMMARY_ERROR);
    }

    const publicError = typeof data?.error === 'string' && data.error.trim()
        ? data.error.trim()
        : DEFAULT_BROWSE_SUMMARY_ERROR;
    if (!response.ok || data?.status !== true) throw new Error(publicError);
    if (typeof data.summary !== 'string' || !data.summary.trim()) {
        throw new Error(DEFAULT_BROWSE_SUMMARY_ERROR);
    }
    return data.summary.trim();
}
