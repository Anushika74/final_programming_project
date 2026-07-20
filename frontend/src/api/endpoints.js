import client from "./client";

// Centralised API surface so components never build URLs by hand.
export const AuthAPI = {
  loginJson: (username, password) =>
    client.post("/auth/login/json", { username, password }).then((r) => r.data),
  register: (payload) =>
    client.post("/auth/register", payload).then((r) => r.data),
  me: () => client.get("/auth/me").then((r) => r.data),
};

export const UsersAPI = {
  list: () => client.get("/users").then((r) => r.data),
  create: (payload) => client.post("/users", payload).then((r) => r.data),
  update: (id, payload) =>
    client.patch(`/users/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/users/${id}`),
};

export const DashboardAPI = {
  summary: () => client.get("/dashboard/summary").then((r) => r.data),
};

export const MetricsAPI = {
  current: () => client.get("/metrics/current").then((r) => r.data),
  history: (minutes = 60, limit = 500) =>
    client
      .get("/metrics/history", { params: { minutes, limit } })
      .then((r) => r.data),
  trends: (minutes = 60, buckets = 60) =>
    client
      .get("/metrics/trends", { params: { minutes, buckets } })
      .then((r) => r.data),
};

export const ProcessesAPI = {
  list: (params) => client.get("/processes", { params }).then((r) => r.data),
  top: (by = "memory", limit = 5) =>
    client.get("/processes/top", { params: { by, limit } }).then((r) => r.data),
  detail: (pid) => client.get(`/processes/${pid}`).then((r) => r.data),
};

export const RecommendationsAPI = {
  list: (params) =>
    client.get("/recommendations", { params }).then((r) => r.data),
  generate: () => client.post("/recommendations/generate").then((r) => r.data),
  acknowledge: (id) =>
    client.post(`/recommendations/${id}/acknowledge`).then((r) => r.data),
};

export const PredictionsAPI = {
  forecast: (metric = "cpu", horizon_minutes = 10) =>
    client
      .get("/predictions/forecast", { params: { metric, horizon_minutes } })
      .then((r) => r.data),
  disk: (horizon_days = 7) =>
    client
      .get("/predictions/disk", { params: { horizon_days } })
      .then((r) => r.data),
  history: (limit = 50) =>
    client
      .get("/predictions/history", { params: { limit } })
      .then((r) => r.data),
};

export const FilesAPI = {
  scan: (payload) => client.post("/files/scan", payload).then((r) => r.data),
};

export const LogsAPI = {
  analyze: (content, source = "manual") =>
    client.post("/logs/analyze", { content, source }).then((r) => r.data),
  recent: (limit = 100) =>
    client.get("/logs/recent", { params: { limit } }).then((r) => r.data),
};

export const OptimizationAPI = {
  actions: () => client.get("/optimization/actions").then((r) => r.data),
  execute: (action_key, confirm = false, dry_run = true) =>
    client
      .post("/optimization/execute", { action_key, confirm, dry_run })
      .then((r) => r.data),
};

export const AssistantAPI = {
  ask: (query) => client.post("/assistant/ask", { query }).then((r) => r.data),
  context: (predictions = true) =>
    client
      .get("/assistant/context", { params: { predictions } })
      .then((r) => r.data),
};

export const AlertsAPI = {
  list: (params) => client.get("/alerts", { params }).then((r) => r.data),
  resolve: (id) => client.post(`/alerts/${id}/resolve`).then((r) => r.data),
};

export const HardwareAPI = {
  current: () => client.get("/hardware/current").then((r) => r.data),
  history: (minutes = 60, limit = 500) =>
    client
      .get("/hardware/history", { params: { minutes, limit } })
      .then((r) => r.data),
  healthScore: () => client.get("/hardware/health-score").then((r) => r.data),
  throttling: () => client.get("/hardware/throttling").then((r) => r.data),
  predictions: (sensor = "cpu_package_temp", horizon_minutes = 10) =>
    client
      .get("/hardware/predictions", { params: { sensor, horizon_minutes } })
      .then((r) => r.data),
  recommendations: () =>
    client.get("/hardware/recommendations").then((r) => r.data),
  alerts: (params) =>
    client.get("/hardware/alerts", { params }).then((r) => r.data),
  overview: () => client.get("/hardware/overview").then((r) => r.data),
};
