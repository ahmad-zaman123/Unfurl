import { Navigate, Route, Routes } from "react-router-dom";

import { isAuthenticated } from "./api.js";
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Docs from "./pages/Docs.jsx";

function Home() {
  return isAuthenticated() ? <Dashboard /> : <Landing />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/docs" element={<Docs />} />
      <Route path="/" element={<Home />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
