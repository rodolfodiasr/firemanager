// SecOps PWA Service Worker
// Altere a versão para forçar atualização em todos os clientes
const VERSION = 'v1';
const CACHE_SHELL = `secops-shell-${VERSION}`;
const CACHE_ASSETS = `secops-assets-${VERSION}`;

// Rotas que NUNCA devem ser cacheadas (dados em tempo real)
const NO_CACHE_PATTERNS = [
  /\/auth\//,
  /\/devices/,
  /\/alerts/,
  /\/assistant/,
  /\/operations/,
  /\/audit/,
  /\/connectivity/,
  /\/executive/,
  /\/investigations/,
  /\/rmm/,
  /\/servers/,
  /\/network-segments/,
  /\/server-groups/,
  /\/health/,
];

const isApiCall = (url) => {
  const path = new URL(url).pathname;
  return NO_CACHE_PATTERNS.some((p) => p.test(path));
};

const isStaticAsset = (url) => {
  return /\.(js|css|woff2?|png|svg|ico|webp)(\?.*)?$/.test(url);
};

// ── Install: pré-caching mínimo ───────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_SHELL).then((cache) =>
      cache.addAll(['/'])
    )
  );
  // Ativa imediatamente sem esperar tabs antigas fecharem
  self.skipWaiting();
});

// ── Activate: limpa caches de versões antigas ─────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_SHELL && k !== CACHE_ASSETS)
          .map((k) => caches.delete(k))
      )
    ).then(() => {
      // Notifica todas as tabs abertas que há nova versão
      self.clients.matchAll({ includeUncontrolled: true }).then((clients) => {
        clients.forEach((client) =>
          client.postMessage({ type: 'SW_UPDATED', version: VERSION })
        );
      });
      return self.clients.claim();
    })
  );
});

// ── Fetch: estratégia por tipo de request ─────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = request.url;

  // Ignora requests que não são HTTP/HTTPS (chrome-extension, etc)
  if (!url.startsWith('http')) return;

  // Ignora POST, PUT, DELETE, PATCH — nunca cachear mutações
  if (request.method !== 'GET') return;

  // Chamadas de API: Network Only — nunca cachear
  if (isApiCall(url)) return;

  // Assets estáticos com hash (JS/CSS do Vite): Cache First
  // Vite gera hashes nos filenames, então cache é seguro
  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_ASSETS).then((cache) => cache.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // Navegação (HTML/SPA): Network First com fallback para shell cacheado
  // Garante que o usuário sempre veja a versão mais recente
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_SHELL).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() =>
          caches.match('/').then((cached) => cached || caches.match('/index.html'))
        )
    );
    return;
  }
});

// ── Push notifications (para uso futuro com alertas) ─────────────────────────
self.addEventListener('push', (event) => {
  if (!event.data) return;

  let data;
  try { data = event.data.json(); } catch { return; }

  const options = {
    body: data.body || 'Novo alerta na plataforma',
    icon: '/icons/icon.svg',
    badge: '/icons/icon.svg',
    tag: data.tag || 'secops-alert',
    renotify: true,
    requireInteraction: data.priority === 'critical',
    data: { url: data.url || '/alerts' },
    actions: [
      { action: 'open', title: 'Ver detalhes' },
      { action: 'dismiss', title: 'Dispensar' },
    ],
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'SecOps Alert', options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const targetUrl = event.notification.data?.url || '/alerts';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      const existing = clients.find((c) => c.url.includes(self.location.origin));
      if (existing) {
        existing.focus();
        existing.navigate(targetUrl);
      } else {
        self.clients.openWindow(targetUrl);
      }
    })
  );
});
