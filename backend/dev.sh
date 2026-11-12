#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "找不到 .venv。请先在 backend 目录创建虚拟环境并安装依赖。"
  exit 1
fi

if command -v lsof >/dev/null 2>&1; then
  pids="$(lsof -ti tcp:8000 -sTCP:LISTEN || true)"
  if [[ -n "${pids}" ]]; then
    echo "停掉占用 8000 端口的进程：${pids}"
    kill ${pids}
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      sleep 0.2
      if ! lsof -ti tcp:8000 -sTCP:LISTEN >/dev/null 2>&1; then
        break
      fi
    done
  fi
fi

exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
