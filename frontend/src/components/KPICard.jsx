import React from 'react';

const KPICard = ({ title, value, subtitle, icon: Icon, color = '#1e3a8a' }) => {
  return (
    <div className="card" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
      <div>
        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          {title}
        </div>
        <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '8px' }}>
          {value}
        </div>
        {subtitle && (
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {subtitle}
          </div>
        )}
      </div>

      {Icon && (
        <div style={{
          padding: '10px',
          borderRadius: '8px',
          backgroundColor: `${color}15`,
          color: color,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <Icon size={22} />
        </div>
      )}
    </div>
  );
};

export default KPICard;
