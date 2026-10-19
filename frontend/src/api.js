async function postJSON(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `请求失败(${r.status})`);
  return data;
}

export const api = {
  start(position, difficulty, rounds, jd = '') {
    return postJSON('/api/interview/start', { position, difficulty, rounds, jd });
  },
  streamQuestion(sessionId, onToken, onDone) {
    // onDone(fullText):把 SSE 收到的完整题面回传,调用方用它做语音播报,避免与本地题序不一致
    const es = new EventSource(`/api/interview/stream?session_id=${sessionId}`);
    let full = '';
    es.addEventListener('token', e => { const ch = JSON.parse(e.data).ch; full += ch; onToken(ch); });
    es.addEventListener('done', () => { es.close(); onDone(full); });
    es.onerror = () => { es.close(); onDone(full); };
    return es;
  },
  answer(session_id, answer) {
    return postJSON('/api/interview/answer', { session_id, answer });
  },
  report(session_id) {
    return postJSON('/api/interview/report', { session_id });
  },
  async state(session_id) {
    const r = await fetch(`/api/interview/state?session_id=${session_id}`);
    if (!r.ok) return null; // 旧 session 不存在就当没有,不打断首页
    return r.json();
  },
  speak(text) {
    // Web Speech 免费离线可用;对比接云厂商 TTS:零成本零延迟,演示最稳
    try { speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.lang = 'zh-CN'; u.rate = 1.05; speechSynthesis.speak(u); } catch {}
  },
};
