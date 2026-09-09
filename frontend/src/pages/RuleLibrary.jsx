import React from 'react';
import { Scale, CheckCircle2, ShieldAlert } from 'lucide-react';

const RuleLibrary = () => {
  const rules = [
    {
      code: 'LMR_2011_R06_MRP',
      name: 'Mandatory Maximum Retail Price (MRP)',
      version: '2011.1.0',
      target: 'MRP',
      severity: 'HIGH',
      description: 'Rule 6(1)(e): Maximum Retail Price inclusive of all taxes must be clearly declared.',
    },
    {
      code: 'LMR_2011_R06_NET_QTY',
      name: 'Net Quantity in Standard Units',
      version: '2011.1.0',
      target: 'NET_QUANTITY',
      severity: 'HIGH',
      description: 'Rule 6(1)(b): Net quantity in standard metric units of mass or volume.',
    },
    {
      code: 'LMR_2011_R06_MANUFACTURER',
      name: 'Manufacturer / Packer Name & Complete Address',
      version: '2011.1.0',
      target: 'MANUFACTURER',
      severity: 'HIGH',
      description: 'Rule 6(1)(a): Complete registered postal address of manufacturer.',
    },
    {
      code: 'LMR_2011_R06_CONSUMER_CARE',
      name: 'Consumer Care Contact Helpline / Email',
      version: '2011.1.0',
      target: 'CONSUMER_CARE_PHONE',
      severity: 'HIGH',
      description: 'Rule 6(1)(h): Name, address, phone number, and email of person/office to contact for consumer grievances.',
    },
  ];

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Legal Metrology Compliance Rule Library</h1>
        <p className="page-subtitle">Deterministic, version-controlled rule definitions executed by the inspection engine.</p>
      </div>

      <div style={{ display: 'grid', gap: '16px' }}>
        {rules.map((rule) => (
          <div key={rule.code} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <span style={{
                  fontSize: '11px',
                  fontFamily: 'monospace',
                  backgroundColor: '#f1f5f9',
                  padding: '2px 6px',
                  borderRadius: '3px',
                  color: '#475569',
                  marginRight: '8px',
                }}>
                  {rule.code}
                </span>
                <span style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  backgroundColor: '#e0f2fe',
                  color: '#0369a1',
                  padding: '2px 6px',
                  borderRadius: '3px',
                }}>
                  v{rule.version}
                </span>
                <h2 style={{ fontSize: '16px', fontWeight: 600, marginTop: '6px' }}>{rule.name}</h2>
              </div>
              <span className="badge badge-fail" style={{ textTransform: 'capitalize' }}>
                Severity: {rule.severity}
              </span>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
              {rule.description}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RuleLibrary;
