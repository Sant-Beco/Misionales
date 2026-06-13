// /static/js/service-worker.js
// Service Worker FIXED - Caché + offline completo

const CACHE_NAME = 'misionales-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/login',
  '/static/css/incubant-theme.css',
  '/static/img/logotipo_01.png'
];

// ============================================
// 1. INSTALAR - Cachear assets críticos
// ============================================
self.addEventListener('install', (event) => {
  console.log('🔧 SW: Instalando...');
  
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('✅ SW: Assets cacheados');
      return cache.addAll(ASSETS_TO_CACHE).catch(err => {
        console.log('⚠️ SW: Error cacheando algunos assets:', err);
        // No fallar si algunos assets no se pueden cachear
        return Promise.resolve();
      });
    })
  );
  
  self.skipWaiting();
});

// ============================================
// 2. ACTIVAR - Limpiar caché viejo
// ============================================
self.addEventListener('activate', (event) => {
  console.log('⚡ SW: Activando...');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('🗑️ SW: Limpiando caché viejo:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  
  self.clients.claim();
});

// ============================================
// 3. FETCH - Estrategia: Network-First con fallback a caché
// ============================================
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // NO cachear API ni admin (siempre del servidor)
  if (url.pathname.startsWith('/inspecciones/submit') || 
      url.pathname.startsWith('/auth/') ||
      url.pathname.startsWith('/admin')) {
    
    return event.respondWith(
      fetch(request)
        .then(response => {
          console.log('✅ API responde:', url.pathname);
          return response;
        })
        .catch(() => {
          console.log('❌ API sin conexión:', url.pathname);
          return new Response(
            JSON.stringify({ error: 'Sin conexión. Los datos se enviarán cuando haya internet.' }),
            { 
              status: 503, 
              headers: { 'Content-Type': 'application/json' } 
            }
          );
        })
    );
  }

  // Para assets estáticos (CSS, JS, imágenes, fonts)
  if (url.pathname.startsWith('/static/')) {
    return event.respondWith(
      caches.match(request).then(response => {
        if (response) {
          console.log('📦 Desde caché:', url.pathname);
          return response;
        }

        return fetch(request)
          .then(response => {
            // Cachear si es éxito
            if (response.ok && request.method === 'GET') {
              const responseClone = response.clone();
              caches.open(CACHE_NAME).then(cache => {
                cache.put(request, responseClone);
              });
            }
            console.log('🌐 Desde red:', url.pathname);
            return response;
          })
          .catch(() => {
            console.log('❌ Sin caché ni red:', url.pathname);
            // Retornar algo genérico
            return new Response('Recurso no disponible', { status: 404 });
          });
      })
    );
  }

  // Para páginas HTML (/, /login, etc)
  return event.respondWith(
    fetch(request)
      .then(response => {
        // Cachear páginas HTML exitosas
        if (response.ok && request.method === 'GET') {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, responseClone);
          });
        }
        console.log('🌐 Página desde red:', url.pathname);
        return response;
      })
      .catch(() => {
        // Si falla, intentar desde caché
        console.log('🔄 Intentando caché:', url.pathname);
        return caches.match(request)
          .then(response => {
            if (response) {
              console.log('📦 Página desde caché:', url.pathname);
              return response;
            }
            
            // Si ni en caché ni en red, devolver página offline
            console.log('❌ Sin caché ni red:', url.pathname);
            return caches.match('/login')
              .then(loginPage => {
                if (loginPage) return loginPage;
                
                return new Response(
                  `
                    <html>
                    <head>
                      <meta charset="UTF-8">
                      <meta name="viewport" content="width=device-width, initial-scale=1.0">
                      <title>Sin conexión</title>
                      <style>
                        body {
                          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                          background: #1a1a1a;
                          color: #fff;
                          display: flex;
                          align-items: center;
                          justify-content: center;
                          min-height: 100vh;
                          margin: 0;
                          padding: 20px;
                        }
                        .container {
                          text-align: center;
                          max-width: 500px;
                        }
                        h1 { font-size: 3em; margin: 0 0 20px; }
                        p { font-size: 1.2em; color: #ccc; line-height: 1.6; }
                      </style>
                    </head>
                    <body>
                      <div class="container">
                        <h1>📵</h1>
                        <h2>Sin conexión</h2>
                        <p>No hay conexión a internet y no pudimos cargar esta página del caché.</p>
                        <p>Intenta cuando tengas señal.</p>
                      </div>
                    </body>
                    </html>
                  `,
                  { 
                    status: 503, 
                    headers: { 'Content-Type': 'text/html; charset=utf-8' } 
                  }
                );
              });
          });
      })
  );
});