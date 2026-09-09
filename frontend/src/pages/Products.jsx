import React from 'react';
import { Link } from 'react-router-dom';
import { Search, Filter } from 'lucide-react';

const Products = () => {
  const products = [
    { id: 'p-101', name: 'Premium Dairy Ghee 500ml', brand: 'Heritage Foods', category: 'Dairy & Edible Oils', barcode: '8901030010012' },
    { id: 'p-102', name: 'Imported Roasted Almonds 200g', brand: 'NutriBites', category: 'Dry Fruits & Nuts', barcode: '8901030010029' },
    { id: 'p-103', name: 'Herbal Hair Oil 100ml', brand: 'AyurCare', category: 'Cosmetics & Personal Care', barcode: '8901030010036' },
    { id: 'p-104', name: 'Organic Rolled Oats 1kg', brand: 'GrainField', category: 'Packaged Food Grains', barcode: '8901030010043' },
  ];

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Registered Packaged Commodities</h1>
        <p className="page-subtitle">Master commodity repository cataloged across Legal Metrology categories.</p>
      </div>

      <div className="card" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', gap: '16px' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <input type="text" className="form-control" placeholder="Search by commodity name, brand, or barcode..." />
          </div>
          <button className="btn btn-outline">
            <Filter size={16} /> Filter Category
          </button>
        </div>
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Barcode</th>
              <th>Commodity Name</th>
              <th>Brand / Manufacturer</th>
              <th>Category</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id}>
                <td style={{ fontFamily: 'monospace' }}>{p.barcode}</td>
                <td style={{ fontWeight: 600 }}>{p.name}</td>
                <td>{p.brand}</td>
                <td>{p.category}</td>
                <td>
                  <Link to={`/products/${p.id}`} style={{ fontSize: '13px', fontWeight: 500 }}>
                    View Profile
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

export default Products;
