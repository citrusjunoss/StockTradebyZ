/**
 * 服务工作者 (Service Worker)
 * 提供离线缓存、后台同步和推送通知功能
 */

const CACHE_NAME = 'stock-trader-v1';
const API_CACHE_NAME = 'stock-trader-api-v1';
const CACHE_EXPIRY = 7 * 24 * 60 * 60 * 1000; // 7天

// 需要缓存的静态资源
const STATIC_ASSETS = [
    '/',
    '/static/css/main.css',
    '/static/js/cache.js',
    '/static/js/api.js',
    '/static/js/app.js',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png',
    '/manifest.json',
    // 外部资源
    'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js'
];

// API路径模式
const API_PATTERNS = [
    /^\/api\/dates/,
    /^\/api\/results\/\d{4}-\d{2}-\d{2}/,
    /^\/api\/statistics/,
    /^\/api\/search/
];

/**
 * 安装事件 - 预缓存静态资源
 */
self.addEventListener('install', event => {
    console.log('[SW] 安装服务工作者');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[SW] 缓存静态资源');
                return cache.addAll(STATIC_ASSETS);
            })
            .catch(error => {
                console.error('[SW] 缓存静态资源失败:', error);
            })
    );
    
    // 立即激活新的服务工作者
    self.skipWaiting();
});

/**
 * 激活事件 - 清理旧缓存
 */
self.addEventListener('activate', event => {
    console.log('[SW] 激活服务工作者');
    
    event.waitUntil(
        Promise.all([
            // 清理旧的缓存
            caches.keys().then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== CACHE_NAME && cacheName !== API_CACHE_NAME) {
                            console.log('[SW] 删除旧缓存:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            }),
            // 立即控制所有客户端
            clients.claim()
        ])
    );
});

/**
 * 获取事件 - 缓存策略
 */
self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    
    // 只处理同源请求或外部CDN资源
    if (url.origin !== location.origin && !isAllowedExternalResource(url)) {
        return;
    }
    
    // 根据资源类型选择缓存策略
    if (isStaticAsset(request)) {
        // 静态资源：缓存优先
        event.respondWith(cacheFirst(request));
    } else if (isAPIRequest(request)) {
        // API请求：网络优先，带缓存回退
        event.respondWith(networkFirstWithCache(request));
    } else {
        // 其他请求：网络优先
        event.respondWith(networkFirst(request));
    }
});

/**
 * 检查是否为静态资源
 */
function isStaticAsset(request) {
    const url = new URL(request.url);
    
    // 静态文件扩展名
    const staticExtensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2'];
    
    return staticExtensions.some(ext => url.pathname.endsWith(ext)) ||
           url.pathname.startsWith('/static/') ||
           url.pathname === '/manifest.json' ||
           isAllowedExternalResource(url);
}

/**
 * 检查是否为API请求
 */
function isAPIRequest(request) {
    const url = new URL(request.url);
    return API_PATTERNS.some(pattern => pattern.test(url.pathname));
}

/**
 * 检查是否为允许的外部资源
 */
function isAllowedExternalResource(url) {
    const allowedDomains = [
        'cdn.jsdelivr.net',
        'cdnjs.cloudflare.com'
    ];
    
    return allowedDomains.some(domain => url.hostname === domain);
}

/**
 * 缓存优先策略
 */
async function cacheFirst(request) {
    try {
        const cachedResponse = await caches.match(request);
        
        if (cachedResponse) {
            // 检查缓存是否过期（仅对API缓存）
            const cacheDate = cachedResponse.headers.get('sw-cache-date');
            if (cacheDate && Date.now() - new Date(cacheDate).getTime() > CACHE_EXPIRY) {
                console.log('[SW] 缓存已过期:', request.url);
            } else {
                console.log('[SW] 使用缓存:', request.url);
                return cachedResponse;
            }
        }
        
        // 缓存未命中或过期，从网络获取
        const response = await fetch(request);
        
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        
        return response;
        
    } catch (error) {
        console.error('[SW] 缓存优先策略失败:', error);
        
        // 网络失败时尝试返回缓存
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // 返回离线页面或错误响应
        return new Response('离线模式 - 资源不可用', {
            status: 503,
            statusText: 'Service Unavailable'
        });
    }
}

/**
 * 网络优先策略（带缓存）
 */
async function networkFirstWithCache(request) {
    try {
        // 先尝试网络请求
        const response = await fetch(request);
        
        if (response.ok) {
            // 缓存成功的API响应
            const cache = await caches.open(API_CACHE_NAME);
            const responseToCache = response.clone();
            
            // 添加缓存时间戳
            const headers = new Headers(responseToCache.headers);
            headers.set('sw-cache-date', new Date().toISOString());
            
            const cachedResponse = new Response(responseToCache.body, {
                status: responseToCache.status,
                statusText: responseToCache.statusText,
                headers: headers
            });
            
            cache.put(request, cachedResponse);
            console.log('[SW] 缓存API响应:', request.url);
        }
        
        return response;
        
    } catch (error) {
        console.log('[SW] 网络请求失败，尝试使用缓存:', request.url);
        
        // 网络失败，尝试使用缓存
        const cachedResponse = await caches.match(request);
        
        if (cachedResponse) {
            console.log('[SW] 使用缓存的API响应:', request.url);
            return cachedResponse;
        }
        
        // 没有缓存，返回错误响应
        return new Response(JSON.stringify({
            status: 'error',
            message: '网络不可用且无缓存数据'
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

/**
 * 网络优先策略
 */
async function networkFirst(request) {
    try {
        return await fetch(request);
    } catch (error) {
        // 对于HTML页面，可以返回离线页面
        if (request.headers.get('accept').includes('text/html')) {
            const cachedResponse = await caches.match('/');
            if (cachedResponse) {
                return cachedResponse;
            }
        }
        
        throw error;
    }
}

/**
 * 后台同步事件
 */
self.addEventListener('sync', event => {
    if (event.tag === 'background-sync') {
        console.log('[SW] 执行后台同步');
        event.waitUntil(doBackgroundSync());
    }
});

/**
 * 执行后台同步
 */
async function doBackgroundSync() {
    try {
        // 这里可以执行数据同步逻辑
        // 例如：预加载最新的选股结果
        
        const response = await fetch('/api/dates');
        if (response.ok) {
            const dates = await response.json();
            
            // 预加载最近的选股结果
            if (dates.data && dates.data.length > 0) {
                const latestDate = dates.data[0];
                await fetch(`/api/results/${latestDate}`);
                console.log('[SW] 后台同步完成');
            }
        }
    } catch (error) {
        console.error('[SW] 后台同步失败:', error);
    }
}

/**
 * 推送消息事件
 */
self.addEventListener('push', event => {
    console.log('[SW] 收到推送消息');
    
    const options = {
        body: '有新的选股结果可查看',
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/badge-72x72.png',
        vibrate: [200, 100, 200],
        data: {
            url: '/'
        },
        actions: [
            {
                action: 'view',
                title: '查看结果',
                icon: '/static/icons/action-view.png'
            },
            {
                action: 'dismiss',
                title: '稍后查看',
                icon: '/static/icons/action-dismiss.png'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification('股票选择系统', options)
    );
});

/**
 * 通知点击事件
 */
self.addEventListener('notificationclick', event => {
    event.notification.close();
    
    if (event.action === 'view') {
        // 打开应用
        event.waitUntil(
            clients.openWindow(event.notification.data.url || '/')
        );
    }
    // dismiss action不需要额外处理
});

/**
 * 消息事件 - 与客户端通信
 */
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'CACHE_STATS') {
        // 返回缓存统计信息
        getCacheStats().then(stats => {
            event.ports[0].postMessage({ stats });
        });
    }
});

/**
 * 获取缓存统计信息
 */
async function getCacheStats() {
    const cacheNames = await caches.keys();
    const stats = {};
    
    for (const cacheName of cacheNames) {
        const cache = await caches.open(cacheName);
        const keys = await cache.keys();
        stats[cacheName] = keys.length;
    }
    
    return stats;
}