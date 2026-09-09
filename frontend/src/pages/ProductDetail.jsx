import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Package } from 'lucide-react';

const ProductDetail = () => {
  const { id } = useParams();

  return (
    <div>
      <Link to="/products" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', marginBottom: '16px', fontSize: '13px', fontWeight: 500 }}>
        <ArrowLeft size={14} /> Back to Products
      </Link>

      <div className="page-header">
        <h1 className="page-title">Product Metadata: {id}</h1>
        <p className="page-subtitle">Detailed commodity record, inspection history, and category classifications.</p>
      </div>

      <div className="card">
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '20px' }}>
          <div style={{ padding: '12px', backgroundColor: '#eff6ff', borderRadius: '8px', color: '#1e3a8a' }}>
            <Package size={28} />
          </div>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 700 }}>Premium Dairy Ghee 500ml</h2>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Heritage Foods | Category: Dairy & Edible Oils</div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Barcode (EAN-13)</div>
            <div style={{ fontWeight: 600, fontFamily: 'monospace' }}>8901030010012</div>
          </div>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Registered Manufacturer</div>
            <div style={{ fontWeight: 600 }}>Heritage Foods India Pvt Ltd</div>
          </div>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Total Inspections Performed</div>
            <div style={{ fontWeight: 600 }}>8 Scans (100% Pass)</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProductDetail;
