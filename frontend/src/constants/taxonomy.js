export const DECLARATION_TAXONOMY = {
  MRP: { label: 'Maximum Retail Price (MRP)', category: 'Commercial' },
  NET_QUANTITY: { label: 'Net Quantity', category: 'Measurement' },
  MANUFACTURER_NAME: { label: 'Manufacturer Name', category: 'Entity' },
  MANUFACTURER_ADDRESS: { label: 'Manufacturer Address', category: 'Entity' },
  MANUFACTURER: { label: 'Manufacturer Details', category: 'Entity' },
  PACKER_NAME: { label: 'Packer Name', category: 'Entity' },
  PACKER_ADDRESS: { label: 'Packer Address', category: 'Entity' },
  PACKER: { label: 'Packer Details', category: 'Entity' },
  IMPORTER_NAME: { label: 'Importer Name', category: 'Entity' },
  IMPORTER_ADDRESS: { label: 'Importer Address', category: 'Entity' },
  IMPORTER: { label: 'Importer Details', category: 'Entity' },
  COUNTRY_OF_ORIGIN: { label: 'Country of Origin', category: 'Origin' },
  COMMODITY_NAME: { label: 'Generic Commodity Name', category: 'Product' },
  DATE_OF_MANUFACTURE: { label: 'Date of Manufacture', category: 'Dates' },
  MANUFACTURE_DATE: { label: 'Date of Manufacture', category: 'Dates' },
  DATE_OF_PACKING: { label: 'Date of Packing', category: 'Dates' },
  PACKING_DATE: { label: 'Date of Packing', category: 'Dates' },
  DATE_OF_IMPORT: { label: 'Date of Import', category: 'Dates' },
  IMPORT_DATE: { label: 'Date of Import', category: 'Dates' },
  BEST_BEFORE: { label: 'Best Before', category: 'Dates' },
  EXPIRY_DATE: { label: 'Expiry Date', category: 'Dates' },
  CONSUMER_CARE_PHONE: { label: 'Consumer Care Phone', category: 'Consumer Care' },
  CONSUMER_CARE_EMAIL: { label: 'Consumer Care Email', category: 'Consumer Care' },
  CONSUMER_CARE_ADDRESS: { label: 'Consumer Care Address', category: 'Consumer Care' },
  BATCH_OR_LOT_NUMBER: { label: 'Batch / Lot Number', category: 'Traceability' },
  OTHER: { label: 'Other Disclosure', category: 'Other' },
};

export const TAXONOMY_CHECKLIST_ITEMS = [
  { key: 'MRP', label: 'Maximum Retail Price (MRP)', category: 'Commercial' },
  { key: 'NET_QUANTITY', label: 'Net Quantity', category: 'Measurement' },
  { key: 'COMMODITY_NAME', label: 'Generic Commodity Name', category: 'Product' },
  { key: 'DATE_OF_MANUFACTURE', label: 'Date of Manufacture', category: 'Dates', aliasKeys: ['MANUFACTURE_DATE'] },
  { key: 'DATE_OF_PACKING', label: 'Date of Packing', category: 'Dates', aliasKeys: ['PACKING_DATE'] },
  { key: 'EXPIRY_DATE', label: 'Expiry Date / Best Before', category: 'Dates', aliasKeys: ['BEST_BEFORE'] },
  { key: 'MANUFACTURER_NAME', label: 'Manufacturer Name', category: 'Entity', aliasKeys: ['MANUFACTURER'] },
  { key: 'MANUFACTURER_ADDRESS', label: 'Manufacturer Address', category: 'Entity' },
  { key: 'PACKER_NAME', label: 'Packer Name', category: 'Entity', aliasKeys: ['PACKER'] },
  { key: 'PACKER_ADDRESS', label: 'Packer Address', category: 'Entity' },
  { key: 'IMPORTER_NAME', label: 'Importer Name', category: 'Entity', aliasKeys: ['IMPORTER'] },
  { key: 'IMPORTER_ADDRESS', label: 'Importer Address', category: 'Entity' },
  { key: 'COUNTRY_OF_ORIGIN', label: 'Country of Origin', category: 'Origin' },
  { key: 'CONSUMER_CARE_PHONE', label: 'Consumer Care Phone', category: 'Consumer Care' },
  { key: 'CONSUMER_CARE_EMAIL', label: 'Consumer Care Email', category: 'Consumer Care' },
  { key: 'CONSUMER_CARE_ADDRESS', label: 'Consumer Care Address', category: 'Consumer Care' },
  { key: 'BATCH_OR_LOT_NUMBER', label: 'Batch / Lot Number', category: 'Traceability' },
];

export const REVIEW_STATUSES = {
  UNREVIEWED: { label: 'Unreviewed', color: '#475569', bg: '#f1f5f9', border: '#cbd5e1' },
  CONFIRMED: { label: 'Confirmed', color: '#15803d', bg: '#dcfce7', border: '#86efac' },
  CORRECTED: { label: 'Corrected', color: '#0369a1', bg: '#e0f2fe', border: '#7dd3fc' },
  REJECTED: { label: 'Rejected', color: '#b91c1c', bg: '#fee2e2', border: '#fca5a5' },
};

export const CONFIDENCE_LEVELS = {
  HIGH: { label: 'HIGH', color: '#15803d', bg: '#dcfce7', border: '#86efac' },
  MEDIUM: { label: 'MEDIUM', color: '#b45309', bg: '#fef3c7', border: '#fde68a' },
  LOW: { label: 'LOW', color: '#b91c1c', bg: '#fee2e2', border: '#fca5a5' },
};

export const COMPLIANCE_STATUSES = {
  PASS: { label: 'Compliant', color: 'pass' },
  FAIL: { label: 'Non-Compliant', color: 'fail' },
  REVIEW: { label: 'Review Required', color: 'review' },
  NOT_APPLICABLE: { label: 'Not Applicable', color: 'na' },
};
