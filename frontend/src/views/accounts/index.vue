<template>
  <main class="accounts">
    <aside class="side">
      <div class="side-head">
        <h1>账号</h1>
        <p>新建后即可登录。管理员能看到全部文档，普通员工只能看到审核时勾选了该角色的已发布文档。</p>
      </div>
      <form class="create" @submit.prevent="onCreate">
        <label class="field">
          <span>用户名</span>
          <el-input v-model="form.username" autocomplete="off" />
        </label>
        <label class="field">
          <span>姓名</span>
          <el-input v-model="form.display_name" />
        </label>
        <label class="field">
          <span>密码</span>
          <el-input v-model="form.password" type="password" show-password autocomplete="new-password" />
        </label>
        <label class="field">
          <span>角色</span>
          <el-select v-model="form.role">
            <el-option label="管理员" value="admin" />
            <el-option label="普通员工" value="user" />
          </el-select>
        </label>
        <button class="button" type="submit" :disabled="saving">{{ saving ? "正在创建" : "新建账号" }}</button>
        <p v-if="error" class="error">{{ error }}</p>
      </form>
    </aside>
    <section class="board">
      <div class="sheet">
        <el-table v-loading="loading" :data="users" height="100%" empty-text="还没有账号">
          <el-table-column prop="username" label="用户名" min-width="140" />
          <el-table-column prop="display_name" label="姓名" min-width="140" />
          <el-table-column label="角色" min-width="120">
            <template #default="{ row }">{{ roleLabel[row.role] || row.role }}</template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="180">
            <template #default="{ row }">{{ row.created_at ? formatTime(row.created_at) : "" }}</template>
          </el-table-column>
        </el-table>
      </div>
      <p v-if="listError" class="error">{{ listError }}</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { errorMessage } from "@/api/http";
import { createUser, listUsers } from "@/api/users";
import { notifySuccess } from "@/feedback";
import { formatTime, roleLabel } from "@/labels";
import type { User } from "@/types";

const users = ref<User[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const listError = ref("");
const form = reactive({
  username: "",
  display_name: "",
  password: "",
  role: "user" as "admin" | "user",
});

async function load() {
  loading.value = true;
  listError.value = "";
  try {
    users.value = await listUsers();
  } catch (err) {
    listError.value = errorMessage(err, "账号列表读取失败");
  } finally {
    loading.value = false;
  }
}

async function onCreate() {
  error.value = "";
  saving.value = true;
  try {
    await createUser({
      username: form.username.trim(),
      display_name: form.display_name.trim(),
      password: form.password,
      role: form.role,
    });
    form.username = "";
    form.display_name = "";
    form.password = "";
    form.role = "user";
    notifySuccess("账号已创建");
    await load();
  } catch (err) {
    error.value = errorMessage(err, "账号创建失败");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.accounts {
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

.create {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.board {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 32px 0 16px 24px;
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

@media (max-width: 800px) {
  .accounts {
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

  .sheet {
    height: 60svh;
  }

  .create .button {
    width: 100%;
  }
}
</style>
