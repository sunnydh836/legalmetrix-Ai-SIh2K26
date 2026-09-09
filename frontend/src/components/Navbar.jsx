import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Bell, LogOut, ChevronDown, Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const ROLE_LABELS = {
  ADMIN: 'Administrator',
  INSPECTOR: 'Enforcement Inspector',
  REVIEWER: 'Review Officer',
};

const Navbar = ({ title = 'Enforcement Portal' }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setDropdownOpen(false);
    await logout();
    navigate('/login', { replace: true });
  };

  const displayName = user?.full_name || 'Enforcement Officer';
  const roleLabel = ROLE_LABELS[user?.role] || user?.role || 'Inspector';

  return (
    <header style={{
      height: '60px',
      backgroundColor: '#ffffff',
      borderBottom: '1px solid #e2e8f0',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 32px',
      position: 'relative',
      zIndex: 100,
    }}>
      <div style={{ fontWeight: 600, fontSize: '15px', color: '#1e293b' }}>
        {title}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <button style={{
          background: 'none',
          border: 'none',
          color: '#64748b',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          padding: '6px',
          borderRadius: '4px',
        }} title="System Notifications">
          <Bell size={18} />
        </button>

        {/* User Profile Menu */}
        <div style={{ position: 'relative' }} ref={dropdownRef}>
          <div
            onClick={() => setDropdownOpen(!dropdownOpen)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              paddingLeft: '16px',
              borderLeft: '1px solid #e2e8f0',
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            <div style={{
              width: '34px',
              height: '34px',
              borderRadius: '50%',
              backgroundColor: user?.role === 'ADMIN' ? '#dbeafe' : '#f1f5f9',
              color: user?.role === 'ADMIN' ? '#1d4ed8' : '#475569',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 600,
              fontSize: '14px',
            }}>
              {user?.role === 'ADMIN' ? <Shield size={18} /> : <User size={18} />}
            </div>
            <div style={{ fontSize: '13px', textAlign: 'left' }}>
              <div style={{ fontWeight: 600, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span>{displayName}</span>
                <ChevronDown size={14} color="#64748b" />
              </div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>Role: {roleLabel}</div>
            </div>
          </div>

          {/* Profile Dropdown */}
          {dropdownOpen && (
            <div style={{
              position: 'absolute',
              right: 0,
              top: 'calc(100% + 12px)',
              width: '240px',
              backgroundColor: '#ffffff',
              borderRadius: '8px',
              boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
              border: '1px solid #e2e8f0',
              overflow: 'hidden',
              animation: 'fadeIn 0.15s ease-out',
            }}>
              <div style={{ padding: '14px 16px', borderBottom: '1px solid #f1f5f9', backgroundColor: '#f8fafc' }}>
                <div style={{ fontWeight: 600, fontSize: '14px', color: '#0f172a' }}>{displayName}</div>
                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px', wordBreak: 'break-all' }}>{user?.email}</div>
                <div style={{ marginTop: '8px' }}>
                  <span style={{
                    display: 'inline-block',
                    fontSize: '10px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    padding: '2px 8px',
                    borderRadius: '9999px',
                    backgroundColor: user?.role === 'ADMIN' ? '#dbeafe' : '#f1f5f9',
                    color: user?.role === 'ADMIN' ? '#1e40af' : '#475569',
                  }}>
                    {user?.role}
                  </span>
                </div>
              </div>

              <div style={{ padding: '6px' }}>
                <button
                  onClick={handleLogout}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '10px 12px',
                    backgroundColor: 'transparent',
                    border: 'none',
                    borderRadius: '6px',
                    color: '#dc2626',
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'background-color 0.15s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#fef2f2'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <LogOut size={16} />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Navbar;
