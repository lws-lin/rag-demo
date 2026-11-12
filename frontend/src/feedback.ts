import { ElMessage } from "element-plus";

export function notifySuccess(message: string) {
  ElMessage.success({ message, offset: 80 });
}
