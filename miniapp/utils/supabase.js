let CONFIG;

try {
  CONFIG = require("../config.js");
} catch (error) {
  CONFIG = require("../config.example.js");
}

const SESSION_KEY = "projectDeskMiniappSession";

function assertConfig() {
  if (!CONFIG.supabaseUrl || !CONFIG.supabaseAnonKey || CONFIG.supabaseUrl.includes("你的项目")) {
    throw new Error("请先复制 miniapp/config.example.js 为 miniapp/config.js，并填入 Supabase 公开配置。");
  }
}

function getSession() {
  return wx.getStorageSync(SESSION_KEY) || null;
}

function saveSession(session) {
  if (!session) return;
  const normalized = Object.assign({}, session);
  if (!normalized.expires_at && normalized.expires_in) {
    normalized.expires_at = Math.floor(Date.now() / 1000) + Number(normalized.expires_in);
  }
  wx.setStorageSync(SESSION_KEY, normalized);
}

function clearSession() {
  wx.removeStorageSync(SESSION_KEY);
}

function shouldRefresh(session) {
  if (!session?.refresh_token || !session.expires_at) return false;
  return Number(session.expires_at) - Math.floor(Date.now() / 1000) < 60;
}

async function refreshSession() {
  const session = getSession();
  if (!session?.refresh_token) throw new Error("登录状态已失效，请重新登录。");
  const data = await request({
    path: "/auth/v1/token?grant_type=refresh_token",
    method: "POST",
    auth: false,
    data: { refresh_token: session.refresh_token }
  });
  saveSession(data);
  return data;
}

function sendRequest(options, session) {
  const headers = Object.assign({
    apikey: CONFIG.supabaseAnonKey,
    "Content-Type": "application/json"
  }, options.headers || {});

  if (options.auth !== false && session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`;
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${CONFIG.supabaseUrl}${options.path}`,
      method: options.method || "GET",
      data: options.data,
      header: headers,
      success(response) {
        const ok = response.statusCode >= 200 && response.statusCode < 300;
        if (ok) {
          resolve(response.data);
          return;
        }
        const message = response.data?.msg || response.data?.message || response.data?.error_description || `请求失败：${response.statusCode}`;
        const error = new Error(message);
        error.statusCode = response.statusCode;
        reject(error);
      },
      fail(error) {
        reject(new Error(error.errMsg || "网络请求失败"));
      }
    });
  });
}

async function request(options) {
  assertConfig();
  const needsAuth = options.auth !== false;
  let session = getSession();
  if (needsAuth && shouldRefresh(session)) {
    try {
      session = await refreshSession();
    } catch (error) {
      clearSession();
      throw error;
    }
  }

  try {
    return await sendRequest(options, session);
  } catch (error) {
    if (needsAuth && !options._retry && error.statusCode === 401 && getSession()?.refresh_token) {
      await refreshSession();
      return request(Object.assign({}, options, { _retry: true }));
    }
    throw error;
  }
}

function buildQuery(params) {
  return Object.keys(params)
    .filter((key) => params[key] !== undefined && params[key] !== "")
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join("&");
}

function restPath(table, params) {
  const query = params ? buildQuery(params) : "";
  return `/rest/v1/${table}${query ? `?${query}` : ""}`;
}

function eq(value) {
  return `eq.${value}`;
}

async function signInWithPassword(email, password) {
  const data = await request({
    path: "/auth/v1/token?grant_type=password",
    method: "POST",
    auth: false,
    data: { email, password }
  });
  saveSession(data);
  return data;
}

async function signOut() {
  try {
    await request({ path: "/auth/v1/logout", method: "POST" });
  } finally {
    clearSession();
  }
}

function select(table, params) {
  return request({ path: restPath(table, Object.assign({ select: "*" }, params || {})) });
}

function insert(table, row) {
  return request({
    path: `/rest/v1/${table}`,
    method: "POST",
    data: row,
    headers: { Prefer: "return=representation" }
  });
}

function update(table, id, row) {
  return request({
    path: restPath(table, { id: eq(id) }),
    method: "PATCH",
    data: row,
    headers: { Prefer: "return=representation" }
  });
}

function upsert(table, row, conflictColumns) {
  return request({
    path: restPath(table, { on_conflict: conflictColumns }),
    method: "POST",
    data: row,
    headers: { Prefer: "resolution=merge-duplicates,return=representation" }
  });
}

module.exports = {
  clearSession,
  eq,
  getSession,
  insert,
  restPath,
  request,
  saveSession,
  select,
  signInWithPassword,
  signOut,
  refreshSession,
  update,
  upsert
};
