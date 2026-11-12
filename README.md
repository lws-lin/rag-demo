# 医疗机构知识库

给医疗机构用的知识库演示。可以登录、导入文档、复核发布，再按已发布原文做多轮对话。回答由对话模型流式生成。出方案目前只生成文字。

## 现在能做什么

- 使用管理员账号登录。后端启动时，如果 `.env` 里的用户名还不存在，会自动创建一名知识管理员。
- 从页面上传文档，或把文件放进收件目录后用命令批量导入。相同内容（SHA-256）不会重复入库。
- 在知识库按标题、分类、状态筛选，每页 20 条。打开文档可以看到片段和原文。
- 管理员复核：发布、拒绝或下线。发布时写入向量；拒绝或下线会删掉该文档的向量。向量写失败时，文档状态不变。已发布的文档只能下线。
- 管理员在账号页新建管理员或普通员工。
- 新建对话、切换、删除。删除前会再确认一次，消息会一起删除。同一会话会带上最近 8 条已保存消息。模型调用失败时，这一轮不会写入。

支持的格式：`txt`、`md`、`pdf`、`docx`、`pptx`、`xlsx`、`xls`、`csv`、`tsv`、`html`、`json`、`png`、`jpg`、`jpeg`、`webp`、`tif`、`tiff`。单文件不超过 20MB。`htm` 与 `html` 同样接受。图片和几乎没有文字层的 PDF 会在本地做文字识别。

能读出文字的文档进入待复核，读不出文字的为已拒绝。页面上的状态是待复核、已发布、已拒绝、已下线。

分类对应收件目录：

| 目录 | 分类 |
| --- | --- |
| `data/inbox/design` | 工业设计 |
| `data/inbox/regulation` | 法律法规 |
| `data/inbox/other` | 其他 |

## 分段和检索

入库时先按标题、段落、列表、表格、代码等语义单元切开。单元过长时，再按约 800 字拆开，相邻片段重叠约 120 字。表格片段会带上表头。每段记下页码和章节路径。细则见 [docs/知识库文档解析与分段方案.md](docs/知识库文档解析与分段方案.md)。

改了切分规则或 `CHUNK_SIZE` 后，已经入库的文档不会自动重切。

发布时用本地模型 `BAAI/bge-small-zh-v1.5` 把片段写成 512 维向量，存在 PostgreSQL 里，并在向量列上建了 HNSW 余弦索引。首次发布会把模型下载到 `data/models`。

查资料时：

- 只检索已发布、并且当前角色可见的片段。
- 向量先取最近 12 条。问句里的英文专名再按原文补最多 8 条。
- 命中专名的片段会往前排。距离过远的整组丢掉。最后最多 4 条交给对话模型。
- 没有单独的重排模型。

闲聊、问候，以及询问当前模型是谁，不会去检索知识库。

## 谁能看见什么

角色只有两种：管理员 `admin`、普通员工 `user`。

- 管理员能看到全部文档和全部对话，也可以复核和建账号。
- 普通员工能看到自己上传的文档，以及已发布且可见范围包含普通员工的文档。对话只看到自己的。
- 发布时可见范围留空，表示仅管理员可检索、可查看。

## 本地调试

需要 Python 3.12、Node.js 和 Docker。

只启动数据库：

```bash
docker compose up -d postgres
```

后端第一次：

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

之后在项目根目录执行：

```bash
./backend/dev.sh
```

这个脚本会停掉占用 8000 端口的进程，再启动带自动重载的接口。`.env` 只在进程启动时读取，改完配置要重新执行它。

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

镜像里已经执行过数据库迁移。改了代码后要重新 `docker compose up --build`，否则容器里还是旧版本。收件目录、原文件目录和向量模型缓存通过 `./data:/data` 挂进后端容器。

## 配置

复制 `.env.example` 为 `.env`。

| 变量 | 作用 |
| --- | --- |
| `DATABASE_URL` | 本地数据库地址。`docker compose` 会改写成容器内的 `postgres` 服务 |
| `JWT_SECRET` | 登录令牌密钥。令牌默认 720 分钟有效 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 首次启动时创建管理员。密码至少 8 位。示例是 `admin` / `ChangeMe-123456` |
| `CORS_ORIGINS` | 允许访问接口的前端地址 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 超长片段的长度和重叠，默认 800 和 120 |
| `INBOX_DIR` / `LIBRARY_DIR` | 收件目录和原文件目录。留空时使用项目下的 `data/inbox` 和 `data/library` |
| `EMBEDDING_MODEL` | 发布时使用的向量模型，默认 `BAAI/bge-small-zh-v1.5`。维度是 512，更换模型需要同时改维度并做数据库迁移 |
| `CHAT_BASE_URL` / `CHAT_API_KEY` / `CHAT_MODEL` | 对话模型。使用 OpenAI 兼容的 `/chat/completions` 接口。地址不要自己带上 `/chat/completions` |

对话模型示例：

- DeepSeek：`https://api.deepseek.com`，模型名如 `deepseek-chat`
- 通义千问兼容模式：`https://dashscope.aliyuncs.com/compatible-mode/v1`，模型名如 `qwen-plus`
- OpenAI：`https://api.openai.com/v1`，模型名如 `gpt-4o-mini`

三项都填写后，对话才会调用模型。接口形状不同的服务接不上。

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
| `GET` | `/api/documents/{id}` | 文档详情，含片段 |
| `GET` | `/api/documents/{id}/file` | 打开原文 |
| `POST` | `/api/documents/{id}/review` | 复核。决定为发布、拒绝或下线 |
| `GET` | `/api/users` | 账号列表。仅管理员 |
| `POST` | `/api/users` | 新建账号。仅管理员 |
| `GET` | `/api/conversations` | 对话列表 |
| `POST` | `/api/conversations` | 新建对话。可带标题，留空则为「新对话」 |
| `DELETE` | `/api/conversations/{id}` | 删除对话 |
| `GET` | `/api/conversations/{id}/messages` | 消息列表 |
| `POST` | `/api/conversations/{id}/messages` | 发送消息。响应是 `text/event-stream`，逐段返回回答；完成后才保存这一轮 |
