<template>
  <main class="knowledge">
    <aside class="side">
      <div class="side-head">
        <h1>知识库</h1>
        <p>上传或从收件目录导入后，文件会读取并拆成片段，状态为待复核。</p>
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
          <input id="doc-file" class="file" type="file" accept=".txt,.md,.pdf,.docx,text/plain,application/pdf" @change="onPick" />
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
            <el-option v-for="(label, value) in statusLabel" :key="value" :label="label" :value="value" />
          </el-select>
        </label>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="sheet">
        <el-table v-loading="loading" :data="documents" height="100%" empty-text="还没有文档。在这里上传，或把文件放进收件目录后执行导入。">
          <el-table-column prop="title" label="标题" min-width="240" />
          <el-table-column label="分类" min-width="120">
            <template #default="{ row }">{{ categoryLabel[row.category] || row.category }}</template>
          </el-table-column>
          <el-table-column prop="chunk_count" label="片段" width="88" />
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
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { errorMessage } from "@/api/http";
import { listDocuments, uploadDocument } from "@/api/documents";
import { categoryLabel, formatTime, statusLabel } from "@/labels";
import type { DocumentItem } from "@/types";

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
}
</style>
