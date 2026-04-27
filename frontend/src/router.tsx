import { Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "./store/authStore";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Agent } from "./pages/Agent";
import { Devices } from "./pages/Devices";
import { Operations } from "./pages/Operations";
import { Logs } from "./pages/Logs";
import { Settings } from "./pages/Settings";
import { Audit } from "./pages/Audit";
import { DirectMode } from "./pages/DirectMode";
import { Templates } from "./pages/Templates";
import { Inspector } from "./pages/Inspector";
import { Sidebar } from "./components/layout/Sidebar";

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return (
    <div className="flex">
      <Sidebar />
      {children}
    </div>
  );
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedLayout>
            <Dashboard />
          </ProtectedLayout>
        }
      />
      <Route
        path="/agent"
        element={
          <ProtectedLayout>
            <Agent />
          </ProtectedLayout>
        }
      />
      <Route
        path="/devices"
        element={
          <ProtectedLayout>
            <Devices />
          </ProtectedLayout>
        }
      />
      <Route
        path="/operations"
        element={
          <ProtectedLayout>
            <Operations />
          </ProtectedLayout>
        }
      />
      <Route
        path="/audit"
        element={
          <ProtectedLayout>
            <Audit />
          </ProtectedLayout>
        }
      />
      <Route
        path="/logs"
        element={
          <ProtectedLayout>
            <Logs />
          </ProtectedLayout>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedLayout>
            <Settings />
          </ProtectedLayout>
        }
      />
      <Route
        path="/direct-mode"
        element={
          <ProtectedLayout>
            <DirectMode />
          </ProtectedLayout>
        }
      />
      <Route
        path="/templates"
        element={
          <ProtectedLayout>
            <Templates />
          </ProtectedLayout>
        }
      />
      <Route
        path="/inspector"
        element={
          <ProtectedLayout>
            <Inspector />
          </ProtectedLayout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
