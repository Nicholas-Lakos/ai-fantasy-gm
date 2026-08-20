const CACHE='ai-fantasy-gm-static-v1';
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(c => c.addAll(['/','/manifest.webmanifest']))));
self.addEventListener('fetch', event => {
  const u=new URL(event.request.url);
  if (u.origin!==location.origin || u.pathname.startsWith('/auth/') || u.pathname.startsWith('/dashboard') || u.pathname.startsWith('/espn/') || u.pathname.startsWith('/ai/')) return;
  event.respondWith(caches.match(event.request).then(r=>r||fetch(event.request).then(res=>{const copy=res.clone();caches.open(CACHE).then(c=>c.put(event.request,copy));return res;})));
});
