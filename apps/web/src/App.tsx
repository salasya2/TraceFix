import { NavLink, Route, Routes } from "react-router-dom";
import Overview from "./pages/Overview";
import RunDetail from "./pages/RunDetail";
import PatchReview from "./pages/PatchReview";
import Repositories from "./pages/Repositories";
import SettingsPage from "./pages/Settings";
import UsagePage from "./pages/Usage";
import Login from "./pages/Login";

export default function App() {
  return (
    <div className="shell">
      <nav className="nav">
        <h1>TraceFix</h1>
        <NavLink to="/" end>Overview</NavLink>
        <NavLink to="/repositories">Repositories</NavLink>
        <NavLink to="/usage">Usage</NavLink>
        <NavLink to="/settings">Organization</NavLink>
        <NavLink to="/login">Sign in</NavLink>
      </nav>
      <main className="main">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Overview />} />
          <Route path="/runs/:id" element={<RunDetail />} />
          <Route path="/runs/:id/patch/:candidateId" element={<PatchReview />} />
          <Route path="/repositories" element={<Repositories />} />
          <Route path="/usage" element={<UsagePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
