import { createRouter, createWebHistory } from "vue-router";
import AppLayout from "@/layouts/AppLayout.vue";
import ChatPage from "@/views/chat/index.vue";
import KnowledgePage from "@/views/knowledge/index.vue";
import LoginPage from "@/views/login/index.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginPage, meta: { public: true } },
    {
      path: "/",
      component: AppLayout,
      children: [
        { path: "", redirect: "/knowledge" },
        { path: "knowledge", component: KnowledgePage },
        { path: "chat", component: ChatPage },
        { path: "chat/:id", component: ChatPage },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const token = localStorage.getItem("token");
  if (!to.meta.public && !token) return "/login";
  if (to.path === "/login" && token) return "/knowledge";
  return true;
});
