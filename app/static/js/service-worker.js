// /static/js/service-worker.js
// Service Worker SIMPLE para offline + caché
 
const CACHE_NAME = 'misionales-v1';
const URLS_TO_CACHE = [
  '/',
  '/login',
  '/static/css/incubant-theme.css',
  '/static/img/logotipo_01.png',
  '/static/js/offline-handler.js'
];
 
// ============================================
// 1. INSTALAR - Cachear assets críticos
// ============================================
self.addEventListener('install', (event) => {
  console.log('🔧 Service Worker: Instalando...');
  
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('✅ Assets cacheados:', URLS_TO_CACHE);
      return cache.addAll(URLS_TO_CACHE);
    }).catch(err => {
      console.log('⚠️ Error cacheando:', err);
    })
  );
  
  self.skipWaiting();
});
 
// ============================================
// 2. ACTIVAR - Limpiar caché viejo
// ============================================
self.addEventListener('activate', (event) => {
  console.log('⚡ Service Worker: Activando...');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('🗑️ Limpiando caché viejo:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  
  self.clients.claim();
});
 
// ============================================
// 3. FETCH - Estrategia: Caché primero
// ============================================
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
 
  // NO cachear peticiones a API (siempre traer del servidor)
  if (url.pathname.startsWith('/inspecciones/submit') || 
      url.pathname.startsWith('/auth/') ||
      url.pathname.startsWith('/api/')) {
    return event.respondWith(
      fetch(request)
        .then(response => response)
        .catch(() => {
          // Si falla API y estamos offline, devolver error JSON
          return new Response(
            JSON.stringify({ error: 'Sin conexión. Los datos se enviarán cuando haya internet.' }),
            { status: 503, headers: { 'Content-Type': 'application/json' } }
          );
        })
    );
  }
 
  // Para assets (CSS, JS, imágenes): usar caché
  event.respondWith(
    caches.match(request).then((response) => {
      if (response) {
        console.log('📦 Desde caché:', url.pathname);
        return response;
      }
 
      return fetch(request).then((response) => {
        // Si es éxito, cachear para próximas veces
        if (response.ok && request.method === 'GET') {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseClone);
          });
        }
        return response;
      }).catch((error) => {
        console.log('❌ Error y sin caché:', url.pathname, error);
        
        // Si es una página HTML, devolver una página offline
        if (request.mode === 'navigate') {
          return caches.match('/login').catch(() => {
            return new Response(
              '<h1>Sin conexión</h1><p>Intenta más tarde.</p>',
              { status: 503, headers: { 'Content-Type': 'text/html' } }
            );
          });
        }
 
        return new Response('Recurso no disponible', { status: 404 });
      });
    })
  );
});