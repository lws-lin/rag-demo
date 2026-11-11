# 医疗机构知识库

给医疗机构用的知识库演示。现在可以登录、把文档拆成片段入库，以及保存对话。检索回答和出方案还没有接入，发送消息后会保存一条占位回复。

## 现在能做什么

- 使用管理员账号登录。后端启动时，如果 `.env` 里的用户名还不存在，会自动创建一名知识管理员。
- 从页面上传文档，或把文件放进收件目录后用命令批量导入。
- 支持 `txt`、`md`、`pdf`、`docx`，单文件不超过 20MB。相同内容（SHA-256）不会重复入库。
- 文本按约 800 字拆成片段，相邻片段重叠约 120 字，并尽量在换行或 `。；！？` 处断开。能读出文字的文档状态为待复核，读不出文字的为已拒绝。
- 在知识库页面按标题、分类、状态筛选，每页 20 条。
- 新建对话、查看最近修改时间、删除对话。删除前会再确认一次，消息会一起删除。

分类对应收件目录：

| 目录 | 分类 |
| --- | --- |
| `data/inbox/design` | 工业设计 |
| `data/inbox/regulation` | 法律法规 |
| `data/inbox/other` | 其他 |

角色有三种：知识管理员 `admin`、业务用户 `user`、审计 `auditor`。审计只能查看。业务用户只能看到自己的对话；管理员可以看到全部对话。页面上还没有账号管理。

## 本地调试

需要 Python 3.12、Node.js 和 Docker。系统自带的 Python 3.9 不能跑这份代码。

只启动数据库：

```bash
docker compose up -d postgres
```

后端：

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:5173 。前端把 `/api` 代理到 http://127.0.0.1:8000 。

这样改代码会自动重载，不需要重新构建镜像。

## 用 Docker 一起跑

```bash
docker compose up --build
```

- 页面：http://127.0.0.1:8088
- 接口：http://127.0.0.1:8000
- 数据库：本机 `5432`

镜像里已经执行过数据库迁移。改了代码后要重新 `docker compose up --build`，否则容器里还是旧版本。收件目录和原文件目录通过 `./data:/data` 挂进后端容器。

## 配置

复制 `.env.example` 为 `.env`。本地默认值：

| 变量 | 作用 |
| --- | --- |
| `DATABASE_URL` | 本地数据库地址。`docker compose` 会改写成容器内的 `postgres` 服务 |
| `JWT_SECRET` | 登录令牌密钥。令牌默认 720 分钟有效 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 首次启动时创建管理员。密码至少 8 位。示例是 `admin` / `ChangeMe-123456` |
| `CORS_ORIGINS` | 允许访问接口的前端地址 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 片段长度和重叠，默认 800 和 120 |
| `INBOX_DIR` / `LIBRARY_DIR` | 收件目录和原文件目录。留空时使用项目下的 `data/inbox` 和 `data/library` |

改了片段长度后，已经入库的文件不会自动重拆。需要先删掉该文档，再重新导入。

## 批量导入

把文件放进上表里的三个目录，在 `backend` 目录执行：

```bash
source .venv/bin/activate
python -m app.cli.ingest
```

命令会打印每份文件是新入库、已存在、无文字还是失败。也可以用 `--inbox` 指定别的收件目录。

页面上传和这条命令使用同一套拆分规则。原文件会复制到 `data/library`。

## 主要接口

除了登录和健康检查，请求都要带 `Authorization: Bearer <token>`。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/auth/login` | 登录 |
| `GET` | `/api/auth/me` | 当前用户 |
| `GET` | `/api/documents` | 文档列表。查询参数：`q`、`category`、`status`、`page`、`page_size` |
| `POST` | `/api/documents` | 上传文档。表单字段 `file`、`category` |
| `GET` | `/api/conversations` | 对话列表 |
| `POST` | `/api/conversations` | 新建对话。可带标题，留空则为「新对话」 |
| `DELETE` | `/api/conversations/{id}` | 删除对话 |
| `GET` | `/api/conversations/{id}/messages` | 消息列表 |
| `POST` | `/api/conversations/{id}/messages` | 发送消息并保存占位回复 |
