import { api } from "./api";

export const AuthAPI = {
  login: (email, password) => api.post("/auth/login", { email, password }),
  register: (name, email, password) => api.post("/auth/register", { name, email, password }),
};

export const MonitoringAPI = {
  current: () => api.get("/monitoring/current"),
  history: (limit = 60) => api.get(`/monitoring/history?limit=${limit}`),
  health: () => api.get("/monitoring/health"),
  start: () => api.post("/monitoring/start"),
  stop: () => api.post("/monitoring/stop"),
};

export const PredictionAPI = {
  predict: (override = {}) => api.post("/prediction/predict", override),
  history: (limit = 20) => api.get(`/prediction/history?limit=${limit}`),
};

export const DecisionAPI = {
  evaluate: () => api.post("/decision/evaluate"),
  history: (limit = 20) => api.get(`/decision/history?limit=${limit}`),
};

export const RecoveryAPI = {
  execute: (override = null) => api.post("/recovery/execute", override),
  history: (limit = 20) => api.get(`/recovery/history?limit=${limit}`),
  status: () => api.get("/recovery/status"),
};

export const SimulationAPI = {
  cpu: (value) => api.post("/simulation/cpu", { value }),
  memory: (value) => api.post("/simulation/memory", { value }),
  disk: (value, junk_files = 20, junk_file_size_mb = 5) =>
    api.post("/simulation/disk", { value, junk_files, junk_file_size_mb }),
  network: (latency_ms, throughput_multiplier = 0.3) =>
    api.post("/simulation/network", { latency_ms, throughput_multiplier }),
  errorRate: (value = 0.18) => api.post("/simulation/error-rate", { value }),
  resourceSaturation: (cpu = 94, memory = 91) => api.post("/simulation/resource-saturation", { cpu, memory }),
  serviceDegraded: () => api.post("/simulation/service-degraded"),
  serviceFailure: () => api.post("/simulation/service-failure"),
  reset: () => api.post("/simulation/reset"),
  status: () => api.get("/simulation/status"),
};

export const AlertsAPI = {
  list: (limit = 30) => api.get(`/alerts?limit=${limit}`),
  acknowledge: (id) => api.post(`/alerts/${id}/acknowledge`),
};

export const LogsAPI = {
  list: (serviceName = null, limit = 100) =>
    api.get(`/logs${serviceName ? `/${serviceName}` : ""}?limit=${limit}`),
};

export const DashboardAPI = {
  summary: () => api.get("/dashboard/summary"),
  metrics: (limit = 60) => api.get(`/dashboard/metrics?limit=${limit}`),
  failures: (limit = 20) => api.get(`/dashboard/failures?limit=${limit}`),
  recoveries: (limit = 20) => api.get(`/dashboard/recoveries?limit=${limit}`),
  alerts: (limit = 20) => api.get(`/dashboard/alerts?limit=${limit}`),
};
