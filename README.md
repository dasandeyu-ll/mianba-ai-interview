# 面霸 —— AI 智能模拟面试系统

选岗(可选粘贴 JD) → AI 流式提问(+语音播报) → 答浅自动追问 → 四维雷达图报告(可打印 PDF)。

## 一键启动

```powershell
cd "C:\Users\wu\Desktop\代码修复"
copy backend\.env.example backend\.env   # 可选:填入 DEEPSEEK_API_KEY;不填也跑(Mock 题库+启发式评分)
docker compose up --build
```

- 前端 http://localhost:5173,后端 http://localhost:8000,接口文档 http://localhost:8000/docs
- 本地调试:后端 `pip install -r backend/requirements.txt` 后 `uvicorn app.main:app --reload --port 8000`;
  前端 `npm install && npm run dev`(代理已配好 `/api -> 8000`)。

## 全功能验证(后端 28 项断言)

```powershell
cd backend
python -u verify.py            # 默认 5 题; --rounds N 改题数; --base URL 换地址
```

覆盖:健康检查 / 非法轮数 422 / 出题四维约束 / 题号连续 / **JD 按岗出题** / SSE 题面一致 /
空回答 422 / 错误 session 404 / 浅回答必追问且不推进 / 同题最多追问 2 次 / 好回答高分通过 /
答完 finished / 终面再答 400 / 报告四维 0~100 / 点评条数==题数 / 追问记录 / 总评建议。

前端验证:配置(粘 JD 看题目是否贴技术栈)→答题(含追问气泡、语音作答)→报告→打印 PDF;
刷新页面应提示"继续面试";Chrome/Edge 点"语音作答"可用麦克风输入。

## 关键设计取舍

| 点 | 做法 | 为什么不用别的 |
|---|---|---|
| 前后端通信 | REST + SSE | WebSocket 要心跳/重连/房间管理,面试只是单向推题;轮询延迟高 |
| 出题/追问/报告 | LangGraph 状态机 | 纯 if-else 3 分支后就成面条,图可单节点重试、断点续跑、可视化 |
| 追问判定 | LLM 判 + 启发式兜底 | 纯 LLM 没 Key 就挂;纯关键词太傻 |
| 评分 | LLM 打分 + 长度/采分点校准 | 直接信 LLM 会"5 个字给 75 分",校准后才有区分度 |
| JD 出题 | JD 进提示词(轻量 RAG) | 不上向量库:8 题场景检索收益低,提示词注入已够贴岗 |
| 存储 | SQLite 单表 | 免运维 mysql 容器;换 SQLAlchemy 只改 db.py 一个文件 |
| PDF | 打印样式 + window.print() | 后端 reportlab 要调字体分页,样式难对齐,3 行代码已够 |
| 语音 | Web Speech API | 浏览器原生零成本零 Key;云 TTS 演示断网就没声 |

## 架构速览

```
React/Vite + ECharts(懒加载) + Web Speech
  │  REST + SSE(单向推送,比 WebSocket 轻)
  ▼
FastAPI(/start /answer /report /stream /state)
  ├── LangGraph 状态机: generate(出题) → evaluate(追问+评分) → report(四维+总评)
  ├── DeepSeek 出题/判追问/打分,全链路 Mock+规则兜底(无 Key 也跑通)
  ├── Pydantic 约束题型/轮数/报告结构;长度+采分点校准压住 LLM 虚高分
  └── SQLite 持久化会话,支持断点续面
```
