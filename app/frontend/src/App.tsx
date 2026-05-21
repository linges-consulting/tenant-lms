import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthLogin } from './pages/AuthLogin';
import { AuthSignup } from './pages/AuthSignup';
import { AuthPasswordReset } from './pages/AuthPasswordReset';
import { PrivacyPolicy } from './pages/PrivacyPolicy';
import { TermsOfService } from './pages/TermsOfService';
import { AppLayout } from './layouts/AppLayout';
import { MyTrainings } from './pages/MyTrainings';
import { UnifiedDashboard } from './pages/UnifiedDashboard';
import { ManagerTrainings } from './pages/ManagerTrainings';
import { SettingsPage } from './pages/SettingsPage';

import { AdminDashboard } from './pages/AdminDashboard';
import { AdminTenants } from './pages/AdminTenants';
import { AdminRegisterTenant } from './pages/AdminRegisterTenant';
import { AdminUsers } from './pages/AdminUsers';
import { TenantSettingsPage } from './pages/TenantSettingsPage';
import { DynamicLayout } from './layouts/DynamicLayout';
import { AuthGuard } from './components/AuthGuard';
import { NoAuthGuard } from './components/NoAuthGuard';
import { TrainingViewer } from './pages/TrainingViewer';
import { ManagerTrainingEditor } from './pages/ManagerTrainingEditor';
import { ManagerTrainingAssignments } from './pages/ManagerTrainingAssignments';
import { ManagerEmployees } from './pages/ManagerEmployees';
import { ManagerGroups } from './pages/ManagerGroups';
import { ProfilePage } from './pages/ProfilePage';
import { NotificationPage } from './pages/NotificationPage';
import { SystemCheck } from './pages/SystemCheck';
import { AdminCertificateTemplates } from './pages/AdminCertificateTemplates';
import { AdminCertificateTemplateEditor } from './pages/AdminCertificateTemplateEditor';
import { LearnerCertificates } from './pages/LearnerCertificates';
import { NotFound } from './pages/NotFound';
import { ManagerReports } from './pages/ManagerReports';
import { ManagerPublishTrainings } from './pages/ManagerPublishTrainings';
import { AdminBulkImport } from './pages/AdminBulkImport';
import { DynamicTitleUpdater } from './hooks/useDynamicTitle';
import { NotificationProvider } from './contexts/notification-context';
import { Toaster } from 'sonner';

function App() {
  return (
    <BrowserRouter>
      <NotificationProvider>
        <Toaster richColors position="top-right" />
        <DynamicTitleUpdater />
        <Routes>
        {/* Public Legal Routes */}
        <Route path="/privacy" element={<PrivacyPolicy />} />
        <Route path="/terms" element={<TermsOfService />} />

        {/* Auth Routes */}
        <Route path="/" element={<NoAuthGuard><AuthLogin /></NoAuthGuard>} />
        <Route path="/login" element={<NoAuthGuard><AuthLogin /></NoAuthGuard>} />
        <Route path="/register" element={<NoAuthGuard><AuthSignup /></NoAuthGuard>} />
        <Route path="/forgot-password" element={<AuthPasswordReset />} />
        <Route path="/reset-password" element={<AuthPasswordReset />} />

        {/* Global Standalone Routes - Require Auth */}
        <Route element={<AuthGuard><DynamicLayout /></AuthGuard>}>
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/profile/:username" element={<ProfilePage />} />
          <Route path="/notifications" element={<NotificationPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        {/* Learner Portal Routes - Require Auth */}
        <Route path="/dashboard" element={<AuthGuard><AppLayout /></AuthGuard>}>
          <Route index element={<UnifiedDashboard />} />
          <Route path="my-courses" element={<Navigate to="/dashboard" replace />} />
          <Route path="certificates" element={<LearnerCertificates />} />
          <Route path="learn/:id" element={<TrainingViewer />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        {/* Manager Portal Routes - Require Auth */}
        <Route path="/manage" element={<AuthGuard><AppLayout /></AuthGuard>}>
          <Route index element={<UnifiedDashboard />} />
          <Route path="employees" element={<ManagerEmployees />} />
          <Route path="groups" element={<ManagerGroups />} />
          <Route path="courses" element={<AuthGuard requireTrainingCreator><ManagerTrainings /></AuthGuard>} />
          <Route path="courses/:id" element={<AuthGuard requireTrainingCreator><ManagerTrainingEditor /></AuthGuard>} />
          <Route path="courses/:id/assignments" element={<AuthGuard requireBusinessManager><ManagerTrainingAssignments /></AuthGuard>} />
          <Route path="my-courses" element={<MyTrainings basePath="/manage" />} />
          <Route path="certificates" element={<LearnerCertificates />} />
          <Route path="learn/:id" element={<TrainingViewer />} />
          <Route path="reports" element={<AuthGuard requireBusinessManager><ManagerReports /></AuthGuard>} />
          <Route path="publish" element={<AuthGuard requireBusinessManager><ManagerPublishTrainings /></AuthGuard>} />
          <Route path="publish/:id/assignments" element={<AuthGuard requireBusinessManager><ManagerTrainingAssignments /></AuthGuard>} />
          <Route path="*" element={<NotFound />} />
        </Route>

        {/* SysAdmin Portal Routes - Require SysAdmin Auth */}
        <Route path="/admin" element={<AuthGuard requireSysAdmin><AppLayout /></AuthGuard>}>
          <Route index element={<AdminDashboard />} />
          <Route path="tenants" element={<AdminTenants />} />
          <Route path="tenants/new" element={<AdminRegisterTenant />} />
          <Route path="tenants/:id" element={<TenantSettingsPage />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="certificate-templates" element={<AdminCertificateTemplates />} />
          <Route path="certificate-templates/new" element={<AdminCertificateTemplateEditor />} />
          <Route path="certificate-templates/:id" element={<AdminCertificateTemplateEditor />} />
          <Route path="bulk-import" element={<AdminBulkImport />} />
          <Route path="check" element={<SystemCheck />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        {/* Catch-all redirect for unauthenticated users at root */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </NotificationProvider>
  </BrowserRouter>
  );
}

export default App;
