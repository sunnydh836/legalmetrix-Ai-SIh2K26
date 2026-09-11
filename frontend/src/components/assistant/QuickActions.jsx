import React from 'react';
import { Sparkles, ShieldAlert, Camera, Scale, FileText } from 'lucide-react';

const QUICK_ACTIONS = [
  {
    label: 'Check MRP Compliance',
    prompt: 'What are the mandatory MRP declaration rules under Rule 6(1)(e) of LMR 2011?',
    icon: Scale,
  },
  {
    label: 'Fix Glare / Blur Warning',
    prompt: 'How do I resolve a Glare or Blur warning on glossy packaging images?',
    icon: Camera,
  },
  {
    label: 'Net Quantity Rules',
    prompt: 'What are the mandatory units and standards for Net Quantity declarations under Rule 6(1)(b)?',
    icon: FileText,
  },
  {
    label: 'Consumer Grievance Checklist',
    prompt: 'What consumer care contact details must be printed on the label under Rule 6(1)(h)?',
    icon: ShieldAlert,
  },
  {
    label: 'Inspection Workflow Help',
    prompt: 'Explain the end-to-end LegalMetrix AI inspection workflow from image capture to report generation.',
    icon: Sparkles,
  },
];

const QuickActions = ({ onSelectAction, disabled }) => {
  return (
    <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border-color, #e2e8f0)' }}>
      <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted, #64748b)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
        <Sparkles size={12} color="#3b82f6" /> Quick Inquiries
      </div>
      <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '4px' }}>
        {QUICK_ACTIONS.map((action, idx) => {
          const Icon = action.icon;
          return (
            <button
              key={idx}
              type="button"
              disabled={disabled}
              onClick={() => onSelectAction(action.prompt)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                fontSize: '11px',
                fontWeight: 500,
                borderRadius: '16px',
                border: '1px solid var(--border-color, #e2e8f0)',
                backgroundColor: 'var(--bg-secondary, #f8fafc)',
                color: 'var(--text-primary, #1e293b)',
                cursor: disabled ? 'not-allowed' : 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!disabled) {
                  e.currentTarget.style.backgroundColor = 'var(--info-bg)';
                  e.currentTarget.style.borderColor = 'var(--info)';
                  e.currentTarget.style.color = '#1d4ed8';
                }
              }}
              onMouseLeave={(e) => {
                if (!disabled) {
                  e.currentTarget.style.backgroundColor = 'var(--bg-secondary, #f8fafc)';
                  e.currentTarget.style.borderColor = 'var(--border-color, #e2e8f0)';
                  e.currentTarget.style.color = 'var(--text-primary, #1e293b)';
                }
              }}
            >
              <Icon size={11} />
              {action.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default QuickActions;
