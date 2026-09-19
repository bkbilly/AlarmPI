/**
 * AlarmPI Service Worker for Browser Web Push Notifications.
 * Handles background push alerts, rich notifications, and notification click navigation.
 */

self.addEventListener('install', function(event) {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', function(event) {
  let data = {
    title: '🚨 AlarmPI Security Alert',
    message: 'A security event has been detected.',
    is_alarm: false,
    url: '/'
  };

  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data.message = event.data.text();
    }
  }

  const title = data.title || '🚨 AlarmPI Alert';
  const isAlarm = Boolean(data.is_alarm);

  const options = {
    body: data.message || data.body || 'AlarmPI Event',
    icon: '/static/icon.png',
    badge: '/static/icon.png',
    tag: isAlarm ? 'alarmpi-alarm-' + Date.now() : 'alarmpi-status',
    renotify: true,
    requireInteraction: isAlarm,
    vibrate: isAlarm ? [500, 200, 500, 200, 500, 200, 1000] : [200, 100, 200],
    data: {
      url: data.url || '/',
      timestamp: data.timestamp || Date.now()
    },
    actions: [
      { action: 'open', title: '🛡️ Open AlarmPI' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (let i = 0; i < clientList.length; i++) {
        const client = clientList[i];
        if (client.url && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
