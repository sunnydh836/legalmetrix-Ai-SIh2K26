import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  ShieldCheck, Eye, EyeOff, Loader2, AlertCircle, 
  ScanLine, Scale, ClipboardCheck, FileText, 
  CheckCircle2, ArrowRight, Lock, Mail, KeyRound
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Login.css';

const Login = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // Target path user was trying to access
  const from = location.state?.from?.pathname || '/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage('Please enter both email and password.');
      return;
    }

    setIsLoading(true);
    setErrorMessage('');

    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      if (err.response) {
        if (err.response.status === 401) {
          setErrorMessage(err.response.data?.detail || 'Invalid email or password.');
        } else if (err.response.status === 422) {
          setErrorMessage('Please provide a valid email format.');
        } else {
          setErrorMessage(err.response.data?.detail || 'Authentication failed. Please try again.');
        }
      } else if (err.request) {
        setErrorMessage('Unable to connect to authentication server. Please check backend service.');
      } else {
        setErrorMessage('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      {/* LEFT PANEL - Product Story & Features */}
      <div className="login-left">
        <div className="bg-decoration-orb orb-1"></div>
        <div className="bg-decoration-orb orb-2"></div>
        
        <div style={{ maxWidth: '600px' }}>
          <div className="brand">
            <ShieldCheck size={36} color="#38bdf8" />
            <div>
              LegalMetrix AI
              <span className="brand-subtitle">Department of Enforcement Intelligence</span>
            </div>
          </div>

          <h1 className="hero-title">
            Smarter Inspections.<br />
            Stronger Compliance.
          </h1>
          <p className="hero-subtitle">
            AI-assisted inspection and compliance intelligence for packaged commodities — helping enforcement officers verify declarations, trace applicable rules and document findings efficiently.
          </p>

          <div className="features-grid">
            <div className="feature-card delay-1">
              <div className="feature-icon"><ScanLine size={22} /></div>
              <div className="feature-text">
                <h3>AI-Assisted Extraction</h3>
                <p>Extract key declarations from package labels and organize them for inspector review.</p>
              </div>
            </div>
            
            <div className="feature-card delay-2">
              <div className="feature-icon"><ShieldCheck size={22} /></div>
              <div className="feature-text">
                <h3>Rule-Based Compliance</h3>
                <p>Evaluate extracted declarations against applicable Legal Metrology requirements.</p>
              </div>
            </div>
            
            <div className="feature-card delay-3">
              <div className="feature-icon"><Scale size={22} /></div>
              <div className="feature-text">
                <h3>Traceable Evidence</h3>
                <p>Connect findings with relevant rule references and supporting inspection evidence.</p>
              </div>
            </div>
            
            <div className="feature-card delay-4">
              <div className="feature-icon"><ClipboardCheck size={22} /></div>
              <div className="feature-text">
                <h3>Faster Workflows</h3>
                <p>Move from package capture to structured compliance findings through one workflow.</p>
              </div>
            </div>
          </div>

          <div className="compliance-preview delay-5">
            <div className="preview-header">
              <span>Compliance Check Preview</span>
              <span className="badge-pulse">Live</span>
            </div>
            <div className="preview-item">
              <CheckCircle2 size={18} className="text-success" /> Product identity detected
            </div>
            <div className="preview-item">
              <CheckCircle2 size={18} className="text-success" /> Net quantity detected
            </div>
            <div className="preview-item">
              <CheckCircle2 size={18} className="text-success" /> MRP detected
            </div>
            <div className="preview-item">
              <AlertCircle size={18} className="text-warning" /> Manufacturer declaration review
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT PANEL - Authentication Panel */}
      <div className="login-right">
        <div className="login-panel">
          
          {/* Mobile Header Visibility */}
          <div className="login-header-mobile">
            <ShieldCheck size={48} color="var(--primary)" style={{ margin: '0 auto' }} />
            <h2>LEGALMETRIX AI</h2>
            <p>Enforcement Officer Portal</p>
          </div>

          <div className="login-intro">
            <h3>Welcome back</h3>
            <p>Sign in to continue to your inspection workspace.</p>
          </div>

          {errorMessage && (
            <div className="auth-error">
              <AlertCircle size={18} style={{ flexShrink: 0 }} />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="auth-input-group">
              <label className="auth-label">Enforcement Officer Email</label>
              <div className="auth-input-wrapper">
                <Mail size={18} className="auth-icon" />
                <input
                  type="email"
                  className="auth-input"
                  placeholder="officer@legalmetrix.local"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading}
                  required
                  autoFocus
                />
              </div>
            </div>

            <div className="auth-input-group">
              <label className="auth-label">Security Password</label>
              <div className="auth-input-wrapper">
                <KeyRound size={18} className="auth-icon" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="auth-input"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  required
                  style={{ paddingRight: '48px' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px',
                    transition: 'color 0.2s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.color = 'var(--primary)'}
                  onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <label className="remember-me">
              <input type="checkbox" defaultChecked />
              <span>Remember me for 30 days</span>
            </label>

            <button
              type="submit"
              className="auth-btn"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="spin-animation" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In to Enforcement Portal</span>
                  <ArrowRight size={18} className="auth-btn-icon" />
                </>
              )}
            </button>
          </form>

          <div className="security-card">
            <Lock size={18} className="security-icon" />
            <div className="security-content">
              <h4>Authorized Access</h4>
              <p>This portal is intended for authorized Legal Metrology enforcement personnel. Inspection activities are structured for compliance intelligence.</p>
            </div>
          </div>

        </div>

        <div className="login-footer">
          LegalMetrix AI • Legal Metrology Inspection & Compliance Platform
        </div>
      </div>
    </div>
  );
};

export default Login;
