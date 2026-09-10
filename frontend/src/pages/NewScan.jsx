import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  UploadZone,
  OCRImageOverlay,
  ImageQualityCard,
  ConfidenceIndicator,
  DeclarationCard,
} from '../components';
import {
  ArrowRight,
  Info,
  CheckCircle2,
  AlertCircle,
  Search,
  Save,
  RotateCcw,
  Tag,
  Barcode,
  Loader2,
  Cpu,
  Layers,
  FileText,
  RefreshCw,
  Eye,
  ShieldAlert,
  Sparkles,
  CheckCheck,
  Filter,
} from 'lucide-react';
import scanService from '../services/scanService';
import { DECLARATION_TAXONOMY, TAXONOMY_CHECKLIST_ITEMS } from '../constants/taxonomy';

const NewScan = () => {
  const { scanId } = useParams();
  const navigate = useNavigate();

  // Product form state
  const [productName, setProductName] = useState('');
  const [brand, setBrand] = useState('');
  const [category, setCategory] = useState('');
  const [barcode, setBarcode] = useState('');
  const [manufacturerName, setManufacturerName] = useState('');

  // Scan state
  const [currentScanId, setCurrentScanId] = useState(scanId || null);
  const [scanCode, setScanCode] = useState(null);
  const [scanStatus, setScanStatus] = useState(null);
  const [images, setImages] = useState([]);

  // Day 4 OCR & Quality state
  const [ocrData, setOcrData] = useState(null);
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [hoveredBlockId, setHoveredBlockId] = useState(null);
  const [selectedBlockId, setSelectedBlockId] = useState(null);
  const [showOverlay, setShowOverlay] = useState(true);
  const [processingScan, setProcessingScan] = useState(false);
  const [reprocessingImageId, setReprocessingImageId] = useState(null);

  // Day 5 Declaration Extraction & Review state
  const [declarationsData, setDeclarationsData] = useState(null);
  const [extractingDeclarations, setExtractingDeclarations] = useState(false);
  const [reviewingDeclId, setReviewingDeclId] = useState(null);
  const [activeDeclFilter, setActiveDeclFilter] = useState('ALL');

  // UI state
  const [loadingScan, setLoadingScan] = useState(false);
  const [savingScan, setSavingScan] = useState(false);
  const [barcodeSearching, setBarcodeSearching] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // 1. Recover scan, OCR data, and declarations after refresh if scanId is provided in URL
  useEffect(() => {
    const targetId = scanId || currentScanId;
    if (targetId) {
      loadExistingScan(targetId);
    }
  }, [scanId]);

  const loadExistingScan = async (id) => {
    try {
      setLoadingScan(true);
      setErrorMessage('');
      const scanData = await scanService.getScan(id);
      setCurrentScanId(scanData.id);
      setScanCode(scanData.scan_code);
      setScanStatus(scanData.status);

      if (scanData.product) {
        setProductName(scanData.product.name || '');
        setBrand(scanData.product.brand || '');
        setCategory(scanData.product.category || '');
        setBarcode(scanData.product.barcode || '');
        setManufacturerName(scanData.product.manufacturer_name || '');
      }

      // Format images from backend
      if (scanData.images && Array.isArray(scanData.images)) {
        const formattedImages = scanData.images.map((img) => ({
          id: img.id,
          name: img.original_filename || `Panel_${img.display_order + 1}`,
          previewUrl: img.preview_url
            ? `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}${img.preview_url}`
            : '',
          size: img.file_size,
          imageType: img.image_type,
          status: 'UPLOADED',
          isPersisted: true,
        }));
        setImages(formattedImages);
      }

      // Load OCR results if available
      if (scanData.images && scanData.images.length > 0) {
        try {
          const ocrResp = await scanService.getScanOcr(id);
          if (ocrResp && ocrResp.images && ocrResp.images.length > 0) {
            setOcrData(ocrResp);
          }
        } catch (ocrErr) {
          console.log('OCR results not yet generated for scan.');
        }

        // Load declarations if available
        try {
          const declResp = await scanService.getDeclarations(id);
          if (declResp && declResp.declarations && declResp.declarations.length > 0) {
            setDeclarationsData(declResp);
          }
        } catch (declErr) {
          console.log('Declarations not yet extracted for scan.');
        }
      }
    } catch (err) {
      console.error('Failed to load existing scan:', err);
      setErrorMessage(
        err.response?.data?.detail || 'Failed to recover scan session. It may not exist or you lack permission.'
      );
    } finally {
      setLoadingScan(false);
    }
  };

  // 2. Barcode auto-lookup
  const handleBarcodeLookup = async () => {
    const cleanBarcode = barcode.trim();
    if (!cleanBarcode) return;

    try {
      setBarcodeSearching(true);
      setErrorMessage('');
      const product = await scanService.lookupProductByBarcode(cleanBarcode);
      if (product) {
        if (product.name) setProductName(product.name);
        if (product.brand) setBrand(product.brand);
        if (product.category) setCategory(product.category);
        if (product.manufacturer_name) setManufacturerName(product.manufacturer_name);
        setSuccessMessage(`Found existing product record: "${product.name}"`);
        setTimeout(() => setSuccessMessage(''), 4000);
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setSuccessMessage('New barcode detected. Product details will be registered with this inspection.');
        setTimeout(() => setSuccessMessage(''), 4000);
      } else {
        setErrorMessage(err.response?.data?.detail || 'Barcode lookup failed.');
      }
    } finally {
      setBarcodeSearching(false);
    }
  };

  // 3. Handle image deletion
  const handleRemoveImage = async (index, item) => {
    if (item.isPersisted && currentScanId) {
      try {
        await scanService.deleteImage(currentScanId, item.id);
      } catch (err) {
        setErrorMessage(err.response?.data?.detail || 'Failed to delete image from server.');
        return;
      }
    } else if (item.previewUrl && item.previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(item.previewUrl);
    }

    const updated = images.filter((_, i) => i !== index);
    setImages(updated);
    if (selectedImageIndex >= updated.length) {
      setSelectedImageIndex(Math.max(0, updated.length - 1));
    }
  };

  // 4. Handle image reordering
  const handleReorderImages = async (newOrderedList) => {
    setImages(newOrderedList);
    const allPersisted = newOrderedList.every((img) => img.isPersisted);
    if (allPersisted && currentScanId && newOrderedList.length > 0) {
      try {
        const imageIds = newOrderedList.map((img) => img.id);
        await scanService.reorderImages(currentScanId, imageIds);
      } catch (err) {
        console.error('Failed to sync reorder on server:', err);
      }
    }
  };

  // 5. Create scan and upload images
  const handleSaveScan = async () => {
    setErrorMessage('');
    setSuccessMessage('');
    setSavingScan(true);

    try {
      let activeScanId = currentScanId;

      if (!activeScanId) {
        const payload = {
          product: {
            name: productName.trim() || undefined,
            brand: brand.trim() || undefined,
            category: category.trim() || undefined,
            barcode: barcode.trim() || undefined,
            manufacturer_name: manufacturerName.trim() || undefined,
          },
        };

        const createdScan = await scanService.createScan(payload);
        activeScanId = createdScan.id;
        setCurrentScanId(createdScan.id);
        setScanCode(createdScan.scan_code);
        setScanStatus(createdScan.status);

        navigate(`/scans/${createdScan.id}`, { replace: true });
      }

      const pendingImages = images.filter((img) => !img.isPersisted && img.file);

      if (pendingImages.length > 0) {
        for (let i = 0; i < pendingImages.length; i++) {
          const item = pendingImages[i];
          setImages((prev) =>
            prev.map((img) => (img.id === item.id ? { ...img, status: 'UPLOADING' } : img))
          );

          try {
            const uploadedList = await scanService.uploadImages(
              activeScanId,
              [item.file],
              item.imageType || 'FRONT'
            );

            const uploaded = uploadedList[0];
            setImages((prev) =>
              prev.map((img) =>
                img.id === item.id
                  ? {
                    ...img,
                    id: uploaded.id,
                    status: 'UPLOADED',
                    isPersisted: true,
                    previewUrl: `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}${uploaded.preview_url}`,
                  }
                  : img
              )
            );
          } catch (uploadErr) {
            setImages((prev) =>
              prev.map((img) =>
                img.id === item.id
                  ? { ...img, status: 'FAILED', errorMessage: uploadErr.response?.data?.detail }
                  : img
              )
            );
            throw uploadErr;
          }
        }
      }

      await loadExistingScan(activeScanId);

      // Automatic inspection pipeline: Quality -> OCR -> Declarations
      setProcessingScan(true);
      try {
        const ocrResult = await scanService.processScan(activeScanId);
        setOcrData(ocrResult);
        setScanStatus(ocrResult.status);

        // Step 3: Run Declaration Extraction automatically
        setExtractingDeclarations(true);
        try {
          const declResult = await scanService.extractDeclarations(activeScanId);
          setDeclarationsData(declResult);
          setScanStatus('DECLARATIONS_EXTRACTED');
          setSuccessMessage(
            `Inspection session saved, OCR completed (${ocrResult.images_processed} image(s)), and ${declResult.total_declarations} declarations extracted successfully!`
          );
        } catch (declErr) {
          console.error('Auto declaration extraction error:', declErr);
          setSuccessMessage('Inspection session saved and OCR completed successfully.');
        } finally {
          setExtractingDeclarations(false);
        }
      } catch (procErr) {
        console.error('Auto OCR processing error:', procErr);
        setSuccessMessage('Inspection session and label images saved successfully.');
      } finally {
        setProcessingScan(false);
      }
    } catch (err) {
      console.error('Save scan error:', err);
      setErrorMessage(
        err.response?.data?.detail || 'An error occurred while saving the inspection session.'
      );
    } finally {
      setSavingScan(false);
    }
  };

  // 6. Day 4: Execute Image Quality Analysis & PaddleOCR Extraction (Manual Reprocess)
  const handleProcessImages = async () => {
    if (!currentScanId) {
      setErrorMessage('Please save the inspection session and upload images before processing.');
      return;
    }

    setErrorMessage('');
    setSuccessMessage('');
    setProcessingScan(true);

    try {
      const result = await scanService.processScan(currentScanId);
      setScanStatus(result.status);
      setOcrData(result);

      // Auto re-extract declarations after reprocessing OCR
      try {
        const declResp = await scanService.extractDeclarations(currentScanId);
        setDeclarationsData(declResp);
        setScanStatus('DECLARATIONS_EXTRACTED');
      } catch (declErr) {
        console.error('Failed to auto-refresh declarations:', declErr);
      }

      setSuccessMessage(
        `Successfully reprocessed ${result.images_processed} image(s)! OCR text, quality metrics, and declarations updated.`
      );
      setTimeout(() => setSuccessMessage(''), 5000);
    } catch (err) {
      console.error('Processing error:', err);
      setErrorMessage(
        err.response?.data?.detail || 'Failed to process images. Please check backend logs and retry.'
      );
    } finally {
      setProcessingScan(false);
    }
  };

  // 7. Day 4: Reprocess single image
  const handleReprocessSingle = async (imageId) => {
    if (!currentScanId || !imageId) return;
    setReprocessingImageId(imageId);
    setErrorMessage('');

    try {
      const updatedImageDetail = await scanService.reprocessImage(currentScanId, imageId);
      setOcrData((prev) => {
        if (!prev || !prev.images) return prev;
        const updatedImages = prev.images.map((img) =>
          img.image_id === imageId ? updatedImageDetail : img
        );
        return { ...prev, images: updatedImages };
      });

      // Auto re-extract declarations after single image reprocess
      try {
        const declResp = await scanService.extractDeclarations(currentScanId);
        setDeclarationsData(declResp);
        setScanStatus('DECLARATIONS_EXTRACTED');
      } catch (declErr) {
        console.error('Failed to auto-refresh declarations:', declErr);
      }

      setSuccessMessage('Image reprocessed and declarations updated successfully.');
      setTimeout(() => setSuccessMessage(''), 4000);
    } catch (err) {
      setErrorMessage(err.response?.data?.detail || 'Failed to reprocess image.');
    } finally {
      setReprocessingImageId(null);
    }
  };

  // 8. Day 5: Extract Declarations
  const handleExtractDeclarations = async () => {
    if (!currentScanId) {
      setErrorMessage('Please save the scan and ensure OCR has run.');
      return;
    }

    setErrorMessage('');
    setSuccessMessage('');
    setExtractingDeclarations(true);

    try {
      const resp = await scanService.extractDeclarations(currentScanId);
      setDeclarationsData(resp);
      setScanStatus('DECLARATIONS_EXTRACTED');
      setSuccessMessage(
        `Extracted ${resp.total_declarations} legal declarations with OCR evidence linkage in ${resp.extraction_duration_ms || 0}ms!`
      );
      setTimeout(() => setSuccessMessage(''), 5000);
    } catch (err) {
      console.error('Extraction error:', err);
      setErrorMessage(
        err.response?.data?.detail || 'Failed to extract declarations. Please ensure OCR completed.'
      );
    } finally {
      setExtractingDeclarations(false);
    }
  };

  // 9. Day 5: Review / Edit Declaration
  const handleReviewDeclaration = async (declarationId, reviewPayload) => {
    if (!currentScanId || !declarationId) return;
    setReviewingDeclId(declarationId);
    setErrorMessage('');

    try {
      const updated = await scanService.reviewDeclaration(declarationId, reviewPayload, currentScanId);
      setDeclarationsData((prev) => {
        if (!prev || !prev.declarations) return prev;
        const updatedList = prev.declarations.map((d) =>
          d.id === declarationId ? updated : d
        );
        const unreviewed = updatedList.filter((d) => d.resolution_status === 'NEEDS_REVIEW' || d.resolution_status === 'CONFLICT').length;
        const confirmed = updatedList.filter((d) => d.resolution_status === 'CONFIRMED').length;
        const autoResolved = updatedList.filter((d) => d.resolution_status === 'AUTO_RESOLVED').length;
        const rejected = updatedList.filter((d) => d.resolution_status === 'REJECTED').length;

        return {
          ...prev,
          declarations: updatedList,
          unreviewed_count: unreviewed,
          confirmed_count: confirmed + autoResolved,
          corrected_count: 0,
          rejected_count: rejected,
        };
      });
      setSuccessMessage(`Declaration review updated to ${reviewPayload.review_status}.`);
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err) {
      console.error('Review error:', err);
      setErrorMessage(err.response?.data?.detail || 'Failed to update declaration review status.');
    } finally {
      setReviewingDeclId(null);
    }
  };

  // 10. Day 5: View Evidence link
  const handleViewEvidence = (declaration) => {
    if (declaration.image_id && ocrData?.images) {
      const imgIdx = ocrData.images.findIndex((im) => im.image_id === declaration.image_id);
      if (imgIdx >= 0) {
        setSelectedImageIndex(imgIdx);
      }
    }
    if (declaration.source_blocks && declaration.source_blocks.length > 0) {
      setSelectedBlockId(declaration.source_blocks[0]);
    }
    // Scroll smoothly to OCR viewer
    const ocrSection = document.getElementById('ocr-evidence-section');
    if (ocrSection) {
      ocrSection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleResetForNew = () => {
    setCurrentScanId(null);
    setScanCode(null);
    setScanStatus(null);
    setProductName('');
    setBrand('');
    setCategory('');
    setBarcode('');
    setManufacturerName('');
    setImages([]);
    setOcrData(null);
    setDeclarationsData(null);
    setSelectedImageIndex(0);
    setErrorMessage('');
    setSuccessMessage('');
    navigate('/scans/new');
  };

  const currentOcrImage = ocrData?.images?.[selectedImageIndex] || null;

  // Filter declarations
  const filteredDeclarations = declarationsData?.declarations?.filter((d) => {
    if (activeDeclFilter === 'ALL') return true;
    if (activeDeclFilter === 'NEEDS_REVIEW') return d.resolution_status === 'NEEDS_REVIEW';
    if (activeDeclFilter === 'CONFIRMED') return d.resolution_status === 'CONFIRMED';
    if (activeDeclFilter === 'AUTO_RESOLVED') return d.resolution_status === 'AUTO_RESOLVED';
    if (activeDeclFilter === 'REJECTED') return d.resolution_status === 'REJECTED';
    if (activeDeclFilter === 'CONFLICT') return d.resolution_status === 'CONFLICT' || d.has_conflict;
    return true;
  }) || [];

  // Derive Taxonomy Checklist items from the current declarations state (Canonical Source of Truth)
  const checklistItems = TAXONOMY_CHECKLIST_ITEMS.map((item) => {
    const matching = declarationsData?.declarations?.filter((d) =>
      d.declaration_type === item.key || (item.aliasKeys && item.aliasKeys.includes(d.declaration_type))
    ) || [];

    if (matching.length === 0) {
      return {
        ...item,
        status: 'NOT_DETECTED',
        badgeText: 'Not detected',
        color: '#94a3b8',
        bg: '#f8fafc',
        border: '#e2e8f0',
        matchingCount: 0,
      };
    }

    const hasConflict = matching.some((d) => d.has_conflict);
    if (hasConflict) {
      return {
        ...item,
        status: 'CONFLICT',
        badgeText: 'Detected — Conflict',
        color: '#b91c1c',
        bg: '#fee2e2',
        border: '#fca5a5',
        matchingCount: matching.length,
      };
    }

    const hasConfirmed = matching.some((d) => d.resolution_status === 'CONFIRMED' || d.resolution_status === 'AUTO_RESOLVED');
    if (hasConfirmed) {
      return {
        ...item,
        status: 'CONFIRMED',
        badgeText: 'Detected — Confirmed',
        color: '#15803d',
        bg: '#dcfce7',
        border: '#86efac',
        matchingCount: matching.length,
      };
    }

    const allRejected = matching.every((d) => d.resolution_status === 'REJECTED');
    if (allRejected) {
      return {
        ...item,
        status: 'REJECTED',
        badgeText: 'Rejected',
        color: '#dc2626',
        bg: '#fef2f2',
        border: '#fecaca',
        matchingCount: matching.length,
      };
    }

    // Default for active unreviewed declaration
    return {
      ...item,
      status: 'NEEDS_REVIEW',
      badgeText: 'Detected — Needs Review',
      color: '#b45309',
      bg: '#fef3c7',
      border: '#fde68a',
      matchingCount: matching.length,
    };
  });

  return (
    <div>
      {/* Page Header */}
      <div
        className="page-header"
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}
      >
        <div>
          <h1 className="page-title">Packaging Inspection Capture & Declaration Review</h1>
          <p className="page-subtitle">
            Capture multi-angle package labels, extract OCR blocks, normalize legal declarations, and review evidence with full traceability.
          </p>
        </div>

        {scanCode && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                backgroundColor: '#e0f2fe',
                border: '1px solid #bae6fd',
                borderRadius: '6px',
                padding: '6px 12px',
                textAlign: 'right',
              }}
            >
              <div style={{ fontSize: '11px', color: '#0369a1', fontWeight: 600 }}>INSPECTION CODE</div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: '#0284c7', fontFamily: 'monospace' }}>
                {scanCode}
              </div>
            </div>
            <button
              type="button"
              className="btn"
              onClick={handleResetForNew}
              style={{ fontSize: '12px', border: '1px solid var(--border)' }}
            >
              <RotateCcw size={14} /> New Inspection
            </button>
          </div>
        )}
      </div>

      {/* Alert Messages */}
      {errorMessage && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '6px',
            color: '#b91c1c',
            fontSize: '13px',
            marginBottom: '20px',
          }}
        >
          <AlertCircle size={18} />
          <span>{errorMessage}</span>
        </div>
      )}

      {successMessage && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            backgroundColor: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: '6px',
            color: '#15803d',
            fontSize: '13px',
            marginBottom: '20px',
          }}
        >
          <CheckCircle2 size={18} />
          <span>{successMessage}</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px', marginBottom: '24px' }}>
        <div className="card">
          {/* Step 1: Product Identification */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <div
              style={{
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                backgroundColor: 'var(--primary)',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: 700,
              }}
            >
              1
            </div>
            <h2 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
              Product Identification & Metadata (Optional)
            </h2>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
            <div className="form-group" style={{ gridColumn: 'span 2' }}>
              <label className="form-label">Product Name / Title</label>
              <input
                type="text"
                className="form-control"
                placeholder="e.g. Organic Rolled Oats 500g"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                disabled={savingScan || loadingScan || processingScan || extractingDeclarations}
              />
            </div>

            <div className="form-group">
              <label className="form-label">EAN / Barcode (Optional)</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. 8901234567890"
                  value={barcode}
                  onChange={(e) => setBarcode(e.target.value)}
                  disabled={savingScan || loadingScan || processingScan || extractingDeclarations}
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleBarcodeLookup}
                  disabled={!barcode.trim() || barcodeSearching || savingScan}
                  style={{ whiteSpace: 'nowrap', padding: '0 12px' }}
                  title="Search existing product registry"
                >
                  {barcodeSearching ? <Loader2 size={15} className="spin-animation" /> : <Search size={15} />}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Brand Name</label>
              <input
                type="text"
                className="form-control"
                placeholder="e.g. Nature Valley"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                disabled={savingScan || loadingScan || processingScan || extractingDeclarations}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Category</label>
              <input
                type="text"
                className="form-control"
                placeholder="e.g. Packaged Food / Dairy"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={savingScan || loadingScan || processingScan || extractingDeclarations}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Manufacturer / Packer Name</label>
              <input
                type="text"
                className="form-control"
                placeholder="e.g. Nature Foods Private Limited"
                value={manufacturerName}
                onChange={(e) => setManufacturerName(e.target.value)}
                disabled={savingScan || loadingScan || processingScan || extractingDeclarations}
              />
            </div>
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '24px 0' }} />

          {/* Step 2: Label Image Upload */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <div
              style={{
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                backgroundColor: 'var(--primary)',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: 700,
              }}
            >
              2
            </div>
            <h2 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
              Package Label Evidence Upload
            </h2>
          </div>

          <UploadZone
            images={images}
            onImagesChange={setImages}
            onRemoveImage={handleRemoveImage}
            onReorderImages={handleReorderImages}
            disabled={savingScan || loadingScan || processingScan || extractingDeclarations}
          />

          {/* Step 2 Action Buttons */}
          <div
            style={{
              marginTop: '24px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderTop: '1px solid var(--border)',
              paddingTop: '16px',
            }}
          >
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              {images.length === 0
                ? 'Upload at least 1 image to save inspection'
                : `${images.length} panel image(s) ready`}
            </span>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSaveScan}
                disabled={savingScan || loadingScan || processingScan || extractingDeclarations || images.length === 0}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
              >
                {savingScan ? (
                  <>
                    <Loader2 size={16} className="spin-animation" />
                    Saving Inspection...
                  </>
                ) : (
                  <>
                    <Save size={16} />
                    {currentScanId ? 'Save Inspection Changes' : 'Create Inspection Session'}
                  </>
                )}
              </button>

              {currentScanId && images.some((img) => img.isPersisted) && (
                <button
                  type="button"
                  className="btn"
                  onClick={handleProcessImages}
                  disabled={processingScan || savingScan || loadingScan || extractingDeclarations}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    backgroundColor: '#0284c7',
                    color: '#ffffff',
                    fontWeight: 600,
                  }}
                >
                  {processingScan ? (
                    <>
                      <Loader2 size={16} className="spin-animation" />
                      Analyzing Quality & Running OCR...
                    </>
                  ) : (
                    <>
                      <Cpu size={16} />
                      {ocrData ? 'Reprocess OCR' : 'Process Images & OCR'}
                    </>
                  )}
                </button>
              )}

              {/* Day 5 Extract Declarations CTA */}
              {ocrData && (
                <button
                  type="button"
                  className="btn"
                  onClick={handleExtractDeclarations}
                  disabled={extractingDeclarations || processingScan || savingScan}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    backgroundColor: '#16a34a',
                    color: '#ffffff',
                    fontWeight: 600,
                  }}
                >
                  {extractingDeclarations ? (
                    <>
                      <Loader2 size={16} className="spin-animation" />
                      Extracting Declarations...
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} />
                      {declarationsData ? 'Re-extract Declarations' : 'Extract Declarations'}
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar Info & Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Current Session State */}
          <div className="card" style={{ backgroundColor: '#f8fafc' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', color: 'var(--text-primary)' }}>
              Inspection Session Status
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Status:</span>
                <span
                  style={{
                    fontWeight: 600,
                    color:
                      scanStatus === 'DECLARATIONS_EXTRACTED'
                        ? '#16a34a'
                        : scanStatus === 'OCR_COMPLETED'
                          ? '#0284c7'
                          : '#64748b',
                  }}
                >
                  {scanStatus || 'NOT_CREATED'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Panels Uploaded:</span>
                <span style={{ fontWeight: 600 }}>{images.length} Panels</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Declarations Found:</span>
                <span style={{ fontWeight: 600, color: '#16a34a' }}>
                  {declarationsData?.total_declarations || 0} Fields
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Extractor Version:</span>
                <span style={{ color: '#0284c7', fontWeight: 600, fontFamily: 'monospace' }}>
                  v1.0.0 (Deterministic)
                </span>
              </div>
            </div>
          </div>

          {/* Architectural Guardrails */}
          <div className="card" style={{ backgroundColor: '#ffffff', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--primary)' }}>
              <Info size={18} />
              <h3 style={{ fontSize: '14px', fontWeight: 600 }}>Day 5 Intelligence Boundary</h3>
            </div>
            <ul style={{ fontSize: '12px', color: 'var(--text-secondary)', paddingLeft: '16px', lineHeight: 1.6 }}>
              <li><strong>Local & Deterministic:</strong> 100% regex, geometry, and layout rules without external LLMs.</li>
              <li><strong>Evidence Provenance:</strong> Every declaration maintains live links to contributing OCR blocks.</li>
              <li><strong>Human-in-the-loop:</strong> Reviewer corrections never overwrite machine extractions.</li>
              <li><strong>Legal Safety:</strong> Missing fields are marked "Not detected" without declaring legal violations.</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Step 4: Structured Legal Declarations & Inspector Review Panel (Day 5 Focus) */}
      {declarationsData && (
        <div className="card" style={{ marginTop: '24px', marginBottom: '24px', border: '1.5px solid #bbf7d0' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '20px',
              borderBottom: '1px solid var(--border)',
              paddingBottom: '16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  backgroundColor: '#16a34a',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '13px',
                  fontWeight: 700,
                }}
              >
                4
              </div>
              <div>
                <h2 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                  Structured Declaration Extraction & Inspector Review
                </h2>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                  Extracted {declarationsData.total_declarations} legal declaration fields. Review and confirm machine findings before Day 6 compliance evaluation.
                </p>
              </div>
            </div>

            {/* Quick Stat Chips */}
            <div style={{ display: 'flex', gap: '8px' }}>
              <div style={{ padding: '4px 10px', borderRadius: '6px', backgroundColor: '#f1f5f9', fontSize: '12px' }}>
                Total: <strong>{declarationsData.total_declarations}</strong>
              </div>
              <div style={{ padding: '4px 10px', borderRadius: '6px', backgroundColor: '#fef3c7', color: '#b45309', fontSize: '12px' }}>
                Unreviewed: <strong>{declarationsData.unreviewed_count}</strong>
              </div>
              <div style={{ padding: '4px 10px', borderRadius: '6px', backgroundColor: '#dcfce7', color: '#15803d', fontSize: '12px' }}>
                Confirmed: <strong>{declarationsData.confirmed_count}</strong>
              </div>
              {declarationsData.corrected_count > 0 && (
                <div style={{ padding: '4px 10px', borderRadius: '6px', backgroundColor: '#e0f2fe', color: '#0369a1', fontSize: '12px' }}>
                  Corrected: <strong>{declarationsData.corrected_count}</strong>
                </div>
              )}
              {declarationsData.rejected_count > 0 && (
                <div style={{ padding: '4px 10px', borderRadius: '6px', backgroundColor: '#fee2e2', color: '#b91c1c', fontSize: '12px' }}>
                  Rejected: <strong>{declarationsData.rejected_count}</strong>
                </div>
              )}
            </div>
          </div>

          {/* Filter Bar */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', alignItems: 'center' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Filter size={13} /> Filter:
            </span>
            {['ALL', 'NEEDS_REVIEW', 'CONFLICT', 'AUTO_RESOLVED', 'CONFIRMED', 'REJECTED'].map((filterKey) => (
              <button
                key={filterKey}
                type="button"
                onClick={() => setActiveDeclFilter(filterKey)}
                className={`btn ${activeDeclFilter === filterKey ? 'btn-primary' : 'btn-secondary'}`}
                style={{ fontSize: '11px', padding: '3px 10px' }}
              >
                {filterKey}
              </button>
            ))}
          </div>

          {/* Grid Layout: Extracted Declarations on Left, Undetected Taxonomy on Right */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
            {/* Left: Declaration Cards */}
            <div>
              {filteredDeclarations.length > 0 ? (
                filteredDeclarations.map((decl) => (
                  <DeclarationCard
                    key={decl.id}
                    declaration={decl}
                    onReview={handleReviewDeclaration}
                    onViewEvidence={handleViewEvidence}
                    isReviewing={reviewingDeclId === decl.id}
                  />
                ))
              ) : (
                <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
                  No declarations matching filter "{activeDeclFilter}".
                </div>
              )}
            </div>

            {/* Right: Statutory Taxonomy Checklist (Real-time Source of Truth) */}
            <div>
              <div className="card" style={{ padding: '16px', backgroundColor: '#f8fafc', border: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <h4 style={{ fontSize: '13px', fontWeight: 600, color: '#334155', margin: 0 }}>
                    Taxonomy Checklist Status
                  </h4>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: '12px',
                      backgroundColor: '#e2e8f0',
                      color: '#475569',
                    }}
                  >
                    {checklistItems.filter((i) => i.status !== 'NOT_DETECTED' && i.status !== 'REJECTED').length} / {checklistItems.length} Present
                  </span>
                </div>
                <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '12px', lineHeight: 1.4 }}>
                  Real-time statutory declaration coverage based on current evidence and inspector reviews.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '560px', overflowY: 'auto' }}>
                  {checklistItems.map((item) => (
                    <div
                      key={item.key}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '12px',
                        padding: '7px 10px',
                        backgroundColor: '#ffffff',
                        borderRadius: '6px',
                        border: '1px solid #e2e8f0',
                      }}
                    >
                      <span style={{ color: '#334155', fontWeight: 500, fontSize: '12px' }}>{item.label}</span>
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 600,
                          padding: '2px 7px',
                          borderRadius: '4px',
                          color: item.color,
                          backgroundColor: item.bg,
                          border: `1px solid ${item.border}`,
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {item.badgeText}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: OCR Evidence & Quality Diagnostics Viewer */}
      {ocrData && ocrData.images && ocrData.images.length > 0 && (
        <div id="ocr-evidence-section" className="card" style={{ marginTop: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  backgroundColor: '#0284c7',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 700,
                }}
              >
                3
              </div>
              <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0 }}>
                Structured OCR Evidence & Image Quality Diagnostics
              </h2>
            </div>

            {/* Panel Selector Tabs */}
            <div style={{ display: 'flex', gap: '8px' }}>
              {ocrData.images.map((img, idx) => (
                <button
                  key={img.image_id || idx}
                  type="button"
                  onClick={() => setSelectedImageIndex(idx)}
                  className={`btn ${selectedImageIndex === idx ? 'btn-primary' : 'btn-secondary'}`}
                  style={{
                    fontSize: '12px',
                    padding: '6px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <span>{img.image_type}</span>
                  <span
                    style={{
                      fontSize: '10px',
                      backgroundColor: selectedImageIndex === idx ? 'rgba(255,255,255,0.2)' : '#e2e8f0',
                      padding: '2px 6px',
                      borderRadius: '10px',
                    }}
                  >
                    {img.ocr_blocks?.length || 0} blocks
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Active Panel View */}
          {currentOcrImage && (
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px' }}>
              {/* Left Column: Image Preview with SVG Overlay */}
              <div>
                <OCRImageOverlay
                  imageUrl={`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}${currentOcrImage.preview_url}`}
                  imageWidth={currentOcrImage.quality?.width || 800}
                  imageHeight={currentOcrImage.quality?.height || 600}
                  ocrBlocks={currentOcrImage.ocr_blocks || []}
                  hoveredBlockId={hoveredBlockId}
                  selectedBlockId={selectedBlockId}
                  onBlockHover={setHoveredBlockId}
                  onBlockSelect={(b) => setSelectedBlockId(b.id)}
                  showOverlay={showOverlay}
                  onToggleOverlay={() => setShowOverlay(!showOverlay)}
                />
              </div>

              {/* Right Column: Diagnostics & OCR Text Block List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* Quality Diagnostics Card */}
                <ImageQualityCard
                  quality={currentOcrImage.quality}
                  imageType={currentOcrImage.image_type}
                  processingDurationMs={currentOcrImage.ocr_processing_duration_ms}
                  onRecapture={() => {
                    const idx = images.findIndex((im) => im.id === currentOcrImage.image_id);
                    if (idx >= 0) handleRemoveImage(idx, images[idx]);
                  }}
                />

                {/* OCR Text Block List */}
                <div className="card" style={{ padding: '16px', border: '1px solid var(--border)' }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <FileText size={16} color="var(--primary)" />
                      <h4 style={{ fontSize: '14px', fontWeight: 600, margin: 0 }}>
                        Extracted OCR Text ({currentOcrImage.ocr_blocks?.length || 0} Blocks)
                      </h4>
                    </div>

                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleReprocessSingle(currentOcrImage.image_id)}
                      disabled={reprocessingImageId === currentOcrImage.image_id}
                      style={{ padding: '3px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                      title="Reprocess this single image"
                    >
                      <RefreshCw
                        size={12}
                        className={reprocessingImageId === currentOcrImage.image_id ? 'spin-animation' : ''}
                      />
                      Reprocess Panel
                    </button>
                  </div>

                  {currentOcrImage.ocr_blocks && currentOcrImage.ocr_blocks.length > 0 ? (
                    <div
                      style={{
                        maxHeight: '380px',
                        overflowY: 'auto',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '8px',
                        paddingRight: '4px',
                      }}
                    >
                      {currentOcrImage.ocr_blocks.map((block) => {
                        const isHovered = hoveredBlockId === block.id;
                        const isSelected = selectedBlockId === block.id;
                        const confPercent = Math.round(block.confidence * 100);

                        return (
                          <div
                            key={block.id}
                            onMouseEnter={() => setHoveredBlockId(block.id)}
                            onMouseLeave={() => setHoveredBlockId(null)}
                            onClick={() => setSelectedBlockId(block.id)}
                            style={{
                              padding: '10px 12px',
                              borderRadius: '6px',
                              backgroundColor: isSelected
                                ? '#eff6ff'
                                : isHovered
                                  ? '#f8fafc'
                                  : '#ffffff',
                              border: isSelected
                                ? '1.5px solid #3b82f6'
                                : isHovered
                                  ? '1.5px solid #93c5fd'
                                  : '1px solid var(--border)',
                              cursor: 'pointer',
                              transition: 'all 0.12s ease-in-out',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                                #{block.block_order + 1}
                              </span>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span
                                  style={{
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                    backgroundColor:
                                      block.confidence >= 0.8
                                        ? '#dcfce7'
                                        : block.confidence >= 0.6
                                          ? '#fef3c7'
                                          : '#fee2e2',
                                    color:
                                      block.confidence >= 0.8
                                        ? '#15803d'
                                        : block.confidence >= 0.6
                                          ? '#b45309'
                                          : '#b91c1c',
                                  }}
                                >
                                  {confPercent}% {block.confidence < 0.6 ? '(Review)' : ''}
                                </span>
                              </div>
                            </div>
                            <div
                              style={{
                                fontSize: '13px',
                                fontWeight: 500,
                                color: 'var(--text-primary)',
                                wordBreak: 'break-word',
                              }}
                            >
                              "{block.text}"
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                      No OCR text blocks detected on this image panel.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default NewScan;
