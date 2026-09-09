import React, { useRef, useState } from 'react';
import {
  UploadCloud,
  Image as ImageIcon,
  Trash2,
  ArrowUp,
  ArrowDown,
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2,
} from 'lucide-react';

const MAX_FILE_SIZE_MB = 10;
const MAX_IMAGES_COUNT = 8;
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

const UploadZone = ({
  images = [],
  onImagesChange,
  onRemoveImage,
  onReorderImages,
  disabled = false,
}) => {
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const formatFileSize = (bytes) => {
    if (!bytes && bytes !== 0) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleFiles = (newFiles) => {
    setErrorMessage('');
    if (!newFiles || newFiles.length === 0) return;

    const currentCount = images.length;
    if (currentCount + newFiles.length > MAX_IMAGES_COUNT) {
      setErrorMessage(`Maximum ${MAX_IMAGES_COUNT} images allowed per inspection session.`);
      return;
    }

    const validatedItems = [];
    for (let i = 0; i < newFiles.length; i++) {
      const file = newFiles[i];

      // Format check
      if (!ALLOWED_TYPES.includes(file.type)) {
        setErrorMessage(`Unsupported format in "${file.name}". Only JPEG and PNG images are allowed.`);
        return;
      }

      // Size check
      if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        setErrorMessage(`"${file.name}" exceeds maximum allowed size of ${MAX_FILE_SIZE_MB} MB.`);
        return;
      }

      // Prepare local preview item
      validatedItems.push({
        id: `local-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        file: file,
        previewUrl: URL.createObjectURL(file),
        name: file.name,
        size: file.size,
        imageType: currentCount === 0 && i === 0 ? 'FRONT' : i === 1 ? 'BACK' : 'SIDE',
        status: 'WAITING', // 'WAITING' | 'UPLOADING' | 'UPLOADED' | 'FAILED'
        errorMessage: null,
      });
    }

    if (onImagesChange) {
      onImagesChange([...images, ...validatedItems]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    if (!disabled) setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  const handleTypeChange = (index, newType) => {
    const updated = [...images];
    updated[index] = { ...updated[index], imageType: newType };
    if (onImagesChange) onImagesChange(updated);
  };

  const moveImage = (index, direction) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= images.length) return;
    const updated = [...images];
    const temp = updated[index];
    updated[index] = updated[targetIndex];
    updated[targetIndex] = temp;
    if (onReorderImages) {
      onReorderImages(updated);
    } else if (onImagesChange) {
      onImagesChange(updated);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'UPLOADED':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#16a34a', fontSize: '11px', fontWeight: 600 }}>
            <CheckCircle2 size={13} /> Uploaded
          </span>
        );
      case 'UPLOADING':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#0284c7', fontSize: '11px', fontWeight: 600 }}>
            <Loader2 size={13} className="spin-animation" /> Uploading
          </span>
        );
      case 'FAILED':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#dc2626', fontSize: '11px', fontWeight: 600 }}>
            <AlertCircle size={13} /> Failed
          </span>
        );
      case 'WAITING':
      default:
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#64748b', fontSize: '11px', fontWeight: 500 }}>
            <Clock size={13} /> Ready to save
          </span>
        );
    }
  };

  return (
    <div>
      {/* Upload Drag & Drop Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && fileInputRef.current?.click()}
        style={{
          border: isDragOver ? '2px dashed #0284c7' : '2px dashed var(--border-dark)',
          borderRadius: '8px',
          padding: '28px 20px',
          textAlign: 'center',
          backgroundColor: isDragOver ? '#f0f9ff' : '#f8fafc',
          cursor: disabled ? 'not-allowed' : 'pointer',
          transition: 'all 0.2s ease',
          marginBottom: images.length > 0 ? '20px' : '0px',
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp"
          style={{ display: 'none' }}
          onChange={handleFileInputChange}
          disabled={disabled}
        />
        <div
          style={{
            display: 'inline-flex',
            padding: '12px',
            borderRadius: '50%',
            backgroundColor: '#e0f2fe',
            color: '#0284c7',
            marginBottom: '10px',
          }}
        >
          <UploadCloud size={26} />
        </div>
        <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--text-primary)' }}>
          Upload Packaging Images (Front / Back / Side Panels)
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
          Drag and drop images here, or <span style={{ color: '#0284c7', textDecoration: 'underline' }}>browse from device</span>
        </div>
        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '6px' }}>
          JPEG or PNG • Max 10MB per file • Up to 8 label angles
        </div>
      </div>

      {/* Error Message Box */}
      {errorMessage && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 14px',
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '6px',
            color: '#b91c1c',
            fontSize: '13px',
            marginBottom: '16px',
          }}
        >
          <AlertCircle size={16} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Uploaded Images List & Cards */}
      {images.length > 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Captured Packaging Panels ({images.length} / {MAX_IMAGES_COUNT})
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Order determines OCR scan sequence
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '16px' }}>
            {images.map((item, index) => (
              <div
                key={item.id || index}
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: '8px',
                  backgroundColor: '#ffffff',
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                }}
              >
                {/* Thumbnail Preview */}
                <div
                  style={{
                    position: 'relative',
                    width: '100%',
                    height: '140px',
                    backgroundColor: '#0f172a',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <img
                    src={item.previewUrl}
                    alt={item.name || `Panel ${index + 1}`}
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'contain',
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      top: '6px',
                      left: '6px',
                      backgroundColor: 'rgba(0,0,0,0.65)',
                      color: '#ffffff',
                      fontSize: '11px',
                      fontWeight: 600,
                      padding: '2px 6px',
                      borderRadius: '4px',
                    }}
                  >
                    #{index + 1}
                  </div>
                </div>

                {/* Card Controls & Details */}
                <div style={{ padding: '12px', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '10px' }}>
                  <div>
                    <div
                      style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={item.name}
                    >
                      {item.name || `Image_${index + 1}`}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
                      <span style={{ fontSize: '11px', color: '#64748b' }}>
                        {formatFileSize(item.size || item.file_size)}
                      </span>
                      {getStatusBadge(item.status)}
                    </div>
                  </div>

                  {/* Panel Type Selector */}
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                      Panel Orientation / Type
                    </label>
                    <select
                      className="form-control"
                      style={{ fontSize: '12px', padding: '4px 8px', height: '32px' }}
                      value={item.imageType || 'FRONT'}
                      onChange={(e) => handleTypeChange(index, e.target.value)}
                      disabled={disabled || item.status === 'UPLOADING'}
                    >
                      <option value="FRONT">FRONT Panel</option>
                      <option value="BACK">BACK Panel</option>
                      <option value="SIDE">SIDE Panel</option>
                      <option value="TOP">TOP Panel</option>
                      <option value="BOTTOM">BOTTOM Panel</option>
                      <option value="OTHER">OTHER Panel</option>
                    </select>
                  </div>

                  {/* Action Buttons: Reorder & Remove */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #f1f5f9', paddingTop: '8px' }}>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <button
                        type="button"
                        onClick={() => moveImage(index, -1)}
                        disabled={index === 0 || disabled}
                        style={{
                          background: 'none',
                          border: '1px solid var(--border)',
                          borderRadius: '4px',
                          padding: '3px 6px',
                          cursor: index === 0 ? 'not-allowed' : 'pointer',
                          color: index === 0 ? '#cbd5e1' : 'var(--text-secondary)',
                        }}
                        title="Move Up"
                      >
                        <ArrowUp size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => moveImage(index, 1)}
                        disabled={index === images.length - 1 || disabled}
                        style={{
                          background: 'none',
                          border: '1px solid var(--border)',
                          borderRadius: '4px',
                          padding: '3px 6px',
                          cursor: index === images.length - 1 ? 'not-allowed' : 'pointer',
                          color: index === images.length - 1 ? '#cbd5e1' : 'var(--text-secondary)',
                        }}
                        title="Move Down"
                      >
                        <ArrowDown size={13} />
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={() => onRemoveImage && onRemoveImage(index, item)}
                      disabled={disabled || item.status === 'UPLOADING'}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#ef4444',
                        cursor: disabled ? 'not-allowed' : 'pointer',
                        padding: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '11px',
                        fontWeight: 500,
                      }}
                      title="Remove Image"
                    >
                      <Trash2 size={14} /> Remove
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadZone;
