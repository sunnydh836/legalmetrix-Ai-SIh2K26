import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ScanLine,
  Package,
  FileText,
  Scale,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Sidebar = () => {
  const { hasRole } = useAuth();

  const allNavItems = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['ADMIN', 'INSPECTOR', 'REVIEWER'] },
    { to: '/scans/new', label: 'New Scan', icon: ScanLine, roles: ['ADMIN', 'INSPECTOR'] },
    { to: '/products', label: 'Products', icon: Package, roles: ['ADMIN', 'INSPECTOR', 'REVIEWER'] },
    { to: '/reports', label: 'Reports', icon: FileText, roles: ['ADMIN', 'INSPECTOR', 'REVIEWER'] },
    { to: '/rules', label: 'Rule Library', icon: Scale, roles: ['ADMIN'] },
  ];

  const visibleNavItems = allNavItems.filter((item) => hasRole(item.roles));

  return (
    <aside style={{
      width: '240px',
      backgroundColor: 'var(--bg-sidebar)',
      color: 'var(--text-inverse)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
    }}>
      {/* Brand Header */}
      <div style={{
        padding: '20px',
        borderBottom: '1px solid #1e293b',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
      }}>
        <ShieldCheck size={26} color="var(--info)" />
        <div>
          <div style={{ fontWeight: 700, fontSize: '18px', letterSpacing: '-0.5px' }}>LegalMetrix AI</div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Packaged Commodities</div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ padding: '16px 12px', flex: 1 }}>
        {visibleNavItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 14px',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: 600,
                color: isActive ? 'var(--text-inverse)' : 'var(--text-muted)',
                backgroundColor: isActive ? 'var(--primary-hover)' : 'transparent',
                marginBottom: '4px',
                textDecoration: 'none',
                boxShadow: isActive ? 'inset 4px 0 0 var(--accent)' : 'none',
                transition: 'all 0.2s ease',
              })}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* System Status Footer */}
      <div style={{
        padding: '16px 20px',
        borderTop: '1px solid var(--primary-hover)',
        fontSize: '12px',
        color: 'var(--text-muted)',
      }}>
        <div>Version 1.0 (Day 2)</div>
        <div style={{ color: 'var(--success)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>● System Operational</div>
      </div>
    </aside>
  );
};

export default Sidebar;
