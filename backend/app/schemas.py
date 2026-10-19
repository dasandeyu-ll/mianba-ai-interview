from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class Position(str, Enum):
    backend = "后端"
    frontend = "前端"
    algorithm = "算法"

class Difficulty(str, Enum):
    easy = "简单"
    medium = "中等"
    hard = "困难"

class QuestionType(str, Enum):
    basic = "基础"
    project = "项目"
    algorithm = "算法"
    communication = "沟通"

class Question(BaseModel):
    id: int = Field(description="题号,从0开始")
    type: QuestionType = Field(description="题目类型,四维之一")
    title: str = Field(description="题干")
    difficulty: str = Field(description="难度")
    key_points: List[str] = Field(default_factory=list, description="采分点,用于追问和评分")
    followup_count: int = Field(default=0, description="该题已被追问次数")

class StartRequest(BaseModel):
    position: str = Field(examples=["后端"])
    difficulty: str = Field(default="中等", examples=["中等"])
    rounds: int = Field(default=8, ge=3, le=12)
    # 可选 JD:粘贴岗位描述后,出题会围绕 JD 关键词,相当于轻量 RAG(不做向量库,直接进提示词)
    jd: str = Field(default="", examples=["负责高并发交易系统..."])

class StartResponse(BaseModel):
    session_id: str
    questions: List[Question]
    total: int

class AnswerRequest(BaseModel):
    session_id: str
    answer: str = Field(min_length=1)

class AnswerResponse(BaseModel):
    need_followup: bool
    followup_question: Optional[str] = None
    next_question: Optional[Question] = None
    finished: bool = False
    progress: str = Field(examples=["3/8"])
    done_count: int
    total: int
    realtime_score: int
    comment: str

class PerQuestionReview(BaseModel):
    question: str
    answer: str
    score: int
    comment: str
    followups: List[str] = []

class ReportResponse(BaseModel):
    scores: dict  # {基础:xx, 项目:xx, 算法:xx, 沟通:xx}
    per_question: List[PerQuestionReview]
    overall: str
    suggestions: List[str]
