"""面霸全功能自动化验证:只用标准库,对着跑起来的后端(默认 localhost:8000)
完整走一遍 8 题面试,断言每个环节。用法: python verify.py [--base URL] [--rounds N]"""
import json
import sys
import urllib.request
import urllib.error

BASE = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "http://localhost:8000"
ROUNDS = int(sys.argv[sys.argv.index("--rounds") + 1]) if "--rounds" in sys.argv else 5
DIMS = {"基础", "项目", "算法", "沟通"}
passed, failed = [], []


def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(f"{'[PASS]' if cond else '[FAIL]'} {name}" + (f" -- {detail}" if detail and not cond else ""))


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def read_sse(path):
    """读 SSE,把 token 拼起来,返回(拼出的文本, 是否收到done)。
    注意服务端有心跳保活、连接不会自己断,所以收到 done 事件就主动返回。"""
    text, block = [], ""

    def handle(block):
        ev, data = "message", ""
        for line in block.splitlines():
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
        if ev == "token":
            text.append(json.loads(data)["ch"])
            return False
        return ev == "done"

    done = False
    with urllib.request.urlopen(BASE + path, timeout=60) as resp:
        while not done:
            line = resp.readline().decode()  # 阻塞等下一行,有超时兜底
            if not line:
                break
            if line in ("\n", "\r\n"):
                if block:
                    done = handle(block)
                    block = ""
            else:
                block += line
    return "".join(text), done


SHALLOW = "我会这个。"
LAST_SHALLOW_SCORE = {"v": None}

print(f"== 验证目标 {BASE},轮数 {ROUNDS} ==")

# 1. 健康检查
s, b = req("GET", "/api/health")
check("健康检查 /api/health", s == 200 and b.get("ok") is True, f"status={s}")

# 2. 非法轮数被 Pydantic 拦下
s, _ = req("POST", "/api/interview/start",
           {"position": "后端", "difficulty": "中等", "rounds": 99})
check("非法轮数 rounds=99 返回 422", s == 422, f"status={s}")

# 3. 开始面试
s, b = req("POST", "/api/interview/start",
           {"position": "后端", "difficulty": "中等", "rounds": ROUNDS})
sid = b.get("session_id", "")
qs = b.get("questions", [])
check("开始面试拿到 session+题库", s == 200 and bool(sid) and len(qs) == ROUNDS, f"status={s}")
check("题型全在四维内(基础/项目/算法/沟通)",
      bool(qs) and all(q.get("type") in DIMS for q in qs))
check("题号连续 id=0..N-1", [q.get("id") for q in qs] == list(range(len(qs))))

# 4. 断点续面 state
s, b = req("GET", f"/api/interview/state?session_id={sid}")
check("state 进度 0/N", s == 200 and b.get("progress") == f"0/{ROUNDS}", f"{b.get('progress')}")
check("state 返回完整题库(续面用)", isinstance(b.get("questions"), list) and len(b.get("questions", [])) == ROUNDS)

# 4b. JD 出题:带 JD 开新会话,Mock 降级下也应优先命中 JD 技术词
s, bj = req("POST", "/api/interview/start",
            {"position": "后端", "difficulty": "中等", "rounds": ROUNDS,
             "jd": "负责高并发交易系统,要求熟悉 Redis 缓存、MySQL 索引优化和 Kafka 消息队列"})
jq = bj.get("questions", [])
check("带 JD 能正常出题", s == 200 and len(jq) == ROUNDS, f"status={s}")
check("JD 技术词命中题优先(首题含 Redis/MySQL/Kafka/缓存/索引/高并发)",
      bool(jq) and any(k in jq[0]["title"] for k in ("Redis", "MySQL", "Kafka", "缓存", "索引", "高并发")),
      jq[0]["title"] if jq else "no questions")

# 5. SSE 流式首题与题面一致
streamed, done = read_sse(f"/api/interview/stream?session_id={sid}")
check("SSE 收到 done 事件", done)
check("SSE 拼出的题面 == 第1题", streamed == qs[0]["title"], f"streamed={streamed[:20]}")

# 6. 空回答 422
s, _ = req("POST", "/api/interview/answer", {"session_id": sid, "answer": ""})
check("空回答返回 422", s == 422, f"status={s}")

# 7. 错误 session 404
s, _ = req("POST", "/api/interview/answer", {"session_id": "nope123", "answer": "xxx"})
check("错误 session 回答返回 404", s == 404, f"status={s}")
s, _ = req("POST", "/api/interview/report", {"session_id": "nope123"})
check("错误 session 报告返回 404", s == 404, f"status={s}")

# 8. 答得浅 -> 被追问,且进度不推进
s, b = req("POST", "/api/interview/answer", {"session_id": sid, "answer": SHALLOW})
LAST_SHALLOW_SCORE["v"] = b.get("realtime_score")
check("浅回答触发追问 need_followup=true", s == 200 and b.get("need_followup") is True, f"{b}")
check("追问有具体问题文本", bool(b.get("followup_question")))
check("追问后进度仍为 0/N", b.get("progress") == f"0/{ROUNDS}", f"{b.get('progress')}")

# 9. 追问上限:连答浅回答,第 3 次必须放行(防死循环)
for _ in range(2):
    s, b = req("POST", "/api/interview/answer", {"session_id": sid, "answer": SHALLOW})
check("同一题最多追问 2 次后放行", b.get("need_followup") is False and b.get("progress") == f"1/{ROUNDS}",
      f"{b.get('need_followup')} {b.get('progress')}")

# 10. 好回答必须是"对题"的:用该题的采分点现编答案,LLM 才认分(Mock 下也稳过)
def good_for(i):
    kp = qs[i].get("key_points") or ["核心概念", "项目经历"]
    return (f"针对第{i + 1}题,我的回答如下。因为我在订单项目里亲手做过,峰值 QPS 5000,"
            f"所以先说结论:{'、'.join(kp[:3])}。数据上 P99 从 900ms 降到 120ms,"
            f"缓存命中率 98%,源码层面也看过实现,优化前后做过 AB 对比。")

s, b = req("POST", "/api/interview/answer", {"session_id": sid, "answer": good_for(1)})
tries = 0
while b.get("need_followup") and tries < 2:
    # LLM 对好回答偶发深挖,补答同题最多 2 次(达追问上限必放行)
    tries += 1
    s, b = req("POST", "/api/interview/answer", {"session_id": sid, "answer": good_for(1)})
check("好回答补答后通过(至多追问 2 次)", b.get("need_followup") is False and b.get("next_question"), f"{b}")
shallow_v = LAST_SHALLOW_SCORE["v"]
check("好回答分数高于浅回答(评分有区分度)",
      isinstance(b.get("realtime_score"), int) and isinstance(shallow_v, int)
      and b["realtime_score"] > shallow_v,
      f"good={b.get('realtime_score')} shallow={shallow_v}")

# 11. 跑完剩余题目 -> finished(对题回答;偶发追问则补答一次,上限兜底防死循环)
qi = 2  # 已过第 0、1 题,当前是第 2 题
guard = 0
while True:
    guard += 1
    assert guard < 40, "死循环保护"
    s, b = req("POST", "/api/interview/answer", {"session_id": sid, "answer": good_for(qi)})
    if b.get("finished"):
        break
    if b.get("need_followup"):
        s, b = req("POST", "/api/interview/answer", {"session_id": sid, "answer": good_for(qi)})
        if b.get("finished"):
            break
        if b.get("need_followup"):
            s, b = req("POST", "/api/interview/answer", {"session_id": sid, "answer": SHALLOW})
            if b.get("finished"):
                break
    qi = min(qi + 1, ROUNDS - 1)  # 追问不推进题号,答过才 +1
check("答完 N 题 finished=true", b.get("finished") is True and b.get("progress") == f"{ROUNDS}/{ROUNDS}",
      f"{b.get('progress')}")
check("终面后 state 状态为 done",
      req("GET", f"/api/interview/state?session_id={sid}")[1].get("status") == "done")

# 12. 终面后再答 -> 400
s, _ = req("POST", "/api/interview/answer", {"session_id": sid, "answer": SHALLOW})
check("终面后再答返回 400", s == 400, f"status={s}")

# 13. 报告
s, b = req("POST", "/api/interview/report", {"session_id": sid})
check("报告四维齐全", set((b.get("scores") or {}).keys()) == DIMS, f"{b.get('scores')}")
check("四维分数都在 0~100", all(isinstance(v, int) and 0 <= v <= 100 for v in (b.get("scores") or {}).values()))
check(f"每题点评条数 == {ROUNDS}", len(b.get("per_question", [])) == ROUNDS)
check("有追问记录", any(q.get("followups") for q in b.get("per_question", [])))
check("总评与建议非空", bool(b.get("overall")) and len(b.get("suggestions", [])) >= 1)

print(f"\n== 结果: {len(passed)} 通过, {len(failed)} 失败 ==")
if failed:
    print("失败项:", failed)
    sys.exit(1)
print("ALL GREEN, full pipeline works!")
