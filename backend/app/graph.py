"""LangGraph 编排:出题 -> 评估(追问+评分) -> 报告,状态机推进。
对比纯 if-else:图结构可视化、可断点续跑、可单节点重试,面试官问"工作流怎么做的"直接画图讲。

入口路由按状态分流:
- 无题库      -> generate(出题)
- 有题库+回答  -> evaluate(追问判定+实时评分)
- report_mode -> report(四维打分+总评)
"""
from typing import TypedDict, List


class InterviewState(TypedDict, total=False):
    position: str
    difficulty: str
    rounds: int
    jd: str
    questions: List[dict]
    current: int
    last_answer: str
    need_followup: bool
    followup_q: str
    scores: List[dict]
    qa: List[dict]
    report_mode: bool
    report_data: dict


def node_generate(s: InterviewState) -> dict:
    from .llm import generate_questions
    if s.get("questions"):
        return {}
    return {"questions": generate_questions(s["position"], s["difficulty"], s["rounds"], s.get("jd", "")),
            "current": 0, "scores": []}


def node_evaluate(s: InterviewState) -> dict:
    from .llm import judge_followup, score_answer
    qs = s["questions"]
    idx = s["current"]
    q = qs[idx]
    followed = q.get("followup_count", 0)
    need, fq = judge_followup(q, s.get("last_answer", ""), followed)
    score, comment = score_answer(q, s.get("last_answer", ""))
    if need:
        q["followup_count"] = followed + 1
    entry = {"score": score, "comment": comment, "followup": fq if need else ""}
    scores = list(s.get("scores", [])) + [entry]
    nxt = idx if need else idx + 1  # 追问则停在同一题,否则推进
    return {"need_followup": need, "followup_q": fq, "scores": scores,
            "current": nxt, "questions": qs}


def node_report(s: InterviewState) -> dict:
    from .llm import build_report
    return {"report_data": build_report(s.get("position", ""), s.get("qa", []))}


def route_entry(s: InterviewState) -> str:
    if s.get("report_mode"):
        return "report"
    if s.get("questions"):
        return "evaluate"
    return "generate"


def build_graph():
    from langgraph.graph import StateGraph, END
    g = StateGraph(InterviewState)
    g.add_node("generate", node_generate)
    g.add_node("evaluate", node_evaluate)
    g.add_node("report", node_report)
    g.set_conditional_entry_point(
        route_entry,
        {"generate": "generate", "evaluate": "evaluate", "report": "report"},
    )
    g.add_edge("generate", END)
    g.add_edge("evaluate", END)
    g.add_edge("report", END)
    return g.compile()


graph = build_graph()
