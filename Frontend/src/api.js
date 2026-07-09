const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8010").replace(/\/+$/, "");

const ACCESS_KEY = "unfurl_access";
const REFRESH_KEY = "unfurl_refresh";

export function isAuthenticated() {
  return Boolean(localStorage.getItem(ACCESS_KEY));
}

export function ogImageUrl(params) {
  const url = new URL(API_URL + "/api/v1/og");
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });
  return url.toString();
}

export function logout() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

function extractError(data) {
  if (!data) {
    return null;
  }
  if (typeof data === "string") {
    return data;
  }
  if (data.detail) {
    return data.detail;
  }
  const first = Object.values(data)[0];
  if (Array.isArray(first)) {
    return first[0];
  }
  if (typeof first === "string") {
    return first;
  }
  return null;
}

async function request(path, { method = "GET", body, auth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = localStorage.getItem(ACCESS_KEY);
    if (token) {
      headers.Authorization = "Bearer " + token;
    }
  }
  const response = await fetch(API_URL + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(extractError(data) || "Request failed (" + response.status + ")");
  }
  return data;
}

export const api = {
  register({ email, full_name, password }) {
    return request("/api/auth/register/", {
      method: "POST",
      body: { email, full_name, password },
    });
  },
  async login(email, password) {
    const data = await request("/api/auth/token/", {
      method: "POST",
      body: { email, password },
    });
    localStorage.setItem(ACCESS_KEY, data.access);
    localStorage.setItem(REFRESH_KEY, data.refresh);
    return data;
  },
  me() {
    return request("/api/auth/me/", { auth: true });
  },
  createCard(spec) {
    return request("/api/v1/cards", { method: "POST", body: spec, auth: true });
  },
  listKeys() {
    return request("/api/keys/", { auth: true });
  },
  createKey(name) {
    return request("/api/keys/", { method: "POST", body: { name }, auth: true });
  },
  revokeKey(id) {
    return request("/api/keys/" + id + "/", { method: "DELETE", auth: true });
  },
  getUsage() {
    return request("/api/usage/", { auth: true });
  },
};
