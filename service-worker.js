const CACHE_NAME = 'ics-course-table-v1';
const ASSETS_TO_CACHE = [
  './',
  './index.html',
  './config.json',
  './course_114-1.json',
  './course_114-2.json',
  './manifest.json',
  './icon-192.png',
  './icon-512.png'
];

// 安裝 SW 並快取靜態資源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('Opened cache');
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  // 強制讓新的 SW 立即接管
  self.skipWaiting();
});

// 啟用 SW 並清除舊快取
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  // 讓 SW 立即控制所有客戶端
  return self.clients.claim();
});

// 攔截請求：Stale-While-Revalidate 策略
// 優先返回快取內容，同時在背景更新快取
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.match(event.request).then((cachedResponse) => {
        const fetchPromise = fetch(event.request)
          .then((networkResponse) => {
            // 只快取成功的 GET 請求
            if (networkResponse.ok && event.request.method === 'GET') {
              cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
          })
          .catch((error) => {
            console.log('Fetch failed; returning offline page if available.', error);
            // 可以在此處理離線 fallback
          });

        // 如果有快取，優先返回快取，否則等待網路回應
        return cachedResponse || fetchPromise;
      });
    })
  );
});
