export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const token = typeof window !== "undefined" ? localStorage.getItem("buildwatch_token") : null;
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

export function saveToken(token: string) { localStorage.setItem("buildwatch_token", token); }
export function clearToken() { localStorage.removeItem("buildwatch_token"); }
