<template>
  <main class="knowledge">
    <aside class="side">
      <div class="side-head">
        <h1>知识库</h1>
        <p>上传文本、PDF、Word、幻灯片、表格、网页、JSON 或票据图片后，文件会读取并拆成片段，状态为待复核。</p>
      </div>
      <form class="upload" @submit.prevent="onUpload">
        <label class="field">
          <span>入库分类</span>
          <el-select v-model="uploadCategory">
            <el-option label="工业设计" value="design" />
            <el-option label="法律法规" value="regulation" />
            <el-option label="其他" value="other" />
          </el-select>
        </label>
        <div class="pick">
          <input id="doc-file" class="file" type="file" accept=".txt,.md,.pdf,.docx,.pptx,.xlsx,.xls,.csv,.tsv,.html,.htm,.json,.png,.jpg,.jpeg,.webp,.tif,.tiff" @change="onPick" />
          <button class="button secondary" type="button" @click="pickFile">选择文件</button>
          <p class="file-name">{{ selected ? selected.name : "尚未选择" }}</p>
        </div>
        <button class="button" type="submit" :disabled="uploading || !selected">
          {{ uploading ? "正在拆分" : "上传文档" }}
        </button>
      </form>
      <p v-if="uploadError" class="error">{{ uploadError }}</p>
    </aside>

    <section class="board">
      <form class="filters" @submit.prevent="search">
        <label class="field keyword">
          <span>标题</span>
          <el-input v-model="keyword" placeholder="搜索标题" clearable @clear="search" @input="onKeyword" />
        </label>
        <label class="field category">
          <span>分类</span>
          <el-select v-model="category" placeholder="全部分类" @change="search">
            <el-option label="全部分类" value="" />
            <el-option label="工业设计" value="design" />
            <el-option label="法律法规" value="regulation" />
            <el-option label="其他" value="other" />
          </el-select>
        </label>
        <label class="field status">
          <span>状态</span>
          <el-select v-model="status" placeholder="全部状态" @change="search">
            <el-option label="全部状态" value="" />
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </label>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="sheet">
        <el-table
          v-loading="loading"
          :data="documents"
          height="100%"
          empty-text="还没有文档。在这里上传，或把文件放进收件目录后执行导入。"
          :row-class-name="rowClass"
          @row-click="openDetail"
        >
          <el-table-column prop="title" label="标题" min-width="240" />
          <el-table-column label="分类" min-width="120">
            <template #default="{ row }">{{ categoryLabel[row.category] || row.category }}</template>
          </el-table-column>
          <el-table-column prop="chunk_count" label="片段" width="88" />
          <el-table-column label="可见" min-width="120">
            <template #default="{ row }">{{ accessRoleText(row.access_roles || []) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <span class="tag" :class="row.status">{{ statusLabel[row.status] || row.status }}</span>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" min-width="180">
            <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
          </el-table-column>
        </el-table>
      </div>
      <nav v-if="total > 0" class="pager" aria-label="文档分页">
        <button class="button secondary" type="button" :disabled="page <= 1 || loading" @click="load(page - 1)">上一页</button>
        <p>第 {{ page }} / {{ pageCount }} 页，共 {{ total }} 份</p>
        <button class="button secondary" type="button" :disabled="page >= pageCount || loading" @click="load(page + 1)">下一页</button>
      </nav>
    </section>

    <el-drawer v-model="detailOpen" :title="detail?.title || '文档'" size="min(1200px, calc(100vw - 32px))" @closed="closeDetail">
      <p v-if="detailLoading" class="drawer-note">正在读取</p>
      <p v-else-if="detailError" class="error">{{ detailError }}</p>
      <div v-else-if="detail" class="detail">
        <p class="drawer-note">
          {{ categoryLabel[detail.category] || detail.category }}
          · {{ statusLabel[detail.status] || detail.status }}
          · {{ detail.chunk_count }} 个片段
          <template v-if="sourceNote"> · {{ sourceNote }}</template>
        </p>
        <div class="detail-split">
          <div class="chunks-pane">
            <ol v-if="detail.chunks.length" class="chunks">
              <li v-for="chunk in detail.chunks" :key="chunk.ordinal">
                <button type="button" class="chunk-pick" :class="{ 'is-selected': chunk.ordinal === selectedOrdinal }" @click="selectChunk(chunk.ordinal)">
                  <p class="chunk-meta">
                    片段 {{ chunk.ordinal + 1 }}
                    <template v-if="chunkPageLabel(chunk)"> · {{ chunkPageLabel(chunk) }}</template>
                    <template v-if="chunkLocator(chunk)"> · {{ chunkLocator(chunk) }}</template>
                    <template v-if="chunk.heading_path?.length"> · {{ chunk.heading_path.join(" / ") }}</template>
                    <template v-if="kindLabel[chunk.block_kind || '']"> · {{ kindLabel[chunk.block_kind || ""] }}</template>
                  </p>
                  <p v-if="chunk.quality_flags?.length" class="chunk-flag">{{ chunk.quality_flags.join("；") }}</p>
                  <p>{{ chunk.content }}</p>
                </button>
              </li>
            </ol>
            <p v-else class="drawer-note">没有片段。</p>
          </div>
          <div class="source-pane">
            <OriginalPreview :document-id="detail.id" :filename="detail.original_filename" :page-number="selectedChunk?.page_number ?? null" />
          </div>
          <form class="review-form" @submit.prevent>
            <label class="field">
              <span>文号</span>
              <el-input v-model="form.doc_number" :disabled="!canReview" placeholder="可留空" />
            </label>
            <label class="field">
              <span>发布机构</span>
              <el-input v-model="form.publisher" :disabled="!canReview" placeholder="可留空" />
            </label>
            <label class="field">
              <span>生效日期</span>
              <el-date-picker v-model="form.effective_date" type="date" value-format="YYYY-MM-DD" placeholder="可留空" :disabled="!canReview" />
            </label>
            <label class="field">
              <span>效力状态</span>
              <el-select v-model="form.effective_status" placeholder="未填写" :disabled="!canReview" clearable>
                <el-option v-for="(label, value) in effectLabel" :key="value" :label="label" :value="value" />
              </el-select>
            </label>
            <div class="field">
              <span>可见角色</span>
              <el-checkbox-group v-model="form.access_roles" :disabled="!canReview">
                <el-checkbox value="user">普通员工</el-checkbox>
              </el-checkbox-group>
              <p class="drawer-note">不勾选时只有管理员能看到。管理员始终能看到全部文档。</p>
            </div>
            <label v-if="canReview || detail.reject_reason" class="field">
              <span>拒绝原因</span>
              <el-input v-model="form.reject_reason" type="textarea" :rows="2" resize="none" :disabled="!canReview" placeholder="拒绝时填写" />
            </label>
            <p v-if="reviewError" class="error">{{ reviewError }}</p>
            <div v-if="canReview" class="decisions">
              <button class="button" type="button" :disabled="saving || detail.status === DocumentStatus.published" @click="decide(DocumentStatus.published)">发布</button>
              <button class="button secondary" type="button" :disabled="saving || detail.status === DocumentStatus.published" @click="decide(DocumentStatus.rejected)">拒绝</button>
              <button class="button secondary" type="button" :disabled="saving || detail.status !== DocumentStatus.published" @click="decide(DocumentStatus.offline)">下线</button>
            </div>
            <p v-else class="drawer-note">只有知识管理员可以复核。</p>
          </form>
        </div>
      </div>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { errorMessage } from "@/api/http";
import { getDocument, listDocuments, reviewDocument, uploadDocument } from "@/api/documents";
import OriginalPreview from "@/components/OriginalPreview.vue";
import { useAuth } from "@/auth";
import { notifySuccess } from "@/feedback";
import { accessRoleText, categoryLabel, effectLabel, formatTime, reviewSuccess, statusLabel, statusOptions } from "@/labels";
import { DocumentStatus } from "@/statuses";
import type { DocumentChunk, DocumentDetail, DocumentItem, DocumentReviewPayload } from "@/types";

const pageSize = 20;
const documents = ref<DocumentItem[]>([]);
const category = ref("");
const status = ref("");
const keyword = ref("");
const page = ref(1);
const total = ref(0);
const loading = ref(false);
const error = ref("");
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));
const uploadCategory = ref("design");
const selected = ref<File | null>(null);
const uploading = ref(false);
const uploadError = ref("");
const detailOpen = ref(false);
const detailLoading = ref(false);
const detail = ref<DocumentDetail | null>(null);
const selectedOrdinal = ref<number | null>(null);
const detailError = ref("");
const reviewError = ref("");
const saving = ref(false);
const form = reactive({
  doc_number: "",
  publisher: "",
  effective_date: null as string | null,
  effective_status: "" as "" | "current" | "abolished" | "draft",
  reject_reason: "",
  access_roles: [] as string[],
});
const { user } = useAuth();
const canReview = computed(() => user.value?.role === "admin");
let keywordTimer = 0;

function pickFile() {
  document.getElementById("doc-file")?.click();
}

function onPick(event: Event) {
  const input = event.target as HTMLInputElement;
  selected.value = input.files?.[0] ?? null;
  uploadError.value = "";
}

async function onUpload() {
  if (!selected.value) return;
  uploading.value = true;
  uploadError.value = "";
  try {
    await uploadDocument(selected.value, uploadCategory.value);
    notifySuccess("文档已上传");
    selected.value = null;
    const input = document.getElementById("doc-file") as HTMLInputElement | null;
    if (input) input.value = "";
    await load(1);
  } catch (err) {
    uploadError.value = errorMessage(err, "文档上传失败");
  } finally {
    uploading.value = false;
  }
}

function search() {
  window.clearTimeout(keywordTimer);
  load(1);
}

function onKeyword() {
  window.clearTimeout(keywordTimer);
  keywordTimer = window.setTimeout(() => search(), 300);
}

async function load(nextPage = page.value) {
  loading.value = true;
  error.value = "";
  try {
    const result = await listDocuments({
      category: category.value || undefined,
      status: status.value || undefined,
      q: keyword.value.trim() || undefined,
      page: nextPage,
      page_size: pageSize,
    });
    documents.value = result.items;
    total.value = result.total;
    page.value = result.page;
  } catch (err) {
    error.value = errorMessage(err, "文档列表读取失败");
  } finally {
    loading.value = false;
  }
}

const kindLabel: Record<string, string> = {
  table: "表格",
  formula: "公式",
  code: "代码",
  footnote: "脚注",
  caption: "图片说明",
  list: "列表",
  record: "记录",
};

const methodLabel: Record<string, string> = {
  pdf_layout: "版面解析",
  ocr: "文字识别",
  docx: "Word",
  markdown: "Markdown",
  plain: "纯文本",
  pptx: "幻灯片",
  spreadsheet: "表格",
  html: "网页",
  json: "JSON",
  receipt: "票据识别",
};

const languageLabel: Record<string, string> = {
  zh: "中文",
  en: "英文",
  mixed: "多语",
};

const sourceNote = computed(() => {
  const page = detail.value?.pages[0];
  const method = page?.extraction_method ? methodLabel[page.extraction_method] || page.extraction_method : "";
  const language = page?.language ? languageLabel[page.language] || page.language : "";
  return [method, language].filter(Boolean).join(" · ");
});

const selectedChunk = computed(() => detail.value?.chunks.find((chunk) => chunk.ordinal === selectedOrdinal.value) ?? null);

function chunkPageLabel(chunk: DocumentChunk) {
  if (chunk.page_number == null) return "";
  const name = detail.value?.original_filename.toLowerCase() ?? "";
  const unit = name.endsWith(".pptx") ? "张" : "页";
  if (chunk.page_end != null && chunk.page_end !== chunk.page_number) return `第 ${chunk.page_number}–${chunk.page_end} ${unit}`;
  return `第 ${chunk.page_number} ${unit}`;
}

function chunkLocator(chunk: DocumentChunk) {
  const region = chunk.regions?.find((item) => item.sheet && item.row_start);
  if (!region?.sheet) return "";
  if (region.row_start && region.row_end && region.row_start !== region.row_end) {
    return `${region.sheet} · 第 ${region.row_start}–${region.row_end} 行`;
  }
  if (region.row_start) return `${region.sheet} · 第 ${region.row_start} 行`;
  return region.sheet;
}

function selectChunk(ordinal: number) {
  selectedOrdinal.value = ordinal;
}

function closeDetail() {
  detail.value = null;
  selectedOrdinal.value = null;
}

function rowClass({ row }: { row: DocumentItem }) {
  return detail.value?.id === row.id ? "is-open" : "";
}

function fillForm(item: DocumentDetail) {
  form.doc_number = item.doc_number || "";
  form.publisher = item.publisher || "";
  form.effective_date = item.effective_date;
  form.effective_status = (item.effective_status as typeof form.effective_status) || "";
  form.reject_reason = item.reject_reason || "";
  form.access_roles = [...(item.access_roles || [])];
}

async function openDetail(row: DocumentItem) {
  detailOpen.value = true;
  detailLoading.value = true;
  detailError.value = "";
  reviewError.value = "";
  try {
    const result = await getDocument(row.id);
    detail.value = result;
    selectedOrdinal.value = result.chunks[0]?.ordinal ?? null;
    fillForm(result);
  } catch (err) {
    detail.value = null;
    detailError.value = errorMessage(err, "文档读取失败");
  } finally {
    detailLoading.value = false;
  }
}

async function decide(decision: DocumentReviewPayload["decision"]) {
  if (!detail.value) return;
  const published = detail.value.status === DocumentStatus.published;
  if ((published && decision !== DocumentStatus.offline) || (!published && decision === DocumentStatus.offline)) return;
  reviewError.value = "";
  if (decision === DocumentStatus.rejected && !form.reject_reason.trim()) {
    reviewError.value = "拒绝时要填写原因";
    return;
  }
  saving.value = true;
  try {
    const result = await reviewDocument(detail.value.id, {
      doc_number: form.doc_number.trim(),
      publisher: form.publisher.trim(),
      effective_date: form.effective_date,
      effective_status: form.effective_status || null,
      decision,
      reject_reason: form.reject_reason.trim(),
      access_roles: form.access_roles,
    });
    detail.value = result;
    fillForm(result);
    notifySuccess(reviewSuccess[decision]);
    await load(page.value);
  } catch (err) {
    reviewError.value = errorMessage(err, "复核失败");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
onUnmounted(() => window.clearTimeout(keywordTimer));
</script>

<style scoped>
.knowledge {
  width: min(1280px, calc(100% - 2 * var(--gut)));
  margin: var(--nav) auto 0;
  height: calc(100svh - var(--nav));
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  min-height: 0;
}

.side,
.board {
  min-height: 0;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 32px 24px 24px 0;
  border-right: 1px solid var(--line);
}

.side-head h1 {
  margin: 0;
  font-size: 32px;
  line-height: 1.15;
}

.side-head p {
  margin: 8px 0 0;
  font-size: 16px;
  line-height: 1.6;
}

.upload,
.pick {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pick {
  gap: 8px;
}

.file {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  border: 0;
}

.file-name {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.board {
  display: flex;
  flex-direction: column;
  padding: 32px 0 16px 24px;
}

.filters {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 12px;
}

.filters .keyword {
  flex: 1;
  min-width: 0;
}

.filters .category,
.filters .status {
  width: 160px;
  flex: none;
}

.sheet {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.sheet :deep(.el-table__row) {
  cursor: pointer;
}

.sheet :deep(.el-table__body tr.is-open td) {
  background: var(--wash);
}

.sheet :deep(.el-table) {
  flex: 1;
  --el-table-header-bg-color: var(--bg);
  --el-table-bg-color: var(--bg);
  --el-table-tr-bg-color: var(--bg);
  --el-table-row-hover-bg-color: color-mix(in oklab, var(--ink) 5%, var(--bg));
  --el-table-border-color: var(--line);
  background: var(--bg);
}

.pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
}

.pager p {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}

.knowledge :deep(.el-drawer__header) {
  margin-bottom: 8px;
}

.knowledge :deep(.el-drawer__body) {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-split {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr) 300px;
}

.chunks-pane {
  min-height: 0;
  overflow: auto;
  padding-right: 16px;
}

.source-pane {
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--line);
}

.drawer-note {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}

.review-form {
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-left: 24px;
  border-left: 1px solid var(--line);
}

.review-form :deep(.el-date-editor) {
  width: 100%;
}

.decisions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: auto;
}

.chunks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chunks li {
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.chunks li:first-child {
  padding-top: 0;
  border-top: 0;
}

.chunks p {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.6;
}

.chunk-pick {
  display: block;
  width: 100%;
  margin: 0;
  padding: 8px;
  border: 0;
  border-radius: var(--r-md);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.chunk-pick.is-selected {
  background: var(--wash);
}

.chunk-meta {
  margin-bottom: 4px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.chunk-flag {
  margin-bottom: 4px;
  color: var(--danger);
  font-size: 13px;
}

@media (max-width: 800px) {
  .knowledge {
    grid-template-columns: 1fr;
    height: auto;
    min-height: calc(100svh - var(--nav));
  }

  .side {
    border-right: 0;
    border-bottom: 1px solid var(--line);
    padding: 24px 0;
  }

  .board {
    padding: 24px 0 16px;
  }

  .filters {
    flex-direction: column;
    align-items: stretch;
  }

  .filters .category,
  .filters .status {
    width: 100%;
  }

  .sheet {
    height: 60svh;
  }

  .upload .button,
  .pick .button,
  .pager .button {
    width: 100%;
  }

  .pager {
    flex-direction: column;
    align-items: stretch;
  }

  .detail-split {
    grid-template-columns: 1fr;
    overflow: auto;
  }

  .chunks-pane {
    max-height: 36svh;
  }

  .source-pane {
    height: 36svh;
  }

  .source-pane,
  .review-form {
    border-left: 0;
    padding-left: 0;
    border-top: 1px solid var(--line);
    padding-top: 16px;
  }
}
</style>
