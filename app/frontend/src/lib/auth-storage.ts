export const authStorage = {
  getToken: (): string | null => {
    try {
      return localStorage.getItem('token');
    } catch {
      return null;
    }
  },
  setToken: (token: string) => {
    try {
      localStorage.setItem('token', token);
    } catch { /* localStorage unavailable */ }
  },
  removeToken: () => {
    try {
      localStorage.removeItem('token');
    } catch { /* localStorage unavailable */ }
  },
  getActiveTenant: (): string | null => {
    try {
      return localStorage.getItem('activeTenant');
    } catch {
      return null;
    }
  },
  setActiveTenant: (tenantJson: string) => {
    try {
      localStorage.setItem('activeTenant', tenantJson);
    } catch { /* localStorage unavailable */ }
  },
  removeActiveTenant: () => {
    try {
      localStorage.removeItem('activeTenant');
    } catch { /* localStorage unavailable */ }
  }
};
