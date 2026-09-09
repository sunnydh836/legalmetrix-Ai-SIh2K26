import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  Sparkles,
  Maximize2,
  SunMedium,
  Focus,
  RefreshCw,
} from 'lucide-react';

const ImageQualityCard = ({
  quality,
  imageType = 'FRONT',
  processingDurationMs = null,
  onRecapture = null,
}) => {
  if (!quality) {
    return (
      <div className="card" style={{ padding: '16px', backgroundColor: '#f8fafc' }}>
        <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
          Image quality diagnostics pending processing.
        </div>
      </div>
    );
  }

  const {
    blur_score,
    glare_score,
    width,
    height,
    megapixels,
    quality_status,
    warnings = [],
    quality_engine_version,
  } = quality;

  const getStatusBadge = () => {
    switch (quality_status) {
      case 'ACCEPTED':
        return (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '20px',
              backgroundColor: '#dcfce7',
              color: '#15803d',
              fontSize: '12px',
              fontWeight: 700,
            }}
          >
            <CheckCircle2 size={14} />
            <span>ACCEPTED (OCR Ready)</span>
          </div>
        );
      case 'REVIEW':
        return (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '20px',
              backgroundColor: '#fef3c7',
              color: '#b45309',
              fontSize: '12px',
              fontWeight: 700,
            }}
          >
            <AlertTriangle size={14} />
            <span>REVIEW (Quality Diagnostics Flagged)</span>
          </div>
        );
      case 'RECAPTURE_RECOMMENDED':
        return (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '20px',
              backgroundColor: '#fee2e2',
              color: '#b91c1c',
              fontSize: '12px',
              fontWeight: 700,
            }}
          >
            <AlertOctagon size={14} />
            <span>RECAPTURE RECOMMENDED</span>
          </div>
        );
      default:
        return (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '4px 10px',
              borderRadius: '20px',
              backgroundColor: '#f1f5f9',
              color: '#475569',
              fontSize: '12px',
            }}
          >
            {quality_status}
          </div>
        );
    }
  };

  const getWarningLabel = (w) => {
    switch (w) {
      case 'BLUR':
        return 'Possible Blur / Soft Focus';
      case 'GLARE':
        return 'Possible Glare / Specular Highlight';
      case 'LOW_RESOLUTION':
        return 'Low Spatial Resolution';
      case 'ROTATED':
        return 'Non-Standard Orientation';
      default:
        return w;
    }
  };

  return (
    <div className="card" style={{ padding: '16px', border: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={16} color="var(--primary)" />
          <h3 style={{ fontSize: '14px', fontWeight: 600, margin: 0 }}>
            Image Quality Diagnostics ({imageType})
          </h3>
        </div>
        {getStatusBadge()}
      </div>

      {/* Metrics Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '12px',
          marginBottom: '14px',
        }}
      >
        {/* Sharpness / Blur */}
        <div
          style={{
            padding: '10px 12px',
            backgroundColor: '#f8fafc',
            borderRadius: '6px',
            border: '1px solid var(--border)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '11px', marginBottom: '4px' }}>
            <Focus size={13} />
            <span>Sharpness (Laplacian)</span>
          </div>
          <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {blur_score?.toFixed(1) || '0.0'}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Threshold: 100.0
          </div>
        </div>

        {/* Glare Ratio */}
        <div
          style={{
            padding: '10px 12px',
            backgroundColor: '#f8fafc',
            borderRadius: '6px',
            border: '1px solid var(--border)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '11px', marginBottom: '4px' }}>
            <SunMedium size={13} />
            <span>Glare Indicator</span>
          </div>
          <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {((glare_score || 0) * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Threshold: 5.0%
          </div>
        </div>

        {/* Resolution */}
        <div
          style={{
            padding: '10px 12px',
            backgroundColor: '#f8fafc',
            borderRadius: '6px',
            border: '1px solid var(--border)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '11px', marginBottom: '4px' }}>
            <Maximize2 size={13} />
            <span>Resolution</span>
          </div>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {width} × {height}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {megapixels ? `${megapixels} MP` : 'Standard'}
          </div>
        </div>
      </div>

      {/* Warnings Banner */}
      {warnings && warnings.length > 0 && (
        <div
          style={{
            padding: '8px 12px',
            backgroundColor: '#fffbeb',
            border: '1px solid #fde68a',
            borderRadius: '6px',
            fontSize: '12px',
            color: '#92400e',
            marginBottom: '12px',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>Quality Diagnostics:</div>
          <ul style={{ margin: 0, paddingLeft: '16px', lineHeight: 1.5 }}>
            {warnings.map((w, idx) => (
              <li key={idx}>{getWarningLabel(w)}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer Info & Actions */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '11px',
          color: 'var(--text-muted)',
          borderTop: '1px solid var(--border)',
          paddingTop: '8px',
        }}
      >
        <div>
          Engine: <span style={{ fontFamily: 'monospace' }}>{quality_engine_version || 'opencv'}</span>
          {processingDurationMs ? ` • OCR: ${processingDurationMs}ms` : ''}
        </div>

        {quality_status === 'RECAPTURE_RECOMMENDED' && onRecapture && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onRecapture}
            style={{ padding: '3px 8px', fontSize: '11px', color: '#b91c1c' }}
          >
            <RefreshCw size={12} /> Replace Image
          </button>
        )}
      </div>
    </div>
  );
};

export default ImageQualityCard;
