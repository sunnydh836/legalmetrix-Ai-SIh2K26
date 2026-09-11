import React from 'react';
import { Link } from 'react-router-dom';
import { FileCheck, AlertTriangle, Clock, PlusCircle } from 'lucide-react';
import KPICard from '../components/KPICard';
import ViolationBadge from '../components/ViolationBadge';

const Dashboard = () => {
  const recentInspections = [
    { id: 'SCAN-2026-001', product: 'Premium Dairy Ghee 500ml', brand: 'Heritage Foods', status: 'PASS', date: '2026-09-05' },
    { id: 'SCAN-2026-002', product: 'Imported Roasted Almonds 200g', brand: 'NutriBites', status: 'FAIL', date: '2026-09-05' },
    { id: 'SCAN-2026-003', product: 'Herbal Hair Oil 100ml', brand: 'AyurCare', status: 'REVIEW', date: '2026-09-04' },
    { id: 'SCAN-2026-004', product: 'Organic Rolled Oats 1kg', brand: 'GrainField', status: 'PASS', date: '2026-09-04' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title">Enforcement & Compliance Overview</h1>
          <p className="page-subtitle">Legal Metrology (Packaged Commodities) Rules, 2011 — Surveillance Dashboard</p>
        </div>
        <Link to="/scans/new" className="btn btn-primary">
          <PlusCircle size={16} />
          New Inspection Scan
        </Link>
      </div>

      {/* KPI Summary Cards */}
      <div className="kpi-grid">
        <KPICard title="Total Inspections" value="1,248" subtitle="+12% this week" icon={FileCheck} color="var(--primary)" bg="var(--primary-light)" />
        <KPICard title="Compliant (Pass)" value="1,082" subtitle="86.7% compliance rate" icon={FileCheck} color="var(--success)" bg="var(--success-bg)" />
        <KPICard title="Violations Detected" value="114" subtitle="Action notices generated" icon={AlertTriangle} color="var(--danger)" bg="var(--danger-bg)" />
        <KPICard title="Pending Review" value="52" subtitle="Human inspection queue" icon={Clock} color="var(--warning)" bg="var(--warning-bg)" />
      </div>

      {/* Recent Inspections Table */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700 }}>Recent Inspection Scans</h2>
          <Link to="/reports" style={{ fontSize: '13px', fontWeight: 600 }}>View All Reports →</Link>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th>Scan Code</th>
              <th>Product Name</th>
              <th>Brand</th>
              <th>Evaluation Result</th>
              <th>Inspection Date</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {recentInspections.map((scan) => (
              <tr key={scan.id}>
                <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--primary)' }}>{scan.id}</td>
                <td style={{ fontWeight: 500 }}>{scan.product}</td>
                <td>{scan.brand}</td>
                <td><ViolationBadge status={scan.status} /></td>
                <td style={{ color: 'var(--text-muted)' }}>{scan.date}</td>
                <td>
                  <Link to={`/inspections/${scan.id}`} style={{ fontSize: '13px', fontWeight: 600, color: 'var(--info)' }}>
                    Details
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Dashboard;
