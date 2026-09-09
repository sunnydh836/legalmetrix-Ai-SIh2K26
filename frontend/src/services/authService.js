import apiClient from './api';

const TOKEN_KEY = 'legalmetrix_access_token';
const USER_KEY = 'legalmetrix_user_data';

export const authService = {
  /**
   * Authenticate user with credentials and store access token
   */
  async login(email, password) {
    const response = await apiClient.post('/auth/login', {
      email: email.trim().toLowerCase(),
      password,
    });
    const { access_token, user } = response.data;
    if (access_token) {
      this.setToken(access_token);
      this.setUser(user);
    }
    return response.data;
  },

  /**
   * Fetch current authenticated user profile
   */
  async getCurrentUser() {
    const response = await apiClient.get('/auth/me');
    if (response.data) {
      this.setUser(response.data);
    }
    return response.data;
  },

  /**
   * Log out user locally and trigger backend audit log
   */
  async logout() {
    try {
      await apiClient.post('/auth/logout');
    } catch {
      // Proceed with client logout even if backend fails
    } finally {
      this.clearSession();
    }
  },

  /**
   * Token storage utilities (Isolated for MVP development)
   */
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  setToken(token) {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    }
  },

  getUser() {
    try {
      const data = localStorage.getItem(USER_KEY);
      return data ? JSON.parse(data) : null;
    } catch {
      return null;
    }
  },

  setUser(user) {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
  },

  clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

export default authService;
