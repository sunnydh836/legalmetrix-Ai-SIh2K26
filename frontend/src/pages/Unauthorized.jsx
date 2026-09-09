import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, ArrowLeft, LayoutDashboard } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Unauthorized = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  return (
    <div style={{
      minHeight: '80vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
    }}>
      <div className="card" style={{
        maxWidth: '520px',
        width: '100%',
        padding: '36px',
        textAlign: 'center',
        borderTop: '4px solid #ef4444',
      }}>
        <div style={{
          width: '64px',
          height: '64px',
          borderRadius: '50%',
          backgroundColor: '#fee2e2',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 20px',
          color: '#dc2626',
        }}>
          <ShieldAlert size={36} />
        </div>

        <h1 style={{
          fontSize: '22px',
          fontWeight: 700,
          color: '#0f172a',
          marginBottom: '8px',
        }}>
          Access Restricted
        </h1>

        <p style={{
          fontSize: '14px',
          color: '#64748b',
          lineHeight: '1.6',
          marginBottom: '20px',
        }}>
          You do not have permission to access this section. This area requires administrative or specialized role clearance.
        </p>

        {user && (
          <div style={{
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '6px',
            padding: '12px 16px',
            fontSize: '13px',
            color: '#475569',
            marginBottom: '24px',
            textAlign: 'left',
          }}>
            <div><strong>Logged in as:</strong> {user.full_name}</div>
            <div><strong>Active Role:</strong> {user.role}</div>
            <div><strong>Email:</strong> {user.email}</div>
          </div>
        )}

        <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
          <button
            onClick={() => navigate(-1)}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <ArrowLeft size={16} />
            Go Back
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <LayoutDashboard size={16} />
            Return to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
};

export default Unauthorized;
