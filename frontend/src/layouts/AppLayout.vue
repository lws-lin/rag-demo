<template>
  <div class="shell">
    <a class="skip-link" href="#top">跳到内容</a>
    <header class="topbar">
      <div class="bar">
        <router-link class="brand" to="/knowledge">
          <span class="mark" aria-hidden="true"></span>
          <span>医疗机构知识库</span>
        </router-link>
        <nav id="app-nav" class="nav" :class="{ open: menuOpen }">
          <router-link to="/knowledge" @click="menuOpen = false">知识库</router-link>
          <router-link to="/chat" :class="{ 'is-current': route.path === '/chat' || route.path.startsWith('/chat/') }" @click="menuOpen = false">对话</router-link>
          <div class="nav-account">
            <p v-if="user" class="account-line">{{ user.display_name }} · {{ roleLabel[user.role] }}</p>
            <button class="button secondary" type="button" @click="onLogout">退出登录</button>
          </div>
        </nav>
        <div class="account">
          <span v-if="user" class="account-line">{{ user.display_name }} · {{ roleLabel[user.role] }}</span>
          <button class="button secondary" type="button" @click="onLogout">退出登录</button>
        </div>
        <button
          class="nav-toggle button secondary"
          type="button"
          :aria-expanded="menuOpen"
          aria-controls="app-nav"
          @click="menuOpen = !menuOpen"
        >
          {{ menuOpen ? "关闭" : "菜单" }}
        </button>
      </div>
    </header>
    <div id="top">
      <router-view />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuth } from "@/auth";
import { roleLabel } from "@/labels";

const route = useRoute();
const router = useRouter();
const { user, logout, refreshMe } = useAuth();
const menuOpen = ref(false);

onMounted(async () => {
  try {
    await refreshMe();
  } catch {
    // 401 时拦截器会回到登录页
  }
});

watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false;
  },
);

function onLogout() {
  menuOpen.value = false;
  logout();
  router.push("/login");
}
</script>

<style scoped>
.topbar {
  position: fixed;
  inset: 0 0 auto 0;
  z-index: 10;
  height: var(--nav);
  background: var(--bg);
  border-bottom: 1px solid var(--line);
}

.bar {
  height: 100%;
  width: min(1280px, calc(100% - 2 * var(--gut)));
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 32px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  line-height: 1;
}

.nav {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 100%;
}

.nav a {
  position: relative;
  display: inline-flex;
  align-items: center;
  height: 44px;
  padding: 0 12px;
  font-size: 15px;
  font-weight: 500;
}

.nav a::before,
.nav a.router-link-active::after,
.nav a.is-current::after {
  content: "";
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 8px;
  background: currentColor;
}

.nav a::before {
  height: 1px;
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 150ms var(--ease);
}

.nav a.router-link-active::after,
.nav a.is-current::after {
  height: 2px;
}

.nav-account {
  display: none;
}

.account {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 16px;
}

.account-line {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}

.nav-toggle {
  display: none;
}

@media (hover: hover) and (pointer: fine) {
  .nav a:hover::before {
    transform: scaleX(1);
  }

  .nav a.router-link-active:hover::before {
    transform: none;
  }
}

@media (max-width: 800px) {
  .bar {
    gap: 12px;
  }

  .account {
    display: none;
  }

  .nav-toggle {
    display: inline-flex;
    margin-left: auto;
    padding: 0 16px;
  }

  .nav {
    display: none;
    position: fixed;
    inset: var(--nav) 0 0 0;
    height: auto;
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    padding: 16px var(--gut) 32px;
    background: var(--bg);
    overflow: auto;
  }

  .nav.open {
    display: flex;
  }

  .nav a {
    height: 56px;
    padding: 0;
    font-size: 20px;
  }

  .nav a::before,
  .nav a.router-link-active::after {
    left: 0;
    right: auto;
    width: 28px;
    bottom: 10px;
  }

  .nav-account {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
    margin-top: 32px;
  }

  .nav-account .button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .nav a::before {
    transition: none;
  }
}
</style>
