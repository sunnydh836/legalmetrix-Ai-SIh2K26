import React, { useState, useRef, useEffect } from 'react';
import { Layers, Eye, EyeOff, ZoomIn, ZoomOut, RotateCcw, AlertTriangle } from 'lucide-react';

const OCRImageOverlay = ({
  imageUrl,
  imageWidth = 800,
  imageHeight = 600,
  ocrBlocks = [],
  hoveredBlockId = null,
  selectedBlockId = null,
  onBlockSelect = null,
  onBlockHover = null,
  showOverlay = true,
  onToggleOverlay = null,
}) => {
  const [naturalWidth, setNaturalWidth] = useState(imageWidth);
  const [naturalHeight, setNaturalHeight] = useState(imageHeight);
  const [activeTooltip, setActiveTooltip] = useState(null);
  const [imageError, setImageError] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);
  const imgRef = useRef(null);

  useEffect(() => {
    setImageError(false);
  }, [imageUrl]);

  const handleImageLoad = (e) => {
    setImageError(false);
    if (e.target.naturalWidth && e.target.naturalHeight) {
      setNaturalWidth(e.target.naturalWidth);
      setNaturalHeight(e.target.naturalHeight);
    }
  };

  const getConfidenceColor = (conf, isHighlighted) => {
    if (isHighlighted) {
      return {
        stroke: '#2563eb',
        fill: 'rgba(37, 99, 235, 0.32)',
        strokeWidth: 3,
      };
    }
    if (conf >= 0.8) {
      return {
        stroke: 'var(--success)',
        fill: 'rgba(22, 163, 74, 0.15)',
        strokeWidth: 1.5,
      };
    }
    if (conf >= 0.6) {
      return {
        stroke: '#d97706',
        fill: 'rgba(217, 119, 6, 0.18)',
        strokeWidth: 1.5,
      };
    }
    return {
      stroke: 'var(--danger)',
      fill: 'rgba(220, 38, 38, 0.20)',
      strokeWidth: 1.5,
    };
  };

  const formatPolygonPoints = (block) => {
    if (block.polygon && Array.isArray(block.polygon) && block.polygon.length >= 3) {
      return block.polygon.map((pt) => `${pt[0]},${pt[1]}`).join(' ');
    }
    // Fallback to bounding box rectangle
    const x1 = block.bbox_x1 ?? 0;
    const y1 = block.bbox_y1 ?? 0;
    const x2 = block.bbox_x2 ?? 10;
    const y2 = block.bbox_y2 ?? 10;
    return `${x1},${y1} ${x2},${y1} ${x2},${y2} ${x1},${y2}`;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {/* Overlay Toolbar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: 'var(--bg-primary)',
          padding: '6px 12px',
          borderRadius: '6px',
          fontSize: '12px',
          border: '1px solid var(--border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
          <Layers size={14} />
          <span>
            <strong>{ocrBlocks.length}</strong> OCR Text Regions Detected
          </span>
          {naturalWidth > 0 && (
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              ({naturalWidth} × {naturalHeight}px)
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Zoom controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '2px', borderRight: '1px solid var(--border)', paddingRight: '8px' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.25))}
              style={{ padding: '3px 6px', fontSize: '11px' }}
              title="Zoom In"
            >
              <ZoomIn size={13} />
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setZoomLevel((z) => Math.max(1, z - 0.25))}
              style={{ padding: '3px 6px', fontSize: '11px' }}
              title="Zoom Out"
            >
              <ZoomOut size={13} />
            </button>
            {zoomLevel > 1 && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setZoomLevel(1)}
                style={{ padding: '3px 6px', fontSize: '11px' }}
                title="Reset Zoom"
              >
                <RotateCcw size={12} />
              </button>
            )}
          </div>

          {onToggleOverlay && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onToggleOverlay}
              style={{ padding: '3px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              {showOverlay ? <EyeOff size={13} /> : <Eye size={13} />}
              {showOverlay ? 'Hide Overlay' : 'Show Overlay'}
            </button>
          )}
        </div>
      </div>

      {/* Image Container with SVG Overlay */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          backgroundColor: 'var(--bg-sidebar)',
          borderRadius: '8px',
          overflow: 'auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '340px',
          maxHeight: '620px',
        }}
      >
        {imageError ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--border-dark)' }}>
            <AlertTriangle size={32} color="#f59e0b" style={{ margin: '0 auto 12px auto' }} />
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--bg-primary)', marginBottom: '4px' }}>
              Image Preview Unavailable
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Could not load image resource from <code>{imageUrl}</code>.
            </div>
          </div>
        ) : (
          <div
            style={{
              position: 'relative',
              display: 'inline-block',
              transform: `scale(${zoomLevel})`,
              transformOrigin: 'top center',
              transition: 'transform 0.15s ease-out',
            }}
          >
            <img
              ref={imgRef}
              src={imageUrl}
              alt="Package Evidence"
              onLoad={handleImageLoad}
              onError={() => setImageError(true)}
              style={{
                display: 'block',
                maxWidth: '100%',
                height: 'auto',
                maxHeight: '560px',
                objectFit: 'contain',
              }}
            />

            {showOverlay && naturalWidth > 0 && naturalHeight > 0 && (
              <svg
                viewBox={`0 0 ${naturalWidth} ${naturalHeight}`}
                preserveAspectRatio="none"
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '100%',
                  pointerEvents: 'none',
                }}
              >
                {ocrBlocks.map((block, idx) => {
                  const isHighlighted = hoveredBlockId === block.id || selectedBlockId === block.id;
                  const styleProps = getConfidenceColor(block.confidence, isHighlighted);
                  const pointsStr = formatPolygonPoints(block);

                  return (
                    <g key={block.id || idx}>
                      <polygon
                        points={pointsStr}
                        fill={styleProps.fill}
                        stroke={styleProps.stroke}
                        strokeWidth={styleProps.strokeWidth}
                        strokeLinejoin="round"
                        style={{
                          pointerEvents: 'auto',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease-in-out',
                        }}
                        onMouseEnter={() => {
                          if (onBlockHover) onBlockHover(block.id);
                          setActiveTooltip({
                            text: block.text,
                            confidence: block.confidence,
                            order: block.block_order + 1,
                          });
                        }}
                        onMouseLeave={() => {
                          if (onBlockHover) onBlockHover(null);
                          setActiveTooltip(null);
                        }}
                        onClick={() => {
                          if (onBlockSelect) onBlockSelect(block);
                        }}
                      />
                    </g>
                  );
                })}
              </svg>
            )}
          </div>
        )}

        {/* Hover Tooltip Overlay */}
        {activeTooltip && (
          <div
            style={{
              position: 'absolute',
              bottom: '12px',
              left: '12px',
              right: '12px',
              backgroundColor: 'rgba(15, 23, 42, 0.92)',
              color: 'var(--bg-surface)',
              padding: '8px 12px',
              borderRadius: '6px',
              fontSize: '12px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backdropFilter: 'blur(4px)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              pointerEvents: 'none',
              zIndex: 10,
            }}
          >
            <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>
              #{activeTooltip.order}: "{activeTooltip.text}"
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: activeTooltip.confidence >= 0.8 ? '#4ade80' : activeTooltip.confidence >= 0.6 ? '#fcd34d' : '#f87171',
                }}
              >
                Confidence: {Math.round(activeTooltip.confidence * 100)}%
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Confidence Legend */}
      <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: 'var(--text-muted)', paddingLeft: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '10px', height: '10px', backgroundColor: 'var(--success)', borderRadius: '2px' }} />
          <span>High (≥80%)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '10px', height: '10px', backgroundColor: '#d97706', borderRadius: '2px' }} />
          <span>Medium (60-79%)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '10px', height: '10px', backgroundColor: 'var(--danger)', borderRadius: '2px' }} />
          <span>Low (&lt;60% - Review)</span>
        </div>
      </div>
    </div>
  );
};

export default OCRImageOverlay;
