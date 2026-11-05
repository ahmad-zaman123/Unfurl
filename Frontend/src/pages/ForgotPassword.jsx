import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api.js";
import Brand from "../components/Brand.jsx";
import ThemeToggle from "../components/ThemeToggle.jsx";
import { useDocumentTitle } from "../utils/useDocumentTitle.js";

export default function ForgotPassword() {
  useDocumentTitle("Reset your password");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      setSent((await api.forgotPassword(email)).detail);
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
          <h1>Reset your password</h1>
          {sent ? (
            <p className="auth-subtitle" role="status">
              {sent} It expires in 15 minutes, so check your spam folder if you don&apos;t see it.
            </p>
          ) : (
            <>
              <p className="auth-subtitle">Enter your email and we&apos;ll send you a link to choose a new one.</p>
              <label className="field">
                <span>Email</span>
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </label>
              {error && (
                <div className="error-banner" role="alert">
                  {error}
                </div>
              )}
              <button className="btn primary" type="submit" disabled={busy}>
                {busy ? "One moment…" : "Send reset link"}
              </button>
            </>
          )}
          <div className="auth-alt">
            <Link to="/login" className="link-btn">
              Back to sign in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
