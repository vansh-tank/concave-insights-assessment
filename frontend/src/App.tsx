import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AdminDashboard } from './pages/AdminDashboard';
import { SurveyRunner } from './pages/SurveyRunner';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AdminDashboard />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/survey/:surveyId" element={<SurveyRunner />} />
        <Route path="/r/:token" element={<SurveyRunner />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
