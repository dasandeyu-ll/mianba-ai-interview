import React, { useState } from 'react';
import { api } from './api';

export function ConfigPage({ onStart }) {
  const [position, setPosition] = useState('后端');
  const [difficulty, setDifficulty] = useState('中等');
  const [rounds, setRounds] = useState(8);
  const [jd, setJd] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const go = async () => {
    setLoading(true); setErr('');
    try {
      const data = await api.start(position, difficulty, rounds, jd);
      localStorage.setItem('mianba_session', data.session_id); // 断点续面凭证
      onStart(data);
    } catch (e) {
      setErr(e.message || '出题失败,请确认后端已启动');
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="card">
      <h1>🎯 面霸 · AI 模拟面试</h1>
      <p className="muted">选岗 → 面试 → 报告,8 题约 5 分钟</p>
      <label>岗位</label>
      <div className="row">{['后端', '前端', '算法'].map(p => <button key={p} className={position === p ? 'on' : ''} onClick={() => setPosition(p)}>{p}</button>)}</div>
      <label>难度</label>
      <div className="row">{['简单', '中等', '困难'].map(d => <button key={d} className={difficulty === d ? 'on' : ''} onClick={() => setDifficulty(d)}>{d}</button>)}</div>
      <label>轮数: {rounds} 题</label>
      <input type="range" min="3" max="12" value={rounds} onChange={e => setRounds(+e.target.value)} />
      <label>岗位 JD(选填,粘贴后 AI 围绕 JD 技术栈出题)</label>
      <textarea rows="3" value={jd} onChange={e => setJd(e.target.value)} placeholder="如:负责高并发交易系统,要求熟悉 Redis/MySQL/Kafka…" />
      <button className="primary" onClick={go} disabled={loading}>{loading ? 'AI 正在出题…' : '开始面试 →'}</button>
      {err && <div className="error">⚠️ {err}</div>}
    </div>
  );
}

export function InterviewPage({ session, startIndex = 0, onFinish }) {
  const qs = session.questions;
  const [idx, setIdx] = useState(Math.min(startIndex, qs.length - 1));
  const [typed, setTyped] = useState('');       // SSE 打字机逐字显示
  const [answer, setAnswer] = useState('');
  const [followups, setFollowups] = useState([]); // 追问气泡
  const [feedback, setFeedback] = useState('');
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState('');
  const [recording, setRecording] = useState(false);
  const recRef = React.useRef(null); // Web Speech 识别实例,用 ref 才能读到最新 state

  const toggleRecord = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setErr('当前浏览器不支持语音识别(建议用 Chrome/Edge),请直接打字作答'); return; }
    if (recording && recRef.current) { recRef.current.stop(); return; }
    try {
      const r = new SR();
      r.lang = 'zh-CN'; r.continuous = true; r.interimResults = false;
      let base = answer;
      r.onresult = e => {
        let text = '';
        for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) text += e.results[i][0].transcript;
        if (text) setAnswer(base + text);
      };
      r.onerror = ev => setErr('语音识别失败: ' + ev.error);
      r.onend = () => setRecording(false);
      recRef.current = r; r.start(); setRecording(true);
    } catch (e) { setErr('无法启动录音: ' + e.message); }
  };
  React.useEffect(() => () => recRef.current && recRef.current.stop(), []);

  React.useEffect(() => { playQuestion(idx); }, []);
  const playQuestion = (i) => {
    setTyped(''); setFollowups([]); setFeedback('');
    // 用 SSE 实际播出的题面朗读,而不是本地 qs[i] —— 断点续面时两者可能不一致
    api.streamQuestion(session.session_id,
      ch => setTyped(t => t + ch),
      (fullText) => api.speak(fullText || qs[i]?.title || ''));
  };
  const submit = async () => {
    if (!answer.trim() || sending) return;
    setSending(true); setErr('');
    try {
      const res = await api.answer(session.session_id, answer);
      setFeedback(`实时评分 ${res.realtime_score} 分:${res.comment}`);
      setAnswer('');
      if (res.finished) { onFinish(session.session_id); return; }
      if (res.need_followup) {
        // 追问:停在同一题,追加黄色追问气泡并语音播报
        setFollowups(f => [...f, res.followup_question]);
        api.speak(res.followup_question);
      } else {
        const ni = idx + 1; setIdx(ni); playQuestion(ni);
      }
    } catch (e) {
      setErr(e.message || '提交失败');
    } finally {
      setSending(false);
    }
  };
  return (
    <div className="layout">
      <div className="left">
        <div className="video-mock">🤖 AI 面试官<div className="live">● 面试中</div></div>
        <div className="qbox"><b>Q{idx + 1}.</b> {typed}<span className="cursor">▍</span></div>
        {followups.map((f, i) => <div key={i} className="followup">🔍 追问: {f}</div>)}
        {feedback && <div className="feedback">{feedback}</div>}
        <textarea rows="4" value={answer} onChange={e => setAnswer(e.target.value)} placeholder="输入或语音作答(≥60字、带项目/数据可避免被追问)…" />
        <div className="row audio">
          <button type="button" className={recording ? 'rec' : ''} onClick={toggleRecord} disabled={sending}>
            {recording ? '⏹ 录音中,点击结束' : '🎤 语音作答'}
          </button>
          <span className="muted">{answer.trim().length} 字{answer.trim().length > 0 && answer.trim().length < 60 ? ' · 偏短,可能被追问' : ''}</span>
        </div>
        {err && <div className="error">⚠️ {err}</div>}
        <button className="primary" onClick={submit} disabled={sending}>{sending ? '评分中…' : '提交回答'}</button>
      </div>
      <div className="right"><h3>进度 {Math.min(idx + 1, qs.length)}/{qs.length}</h3>
        <progress value={idx} max={qs.length} />
        {qs.map((q, i) => <div key={i} className={i < idx ? 'done' : i === idx ? 'now' : ''}>{i < idx ? '✅' : i === idx ? '👉' : '⬜'} {q.title.slice(0, 14)}…</div>)}
      </div>
    </div>
  );
}

export function ReportPage({ sessionId }) {
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState('');
  React.useEffect(() => {
    api.report(sessionId).then(setRep).catch(e => setErr(e.message || '报告生成失败'));
  }, [sessionId]);
  if (err) return <div className="card">⚠️ {err}</div>;
  if (!rep) return <div className="card">AI 正在写报告…</div>;
  const option = {
    radar: { indicator: ['基础', '项目', '算法', '沟通'].map(k => ({ name: k, max: 100 })), shape: 'polygon' },
    series: [{ type: 'radar', data: [{ value: ['基础', '项目', '算法', '沟通'].map(k => rep.scores[k] ?? 65), name: '能力' }], areaStyle: {} }],
  };
  return (
    <div className="card wide" id="report">
      <h2>📊 面试报告</h2>
      <React.Suspense fallback={<div className="muted">图表加载中…</div>}>
        <div style={{ height: 300 }}><LazyRadar option={option} /></div>
      </React.Suspense>
      <div className="scores">{Object.entries(rep.scores).map(([k, v]) => <span key={k}>{k}: <b>{v}</b></span>)}</div>
      <p>{rep.overall}</p>
      <h3>改进建议</h3><ul>{rep.suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul>
      <h3>每题点评</h3>
      {rep.per_question.map((q, i) => (
        <div key={i} className="review"><b>Q{i + 1} {q.question}</b> —— {q.score} 分<div className="muted">{q.comment}</div>
          {q.followups?.map((f, j) => <div key={j} className="followup">追问{j + 1}: {f}</div>)}</div>
      ))}
      <button className="primary" onClick={() => window.print()}>导出 PDF(打印→另存为 PDF)</button>
    </div>
  );
}
// ECharts 整包较大,只在报告页按需加载,配置页/面试页首屏不带它
const LazyRadar = React.lazy(() => import('echarts-for-react'));
