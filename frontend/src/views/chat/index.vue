<template>
  <main class="chat">
    <aside class="side">
      <div class="side-head">
        <h1>对话</h1>
        <!-- <p>查文档只依据已发布原文。出方案会在后续接入 PPT 和图像。</p> -->
      </div>
      <form class="create" @submit.prevent="create">
        <div class="create-box">
          <el-input v-model="draftTitle" placeholder="请输入会话标题，可留空" />
          <button class="create-submit" type="submit" :disabled="creating">
            {{ creating ? "正在创建" : "新对话" }}
          </button>
        </div>
      </form>
      <p v-if="listError" class="error">{{ listError }}</p>
      <ul class="sessions">
        <li v-for="item in conversations" :key="item.id" :class="{ current: item.id === activeId }">
          <router-link :to="`/chat/${item.id}`">
            <strong>{{ item.title }}</strong>
            <span class="meta">
              <template v-if="item.mode">{{ modeLabel[item.mode] }} · </template>{{ formatTime(item.updated_at) }}
            </span>
          </router-link>
          <button class="remove" type="button" title="删除" :aria-label="`删除${item.title}`" :disabled="deletingId === item.id" @click="remove(item)">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13M10 11v6M14 11v6" />
            </svg>
          </button>
        </li>
      </ul>
    </aside>

    <section class="thread">
      <div v-if="!activeId" class="placeholder">
        <h2>选择或新建会话</h2>
        <p>回答由对话模型生成。查资料时依据已发布原文，并标出文件名和页码。</p>
      </div>
      <template v-else>
        <div ref="thread" class="messages">
          <p v-if="threadError" class="error">{{ threadError }}</p>
          <div v-if="messages.length === 0" class="blank">
            <h2>开始这段对话</h2>
            <p>在下方输入即可。查资料时依据已发布原文，并标出文件名和页码。</p>
          </div>
          <article v-for="(item, index) in messages" :key="item.id" class="bubble" :class="item.role">
            <span class="who">{{ item.role === "user" ? "我" : "助手" }}</span>
            <p :class="{ streaming: sending && index === messages.length - 1 && item.role === 'assistant' }">{{ item.content || (sending && index === messages.length - 1 ? "正在回答" : "") }}</p>
            <ul v-if="item.citations?.length" class="cites">
              <li v-for="(cite, index) in item.citations" :key="`${item.id}-${index}`">
                <button type="button" class="cite" @click="openSource(cite)">{{ citeLabel(cite) }}</button>
              </li>
            </ul>
          </article>
        </div>
        <form class="composer" @submit.prevent="onSend" @keydown="onComposerKeydown">
          <div class="composer-box">
            <el-input v-model="draft" type="textarea" :rows="2" resize="none" placeholder="输入要说的内容" />
            <div class="composer-bar">
              <span>Shift + Enter 发送</span>
              <button class="button" type="submit" :disabled="sending || !draft.trim()">
                {{ sending ? "发送中" : "发送" }}
              </button>
            </div>
          </div>
        </form>
      </template>
    </section>
    <el-drawer v-model="sourceOpen" :title="source?.title || '原文'" size="min(920px, calc(100vw - 32px))" @closed="source = null">
      <div v-if="source" class="source-view">
        <OriginalPreview :document-id="source.document_id" :filename="source.filename" :page-number="source.page_number" />
      </div>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessageBox } from "element-plus";
import { errorMessage } from "@/api/http";
import { createConversation, deleteConversation, listConversations, listMessages, sendMessage } from "@/api/conversations";
import OriginalPreview from "@/components/OriginalPreview.vue";
import { notifySuccess } from "@/feedback";
import { effectLabel, formatTime, modeLabel } from "@/labels";
import type { ChatMessage, Citation, Conversation } from "@/types";

const route = useRoute();
const router = useRouter();
const conversations = ref<Conversation[]>([]);
const messages = ref<ChatMessage[]>([]);
const thread = ref<HTMLElement | null>(null);
const source = ref<Citation | null>(null);
const sourceOpen = ref(false);
const draftTitle = ref("");
const draft = ref("");
const creating = ref(false);
const sending = ref(false);
const deletingId = ref("");
const listError = ref("");
const threadError = ref("");

const activeId = computed(() => (typeof route.params.id === "string" ? route.params.id : ""));

async function loadList() {
  listError.value = "";
  try {
    conversations.value = await listConversations();
  } catch (err) {
    listError.value = errorMessage(err, "会话列表读取失败");
  }
}

async function loadMessages(id: string) {
  threadError.value = "";
  try {
    messages.value = await listMessages(id);
  } catch (err) {
    messages.value = [];
    threadError.value = errorMessage(err, "消息读取失败");
  }
}

async function create() {
  creating.value = true;
  listError.value = "";
  try {
    const created = await createConversation({ title: draftTitle.value.trim() });
    draftTitle.value = "";
    notifySuccess("新对话已创建");
    await loadList();
    await router.push(`/chat/${created.id}`);
  } catch (err) {
    listError.value = errorMessage(err, "会话创建失败");
  } finally {
    creating.value = false;
  }
}

async function remove(item: Conversation) {
  try {
    await ElMessageBox.confirm(`删除「${item.title}」后，其中的消息也会一起去掉。`, "删除对话", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  deletingId.value = item.id;
  listError.value = "";
  try {
    await deleteConversation(item.id);
    notifySuccess("对话已删除");
    if (activeId.value === item.id) await router.push("/chat");
    await loadList();
  } catch (err) {
    listError.value = errorMessage(err, "会话删除失败");
  } finally {
    deletingId.value = "";
  }
}

function citeLabel(cite: Citation) {
  const parts = [cite.title];
  if (cite.page_number) {
    const unit = cite.filename.toLowerCase().endsWith(".pptx") ? "张" : "页";
    parts.push(cite.page_end && cite.page_end !== cite.page_number ? `第 ${cite.page_number}–${cite.page_end} ${unit}` : `第 ${cite.page_number} ${unit}`);
  }
  const heading = cite.heading_path?.[cite.heading_path.length - 1];
  if (heading) parts.push(heading);
  if (cite.effective_status && effectLabel[cite.effective_status]) parts.push(effectLabel[cite.effective_status]);
  return parts.join(" · ");
}

function openSource(cite: Citation) {
  source.value = cite;
  sourceOpen.value = true;
}

async function scrollThread() {
  await nextTick();
  const root = thread.value;
  if (root) root.scrollTop = root.scrollHeight;
}

function onComposerKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter" || !event.shiftKey || event.isComposing) return;
  event.preventDefault();
  void onSend();
}

async function onSend() {
  const content = draft.value.trim();
  if (!content || !activeId.value || sending.value) return;
  const conversationId = activeId.value;
  sending.value = true;
  threadError.value = "";
  draft.value = "";
  const pendingUser: ChatMessage = {
    id: "pending-user",
    role: "user",
    content,
    citations: [],
    created_at: new Date().toISOString(),
  };
  const pendingAssistant: ChatMessage = {
    id: "pending-assistant",
    role: "assistant",
    content: "",
    citations: [],
    created_at: new Date().toISOString(),
  };
  messages.value = [...messages.value, pendingUser, pendingAssistant];
  await scrollThread();
  try {
    const turn = await sendMessage(conversationId, content, (text) => {
      if (activeId.value !== conversationId) return;
      pendingAssistant.content += text;
      messages.value = [...messages.value.slice(0, -1), { ...pendingAssistant }];
      void scrollThread();
    });
    if (activeId.value !== conversationId) return;
    messages.value = [...messages.value.slice(0, -2), turn.user_message, turn.assistant_message];
    await loadList();
    await scrollThread();
  } catch (err) {
    if (activeId.value === conversationId) {
      messages.value = messages.value.filter((item) => item.id !== "pending-user" && item.id !== "pending-assistant");
      draft.value = content;
      threadError.value = err instanceof Error && err.message ? err.message : errorMessage(err, "消息发送失败");
    }
  } finally {
    sending.value = false;
  }
}

watch(activeId, async (id) => {
  sourceOpen.value = false;
  source.value = null;
  if (id) {
    await loadMessages(id);
    await scrollThread();
  } else messages.value = [];
}, { immediate: true });

onMounted(loadList);
</script>

<style scoped>
.chat {
  width: min(1280px, calc(100% - 2 * var(--gut)));
  margin: var(--nav) auto 0;
  height: calc(100vh - var(--nav));
  height: calc(100svh - var(--nav));
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  min-height: 0;
}

.side,
.thread {
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
  font-size: 32px;
}

.side-head p,
.placeholder p {
  margin: 8px 0 0;
  font-size: 16px;
  line-height: 1.6;
}

.create-box {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 40px;
  padding: 0 4px 0 12px;
  border-radius: 8px;
  background: var(--surface);
}

.create-box :deep(.el-input) {
  flex: 1;
  min-width: 0;
  width: auto;
}

.create-box :deep(.el-input__wrapper) {
  padding: 0;
  background: transparent;
  box-shadow: none;
}

.create-box :deep(.el-input__wrapper:hover),
.create-box :deep(.el-input__wrapper.is-focus) {
  box-shadow: none;
}

.create-submit {
  flex: none;
  border: 0;
  border-radius: 6px;
  padding: 6px 8px;
  background: transparent;
  color: var(--accent);
  font: inherit;
  font-size: 14px;
  font-weight: 500;
}

.create-submit:hover:not(:disabled),
.create-submit:active:not(:disabled) {
  background: transparent;
  color: color-mix(in oklab, var(--ink) 18%, var(--accent));
  transform: none;
}

.sessions {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: auto;
}

.sessions li {
  display: flex;
  align-items: center;
  border-radius: var(--r-sm);
}

.sessions li.current {
  background: color-mix(in oklab, var(--ink) 8%, transparent);
}

.sessions a {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 44px;
  justify-content: center;
  padding: 8px 12px;
  border-radius: var(--r-sm);
}

.sessions .remove {
  flex: none;
  width: 32px;
  height: 32px;
  margin-right: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--muted);
  opacity: 0;
}

.sessions .remove svg {
  width: 16px;
  height: 16px;
}

.sessions strong {
  font-weight: 500;
  font-size: 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sessions span,
.who {
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
}

.thread {
  display: flex;
  flex-direction: column;
  padding: 32px 0 0 24px;
}

.placeholder,
.messages {
  flex: 1;
  min-height: 0;
}

.placeholder h2 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: auto;
  padding-bottom: 16px;
}

.bubble {
  max-width: min(640px, 100%);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bubble p {
  margin: 0;
  font-size: 16px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.streaming::after {
  content: "▍";
  margin-left: 2px;
  color: var(--accent);
}

.cites {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.cite {
  max-width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--accent);
  font: inherit;
  font-size: 13px;
  line-height: 1.4;
  text-align: left;
  cursor: pointer;
}

.source-view {
  height: calc(100vh - 96px);
  height: calc(100svh - 96px);
}

.bubble.user {
  align-self: flex-end;
  align-items: flex-end;
}

.bubble.user p {
  padding: 12px 16px;
  border-radius: var(--r-md);
  background: var(--wash);
}

.blank {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 28em;
  margin: 0 auto;
}

.blank h2 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
}

.blank p {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 16px;
  line-height: 1.6;
}

.composer {
  padding: 12px 0 16px;
}

.composer-box {
  padding: 8px 8px 8px 16px;
  border-radius: 12px;
  background: var(--surface);
}

.composer-box :deep(.el-textarea__inner) {
  min-height: calc(2 * 1.5em + 16px);
  padding: 8px 4px 4px 0;
  border: 0;
  border-radius: 0;
  background: var(--surface);
  box-shadow: none;
  line-height: 1.5;
}

.composer-box :deep(.el-textarea__inner:hover),
.composer-box :deep(.el-textarea__inner:focus) {
  border: 0;
  box-shadow: none;
}

.composer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0 4px 0;
}

.composer-bar span {
  color: var(--muted);
  font-size: 13px;
}

@media (hover: hover) and (pointer: fine) {
  .sessions li {
    transition: background-color 150ms var(--ease);
  }

  .sessions li:hover,
  .sessions li:focus-within {
    background: color-mix(in oklab, var(--ink) 8%, transparent);
  }

  .sessions li:hover .remove,
  .sessions li:focus-within .remove,
  .sessions .remove:disabled {
    opacity: 1;
  }

  .sessions .remove:hover:not(:disabled) {
    color: var(--danger);
    background: transparent;
  }
}

@media (hover: none), (pointer: coarse) {
  .sessions .remove {
    opacity: 1;
  }
}

@media (max-width: 800px) {
  .chat {
    grid-template-columns: 1fr;
    height: auto;
    min-height: calc(100svh - var(--nav));
  }

  .side {
    border-right: 0;
    border-bottom: 1px solid var(--line);
    padding: 24px 0;
  }

  .sessions {
    max-height: 240px;
  }

  .thread {
    min-height: 70svh;
    padding: 24px 0 0;
  }

}

@media (prefers-reduced-motion: reduce) {
  .sessions li {
    transition: none;
  }
}
</style>
