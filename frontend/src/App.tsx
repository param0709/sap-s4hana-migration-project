import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AssessmentPage } from "./pages/AssessmentPage";
import { CreateProjectPage } from "./pages/CreateProjectPage";
import { ProjectListPage } from "./pages/ProjectListPage";
import { UploadPage } from "./pages/UploadPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<ProjectListPage />} />
        <Route path="/projects/new" element={<CreateProjectPage />} />
        <Route path="/projects/:projectId/upload" element={<UploadPage />} />
        <Route path="/projects/:projectId/assessment" element={<AssessmentPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
