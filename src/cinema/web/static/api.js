let configPromise;

export async function getConfig() {
  configPromise ??= fetchJson('/api/config');
  return configPromise;
}

export async function initializeAuth(container) {
  const config = await getConfig();
  if (!config.authEnabled) {
    container.textContent = 'מצב פיתוח מקומי';
    return;
  }
  await loadScript(config.clerkScriptUrl, config.publishableKey);
  await window.Clerk.load();
  if (!window.Clerk.user) {
    window.Clerk.mountSignIn(container);
    return;
  }
  window.Clerk.mountUserButton(container);
}

export async function api(path, options = {}) {
  const config = await getConfig();
  const headers = new Headers(options.headers || {});
  if (options.body) headers.set('Content-Type', 'application/json');
  if (config.authEnabled) {
    const token = await window.Clerk?.session?.getToken();
    if (!token) throw new Error('יש להתחבר לפני ביצוע הפעולה');
    headers.set('Authorization', `Bearer ${token}`);
  }
  return fetchJson(path, {...options, headers});
}

export async function fetchJson(path, options = {}) {
  const response = await fetch(path, options);
  const payload = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(payload?.detail || 'הפעולה נכשלה');
  return payload;
}

export function setStatus(message, isError = false) {
  const element = document.querySelector('#status');
  element.textContent = message;
  element.classList.toggle('error', isError);
}

function loadScript(source, publishableKey) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.async = true;
    script.crossOrigin = 'anonymous';
    script.dataset.clerkPublishableKey = publishableKey;
    script.src = source;
    script.addEventListener('load', resolve, {once: true});
    script.addEventListener('error', () => reject(new Error('טעינת ההזדהות נכשלה')), {once: true});
    document.head.append(script);
  });
}
