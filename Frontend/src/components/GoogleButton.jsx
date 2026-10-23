import { useEffect, useRef, useState } from "react";

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const SCRIPT_SRC = "https://accounts.google.com/gsi/client";

function loadScript() {
  if (window.google?.accounts?.id) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${SCRIPT_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", resolve);
      existing.addEventListener("error", reject);
      return;
    }
    const s = document.createElement("script");
    s.src = SCRIPT_SRC;
    s.async = true;
    s.defer = true;
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

/**
 * Google's own sign-in button. Renders nothing unless VITE_GOOGLE_CLIENT_ID is set.
 * `onCredential(idToken)` receives the ID token to send to the backend.
 */
export default function GoogleButton({ onCredential, onError, text = "continue_with" }) {
  const holder = useRef(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!CLIENT_ID || !holder.current) return undefined;
    let cancelled = false;
    loadScript()
      .then(() => {
        if (cancelled || !holder.current) return;
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: (response) => onCredential(response.credential),
          ux_mode: "popup",
        });
        holder.current.innerHTML = "";
        window.google.accounts.id.renderButton(holder.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          text,
          shape: "rectangular",
          width: Math.min(400, holder.current.offsetWidth || 320),
        });
      })
      .catch(() => {
        setFailed(true);
        onError?.("Google sign-in could not load. Check your connection or use a password.");
      });
    return () => {
      cancelled = true;
    };
  }, [onCredential, onError, text]);

  if (!CLIENT_ID || failed) return null;
  return (
    <div className="google-signin">
      <div ref={holder} className="google-signin-button" />
      <div className="google-signin-or">
        <span>or</span>
      </div>
    </div>
  );
}
