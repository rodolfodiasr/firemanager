import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// One in-flight refresh at a time — concurrent 401s share the same promise
let _refreshPromise: Promise<string> | null = null;

function _getJwtTenantId(token: string): string | undefined {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.tenant_id as string | undefined;
  } catch {
    return undefined;
  }
}

async function _doRefresh(): Promise<string> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) throw new Error("no refresh token");

  const accessToken = localStorage.getItem("access_token");
  const tenantId = accessToken ? _getJwtTenantId(accessToken) : undefined;

  const resp = await axios.post<{ access_token: string; refresh_token?: string }>(
    "/api/auth/refresh",
    { refresh_token: refreshToken, ...(tenantId ? { tenant_id: tenantId } : {}) },
  );

  const { access_token, refresh_token: newRefresh } = resp.data;
  localStorage.setItem("access_token", access_token);
  if (newRefresh) localStorage.setItem("refresh_token", newRefresh);
  return access_token;
}

function _clearSession() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  if (!window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as typeof error.config & { _retry?: boolean };

    const isAuthEndpoint =
      original?.url?.includes("/auth/refresh") ||
      original?.url?.includes("/auth/login");

    if (error.response?.status === 401 && !original?._retry && !isAuthEndpoint) {
      original._retry = true;
      try {
        if (!_refreshPromise) {
          _refreshPromise = _doRefresh().finally(() => {
            _refreshPromise = null;
          });
        }
        const newToken = await _refreshPromise;
        original.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(original);
      } catch {
        _clearSession();
        return Promise.reject(error);
      }
    }

    if (error.response?.status === 401) {
      _clearSession();
    }

    return Promise.reject(error);
  },
);

export default apiClient;
