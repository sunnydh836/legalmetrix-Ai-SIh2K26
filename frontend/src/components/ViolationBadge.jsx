import React from 'react';
import { CheckCircle2, XCircle, AlertCircle, HelpCircle } from 'lucide-react';

const statusConfig = {
  PASS: { label: 'PASS', className: 'badge-pass', Icon: CheckCircle2 },
  FAIL: { label: 'FAIL', className: 'badge-fail', Icon: XCircle },
  REVIEW: { label: 'REVIEW', className: 'badge-review', Icon: AlertCircle },
  NOT_APPLICABLE: { label: 'N/A', className: 'badge-na', Icon: HelpCircle },
};

const ViolationBadge = ({ status = 'PASS' }) => {
  const config = statusConfig[status] || statusConfig.REVIEW;
  const Icon = config.Icon;

  return (
    <span className={`badge ${config.className}`}>
      <Icon size={13} />
      <span>{config.label}</span>
    </span>
  );
};

export default ViolationBadge;
