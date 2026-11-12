import axios from "axios";

export const http = axios.create({
  baseURL: "/api",
  timeout: 20000,
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url ?? "";
    if (error.response?.status === 401 && !url.includes("/auth/login")) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  },
);

const fieldName: Record<string, string> = {
  username: "用户名",
  password: "密码",
  display_name: "姓名",
  role: "角色",
};

function validationText(detail: unknown) {
  if (!Array.isArray(detail)) return "";
  const lines: string[] = [];
  for (const item of detail) {
    if (!item || typeof item !== "object") continue;
    const record = item as { loc?: unknown[]; type?: string; msg?: string; ctx?: { min_length?: number } };
    const key = Array.isArray(record.loc) ? String(record.loc.at(-1) ?? "") : "";
    const name = fieldName[key] || "提交内容";
    if (record.type === "string_too_short") {
      const min = record.ctx?.min_length;
      lines.push(min ? `${name}至少 ${min} 个字符` : `${name}太短`);
    } else if (record.type === "missing") {
      lines.push(`请填写${name}`);
    } else if (record.msg) {
      lines.push(`${name}不符合要求`);
    }
  }
  return lines.join("；");
}

export function errorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    const text = validationText(detail);
    if (text) return text;
  }
  return fallback;
}
