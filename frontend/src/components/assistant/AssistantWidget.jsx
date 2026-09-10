import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Bot,
  X,
  Send,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Image as ImageIcon,
  Sparkles,
  Trash2,
  Minimize2,
  Maximize2,
  CheckCircle2,
  Paperclip,
  Zap,
  Info,
} from 'lucide-react';
import assistantService from '../../services/assistantService';
import QuickActions from './QuickActions';

const AssistantWidget = () => {
  const location = useLocation();

  // Widget state
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        'Hello! I am your **LegalMetrix AI Regulatory Copilot**.\n\nI can assist you with package declaration compliance under the **Legal Metrology Rules, 2011**, explain image quality diagnostics (blur/glare), or help review inspection evidence.\n\nHow can I assist your inspection today?',
      timestamp: new Date(),
    },
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [tokensSaved, setTokensSaved] = useState(0);

  // Multimodal State
  const [attachedImage, setAttachedImage] = useState(null); // base64
  const [attachedImageName, setAttachedImageName] = useState('');
  const fileInputRef = useRef(null);

  // Voice State
  const [isListening, setIsListening] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const recognizerRef = useRef(null);

  // Auto-scroll ref
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Detect active scan ID from URL if present (e.g. /scans/:scanId or /inspections/:id)
  const getActiveScanId = () => {
    const parts = location.pathname.split('/');
    if (parts[1] === 'scans' && parts[2] && parts[2] !== 'new') {
      return parts[2];
    }
    if (parts[1] === 'inspections' && parts[2]) {
      return parts[2];
    }
    return null;
  };

  const activeScanId = getActiveScanId();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  // Voice recognition setup
  useEffect(() => {
    if (assistantService.isSpeechRecognitionSupported()) {
      recognizerRef.current = assistantService.createSpeechRecognizer(
        (transcript, isFinal) => {
          setInputMessage(transcript);
          if (isFinal) {
            setIsListening(false);
          }
        },
        () => setIsListening(false),
        (err) => {
          console.error('Speech recognition error:', err);
          setIsListening(false);
        }
      );
    }
  }, []);

  const toggleVoiceInput = () => {
    if (!recognizerRef.current) {
      alert('Speech recognition is not supported in this browser. Please use Chrome or Edge.');
      return;
    }

    if (isListening) {
      recognizerRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognizerRef.current.start();
        setIsListening(true);
      } catch (err) {
        console.error('Failed to start speech recognition:', err);
        setIsListening(false);
      }
    }
  };

  // Image attachment handler
  const handleImageSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('Please select a valid image file (JPEG, PNG, WebP).');
      return;
    }

    setAttachedImageName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      setAttachedImage(reader.result);
    };
    reader.readAsDataURL(file);
  };

  // Clipboard Paste Image Handler (Ctrl+V)
  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      if (items[i].type && items[i].type.startsWith('image/')) {
        e.preventDefault();
        const file = items[i].getAsFile();
        if (file) {
          setAttachedImageName(file.name || 'Pasted_Screenshot.png');
          const reader = new FileReader();
          reader.onload = () => {
            setAttachedImage(reader.result);
          };
          reader.readAsDataURL(file);
        }
        break;
      }
    }
  };

  // Drag and Drop Image Handler
  const handleDrop = (e) => {
    e.preventDefault();
    const files = e.dataTransfer?.files;
    if (files && files[0] && files[0].type.startsWith('image/')) {
      const file = files[0];
      setAttachedImageName(file.name || 'Dropped_Image.png');
      const reader = new FileReader();
      reader.onload = () => {
        setAttachedImage(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const clearAttachedImage = () => {
    setAttachedImage(null);
    setAttachedImageName('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Send message with SSE streaming
  const handleSendMessage = async (textToSend = null) => {
    const query = (textToSend || inputMessage).trim();
    if (!query && !attachedImage) return;

    if (isStreaming) {
      // Abort previous stream
      abortControllerRef.current?.abort();
    }

    const userMsg = {
      role: 'user',
      content: query || 'Analyze attached package image evidence',
      timestamp: new Date(),
      image_base64: attachedImage || null,
    };

    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInputMessage('');
    const imagePayload = attachedImage;
    clearAttachedImage();

    console.log('🤖 [LegalMetrix Copilot] Dispatching Prompt to Assistant:', {
      message: query,
      scanId: activeScanId,
      hasImage: !!imagePayload,
      historyLength: messages.slice(-6).length,
    });

    // Prepare placeholder for streaming assistant response
    const assistantPlaceholder = {
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, assistantPlaceholder]);
    setIsStreaming(true);

    abortControllerRef.current = new AbortController();
    let accumulatedText = '';

    await assistantService.streamChat({
      message: query,
      history: messages.slice(-6), // Send last 3 turns
      scanId: activeScanId,
      imageBase64: imagePayload,
      userRole: 'INSPECTOR',
      signal: abortControllerRef.current.signal,
      onChunk: (chunkText, meta) => {
        accumulatedText += chunkText;
        if (meta?.tokens_saved) {
          setTokensSaved(meta.tokens_saved);
        }
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0) {
            updated[lastIdx] = {
              ...updated[lastIdx],
              content: accumulatedText,
            };
          }
          return updated;
        });
      },
      onDone: () => {
        setIsStreaming(false);
        if (ttsEnabled && accumulatedText) {
          assistantService.speakText(accumulatedText);
        }
      },
      onError: (err) => {
        setIsStreaming(false);
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0) {
            updated[lastIdx] = {
              ...updated[lastIdx],
              content:
                accumulatedText ||
                '⚠️ Unable to reach AI Assistant server. Please check your backend connection.',
            };
          }
          return updated;
        });
      },
    });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const clearChat = () => {
    assistantService.stopSpeaking();
    setMessages([
      {
        role: 'assistant',
        content: 'Chat history cleared. How can I assist your inspection session?',
        timestamp: new Date(),
      },
    ]);
  };

  // Simple Markdown Renderer for assistant formatting
  const renderFormattedContent = (content) => {
    if (!content) return null;

    // Split paragraphs
    const paragraphs = content.split('\n\n');
    return paragraphs.map((p, pIdx) => {
      const lines = p.split('\n');
      return (
        <p key={pIdx} style={{ margin: '0 0 8px 0', lineHeight: 1.5 }}>
          {lines.map((line, lIdx) => {
            // Handle bullet items
            const isBullet = line.trim().startsWith('- ') || line.trim().startsWith('• ');
            const cleanLine = isBullet ? line.replace(/^[-•]\s*/, '') : line;

            // Simple bold and code format replacement
            const formattedParts = cleanLine.split(/(\*\*.*?\*\*|`.*?`)/g).map((part, idx) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={idx}>{part.slice(2, -2)}</strong>;
              }
              if (part.startsWith('`') && part.endsWith('`')) {
                return (
                  <code
                    key={idx}
                    style={{
                      backgroundColor: 'rgba(0,0,0,0.06)',
                      padding: '1px 4px',
                      borderRadius: '3px',
                      fontFamily: 'monospace',
                      fontSize: '12px',
                    }}
                  >
                    {part.slice(1, -1)}
                  </code>
                );
              }
              return part;
            });

            return (
              <span key={lIdx} style={{ display: isBullet ? 'flex' : 'inline', gap: '4px', marginBottom: isBullet ? '2px' : 0 }}>
                {isBullet && <span style={{ color: '#3b82f6' }}>•</span>}
                <span>{formattedParts}</span>
                {lIdx < lines.length - 1 && !isBullet && <br />}
              </span>
            );
          })}
        </p>
      );
    });
  };

  return (
    <>
      {/* Floating Launcher Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            width: '56px',
            height: '56px',
            borderRadius: '50%',
            backgroundColor: '#1e3a8a',
            color: '#ffffff',
            border: 'none',
            boxShadow: '0 8px 24px rgba(30, 58, 138, 0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            zIndex: 9999,
            transition: 'transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.08)')}
          onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
          title="Open LegalMetrix AI Copilot"
        >
          <Bot size={28} />
          <span
            style={{
              position: 'absolute',
              top: '2px',
              right: '2px',
              width: '12px',
              height: '12px',
              backgroundColor: '#10b981',
              borderRadius: '50%',
              border: '2px solid #ffffff',
            }}
          />
        </button>
      )}

      {/* Slide-out Drawer Panel */}
      {isOpen && (
        <div
          style={{
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            width: isExpanded ? '640px' : '400px',
            height: isExpanded ? '80vh' : '560px',
            maxHeight: '85vh',
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            boxShadow: '0 12px 40px rgba(0, 0, 0, 0.18)',
            border: '1px solid #e2e8f0',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 10000,
            overflow: 'hidden',
            transition: 'all 0.25s ease',
          }}
          onPaste={handlePaste}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          {/* Header */}
          <div
            style={{
              padding: '12px 16px',
              backgroundColor: '#1e3a8a',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Bot size={20} />
              <div>
                <div style={{ fontSize: '14px', fontWeight: 600 }}>LegalMetrix AI Copilot</div>
                <div style={{ fontSize: '11px', opacity: 0.85, display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ width: '6px', height: '6px', backgroundColor: '#10b981', borderRadius: '50%' }} />
                  SSE Streaming & Vision Active
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {/* TTS Voice Toggle */}
              <button
                type="button"
                onClick={() => {
                  if (ttsEnabled) assistantService.stopSpeaking();
                  setTtsEnabled(!ttsEnabled);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: ttsEnabled ? '#60a5fa' : '#ffffff',
                  cursor: 'pointer',
                  padding: '4px',
                  borderRadius: '4px',
                }}
                title={ttsEnabled ? 'Disable Voice Readout' : 'Enable Voice Readout'}
              >
                {ttsEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
              </button>

              {/* Clear Chat */}
              <button
                type="button"
                onClick={clearChat}
                style={{ background: 'none', border: 'none', color: '#ffffff', cursor: 'pointer', padding: '4px' }}
                title="Clear Chat History"
              >
                <Trash2 size={16} />
              </button>

              {/* Expand Toggle */}
              <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                style={{ background: 'none', border: 'none', color: '#ffffff', cursor: 'pointer', padding: '4px' }}
                title={isExpanded ? 'Shrink Drawer' : 'Expand Drawer'}
              >
                {isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              </button>

              {/* Close Drawer */}
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                style={{ background: 'none', border: 'none', color: '#ffffff', cursor: 'pointer', padding: '4px' }}
                title="Close Drawer"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Active Context Banner */}
          {activeScanId && (
            <div
              style={{
                backgroundColor: '#eff6ff',
                padding: '6px 12px',
                fontSize: '11px',
                color: '#1e40af',
                borderBottom: '1px solid #dbeafe',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Zap size={12} color="#2563eb" /> Grounded on Scan Session: <strong>{activeScanId}</strong>
              </div>
              {tokensSaved > 0 && (
                <span style={{ fontSize: '10px', backgroundColor: '#dcfce7', color: '#166534', padding: '1px 6px', borderRadius: '10px', fontWeight: 600 }}>
                  ~{tokensSaved} tokens saved
                </span>
              )}
            </div>
          )}

          {/* Quick Actions Bar */}
          <QuickActions onSelectAction={(prompt) => handleSendMessage(prompt)} disabled={isStreaming} />

          {/* Messages Scroll Area */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '14px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              backgroundColor: '#f8fafc',
            }}
          >
            {messages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: isUser ? 'flex-end' : 'flex-start',
                  }}
                >
                  <div
                    style={{
                      maxWidth: '88%',
                      padding: '10px 14px',
                      borderRadius: isUser ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                      backgroundColor: isUser ? '#1e3a8a' : '#ffffff',
                      color: isUser ? '#ffffff' : '#1e293b',
                      fontSize: '13px',
                      boxShadow: isUser
                        ? '0 2px 8px rgba(30, 58, 138, 0.2)'
                        : '0 1px 3px rgba(0, 0, 0, 0.08)',
                      border: isUser ? 'none' : '1px solid #e2e8f0',
                      wordBreak: 'break-word',
                    }}
                  >
                    {/* Attached Image Thumbnail */}
                    {msg.image_base64 && (
                      <div style={{ marginBottom: '8px' }}>
                        <img
                          src={msg.image_base64}
                          alt="Evidence Attachment"
                          style={{ maxHeight: '120px', borderRadius: '6px', objectFit: 'contain' }}
                        />
                      </div>
                    )}

                    {/* Content */}
                    {isUser ? (
                      <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                    ) : (
                      renderFormattedContent(msg.content)
                    )}
                  </div>

                  {/* Message Footer */}
                  {!isUser && msg.content && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '3px', marginLeft: '4px' }}>
                      <button
                        type="button"
                        onClick={() => assistantService.speakText(msg.content)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#64748b',
                          cursor: 'pointer',
                          padding: '2px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '2px',
                          fontSize: '11px',
                        }}
                        title="Listen to response"
                      >
                        <Volume2 size={12} /> Listen
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Attached Image Preview Bar */}
          {attachedImage && (
            <div
              style={{
                padding: '6px 12px',
                backgroundColor: '#f1f5f9',
                borderTop: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <img src={attachedImage} alt="preview" style={{ width: '28px', height: '28px', borderRadius: '4px', objectFit: 'cover' }} />
                <span style={{ fontSize: '11px', color: '#475569', fontWeight: 500 }}>{attachedImageName}</span>
              </div>
              <button
                type="button"
                onClick={clearAttachedImage}
                style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px' }}
              >
                <X size={14} />
              </button>
            </div>
          )}

          {/* Input Bar */}
          <div
            style={{
              padding: '10px 12px',
              backgroundColor: '#ffffff',
              borderTop: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            {/* Hidden File Input */}
            <input
              type="file"
              ref={fileInputRef}
              accept="image/*"
              style={{ display: 'none' }}
              onChange={handleImageSelect}
            />

            {/* Photo / Camera Upload Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              style={{
                background: 'none',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Attach Package Photo for Visual AI Analysis"
            >
              <ImageIcon size={18} />
            </button>

            {/* Voice Input Button */}
            <button
              type="button"
              onClick={toggleVoiceInput}
              style={{
                background: isListening ? '#fee2e2' : 'none',
                border: 'none',
                color: isListening ? '#dc2626' : '#64748b',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                animation: isListening ? 'pulse 1.5s infinite' : 'none',
              }}
              title={isListening ? 'Listening... Click to stop' : 'Voice Input (Hands-free)'}
            >
              {isListening ? <Mic size={18} /> : <MicOff size={18} />}
            </button>

            {/* Query Textarea / Input */}
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={
                isListening
                  ? 'Listening to speech...'
                  : 'Ask question, or paste image (Ctrl+V)...'
              }
              disabled={isStreaming}
              style={{
                flex: 1,
                border: '1px solid #cbd5e1',
                borderRadius: '20px',
                padding: '8px 14px',
                fontSize: '13px',
                outline: 'none',
              }}
            />

            {/* Send Button */}
            <button
              type="button"
              onClick={() => handleSendMessage()}
              disabled={isStreaming || (!inputMessage.trim() && !attachedImage)}
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: isStreaming || (!inputMessage.trim() && !attachedImage) ? '#94a3b8' : '#1e3a8a',
                color: '#ffffff',
                border: 'none',
                cursor: isStreaming || (!inputMessage.trim() && !attachedImage) ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'background-color 0.15s ease',
              }}
              title="Send Message"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </>
  );
};

export default AssistantWidget;
