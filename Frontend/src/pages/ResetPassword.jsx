import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, logout } from "../api.js";
import Brand from "../components/Brand.jsx";
import ThemeToggle from "../components/ThemeToggle.jsx";
import { useDocumentTitle } from "../utils/useDocumentTitle.js";

const INVALID_LINK = "This reset link is invalid or has expired.";

export default function ResetPassword() {
  useDocumentTitle("Choose a new password");
  const [params] = useSearchParams();
  const uid = params.get("uid") || "";
  const token = params.get("token") || "";
  const validLink = Boolean(uid && token);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState(validLink ? "" : INVALID_LINK);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (password !== confirm) {
      setError("The passwords don't match.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await api.resetPassword({ uid, token, new_password: password });
      // Any session in this browser has just ended too.
      logout();
      setDone(true);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <header className="landing-nav">
        <Brand to="/" />
        <nav className="landing-nav-links" aria-label="Primary">
          <ThemeToggle />
        </nav>
      </header>
      <div className="auth-screen">
        <form className="auth-card" onSubmit={handleSubmit}>
          <h1>{done ? "Password changed" : "Choose a new password"}</h1>
          {done ? (
            <p className="auth-subtitle" role="status">
              You can now sign in with it. Any other devices have been signed out.
            </p>
          ) : (
            <>
              <label className="field">
                <span>New password</span>
                <input
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                />
              </label>
              <label className="field">
                <span>Confirm new password</span>
                <input
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </label>
              {error && (
                <div className="error-banner" role="alert">
                  {error}
                </div>
              )}
              <button className="btn primary" type="submit" disabled={busy || !validLink}>
                {busy ? "One moment…" : "Change password"}
              </button>
            </>
          )}
          <div className="auth-alt">
            {done ? (
              <Link to="/login" className="link-btn">
                Go to sign in
              </Link>
            ) : (
              <Link to="/forgot-password" className="link-btn">
                Send a new reset link
              </Link>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
