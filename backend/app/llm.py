"""DeepSeek 调用 + 无 Key 降级 Mock,保证没钱没网也能 5 分钟跑通."""
import json
import os
import random

USE_LLM = bool(os.getenv("DEEPSEEK_API_KEY"))
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

MOCK_BANK = {
    "后端": [
        ("基础", "解释一下 Redis 缓存穿透、击穿、雪崩的区别和各自的解决方案?"),
        ("项目", "讲一个你做过的最有挑战的后端项目,难点在哪,你怎么解决的?"),
        ("算法", "手撕:无重复字符的最长子串,说思路和复杂度。"),
        ("基础", "MySQL InnoDB 索引为什么用 B+ 树而不是 B 树或哈希?"),
        ("项目", "你的接口 QPS 突然从 500 涨到 5000,你会怎么扩容和排查?"),
        ("算法", "TopK 问题:100 亿个数找最大 100 个,内存只有 1G 怎么做?"),
        ("沟通", "和产品经理对需求有分歧,你坚持技术方案但对方坚持上线,你怎么办?"),
        ("基础", "讲讲 TCP 三次握手四次挥手,为什么不能两次握手?"),
        ("项目", "讲一次线上事故的排查过程,你是怎么定位根因的?"),
        ("算法", "LRU 缓存怎么实现?手写一下核心结构。"),
    ],
    "前端": [
        ("基础", "讲讲浏览器输入 URL 到页面渲染的完整过程?"),
        ("项目", "讲一个性能优化印象最深的项目,FCP/LCP 优化了多少?"),
        ("算法", "手写防抖和节流,说清区别和使用场景。"),
        ("基础", "React useEffect 和 useLayoutEffect 区别?闭包陷阱怎么解?"),
        ("项目", "大文件断点续传+秒传你会怎么设计前后端配合?"),
        ("算法", "虚拟列表(DOM 复用)原理是什么?什么场景必须用?"),
        ("沟通", "设计师给的设计稿实现成本极高,排期又紧,你怎么沟通?"),
        ("基础", "讲讲 EventLoop,宏任务微任务各举 3 个例子。"),
        ("项目", "Webpack/Vite 构建慢你排查过吗?从哪几个方向优化?"),
        ("算法", "深拷贝怎么写?循环引用怎么处理?"),
    ],
    "算法": [
        ("基础", "讲讲 Transformer 自注意力机制,复杂度是多少?"),
        ("项目", "讲一个你调参/训模型的项目,指标提升了多少,关键 trick 是什么?"),
        ("算法", "手撕:最长递增子序列,先 O(n^2) 再优化到 O(n log n)。"),
        ("基础", "交叉熵和 MSE 分别适合什么任务?为什么分类不用 MSE?"),
        ("项目", "推荐/搜推广,样本不均衡和冷启动你怎么处理?"),
        ("算法", "手撕:二叉树最近公共祖先,递归和迭代两种写法。"),
        ("沟通", "你的模型离线 AUC 涨了但线上 AB 没效果,你怎么跟老板解释?"),
        ("基础", "BatchNorm 和 LayerNorm 区别,为什么 Transformer 用 LN?"),
        ("项目", "RAG 落地时召回不准/幻觉严重,你做了哪些优化?"),
        ("算法", "动态规划三要素是什么?用 0-1 背包举例说明。"),
    ],
}

def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url=BASE_URL)

DIFF_MAP = {"简单": "intern-level,八股为主", "中等": "校招 P5 水平,八股+项目深挖", "困难": "社招 P6 水平,高并发+源码+场景设计"}

def mock_questions(position: str, difficulty: str, rounds: int, jd: str = "") -> list:
    bank = MOCK_BANK.get(position, MOCK_BANK["后端"])
    if jd and jd.strip():
        # Mock 也有 JD 降级可用:从 JD 提取常见技术词,优先挑命中题,保证无 Key 也能"按岗出题"
        keywords = [w for w in ("Redis", "MySQL", "Kafka", "MQ", "微服务", "分布式", "高并发", "缓存", "索引", "JVM", "React", "Vue", "性能", "算法", "模型", "RAG", "Transformer") if w.lower() in jd.lower()]
        hit = [q for q in bank if any(k.lower() in q[1].lower() for k in keywords)]
        rest = [q for q in bank if q not in hit]
        ordered = (hit + rest)[:len(bank)]
        picked = ordered[:min(rounds, len(ordered))]
    else:
        picked = random.sample(bank, k=min(rounds, len(bank)))
    out = []
    for i, (t, title) in enumerate(picked):
        out.append({"id": i, "type": t, "title": title, "difficulty": difficulty,
                     "key_points": ["答出核心概念", "结合项目经历", "说出 trade-off"], "followup_count": 0})
    return out

def generate_questions(position: str, difficulty: str, rounds: int, jd: str = "") -> list:
    if not USE_LLM:
        return mock_questions(position, difficulty, rounds, jd)
    try:
        c = _client()
        jd_hint = ""
        if jd and jd.strip():
            # JD 进提示词:让项目类题目围绕 JD 技术栈出,比通用题库更贴合岗位
            jd_hint = f"岗位JD(出题必须围绕其中的技术栈/业务场景):\n{jd.strip()[:800]}\n"
        prompt = f"""你是资深{position}面试官。出一套{rounds}题,{DIFF_MAP.get(difficulty, '')}。
{jd_hint}覆盖基础/项目/算法/沟通四类,难度={difficulty}。只返回 JSON 数组,每个元素:
{{"id":i,"type":"基础|项目|算法|沟通","title":"题干","difficulty":"{difficulty}","key_points":["采分点1","采分点2"],"followup_count":0}}"""
        r = c.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}],
                                      response_format={"type": "json_object"}, temperature=0.8)
        data = json.loads(r.choices[0].message.content)
        qs = data if isinstance(data, list) else data.get("questions", data.get("data", []))
        normed = normalize_questions(qs, difficulty, rounds)
        return normed if normed else mock_questions(position, difficulty, rounds, jd)
    except Exception:
        return mock_questions(position, difficulty, rounds, jd)

VALID_TYPES = ("基础", "项目", "算法", "沟通")

def normalize_questions(qs: object, difficulty: str, rounds: int) -> list:
    """LLM 返回经常缺字段/题型写错/id 从 1 开始,这里强制归一化,不合规就整批丢弃走 Mock。"""
    if not isinstance(qs, list) or not qs:
        return []
    out = []
    for i, q in enumerate(qs[:rounds]):
        if not isinstance(q, dict) or not str(q.get("title", "")).strip():
            return []
        t = q.get("type")
        out.append({"id": i,  # 服务端重排题号,不信 LLM 的编号
                    "type": t if t in VALID_TYPES else "基础",
                    "title": str(q["title"]).strip(),
                    "difficulty": q.get("difficulty", difficulty),
                    "key_points": q.get("key_points") or ["答出核心概念", "结合项目经历", "说出 trade-off"],
                    "followup_count": 0})
    return out

def judge_followup(question: dict, answer: str, already_followed: int) -> tuple[bool, str]:
    """返回 (是否追问, 追问问题). 答得浅(<60字或没命中采分点)且追问<2次则深挖."""
    if already_followed >= 2:
        return False, ""
    if USE_LLM:
        try:
            c = _client()
            p = f"""题:{question['title']}\n采分点:{question.get('key_points')}\n候选人回答:{answer}\n
判断回答是否太浅(没例子/没细节/没数据)。如果太浅返回JSON {{"need":true,"followup":"具体的深挖问题"}}否则 {{"need":false,"followup":""}}。只返回JSON。"""
            r = c.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": p}],
                                          response_format={"type": "json_object"}, temperature=0.3)
            d = json.loads(r.choices[0].message.content)
            return bool(d.get("need")), d.get("followup", "")
        except Exception:
            pass
    # 启发式兜底:短回答 / 缺数字 / 缺"因为/所以/项目"必追问
    shallow = len(answer) < 60 or not any(k in answer for k in ("项目", "因为", "所以", "数据", "优化", "%", "QPS", "源码", "实现"))
    if shallow:
        return True, f"你的回答偏概括,能结合具体项目/数据展开讲讲吗?针对「{question['title'][:20]}…」举一个你亲手做的例子?"
    return False, ""

def score_answer(question: dict, answer: str) -> tuple[int, str]:
    """LLM 打分 + 校准。LLM 普遍给分虚高(5 个字也能给 75),这里用长度/采分点做上限,
    保证评分有区分度、有据可依,而不是模型随口一个数。"""
    raw = None
    if USE_LLM:
        try:
            c = _client()
            p = f"""题:{question['title']}(类型{question['type']})\n回答:{answer}\n按0-100打分并一句话点评,只返回JSON {{"score":75,"comment":"..."}}"""
            r = c.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": p}],
                                          response_format={"type": "json_object"}, temperature=0.3)
            d = json.loads(r.choices[0].message.content)
            raw = (int(d.get("score", 65)), d.get("comment", "继续加油"))
        except Exception:
            raw = None
    if raw is None:
        l = len(answer)
        score = 55 + min(30, l // 10) + (5 if any(k in answer for k in ("数据", "%", "QPS", "源码")) else 0)
        comment = "回答有细节,建议补充量化数据。" if score >= 70 else "回答偏浅,建议补充项目实例和数据支撑。"
        return min(95, score), comment
    return calibrate(raw[0], raw[1], question, answer)


def calibrate(score: int, comment: str, question: dict, answer: str) -> tuple[int, str]:
    l = len(answer)
    hit = sum(1 for kp in (question.get("key_points") or []) if kp and kp[:2] in answer)
    caps = []
    if l < 10:
        caps.append((40, "回答过短,无法评估深度"))
    elif l < 30:
        caps.append((60, "回答偏短,缺少展开"))
    elif l < 80:
        caps.append((80, "回答长度一般,建议补充细节"))
    if hit == 0 and l < 120:
        caps.append((75, "未覆盖关键采分点"))
    for cap, reason in caps:
        if score > cap:
            score = cap
            comment = f"{comment}({reason})"
    return max(0, min(100, score)), comment

def build_report(position: str, qa: list) -> dict:
    """qa: [{question,type,answer,score,comment,followups}] -> 四维+总评"""
    dims = {"基础": [], "项目": [], "算法": [], "沟通": []}
    for item in qa:
        dims.get(item["type"], dims["基础"]).append(item["score"])
    scores = {k: (round(sum(v) / len(v)) if v else 65) for k, v in dims.items()}
    if USE_LLM:
        try:
            c = _client()
            p = f"""你是{position}面试官。成绩:{scores}。问答:{json.dumps(qa, ensure_ascii=False)[:4000]}
只返回JSON {{"overall":"200字总评","suggestions":["建议1","建议2","建议3"]}}"""
            r = c.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": p}],
                                          response_format={"type": "json_object"}, temperature=0.7)
            d = json.loads(r.choices[0].message.content)
            return {"scores": scores, "overall": d.get("overall", ""), "suggestions": d.get("suggestions", [])}
        except Exception:
            pass
    avg = sum(scores.values()) // 4
    overall = f"本次{position}模拟面试共 {len(qa)} 题,综合 {avg} 分。优势维度为 {max(scores, key=scores.get)},短板为 {min(scores, key=scores.get)}。建议多准备项目量化数据与高频手撕,回答按 STAR(背景-任务-行动-结果)组织。"
    suggestions = ["每个项目准备 3 个数字(规模/QPS/提升率)", "高频手撕每天 2 道,先说复杂度再写码", "回答用 STAR 结构,先结论后展开"]
    return {"scores": scores, "overall": overall, "suggestions": suggestions}
