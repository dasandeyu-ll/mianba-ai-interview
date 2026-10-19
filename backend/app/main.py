import asyncio
import json
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv

load_dotenv()

from .db import init_db, create_session, load_session, save_progress, save_questions
from .schemas import StartRequest, StartResponse, AnswerRequest, AnswerResponse, Question
from .graph import graph

app = FastAPI(title="面霸 AI 面试官")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
init_db()

@app.get("/api/health")
def health():
    return {"ok": True}

@app.post("/api/interview/start", response_model=StartResponse)
def start(req: StartRequest):
    # 走 LangGraph 的 generate 节点出题(状态机第一步),而不是在接口里手写逻辑
    state = graph.invoke({"position": req.position, "difficulty": req.difficulty,
                          "rounds": req.rounds, "jd": req.jd or "",
                          "questions": [], "current": 0,
                          "last_answer": "", "scores": []})
    sid = create_session(req.position, req.difficulty, state["questions"])
    return StartResponse(session_id=sid, questions=[Question(**q) for q in state["questions"]], total=len(state["questions"]))

@app.get("/api/interview/stream")
async def stream(session_id: str = Query(...)):
    """SSE 流式推送当前题(打字机效果+语音播报逐句读),对比 WebSocket:单向推送用 SSE 更轻,不用维护长连接心跳。"""
    sess = load_session(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    idx = sess["current_index"]
    qs = sess["questions"]
    if idx >= len(qs):
        async def empty():
            yield {"event": "done", "data": "[DONE]"}
        return EventSourceResponse(empty())
    title = qs[idx]["title"]

    async def gen():
        for ch in title:
            yield {"event": "token", "data": json.dumps({"ch": ch}, ensure_ascii=False)}
            await asyncio.sleep(0.03)
        yield {"event": "done", "data": "[DONE]"}
    return EventSourceResponse(gen())

@app.get("/api/interview/state")
def state(session_id: str):
    """断点续面:刷新/关闭页面后用 session_id 恢复进度(含完整题库,前端可直接续答)。"""
    sess = load_session(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    idx = sess["current_index"]
    total = sess["total"]
    return {"session_id": session_id, "position": sess["position"],
            "difficulty": sess["difficulty"],
            "current_index": idx, "total": total,
            "progress": f"{min(idx, total)}/{total}",
            "questions": sess["questions"],
            "current_question": sess["questions"][idx] if idx < total else None,
            "answers": sess["answers"], "status": sess["status"]}

@app.post("/api/interview/answer", response_model=AnswerResponse)
def answer(req: AnswerRequest):
    sess = load_session(req.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    qs, idx, total = sess["questions"], sess["current_index"], sess["total"]
    if idx >= total:
        raise HTTPException(400, "面试已结束,直接看报告")
    # 走 LangGraph evaluate 节点:追问判定+实时评分(状态机推进)。
    # 注意入口路由:有 questions 的状态会进 evaluate,不是 generate。
    out = graph.invoke({"position": sess["position"], "difficulty": sess["difficulty"],
                        "rounds": total, "questions": qs, "current": idx,
                        "last_answer": req.answer, "scores": sess["scores"]})
    need = out.get("need_followup", False)
    fq = out.get("followup_q", "")
    new_scores = out.get("scores", sess["scores"])
    last = new_scores[-1] if new_scores else {"score": 60, "comment": ""}
    answers = sess["answers"] + [{"q": qs[idx]["title"], "type": qs[idx]["type"],
                                  "answer": req.answer, "score": last["score"],
                                  "comment": last["comment"],
                                  "followups": ([fq] if need else [])}]
    # 追问不推进题号(停在同一题,前端显示追问气泡);答得好则推进
    new_idx = out.get("current", idx if need else idx + 1)
    # 同一题多次追问要合并到同一条 answer 记录里
    if need and len(sess["answers"]) > 0 and sess["answers"][-1]["q"] == qs[idx]["title"]:
        answers = sess["answers"][:-1] + [{
            **sess["answers"][-1],
            "answer": sess["answers"][-1]["answer"],
            "followups": sess["answers"][-1].get("followups", []) + [fq],
            "score": last["score"],
            "comment": last["comment"],
        }]
    finished = new_idx >= total
    # followup_count 是图节点在内存里改的,必须回写 DB,否则上限只活在内存里
    save_questions(req.session_id, out.get("questions", qs))
    save_progress(req.session_id, new_idx, answers, sess["followups"], new_scores,
                  status="done" if finished else "ongoing")
    next_q = None if (need or finished) else qs[new_idx]
    return AnswerResponse(
        need_followup=need, followup_question=fq or None,
        next_question=Question(**next_q) if next_q else None,
        finished=finished, progress=f"{min(new_idx, total)}/{total}",
        done_count=min(new_idx, total), total=total,
        realtime_score=last["score"], comment=last["comment"])

@app.post("/api/interview/report")
def report(body: dict):
    sid = body.get("session_id", "")
    sess = load_session(sid)
    if not sess:
        raise HTTPException(404, "会话不存在")
    # 按题库逐题对齐:同一题的多次追问在 answer 环节已合并,所以用题干做键归位。
    # 这样点评条数恒等于题数(之前按 answers 个数截/补,追问一多就错位)。
    by_title: dict[str, dict] = {}
    for a in sess["answers"]:
        prev = by_title.get(a["q"])
        if prev is None:
            by_title[a["q"]] = a
        else:
            by_title[a["q"]] = {**a, "followups": prev.get("followups", []) + a.get("followups", [])}
    qa = []
    for q in sess["questions"]:
        a = by_title.get(q["title"])
        if a:
            qa.append({"question": a["q"], "type": a["type"], "answer": a["answer"],
                       "score": a["score"], "comment": a["comment"],
                       "followups": a.get("followups", [])})
        else:
            # 没答完也允许看阶段性报告(未作答按 0 分,雷达图不空)
            qa.append({"question": q["title"], "type": q["type"], "answer": "(未作答)",
                       "score": 0, "comment": "未作答", "followups": []})
    assert len(qa) == sess["total"]
    # 报告也走 LangGraph 的 report 节点,保持"全流程状态机"的说法成立
    out = graph.invoke({"position": sess["position"], "qa": qa, "report_mode": True})
    r = out.get("report_data") or {"scores": {}, "overall": "", "suggestions": []}
    return {"session_id": sid, "scores": r["scores"],
            "per_question": [{"question": x["question"], "answer": x["answer"][:300],
                              "score": x["score"], "comment": x["comment"],
                              "followups": x["followups"]} for x in qa],
            "overall": r["overall"], "suggestions": r["suggestions"]}
