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
      height: '64px',
      backgroundColor: 'var(--bg-surface)',
      borderBottom: '1px solid var(--border-color)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 32px',
      position: 'relative',
      zIndex: 100,
    }}>
      <div style={{ fontWeight: 700, fontSize: '16px', color: 'var(--text-primary)', letterSpacing: '-0.3px' }}>
        {title}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <button style={{
          background: 'none',
          border: 'none',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          padding: '6px',
          borderRadius: '6px',
          transition: 'all 0.2s',
          backgroundColor: 'var(--info-bg)',
          color: 'var(--info)',
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
              gap: '12px',
              paddingLeft: '20px',
              borderLeft: '1px solid var(--border-color)',
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            <div style={{
              width: '34px',
              height: '36px',
              borderRadius: '8px',
              backgroundColor: user?.role === 'ADMIN' ? 'var(--info-bg)' : 'var(--bg-primary)',
              color: user?.role === 'ADMIN' ? 'var(--info)' : 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 600,
              fontSize: '14px',
            }}>
              {user?.role === 'ADMIN' ? <Shield size={18} /> : <User size={18} />}
            </div>
            <div style={{ fontSize: '13px', textAlign: 'left' }}>
              <div style={{ fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '4px', letterSpacing: '-0.2px' }}>
                <span>{displayName}</span>
                <ChevronDown size={14} color="var(--text-muted)" />
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)' }}>{roleLabel}</div>
            </div>
          </div>

          {/* Profile Dropdown */}
          {dropdownOpen && (
            <div style={{
              position: 'absolute',
              right: 0,
              top: 'calc(100% + 12px)',
              width: '240px',
              backgroundColor: 'var(--bg-surface)',
              borderRadius: '8px',
              boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
              border: '1px solid #e2e8f0',
              overflow: 'hidden',
              animation: 'fadeIn 0.15s ease-out',
            }}>
              <div style={{ padding: '14px 16px', borderBottom: '1px solid #f1f5f9', backgroundColor: 'var(--bg-primary)' }}>
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--bg-sidebar)' }}>{displayName}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px', wordBreak: 'break-all' }}>{user?.email}</div>
                <div style={{ marginTop: '8px' }}>
                  <span style={{
                    display: 'inline-block',
                    fontSize: '10px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    padding: '2px 8px',
                    borderRadius: '9999px',
                    backgroundColor: user?.role === 'ADMIN' ? '#dbeafe' : 'var(--bg-primary)',
                    color: user?.role === 'ADMIN' ? '#1e40af' : 'var(--text-secondary)',
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
                    color: 'var(--danger)',
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'background-color 0.15s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--danger-bg)'}
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
