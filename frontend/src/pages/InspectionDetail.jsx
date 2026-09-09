import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, ShieldCheck, AlertCircle, Loader2 } from 'lucide-react';
import ViolationBadge from '../components/ViolationBadge';
import DeclarationCard from '../components/DeclarationCard';
import scanService from '../services/scanService';

const InspectionDetail = () => {
  const { id } = useParams();
  const [declarations, setDeclarations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reviewingId, setReviewingId] = useState(null);

  useEffect(() => {
    if (id) {
      loadDeclarations();
    }
  }, [id]);

  const loadDeclarations = async () => {
    try {
      setLoading(true);
      setError('');
      const resp = await scanService.getDeclarations(id);
      if (resp && resp.declarations) {
        setDeclarations(resp.declarations);
      }
    } catch (err) {
      console.error('Failed to load declarations:', err);
      // Fallback sample if not extracted yet
      setDeclarations([]);
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (declId, payload) => {
    try {
      setReviewingId(declId);
      const updated = await scanService.reviewDeclaration(declId, payload, id);
      setDeclarations((prev) =>
        prev.map((d) => (d.id === declId ? updated : d))
      );
    } catch (err) {
      console.error('Review failed:', err);
    } finally {
      setReviewingId(null);
    }
  };

  return (
    <div>
      <Link
        to="/dashboard"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          marginBottom: '16px',
          fontSize: '13px',
          fontWeight: 500,
        }}
      >
        <ArrowLeft size={14} /> Back to Dashboard
      </Link>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title">Inspection Findings: {id}</h1>
          <p className="page-subtitle">Declaration Intelligence & Review Provenance Breakdown</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <ViolationBadge status="PASS" />
          <button className="btn btn-outline">Generate PDF Report</button>
        </div>
      </div>

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '60px', gap: '8px' }}>
          <Loader2 size={24} className="spin-animation" />
          <span>Loading extracted declarations...</span>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
          {/* Left Column: Declarations & Evidence */}
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>
              Extracted Declarations & Review Provenance ({declarations.length})
            </h2>
            {declarations.length > 0 ? (
              declarations.map((decl) => (
                <DeclarationCard
                  key={decl.id}
                  declaration={decl}
                  onReview={handleReview}
                  isReviewing={reviewingId === decl.id}
                />
              ))
            ) : (
              <div className="card" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                No declarations extracted yet for this inspection session. Run extraction from the Inspection Capture screen.
              </div>
            )}
          </div>

          {/* Right Column: Rule Engine Audit Log */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color: 'var(--primary)' }}>
              <ShieldCheck size={20} />
              <h2 style={{ fontSize: '16px', fontWeight: 600 }}>Rule Engine Audit Trace (Day 6 Preview)</h2>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Legal Metrology rules will evaluate against version: <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>2011.1.0</span>
            </div>

            <div style={{ borderLeft: '2px solid var(--border-color)', paddingLeft: '16px' }}>
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontWeight: 600, fontSize: '13px' }}>Rule 6(1)(e) — Maximum Retail Price</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Status: PASS | Reason: MRP_PRESENT</div>
              </div>
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontWeight: 600, fontSize: '13px' }}>Rule 6(1)(b) — Net Quantity in Standard Units</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Status: PASS | Reason: NET_QUANTITY_PRESENT</div>
              </div>
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontWeight: 600, fontSize: '13px' }}>Rule 6(1)(a) — Manufacturer Name & Address</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Status: PASS | Reason: MANUFACTURER_PRESENT</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default InspectionDetail;
