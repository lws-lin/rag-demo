import type { User } from "@/types";
import { http } from "./http";

export async function login(username: string, password: string) {
  const { data } = await http.post<{ access_token: string; user: User }>("/auth/login", {
    username,
    password,
  });
  return data;
}

export async function fetchMe() {
  const { data } = await http.get<User>("/auth/me");
  return data;
}
