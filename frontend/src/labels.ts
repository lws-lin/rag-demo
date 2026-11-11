export const categoryLabel: Record<string, string> = {
  design: "工业设计",
  regulation: "法律法规",
  other: "其他",
};

export const statusLabel: Record<string, string> = {
  pending: "待处理",
  parsing: "解析中",
  review: "待复核",
  published: "已发布",
  rejected: "已拒绝",
  offline: "已下线",
};

export const roleLabel: Record<string, string> = {
  admin: "知识管理员",
  user: "业务用户",
  auditor: "审计",
};

export const modeLabel: Record<string, string> = {
  qa: "查文档",
  proposal: "出方案",
};

export function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}
