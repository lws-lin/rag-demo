<template>
  <main class="login">
    <a class="skip-link" href="#login-form">跳到登录</a>
    <div class="login-wrap">
      <section class="login-copy">
        <!-- <p class="eyebrow">
          <span class="mark" aria-hidden="true"></span>
          机构内部
        </p> -->
        <h1>医疗机构知识库</h1>
        <!-- <p class="lead">工业设计资料与法律法规。查文档时回答回到原文件，出方案时单独生成 PPT 和图像。</p>
        <p class="rule">查文档只依据已发布原文。</p> -->
      </section>
      <form id="login-form" class="form" @submit.prevent="onSubmit">
        <h2>登录</h2>
        <p class="form-note">使用机构分配的账号进入知识库或对话。</p>
        <label class="field">
          <span>用户名</span>
          <el-input v-model="username" autocomplete="username" />
        </label>
        <label class="field">
          <span>密码</span>
          <el-input v-model="password" type="password" autocomplete="current-password" show-password />
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="button" type="submit" :disabled="submitting">
          {{ submitting ? "登录中" : "进入系统" }}
          <svg v-if="!submitting" class="arrow" viewBox="0 0 12 12" aria-hidden="true">
            <path
              d="M4.5 2.5 8 6l-3.5 3.5"
              fill="none"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </form>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { errorMessage } from "@/api/http";
import { useAuth } from "@/auth";
import { notifySuccess } from "@/feedback";

const router = useRouter();
const { login } = useAuth();
const username = ref("");
const password = ref("");
const error = ref("");
const submitting = ref(false);

async function onSubmit() {
  error.value = "";
  if (!username.value.trim() || !password.value) {
    error.value = "请填写用户名和密码";
    return;
  }
  submitting.value = true;
  try {
    await login(username.value.trim(), password.value);
    notifySuccess("登录成功");
    await router.push("/knowledge");
  } catch (err) {
    error.value = errorMessage(err, "登录失败，请稍后重试");
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.login {
  min-height: 100vh;
  min-height: 100svh;
}

.login-wrap {
  width: min(1280px, calc(100% - 2 * var(--gut)));
  margin: 0 auto;
  min-height: 100vh;
  min-height: 100svh;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
  column-gap: 64px;
  align-items: start;
  padding: 120px 0 72px;
}

.login-copy {
  grid-column: 1;
  grid-row: 1;
}

.form {
  grid-column: 2;
  grid-row: 1;
}

.eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
}

.login h1 {
  margin: 16px 0 0;
  font-size: clamp(40px, 4.6vw, 72px);
  line-height: 1.05;
  letter-spacing: -0.045em;
}

.lead {
  margin-top: 24px;
  font-size: 20px;
  line-height: 1.5;
}

.rule {
  margin: 24px 0 0;
  font-size: 16px;
  line-height: 1.5;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 32px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
}

.form h2 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
}

.form-note {
  margin: -8px 0 0;
  font-size: 16px;
  line-height: 1.5;
}

.form .button {
  margin-top: 8px;
}

@media (max-width: 900px) {
  .login-wrap {
    grid-template-columns: 1fr;
    row-gap: 32px;
    padding-top: 96px;
    padding-bottom: 48px;
    min-height: 0;
  }

  .login-copy,
  .form {
    grid-column: 1;
    grid-row: auto;
  }

  .login h1 {
    font-size: 40px;
  }

  .lead {
    font-size: 18px;
  }

  .form .button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: no-preference) {
  html.m-enter .login h1,
  html.m-enter .lead,
  html.m-enter .rule,
  html.m-enter .form {
    animation: rise 700ms var(--ease-enter) both;
  }

  html.m-enter .lead {
    animation-delay: 80ms;
  }

  html.m-enter .rule {
    animation-delay: 140ms;
  }

  html.m-enter .form {
    animation-delay: 180ms;
  }
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }

  to {
    opacity: 1;
    transform: none;
  }
}
</style>
