import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, logout } from "../api.js";
import ApiKeys from "../components/ApiKeys.jsx";
import Playground from "../components/Playground.jsx";
import Usage from "../components/Usage.jsx";

export default function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => {
        logout();
        navigate("/login");
      });
  }, [navigate]);

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">Unfurl</div>
        <div className="topbar-right">
          {user && <span className="muted">{user.email}</span>}
          <button className="btn ghost small" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      <main className="dashboard">
        <Usage />
        <div className="panel">
          <div className="panel-head">
            <h2>Playground</h2>
          </div>
          <p className="muted">
            Build a card, then drop the URL into an <code>og:image</code> meta tag. Every
            change re-renders live through the signed API.
          </p>
        </div>
        <Playground />
        <ApiKeys />
      </main>
    </div>
  );
}
