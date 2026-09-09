import apiClient from './api';

export const scanService = {
  // Create a new scan session
  createScan: async (payload = {}) => {
    const response = await apiClient.post('/scans', payload);
    return response.data;
  },

  // Get scan session details
  getScan: async (scanId) => {
    const response = await apiClient.get(`/scans/${scanId}`);
    return response.data;
  },

  // List scans for current user
  listScans: async () => {
    const response = await apiClient.get('/scans');
    return response.data;
  },

  // Upload images to scan session
  uploadImages: async (scanId, files, imageType = 'FRONT', onUploadProgress = null) => {
    const formData = new FormData();
    if (Array.isArray(files)) {
      files.forEach((file) => {
        formData.append('files', file);
      });
    } else {
      formData.append('files', files);
    }
    formData.append('image_type', imageType);

    const config = {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    };

    if (onUploadProgress) {
      config.onUploadProgress = onUploadProgress;
    }

    const response = await apiClient.post(`/scans/${scanId}/images`, formData, config);
    return response.data;
  },

  // Delete an image from a scan session
  deleteImage: async (scanId, imageId) => {
    const response = await apiClient.delete(`/scans/${scanId}/images/${imageId}`);
    return response.data;
  },

  // Reorder scan images
  reorderImages: async (scanId, imageIds) => {
    const response = await apiClient.patch(`/scans/${scanId}/images/order`, {
      image_ids: imageIds,
    });
    return response.data;
  },

  // Lookup existing product by barcode
  lookupProductByBarcode: async (barcode) => {
    const response = await apiClient.get(`/products/by-barcode/${encodeURIComponent(barcode)}`);
    return response.data;
  },

  // Get image content preview URL
  getImagePreviewUrl: (scanId, imageId) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    return `${baseUrl}/api/v1/scans/${scanId}/images/${imageId}/content`;
  },

  // Day 4: Process all images in scan session (Quality analysis + PaddleOCR)
  processScan: async (scanId) => {
    const response = await apiClient.post(`/scans/${scanId}/process`);
    return response.data;
  },

  // Day 4: Retrieve OCR results, bounding boxes, and quality diagnostics
  getScanOcr: async (scanId) => {
    const response = await apiClient.get(`/scans/${scanId}/ocr`);
    return response.data;
  },

  // Day 4: Reprocess a single image
  reprocessImage: async (scanId, imageId) => {
    const response = await apiClient.post(`/scans/${scanId}/images/${imageId}/reprocess`);
    return response.data;
  },

  // Day 5: Extract legal declarations from persisted OCR blocks
  extractDeclarations: async (scanId) => {
    const response = await apiClient.post(`/scans/${scanId}/extract-declarations`);
    return response.data;
  },

  // Day 5: Get all structured declarations for scan
  getDeclarations: async (scanId) => {
    const response = await apiClient.get(`/scans/${scanId}/declarations`);
    return response.data;
  },

  // Day 5: Review / confirm / correct / reject a declaration
  reviewDeclaration: async (declarationId, payload, scanId = null) => {
    const url = scanId
      ? `/scans/${scanId}/declarations/${declarationId}`
      : `/declarations/${declarationId}`;
    const response = await apiClient.patch(url, payload);
    return response.data;
  },

  // Day 5: Benchmark evaluation status
  getBenchmarkEvaluation: async (scanId) => {
    const response = await apiClient.get(`/scans/${scanId}/declarations/benchmark-eval`);
    return response.data;
  },
};

export default scanService;
