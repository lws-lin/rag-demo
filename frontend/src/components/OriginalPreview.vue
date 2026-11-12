<template>
  <div class="original">
    <p v-if="loading" class="note">正在读取原文</p>
    <p v-else-if="error" class="note">{{ error }}</p>
    <template v-else>
      <p v-if="kind === 'pdf' && pageCount" class="page-label">第 {{ shownPage }} / {{ pageCount }} 页</p>
      <div v-if="kind === 'pdf'" ref="scroller" class="scroller" @scroll="onScroll"></div>
      <div v-else-if="kind === 'docx'" ref="docxRoot" class="scroller"></div>
      <div v-else-if="kind === 'markdown' || kind === 'html'" class="scroller">
        <article class="paper prose" v-html="html"></article>
      </div>
      <div v-else-if="kind === 'image'" class="scroller">
        <img class="shot" :src="imageUrl" alt="" />
      </div>
      <div v-else class="scroller">
        <article class="paper plain">{{ text }}</article>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { renderAsync } from "docx-preview";
import DOMPurify from "dompurify";
import { marked } from "marked";
import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { fetchDocumentFile } from "@/api/documents";
import { errorMessage } from "@/api/http";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

const props = defineProps<{
  documentId: string;
  filename: string;
  pageNumber: number | null;
}>();

const loading = ref(false);
const error = ref("");
const kind = ref<"pdf" | "docx" | "markdown" | "html" | "image" | "text">("text");
const text = ref("");
const html = ref("");
const imageUrl = ref("");
const pageCount = ref(0);
const shownPage = ref(1);
const scroller = ref<HTMLElement | null>(null);
const docxRoot = ref<HTMLElement | null>(null);

let generation = 0;
let pdfDoc: pdfjs.PDFDocumentProxy | null = null;
let pdfScale = 1;
let pdfOutputScale = 1;
const painting = new Set<number>();

function suffixOf(name: string) {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index + 1).toLowerCase() : "";
}

function cleanupPdf() {
  painting.clear();
  pdfDoc?.destroy();
  pdfDoc = null;
  scroller.value?.replaceChildren();
  if (imageUrl.value) {
    URL.revokeObjectURL(imageUrl.value);
    imageUrl.value = "";
  }
}

async function load() {
  const token = ++generation;
  cleanupPdf();
  loading.value = true;
  error.value = "";
  text.value = "";
  html.value = "";
  pageCount.value = 0;
  try {
    const blob = await fetchDocumentFile(props.documentId);
    if (token !== generation) return;
    const suffix = suffixOf(props.filename);
    if (suffix === "pdf") {
      kind.value = "pdf";
      loading.value = false;
      await nextTick();
      await renderPdf(await blob.arrayBuffer(), token);
      return;
    }
    if (suffix === "docx") {
      kind.value = "docx";
      loading.value = false;
      await nextTick();
      if (token !== generation || !docxRoot.value) return;
      docxRoot.value.replaceChildren();
      await renderAsync(blob, docxRoot.value, docxRoot.value, { breakPages: true, inWrapper: true, ignoreWidth: true });
      return;
    }
    const images = ["png", "jpg", "jpeg", "webp", "tif", "tiff"];
    if (images.includes(suffix)) {
      kind.value = "image";
      imageUrl.value = URL.createObjectURL(blob);
      return;
    }
    if (suffix === "pptx" || suffix === "xlsx" || suffix === "xls") {
      text.value = "这份文件已保存。左侧是解析出的片段，这里不还原版式。";
      kind.value = "text";
      return;
    }
    const source = await blob.text();
    if (token !== generation) return;
    if (suffix === "md") {
      const parsed = marked.parse(source, { async: false });
      html.value = DOMPurify.sanitize(typeof parsed === "string" ? parsed : "");
      kind.value = "markdown";
      return;
    }
    if (suffix === "html" || suffix === "htm") {
      html.value = DOMPurify.sanitize(source);
      kind.value = "html";
      return;
    }
    if (suffix === "json") {
      try {
        text.value = JSON.stringify(JSON.parse(source), null, 2);
      } catch {
        text.value = source;
      }
      kind.value = "text";
      return;
    }
    text.value = source;
    kind.value = "text";
  } catch (err) {
    if (token !== generation) return;
    error.value = errorMessage(err, "原文读取失败");
  } finally {
    if (token === generation) loading.value = false;
  }
}

async function renderPdf(data: ArrayBuffer, token: number) {
  const doc = await pdfjs.getDocument({ data }).promise;
  if (token !== generation) {
    doc.destroy();
    return;
  }
  pdfDoc = doc;
  pageCount.value = doc.numPages;
  await nextTick();
  const root = scroller.value;
  if (!root) return;
  const first = await doc.getPage(1);
  pdfScale = Math.max(root.clientWidth - 24, 280) / first.getViewport({ scale: 1 }).width;
  pdfOutputScale = Math.min(window.devicePixelRatio || 1, 2);
  const sample = first.getViewport({ scale: pdfScale });
  for (let number = 1; number <= doc.numPages; number += 1) {
    const holder = document.createElement("article");
    holder.className = "pdf-page";
    holder.dataset.page = String(number);
    holder.style.width = `${sample.width}px`;
    holder.style.height = `${sample.height}px`;
    holder.appendChild(document.createElement("canvas"));
    root.appendChild(holder);
  }
  const target = props.pageNumber && props.pageNumber > 0 ? props.pageNumber : 1;
  scrollToPage(target);
  await showAround(target, token);
}

async function showAround(page: number, token: number) {
  const doc = pdfDoc;
  const root = scroller.value;
  if (!doc || !root || token !== generation) return;
  await ensurePage(page, doc, token);
  await ensurePage(page + 1, doc, token);
  for (const holder of root.querySelectorAll<HTMLElement>(".pdf-page")) {
    const number = Number(holder.dataset.page);
    if (Math.abs(number - page) > 1 && holder.dataset.ready === "1" && !painting.has(number)) {
      const canvas = holder.querySelector("canvas");
      if (canvas) {
        canvas.width = 0;
        canvas.height = 0;
      }
      holder.dataset.ready = "0";
    }
  }
}

async function ensurePage(number: number, doc: pdfjs.PDFDocumentProxy, token: number) {
  const holder = scroller.value?.querySelector<HTMLElement>(`[data-page="${number}"]`);
  if (!holder || holder.dataset.ready === "1" || painting.has(number)) return;
  painting.add(number);
  try {
    const page = await doc.getPage(number);
    if (token !== generation) return;
    const viewport = page.getViewport({ scale: pdfScale });
    holder.style.width = `${viewport.width}px`;
    holder.style.height = `${viewport.height}px`;
    const canvas = holder.querySelector("canvas");
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    canvas.width = Math.floor(viewport.width * pdfOutputScale);
    canvas.height = Math.floor(viewport.height * pdfOutputScale);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;
    const transform = pdfOutputScale === 1 ? undefined : [pdfOutputScale, 0, 0, pdfOutputScale, 0, 0];
    await page.render({ canvas, canvasContext: context, viewport, transform }).promise;
    if (token !== generation) return;
    holder.dataset.ready = "1";
    page.cleanup();
  } catch (err) {
    holder.dataset.ready = "0";
    holder.dataset.error = err instanceof Error ? err.message : "render failed";
  } finally {
    painting.delete(number);
  }
}

function scrollToPage(page: number | null) {
  const root = scroller.value;
  if (!root) return;
  const targetPage = page && page > 0 ? page : 1;
  shownPage.value = Math.min(targetPage, pageCount.value || targetPage);
  const target = root.querySelector<HTMLElement>(`[data-page="${shownPage.value}"]`);
  if (!target) return;
  root.scrollTo({ top: target.offsetTop });
}

function onScroll() {
  const root = scroller.value;
  if (!root) return;
  const line = root.scrollTop + 32;
  let current = 1;
  for (const page of root.querySelectorAll<HTMLElement>(".pdf-page")) {
    if (page.offsetTop <= line) current = Number(page.dataset.page);
  }
  if (current === shownPage.value) return;
  shownPage.value = current;
  void showAround(current, generation);
}

watch(() => props.documentId, () => void load(), { immediate: true });
watch(() => props.pageNumber, (page) => {
  if (kind.value !== "pdf" || !pdfDoc) return;
  scrollToPage(page);
  void showAround(shownPage.value, generation);
});

onBeforeUnmount(() => {
  generation += 1;
  cleanupPdf();
});
</script>

<style scoped>
.original {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: var(--bg);
}

.note,
.page-label {
  margin: 0;
  padding: 10px 12px 0;
  color: var(--muted);
  font-size: 13px;
}

.scroller {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px;
}

.scroller :deep(.pdf-page) {
  display: block;
  margin: 0 auto 12px;
  background: white;
  box-shadow: 0 1px 3px color-mix(in oklab, var(--ink) 16%, transparent);
}

.scroller :deep(.pdf-page canvas) {
  display: block;
  width: 100%;
  height: 100%;
}

.scroller :deep(.docx-wrapper) {
  background: transparent;
  padding: 0;
}

.scroller :deep(section.docx) {
  box-sizing: border-box;
  width: 100% !important;
  min-width: 0 !important;
  margin: 0 auto 12px;
  box-shadow: 0 1px 3px color-mix(in oklab, var(--ink) 16%, transparent);
}

.paper {
  box-sizing: border-box;
  max-width: 760px;
  margin: 0 auto;
  padding: 28px 32px;
  background: white;
  color: var(--ink);
  box-shadow: 0 1px 3px color-mix(in oklab, var(--ink) 16%, transparent);
  line-height: 1.7;
}

.plain {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: var(--font-mono);
  font-size: 13px;
}

.shot {
  display: block;
  max-width: 100%;
  margin: 0 auto;
  background: white;
}

.prose :deep(pre) {
  overflow: auto;
  padding: 12px;
  background: var(--bg);
}

.prose :deep(img) {
  max-width: 100%;
}
</style>
