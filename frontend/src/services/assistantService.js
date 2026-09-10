/**
 * LegalMetrix AI Assistant Client Service
 * Supports Server-Sent Events (SSE) streaming, multimodal payloads, and Web Speech API.
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const assistantService = {
  /**
   * SSE Streaming Chat Consumer
   */
  async streamChat({
    message,
    history = [],
    scanId = null,
    imageBase64 = null,
    imageMimeType = 'image/jpeg',
    userRole = 'INSPECTOR',
    onChunk,
    onDone,
    onError,
    signal,
  }) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/assistant/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          message,
          history,
          scan_id: scanId,
          image_base64: imageBase64,
          image_mime_type: imageMimeType,
          user_role: userRole,
        }),
        signal,
      });

      if (!response.ok) {
        throw new Error(`Assistant API returned status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep partial line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.slice(6);
            try {
              const parsed = JSON.parse(jsonStr);
              if (parsed.text && onChunk) {
                onChunk(parsed.text, parsed);
              }
              if (parsed.done && onDone) {
                onDone(parsed);
              }
            } catch (err) {
              // Ignore partial JSON parse errors
            }
          }
        }
      }

      if (onDone) {
        onDone({ done: true });
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        console.log('Stream aborted by user');
      } else {
        console.error('SSE Stream Error:', err);
        if (onError) onError(err);
      }
    }
  },

  /**
   * Get Assistant status
   */
  async getStatus() {
    const resp = await axios.get(`${API_BASE_URL}/api/v1/assistant/status`);
    return resp.data;
  },

  /**
   * Browser Text-to-Speech (TTS)
   */
  speakText(text, onEnd) {
    if (!('speechSynthesis' in window)) return;

    window.speechSynthesis.cancel(); // Stop any previous speech
    const cleanText = text.replace(/[*_#`\[\]]/g, '').trim();
    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.lang = 'en-IN'; // Indian English if available
    if (onEnd) utterance.onend = onEnd;

    window.speechSynthesis.speak(utterance);
  },

  stopSpeaking() {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  },

  /**
   * Check if browser supports Speech Recognition
   */
  isSpeechRecognitionSupported() {
    return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
  },

  /**
   * Create Speech Recognition Instance
   */
  createSpeechRecognizer(onResult, onEnd, onError) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return null;

    const recognizer = new SpeechRecognition();
    recognizer.continuous = false;
    recognizer.interimResults = true;
    recognizer.lang = 'en-IN';

    recognizer.onresult = (event) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      if (onResult) onResult(transcript, event.results[0]?.isFinal);
    };

    recognizer.onend = onEnd;
    recognizer.onerror = onError;
    return recognizer;
  },
};

export default assistantService;
