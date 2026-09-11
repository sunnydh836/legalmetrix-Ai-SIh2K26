import React from 'react';
import { Download, FileText, Search } from 'lucide-react';
import ViolationBadge from '../components/ViolationBadge';

const Reports = () => {
  const reports = [
    { id: 'REP-2026-001', scanId: 'SCAN-2026-001', product: 'Premium Dairy Ghee 500ml', date: '2026-09-05', status: 'PASS', size: '1.2 MB' },
    { id: 'REP-2026-002', scanId: 'SCAN-2026-002', product: 'Imported Roasted Almonds 200g', date: '2026-09-05', status: 'FAIL', size: '1.4 MB' },
    { id: 'REP-2026-003', scanId: 'SCAN-2026-004', product: 'Organic Rolled Oats 1kg', date: '2026-09-04', status: 'PASS', size: '1.1 MB' },
  ];

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Compliance Reports & Audit Dossiers</h1>
        <p className="page-subtitle">Archived official inspection reports with cryptographic and versioned rule audit records.</p>
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Report ID</th>
              <th>Inspection Scan</th>
              <th>Commodity</th>
              <th>Compliance Status</th>
              <th>Generated Date</th>
              <th>Download</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id}>
                <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--primary)' }}>{r.id}</td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>{r.scanId}</td>
                <td style={{ fontWeight: 500 }}>{r.product}</td>
                <td><ViolationBadge status={r.status} /></td>
                <td style={{ color: 'var(--text-muted)' }}>{r.date}</td>
                <td>
                  <button className="btn btn-outline" style={{ padding: '4px 10px', fontSize: '12px' }}>
                    <Download size={14} /> PDF
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Reports;
