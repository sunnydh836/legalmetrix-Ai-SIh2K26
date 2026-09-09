# LegalMetrix AI — Declaration Taxonomy

## 1. Purpose & Disclaimer
This taxonomy defines the technical categorization used by LegalMetrix AI to classify extracted text segments from packaged commodity labels. 

> [!NOTE]
> **Legal Disclaimer**: This taxonomy represents the technical categorization within the software architecture. Exact legal interpretations, sub-clauses, exemptions, and mandatory font sizes under the Legal Metrology (Packaged Commodities) Rules, 2011 will be formally mapped during rule engine verification.

---

## 2. Taxonomy Types & Normalization Schema

| Taxonomy Key | Description | Example Raw Label Text | Normalized JSON Schema |
| :--- | :--- | :--- | :--- |
| `MRP` | Maximum Retail Price inclusive of all taxes | `"MRP Rs. 149.00 (Incl. of all taxes)"` | `{"amount": 149.0, "currency": "INR", "taxes_inclusive": true, "unit_price": null}` |
| `NET_QUANTITY` | Net quantity in metric units of mass/volume/length/number | `"Net Wt.: 500 g (When Packed)"` | `{"quantity": 500.0, "unit": "g", "unit_type": "mass"}` |
| `MANUFACTURER` | Name and complete address of the manufacturing entity | `"Mfg by: ABC Foods Pvt Ltd, Plot 12, Industrial Area, Pune 411001"` | `{"name": "ABC Foods Pvt Ltd", "address": "Plot 12, Industrial Area, Pune 411001", "pincode": "411001"}` |
| `PACKER` | Name and address of the packaging entity if distinct from mfg | `"Packed by: XYZ Packaging Hub, Delhi 110020"` | `{"name": "XYZ Packaging Hub", "address": "Delhi 110020"}` |
| `IMPORTER` | Name and address of the importer for imported goods | `"Imported & Marketed by: Global Trade Corp, Mumbai"` | `{"name": "Global Trade Corp", "address": "Mumbai"}` |
| `MANUFACTURE_DATE` | Month and year / date of manufacture | `"Mfg Date: 01/2026"` | `{"month": 1, "year": 2026, "raw_date": "2026-01"}` |
| `PACKING_DATE` | Month and year of packaging | `"Pkd: 02/2026"` | `{"month": 2, "year": 2026, "raw_date": "2026-02"}` |
| `IMPORT_DATE` | Month and year of import clearance | `"Imported: 03/2026"` | `{"month": 3, "year": 2026, "raw_date": "2026-03"}` |
| `CONSUMER_CARE_PHONE`| Dedicated consumer grievance helpline / toll-free number | `"Toll-free helpline: 1800-200-9999"` | `{"phone": "18002009999", "toll_free": true}` |
| `CONSUMER_CARE_EMAIL`| Customer grievance email ID | `"Customer Care: care@brandname.com"` | `{"email": "care@brandname.com"}` |
| `CONSUMER_CARE_ADDRESS`| Designated grievance officer physical address | `"Contact Consumer Care Officer at Mfg Address"` | `{"address": "Same as manufacturer"}` |
| `COUNTRY_OF_ORIGIN` | Country where commodity originated / manufactured | `"Country of Origin: India"` | `{"country_code": "IND", "country_name": "India"}` |
| `COMMODITY_NAME` | Common or generic name of commodity | `"Wheat Flour (Atta)"` | `{"common_name": "Atta", "generic_name": "Wheat Flour"}` |
| `OTHER` | Miscellaneous label disclosures (ingredients, barcodes, FSSAI) | `"FSSAI Lic No. 10019022009123"` | `{"raw_text": "FSSAI Lic..."}` |
