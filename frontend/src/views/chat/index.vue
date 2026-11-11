<template>
  <main class="chat">
    <aside class="side">
      <div class="side-head">
        <h1>对话</h1>
        <!-- <p>查文档只依据已发布原文。出方案会在后续接入 PPT 和图像。</p> -->
      </div>
      <form class="create" @submit.prevent="create">
        <label class="field">
          <div class="pair">
            <el-input v-model="draftTitle" placeholder="请输入会话标题，可留空" />
            <button class="button" type="submit" :disabled="creating">
              {{ creating ? "正在创建" : "新对话" }}
            </button>
          </div>
        </label>
      </form>
      <p v-if="listError" class="error">{{ listError }}</p>
      <ul class="sessions">
        <li v-for="item in conversations" :key="item.id" :class="{ current: item.id === activeId }">
          <router-link :to="`/chat/${item.id}`">
            <strong>{{ item.title }}</strong>
            <span class="meta">{{ formatTime(item.updated_at) }}</span>
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
        <p>接入检索之后，回答会附带文件名、页码或条号，并能打开原文件。</p>
      </div>
      <template v-else>
        <div class="messages">
          <p v-if="threadError" class="error">{{ threadError }}</p>
          <p v-else-if="messages.length === 0" class="empty">还没有消息。</p>
          <article v-for="item in messages" :key="item.id" class="bubble" :class="item.role">
            <span class="who">{{ item.role === "user" ? "我" : "助手" }}</span>
            <p>{{ item.content }}</p>
          </article>
        </div>
        <form class="composer" @submit.prevent="onSend">
          <label class="field">
            <div class="pair">
              <el-input v-model="draft" type="textarea" :rows="2" resize="none" placeholder="输入要说的内容" />
              <button class="button" type="submit" :disabled="sending || !draft.trim()">
                {{ sending ? "发送中" : "发送消息" }}
              </button>
            </div>
          </label>
        </form>
      </template>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessageBox } from "element-plus";
import { errorMessage } from "@/api/http";
import { createConversation, deleteConversation, listConversations, listMessages, sendMessage } from "@/api/conversations";
import { formatTime } from "@/labels";
import type { ChatMessage, Conversation } from "@/types";

const route = useRoute();
const router = useRouter();
const conversations = ref<Conversation[]>([]);
const messages = ref<ChatMessage[]>([]);
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
    if (activeId.value === item.id) await router.push("/chat");
    await loadList();
  } catch (err) {
    listError.value = errorMessage(err, "会话删除失败");
  } finally {
    deletingId.value = "";
  }
}

async function onSend() {
  const content = draft.value.trim();
  if (!content || !activeId.value) return;
  sending.value = true;
  threadError.value = "";
  try {
    const turn = await sendMessage(activeId.value, content);
    messages.value = [...messages.value, turn.user_message, turn.assistant_message];
    draft.value = "";
    await loadList();
  } catch (err) {
    threadError.value = errorMessage(err, "消息发送失败");
  } finally {
    sending.value = false;
  }
}

watch(activeId, (id) => {
  if (id) loadMessages(id);
  else messages.value = [];
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

.pair {
  display: flex;
  align-items: center;
  gap: 0;
}

.pair :deep(.el-input),
.pair :deep(.el-textarea) {
  flex: 1;
  min-width: 0;
  width: auto;
}

.pair :deep(.el-input__wrapper) {
  border-radius: var(--r-sm) 0 0 var(--r-sm);
}

.pair .button {
  border-radius: 0 4px 4px 0;
}

.pair .button:hover:not(:disabled),
.pair .button:active:not(:disabled) {
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
  gap: 8px;
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

.bubble.user {
  align-self: flex-end;
  align-items: flex-end;
}

.bubble.user p {
  padding: 12px 16px;
  border-radius: var(--r-md);
  background: var(--wash);
}

.composer {
  padding: 16px 0;
  border-top: 1px solid var(--line);
}

.composer .pair {
  align-items: stretch;
}

.composer .pair :deep(.el-textarea__inner) {
  height: calc(2 * 1.5em + 16px);
  min-height: calc(2 * 1.5em + 16px);
  padding: 8px 12px;
  border-radius: var(--r-sm) 0 0 var(--r-sm);
  line-height: 1.5;
}

.composer .pair .button {
  height: auto;
}

@media (hover: hover) and (pointer: fine) {
  .sessions li {
    transition: background-color 150ms var(--ease);
  }

  .sessions a:hover {
    background: color-mix(in oklab, var(--ink) 8%, transparent);
  }

  .sessions li:hover .remove,
  .sessions li:focus-within .remove,
  .sessions .remove:disabled {
    opacity: 1;
  }

  .sessions .remove:hover:not(:disabled) {
    color: var(--danger);
    background: color-mix(in oklab, var(--danger) 12%, transparent);
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
