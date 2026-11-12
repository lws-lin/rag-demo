import type { User } from "@/types";
import { http } from "./http";

export async function listUsers() {
  const { data } = await http.get<User[]>("/users");
  return data;
}

export async function createUser(payload: { username: string; password: string; display_name: string; role: "admin" | "user" }) {
  const { data } = await http.post<User>("/users", payload);
  return data;
}
