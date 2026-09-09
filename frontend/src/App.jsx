import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import MainLayout from './layouts/MainLayout';
import {
  Login,
  Dashboard,
  NewScan,
  Products,
  ProductDetail,
  InspectionDetail,
  Reports,
  RuleLibrary,
  Unauthorized,
} from './pages';
import './App.css';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Authentication Route */}
          <Route path="/login" element={<Login />} />

          {/* Protected Routes Layout */}
          <Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
            {/* Common Authenticated Routes */}
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/products" element={<Products />} />
            <Route path="/products/:id" element={<ProductDetail />} />
            <Route path="/inspections/:id" element={<InspectionDetail />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/unauthorized" element={<Unauthorized />} />

            {/* Inspector / Admin Only */}
            <Route
              path="/scans/new"
              element={
                <ProtectedRoute allowedRoles={['ADMIN', 'INSPECTOR']}>
                  <NewScan />
                </ProtectedRoute>
              }
            />
            <Route
              path="/scans/:scanId"
              element={
                <ProtectedRoute allowedRoles={['ADMIN', 'INSPECTOR']}>
                  <NewScan />
                </ProtectedRoute>
              }
            />


            {/* Admin Only Route */}
            <Route
              path="/rules"
              element={
                <ProtectedRoute allowedRoles={['ADMIN']}>
                  <RuleLibrary />
                </ProtectedRoute>
              }
            />
          </Route>

          {/* Fallback & root redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
