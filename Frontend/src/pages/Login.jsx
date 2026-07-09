import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { api } from "../api.js";

const DEMO_EMAIL = "demo@unfurl.app";
const DEMO_PASSWORD = "demo1234";

function EyeIcon({ off }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
      <path
        d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.6" />
      {off && (
        <path d="M4 4l16 16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      )}
    </svg>
  );
}

export default function Login() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const [isRegister, setIsRegister] = useState(Boolean(state?.register));
  const [email, setEmail] = useState(state?.demo ? DEMO_EMAIL : "");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState(state?.demo ? DEMO_PASSWORD : "");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (isRegister) {
        await api.register({ email, full_name: fullName, password });
      }
      await api.login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="brand">Unfurl</div>
        <p className="auth-subtitle">Social preview images as an API.</p>

        {isRegister && (
          <label className="field">
            <span>Full name</span>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Ada Lovelace"
            />
          </label>
        )}

        <label className="field">
          <span>Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </label>

        <label className="field">
          <span>Password</span>
          <div className="input-wrap">
            <input
              type={showPassword ? "text" : "password"}
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
            <button
              type="button"
              className="reveal-btn"
              onClick={() => setShowPassword((visible) => !visible)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              title={showPassword ? "Hide password" : "Show password"}
            >
              <EyeIcon off={showPassword} />
            </button>
          </div>
        </label>

        {error && <div className="error-banner">{error}</div>}

        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? "Please wait…" : isRegister ? "Create account" : "Sign in"}
        </button>

        <button
          type="button"
          className="link-btn"
          onClick={() => {
            setError("");
            setIsRegister(!isRegister);
          }}
        >
          {isRegister ? "Already have an account? Sign in" : "New here? Create an account"}
        </button>
      </form>
    </div>
  );
}
