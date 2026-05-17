import { Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "./store/authStore";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Agent } from "./pages/Agent";
import { NetworkAgent } from "./pages/NetworkAgent";
import { Devices } from "./pages/Devices";
import { Settings } from "./pages/Settings";
import { Audit } from "./pages/Audit";
import { Organisation } from "./pages/Organisation";
import { DirectMode } from "./pages/DirectMode";
import { Inspector } from "./pages/Inspector";
import { MSSPDashboard } from "./pages/MSSPDashboard";
import { AcceptInvite } from "./pages/AcceptInvite";
import { Servers } from "./pages/Servers";
import { ServerDirectMode } from "./pages/ServerDirectMode";
import { ServerAnalysis } from "./pages/ServerAnalysis";
import { Remediation } from "./pages/Remediation";
import { Compliance } from "./pages/Compliance";
import { GlpiAnalyses } from "./pages/GlpiAnalyses";
import { Migrations } from "./pages/Migrations";
import { FirewallMigrations } from "./pages/FirewallMigrations";
import { GoldenTemplates } from "./pages/GoldenTemplates";
import { Connectivity } from "./pages/Connectivity";
import { KnowledgeBase } from "./pages/KnowledgeBase";
import { DatabaseConnectors } from "./pages/DatabaseConnectors";
import { Identity } from "./pages/Identity";
import { Alerts } from "./pages/Alerts";
import { GoldenBundles } from "./pages/GoldenBundles";
import { VMMigration } from "./pages/VMMigration";
import { AssistantPage } from "./pages/AssistantPage";
import { CloudPosture } from "./pages/CloudPosture";
import { PlaybooksPage } from "./pages/PlaybooksPage";
import { SelfServicePortalPage } from "./pages/SelfServicePortalPage";
import { SecurityInfraPage } from "./pages/SecurityInfraPage";
import { EdgeAgentsPage } from "./pages/EdgeAgentsPage";
import { ProductPage } from "./pages/ProductPage";
import RmmPage from "./pages/RmmPage";
import RmmAgent from "./pages/RmmAgent";
import { AdminBackupPage } from "./pages/AdminBackupPage";
import { HelpCenterPage } from "./pages/HelpCenterPage";
import { CrossDomainPage } from "./pages/CrossDomainPage";
import { CompositeInvestigationPage } from "./pages/CompositeInvestigationPage";
import { VaultPage } from "./pages/VaultPage";
import { Sidebar } from "./components/layout/Sidebar";
import { SupportBanner } from "./components/layout/SupportBanner";

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return (
    <div className="flex">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <SupportBanner />
        {children}
      </div>
    </div>
  );
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/invite/:token" element={<AcceptInvite />} />
      <Route path="/" element={<ProtectedLayout><Dashboard /></ProtectedLayout>} />
      <Route path="/agent" element={<ProtectedLayout><Agent /></ProtectedLayout>} />
      <Route path="/network-agent" element={<ProtectedLayout><NetworkAgent /></ProtectedLayout>} />
      <Route path="/devices" element={<ProtectedLayout><Devices /></ProtectedLayout>} />
      {/* Redirects for consolidated Dispositivos tabs */}
      <Route path="/templates" element={<Navigate to="/devices" replace />} />
      <Route path="/device-groups" element={<Navigate to="/devices" replace />} />
      <Route path="/variables" element={<Navigate to="/devices" replace />} />
      {/* Redirects for consolidated Auditoria tabs */}
      <Route path="/bulk-jobs" element={<Navigate to="/audit" replace />} />
      <Route path="/bulk-jobs/:id" element={<Navigate to="/audit" replace />} />
      <Route path="/operations" element={<Navigate to="/audit" replace />} />
      <Route path="/logs" element={<Navigate to="/audit" replace />} />
      <Route path="/audit" element={<ProtectedLayout><Audit /></ProtectedLayout>} />
      <Route path="/settings" element={<ProtectedLayout><Settings /></ProtectedLayout>} />
      <Route path="/direct-mode" element={<ProtectedLayout><DirectMode /></ProtectedLayout>} />
      <Route path="/inspector" element={<ProtectedLayout><Inspector /></ProtectedLayout>} />
      <Route path="/tenants" element={<Navigate to="/organization" replace />} />
      <Route path="/organization" element={<ProtectedLayout><Organisation /></ProtectedLayout>} />
      <Route path="/mssp" element={<ProtectedLayout><MSSPDashboard /></ProtectedLayout>} />
      <Route path="/servers" element={<ProtectedLayout><Servers /></ProtectedLayout>} />
      <Route path="/server-direct" element={<ProtectedLayout><ServerDirectMode /></ProtectedLayout>} />
      <Route path="/server-analysis" element={<ProtectedLayout><ServerAnalysis /></ProtectedLayout>} />
      <Route path="/remediation" element={<ProtectedLayout><Remediation /></ProtectedLayout>} />
      <Route path="/compliance" element={<ProtectedLayout><Compliance /></ProtectedLayout>} />
      <Route path="/governance" element={<Navigate to="/compliance" replace />} />
      <Route path="/glpi"       element={<ProtectedLayout><GlpiAnalyses /></ProtectedLayout>} />
      <Route path="/migrations"          element={<ProtectedLayout><Migrations /></ProtectedLayout>} />
      <Route path="/firewall-migrations" element={<ProtectedLayout><FirewallMigrations /></ProtectedLayout>} />
      <Route path="/golden-templates"    element={<ProtectedLayout><GoldenTemplates /></ProtectedLayout>} />
      <Route path="/connectivity"        element={<ProtectedLayout><Connectivity /></ProtectedLayout>} />
      <Route path="/knowledge"           element={<ProtectedLayout><KnowledgeBase /></ProtectedLayout>} />
      <Route path="/database-connectors" element={<ProtectedLayout><DatabaseConnectors /></ProtectedLayout>} />
      <Route path="/identity" element={<ProtectedLayout><Identity /></ProtectedLayout>} />
      <Route path="/onboarding" element={<Navigate to="/identity" replace />} />
      <Route path="/alerts" element={<ProtectedLayout><Alerts /></ProtectedLayout>} />
      <Route path="/executive" element={<Navigate to="/?view=executive" replace />} />
      <Route path="/enterprise" element={<Navigate to="/settings" replace />} />
      <Route path="/golden-bundles" element={<ProtectedLayout><GoldenBundles /></ProtectedLayout>} />
      <Route path="/vm-migration" element={<ProtectedLayout><VMMigration /></ProtectedLayout>} />
      <Route path="/platform-config" element={<Navigate to="/settings" replace />} />
      <Route path="/assistant" element={<ProtectedLayout><AssistantPage /></ProtectedLayout>} />
      <Route path="/siem" element={<Navigate to="/alerts" replace />} />
      <Route path="/cloud-posture" element={<ProtectedLayout><CloudPosture /></ProtectedLayout>} />
      <Route path="/playbooks"             element={<ProtectedLayout><PlaybooksPage /></ProtectedLayout>} />
      <Route path="/compliance-enterprise" element={<Navigate to="/compliance" replace />} />
      <Route path="/ai-safety"             element={<Navigate to="/security-infra" replace />} />
      <Route path="/selfservice-portal"    element={<ProtectedLayout><SelfServicePortalPage /></ProtectedLayout>} />
      <Route path="/security-infra"        element={<ProtectedLayout><SecurityInfraPage /></ProtectedLayout>} />
      <Route path="/edge-agents"           element={<ProtectedLayout><EdgeAgentsPage /></ProtectedLayout>} />
      <Route path="/product"               element={<ProtectedLayout><ProductPage /></ProtectedLayout>} />
      <Route path="/rmm"                   element={<ProtectedLayout><RmmPage /></ProtectedLayout>} />
      <Route path="/rmm-agent"             element={<ProtectedLayout><RmmAgent /></ProtectedLayout>} />
      <Route path="/admin-backup"          element={<ProtectedLayout><AdminBackupPage /></ProtectedLayout>} />
      <Route path="/help"                  element={<ProtectedLayout><HelpCenterPage /></ProtectedLayout>} />
      <Route path="/cross-domain"          element={<ProtectedLayout><CrossDomainPage /></ProtectedLayout>} />
      <Route path="/composite-investigation" element={<ProtectedLayout><CompositeInvestigationPage /></ProtectedLayout>} />
      <Route path="/vault"                 element={<ProtectedLayout><VaultPage /></ProtectedLayout>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
