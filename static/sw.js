const CACHE_NAME = 'studylib-v1';
const STATIC_ASSETS = [
    '/',
    '/static/css/custom.css',
    '/static/js/main.js',
    '/static/js/page-loader.js',
    '/static/js/theme.js',
    '/static/js/toast.js',
    '/static/js/keyboard.js',
    '/static/img/favicon.svg',
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(cached => {
            if (cached) return cached;
            return fetch(event.request).then(response => {
                if (event.request.url.includes('/api/workspace/')) {
                    const clone = response.clone();
                    caches.open('api-cache').then(cache => {
                        cache.put(event.request, clone);
                    });
                }
                return response;
            }).catch(() => {
                if (event.request.mode === 'navigate') {
                    return caches.match('/');
                }
                return new Response('Offline', { status: 503 });
            });
        })
    );
});
