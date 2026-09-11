import React from 'react';

const KPICard = ({ title, value, subtitle, icon: Icon, color = 'var(--primary)', bg = 'var(--primary-light)' }) => {
  return (
    <div className="card" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
      <div>
        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          {title}
        </div>
        <div style={{ fontSize: '32px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '8px', letterSpacing: '-0.5px' }}>
          {value}
        </div>
        {subtitle && (
          <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {subtitle}
          </div>
        )}
      </div>

      {Icon && (
        <div style={{
          padding: '12px',
          borderRadius: '10px',
          backgroundColor: bg,
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
