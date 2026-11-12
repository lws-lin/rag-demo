export const DocumentStatus = {
  pending: "pending",
  parsing: "parsing",
  review: "review",
  published: "published",
  rejected: "rejected",
  offline: "offline",
} as const;

export type DocumentStatus = (typeof DocumentStatus)[keyof typeof DocumentStatus];

export type ReviewDecision =
  | typeof DocumentStatus.published
  | typeof DocumentStatus.rejected
  | typeof DocumentStatus.offline;

export const documentStatuses = Object.values(DocumentStatus);

/** 上传完成后实际会出现的状态。待处理和解析中只是预留，页面上不展示。 */
export const visibleDocumentStatuses = [
  DocumentStatus.review,
  DocumentStatus.published,
  DocumentStatus.rejected,
  DocumentStatus.offline,
] as const;
