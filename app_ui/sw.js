// Matka Tracker service worker — makes the web app installable + offline-capable.
const CACHE = "matka-v1";
const SHELL = ["./index.html", "./config.js", "./feed.js",
               "./manifest.webmanifest", "./icon.svg"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const url = e.request.url;
  // Always try the network first for the live data, fall back to cache offline.
  if (url.includes("feed.json")) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }
  // Shell: cache-first for instant load.
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
