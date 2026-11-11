import { computed, ref } from "vue";
import { fetchMe, login as loginRequest } from "@/api/auth";
import type { User } from "@/types";

function readUser(): User | null {
  const raw = localStorage.getItem("user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

const token = ref(localStorage.getItem("token") || "");
const user = ref<User | null>(readUser());

export function useAuth() {
  const isLoggedIn = computed(() => Boolean(token.value));

  async function login(username: string, password: string) {
    const result = await loginRequest(username, password);
    token.value = result.access_token;
    user.value = result.user;
    localStorage.setItem("token", result.access_token);
    localStorage.setItem("user", JSON.stringify(result.user));
  }

  function logout() {
    token.value = "";
    user.value = null;
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  }

  async function refreshMe() {
    user.value = await fetchMe();
    localStorage.setItem("user", JSON.stringify(user.value));
  }

  return { token, user, isLoggedIn, login, logout, refreshMe };
}
