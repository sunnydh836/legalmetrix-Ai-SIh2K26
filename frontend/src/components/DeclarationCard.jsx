import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  Edit3,
  XCircle,
  Eye,
  Check,
  RotateCcw,
  Sparkles,
  Info,
  ShieldAlert,
} from 'lucide-react';
import { DECLARATION_TAXONOMY, REVIEW_STATUSES, CONFIDENCE_LEVELS } from '../constants/taxonomy';

const DeclarationCard = ({
  declaration,
  onReview = null,
  onViewEvidence = null,
  isReviewing = false,
}) => {
  const {
    id,
    declaration_type,
    raw_text,
    raw_value,
    normalized_value,
    confidence = 1.0,
    confidence_level = 'MEDIUM',
    resolution_status = 'NOT_DETECTED',
    machine_extracted_value,
    reviewed = false,
    reviewed_value,
    reviewed_by,
    has_conflict = false,
    conflict_details = null,
    source_blocks = [],
    image_id,
    candidate_details = [],
  } = declaration || {};

  const [isEditing, setIsEditing] = useState(false);
  const [editJson, setEditJson] = useState(
    JSON.stringify(reviewed_value || normalized_value || {}, null, 2)
  );
  const [editError, setEditError] = useState('');

  const meta = DECLARATION_TAXONOMY[declaration_type] || {
    label: declaration_type,
    category: 'Other',
  };
  const confStyle = CONFIDENCE_LEVELS[confidence_level] || CONFIDENCE_LEVELS.MEDIUM;
  const statusStyle = REVIEW_STATUSES[resolution_status] || REVIEW_STATUSES.NOT_DETECTED;
  const confPercent = Math.round(confidence * 100);

  const handleConfirm = () => {
    if (onReview) {
      onReview(id, {
        review_status: 'CONFIRMED',
        reviewed_value: normalized_value,
      });
    }
  };

  const handleReject = () => {
    if (onReview) {
      onReview(id, {
        review_status: 'REJECTED',
        reviewed_value: null,
      });
    }
  };

  const handleSaveCorrection = () => {
    try {
      const parsed = JSON.parse(editJson);
      setEditError('');
      if (onReview) {
        onReview(id, {
          review_status: 'CORRECTED',
          reviewed_value: parsed,
        });
      }
      setIsEditing(false);
    } catch (err) {
      setEditError('Invalid JSON format for normalized fields.');
    }
  };

  return (
    <div
      className="card"
      style={{
        marginBottom: '16px',
        padding: '16px',
        border: has_conflict
          ? '1.5px solid #f59e0b'
          : reviewed
            ? `1.5px solid ${statusStyle.border}`
            : '1px solid var(--border)',
        backgroundColor: '#ffffff',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        transition: 'all 0.15s ease-in-out',
      }}
    >
      {/* Top Header: Declaration Type & Status Badges */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '12px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              {meta.label}
            </h3>
            <span
              style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '12px',
                backgroundColor: '#f1f5f9',
                color: '#64748b',
                fontWeight: 600,
              }}
            >
              {meta.category}
            </span>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'monospace' }}>
            {declaration_type}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Confidence Badge */}
          <span
            style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: '4px',
              backgroundColor: confStyle.bg,
              color: confStyle.color,
              border: `1px solid ${confStyle.border}`,
            }}
          >
            {confPercent}% {confStyle.label}
          </span>

          {/* Review Status Badge */}
          <span
            style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: '4px',
              backgroundColor: statusStyle.bg,
              color: statusStyle.color,
              border: `1px solid ${statusStyle.border}`,
            }}
          >
            {statusStyle.label}
          </span>
        </div>
      </div>

      {/* Multi-Panel Conflict Notice */}
      {has_conflict && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#fffbeb',
            border: '1px solid #fde68a',
            borderRadius: '6px',
            padding: '8px 12px',
            color: '#b45309',
            fontSize: '12px',
            marginBottom: '12px',
          }}
        >
          <AlertTriangle size={16} />
          <div>
            <strong>Candidate Conflict:</strong> Discrepant declarations detected across panels. Reviewer arbitration required.
          </div>
        </div>
      )}

      {/* Extracted Values Grid: Raw Detected vs Structured Normalized */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
        {/* Raw Extracted */}
        <div
          style={{
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '6px',
            padding: '10px 12px',
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#64748b', marginBottom: '4px' }}>
            RAW OCR DETECTED
          </div>
          <div
            style={{
              fontSize: '13px',
              color: '#1e293b',
              fontFamily: 'monospace',
              wordBreak: 'break-word',
            }}
          >
            "{raw_text}"
          </div>
        </div>

        {/* Structured Normalized Value */}
        <div
          style={{
            backgroundColor: isEditing ? '#fff' : '#f0fdf4',
            border: isEditing ? '1px solid #3b82f6' : '1px solid #bbf7d0',
            borderRadius: '6px',
            padding: '10px 12px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '4px',
            }}
          >
            <span style={{ fontSize: '11px', fontWeight: 600, color: isEditing ? '#1d4ed8' : '#15803d' }}>
              {isEditing ? 'EDIT NORMALIZED STRUCTURE' : 'NORMALIZED VALUE'}
            </span>
            {reviewed && reviewed_value && (
              <span style={{ fontSize: '10px', color: '#0369a1', fontWeight: 600 }}>
                (Human Corrected)
              </span>
            )}
          </div>

          {isEditing ? (
            <div>
              <textarea
                value={editJson}
                onChange={(e) => setEditJson(e.target.value)}
                style={{
                  width: '100%',
                  height: '90px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  border: '1px solid #cbd5e1',
                  borderRadius: '4px',
                  padding: '6px',
                  resize: 'vertical',
                }}
              />
              {editError && <div style={{ color: '#dc2626', fontSize: '11px' }}>{editError}</div>}
              <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleSaveCorrection}
                  disabled={isReviewing}
                  style={{ fontSize: '11px', padding: '3px 8px' }}
                >
                  Save Changes
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsEditing(false)}
                  style={{ fontSize: '11px', padding: '3px 8px' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div style={{ fontSize: '13px', color: '#14532d', wordBreak: 'break-word' }}>
              {normalized_value ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  {Object.entries(normalized_value).map(([k, v]) => (
                    <div key={k} style={{ fontSize: '12px' }}>
                      <span style={{ color: '#475569', fontWeight: 500 }}>{k}: </span>
                      <span style={{ fontWeight: 600, color: '#0f172a' }}>
                        {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <span style={{ color: '#94a3b8' }}>Unresolved</span>
              )}
            </div>
          )}

          {/* Alternative Candidate Selector */}
          {isEditing && candidate_details && candidate_details.length > 1 && (
            <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px dashed #cbd5e1' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', marginBottom: '8px' }}>
                ALTERNATIVE EXTRACTED CANDIDATES
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {candidate_details.map((cand, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      backgroundColor: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: '4px',
                      padding: '6px 8px',
                      fontSize: '11px',
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', maxWidth: '75%' }}>
                      <span style={{ color: '#1e293b', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {cand.raw_value || JSON.stringify(cand.normalized_value)}
                      </span>
                      <span style={{ color: '#64748b', fontSize: '10px' }}>
                        Conf: {(cand.confidence * 100).toFixed(1)}% | OCR: {(cand.confidence_breakdown?.ocr_confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setEditJson(JSON.stringify(cand.normalized_value, null, 2))}
                      style={{ fontSize: '10px', padding: '2px 6px' }}
                    >
                      Use
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Machine Value vs Human Review Audit Snapshot */}
      {reviewed && reviewed_value && machine_extracted_value && (
        <div
          style={{
            fontSize: '11px',
            color: '#64748b',
            backgroundColor: '#f8fafc',
            border: '1px dashed #cbd5e1',
            borderRadius: '4px',
            padding: '6px 10px',
            marginBottom: '12px',
          }}
        >
          <span style={{ fontWeight: 600 }}>Original Machine Extraction:</span>{' '}
          <code>{JSON.stringify(machine_extracted_value)}</code>
        </div>
      )}

      {/* Bottom Action Footer: View Evidence & Review Controls */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderTop: '1px solid #f1f5f9',
          paddingTop: '12px',
        }}
      >
        {/* Evidence Traceability Trigger */}
        <button
          type="button"
          onClick={() => onViewEvidence && onViewEvidence(declaration)}
          className="btn btn-secondary"
          style={{
            fontSize: '12px',
            padding: '4px 10px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <Eye size={14} />
          <span>View Evidence ({source_blocks.length} OCR block{source_blocks.length === 1 ? '' : 's'})</span>
        </button>

        {/* Review Controls */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            className="btn"
            onClick={() => setIsEditing(!isEditing)}
            disabled={isReviewing}
            style={{
              fontSize: '12px',
              padding: '4px 10px',
              border: '1px solid #cbd5e1',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Edit3 size={13} />
            <span>Edit</span>
          </button>

          <button
            type="button"
            className="btn"
            onClick={handleReject}
            disabled={isReviewing}
            style={{
              fontSize: '12px',
              padding: '4px 10px',
              border: '1px solid #fca5a5',
              color: '#b91c1c',
              backgroundColor: '#fff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <XCircle size={13} />
            <span>Reject</span>
          </button>

          <button
            type="button"
            className="btn"
            onClick={handleConfirm}
            disabled={isReviewing || resolution_status === 'CONFIRMED' || resolution_status === 'AUTO_RESOLVED'}
            style={{
              fontSize: '12px',
              padding: '4px 10px',
              backgroundColor: '#16a34a',
              color: '#ffffff',
              fontWeight: 600,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <CheckCircle2 size={13} />
            <span>{(resolution_status === 'CONFIRMED' || resolution_status === 'AUTO_RESOLVED') ? 'Confirmed' : 'Confirm'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeclarationCard;
