import React from 'react';

const ConfidenceIndicator = ({ confidence = 1.0, threshold = 0.80 }) => {
  const percent = Math.round(confidence * 100);
  const isHigh = confidence >= threshold;
  const isMedium = confidence >= 0.60 && confidence < threshold;

  const color = isHigh ? '#166534' : isMedium ? '#854d0e' : '#991b1b';
  const bgColor = isHigh ? '#dcfce7' : isMedium ? '#fef9c3' : '#fee2e2';

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <div style={{
        width: '40px',
        height: '6px',
        borderRadius: '3px',
        backgroundColor: '#e2e8f0',
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${percent}%`,
          height: '100%',
          backgroundColor: color,
        }} />
      </div>
      <span style={{
        fontSize: '11px',
        fontWeight: 600,
        color: color,
        backgroundColor: bgColor,
        padding: '1px 4px',
        borderRadius: '3px',
      }}>
        {percent}%
      </span>
    </div>
  );
};

export default ConfidenceIndicator;
