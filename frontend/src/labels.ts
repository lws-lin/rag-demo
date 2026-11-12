import { DocumentStatus, visibleDocumentStatuses, type DocumentStatus as StatusValue, type ReviewDecision } from "@/statuses";

export const categoryLabel: Record<string, string> = {
  design: "工业设计",
  regulation: "法律法规",
  other: "其他",
};

export const statusLabel: Record<StatusValue, string> = {
  [DocumentStatus.pending]: "待处理",
  [DocumentStatus.parsing]: "解析中",
  [DocumentStatus.review]: "待复核",
  [DocumentStatus.published]: "已发布",
  [DocumentStatus.rejected]: "已拒绝",
  [DocumentStatus.offline]: "已下线",
};

export const statusOptions = visibleDocumentStatuses.map((value) => ({
  value,
  label: statusLabel[value],
}));

export const reviewSuccess: Record<ReviewDecision, string> = {
  [DocumentStatus.published]: "文档已发布",
  [DocumentStatus.rejected]: "文档已拒绝",
  [DocumentStatus.offline]: "文档已下线",
};

export const effectLabel: Record<string, string> = {
  current: "现行",
  abolished: "废止",
  draft: "草案",
};

export const roleLabel: Record<string, string> = {
  admin: "管理员",
  user: "普通员工",
};

export function accessRoleText(roles: string[]) {
  if (!roles.length) return "仅管理员";
  return roles.map((role) => roleLabel[role] || role).join("、");
}

export const modeLabel: Record<string, string> = {
  qa: "查文档",
  proposal: "出方案",
};

export function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}
