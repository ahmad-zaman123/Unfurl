import { API_BASE } from "./lib.js";

// The app calls /api on its own address: Vercel (and the Vite dev server) pass those calls to the backend, so the
// sign-in cookies belong to this site. The tokens themselves are httpOnly cookies that scripts here can't read.
const API_URL = "";
const SIGNED_IN = "unfurl_signed_in";

// Tokens from before the switch to cookies.
localStorage.removeItem("unfurl_access");
localStorage.removeItem("unfurl_refresh");

export function isAuthenticated() {
  return localStorage.getItem(SIGNED_IN) === "1";
}

function markSignedIn() {
  localStorage.setItem(SIGNED_IN, "1");
}

export function ogImageUrl(params) {
  const url = new URL(API_BASE + "/api/v1/og");
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });
  return url.toString();
}

/** Forget the session here and ask the server to clear its cookies. */
export function logout() {
  localStorage.removeItem(SIGNED_IN);
  fetch("/api/auth/logout/", { method: "POST" }).catch(() => {});
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

// One refresh at a time: when several requests hit an expired token together
// they all wait for the same new access token instead of each asking for one.
let refreshing = null;

async function refreshAccess() {
  if (!refreshing) {
    refreshing = (async () => {
      if (!isAuthenticated()) return false;
      try {
        // The refresh token rides along as a cookie; the new access token comes back as one.
        const response = await fetch(API_URL + "/api/auth/token/refresh/", { method: "POST" });
        return response.ok;
      } catch {
        return false;
      }
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

/** The session is over: forget it and go to sign in, remembering where we were. */
function sessionExpired() {
  logout();
  if (window.location.pathname === "/login") return;
  const here = window.location.pathname + window.location.search;
  window.location.assign("/login?next=" + encodeURIComponent(here));
}

async function request(path, { method = "GET", body, auth = false, retry = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  const response = await fetch(API_URL + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  // Access tokens last an hour. On the first 401 of an authenticated call, get a fresh
  // one from the refresh cookie and retry once; if that fails too, the session is over.
  if (response.status === 401 && auth) {
    if (retry && (await refreshAccess())) {
      return request(path, { method, body, auth, retry: false });
    }
    sessionExpired();
    throw new Error("Your session has expired. Please sign in again.");
  }
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
    markSignedIn();
    return data;
  },
  me() {
    return request("/api/auth/me/", { auth: true });
  },
  /** Changing the password ends every session; the server sets fresh cookies for this one. */
  changePassword(payload) {
    return request("/api/auth/password/", { method: "POST", body: payload, auth: true });
  },
  forgotPassword(email) {
    return request("/api/auth/password/forgot/", { method: "POST", body: { email } });
  },
  resetPassword(payload) {
    return request("/api/auth/password/reset/", { method: "POST", body: payload });
  },
  /** A private demo: the server makes a fresh account with sample keys and usage and signs us in. */
  async startDemo() {
    const data = await request("/api/auth/demo/", { method: "POST" });
    markSignedIn();
    return data;
  },
  /** Exchange a Google ID token (from the Google button) for our session cookies; creates the account on first use. */
  async loginWithGoogle(credential) {
    const data = await request("/api/auth/google/", { method: "POST", body: { credential } });
    markSignedIn();
    return data;
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
  getBilling() {
    return request("/api/billing/", { auth: true });
  },
  startCheckout() {
    return request("/api/billing/checkout/", { method: "POST", auth: true });
  },
  openBillingPortal() {
    return request("/api/billing/portal/", { method: "POST", auth: true });
  },
};
