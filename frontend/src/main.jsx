import React, { useState } from 'react';
import ReactDOM from 'react-dom/client';
import './style.css';
import { ConfigPage, InterviewPage, ReportPage } from './pages';
import { api } from './api';

function App() {
  // 支持 ?report=<session_id> 直达报告页,方便把报告链接直接分享/截图
  const urlReport = new URLSearchParams(location.search).get('report') || '';
  const [step, setStep] = useState(urlReport ? 'report' : 'config');
  const [session, setSession] = useState(null);
  const [startIndex, setStartIndex] = useState(0);
  const [sid, setSid] = useState(urlReport || localStorage.getItem('mianba_session') || '');
  const [resumeInfo, setResumeInfo] = useState(null);

  // 有旧 session_id 就查一下状态,支持断点续面(刷新页面不丢进度)
  React.useEffect(() => {
    if (!sid) return;
    api.state(sid).then(s => {
      if (s && s.status === 'ongoing' && s.current_index > 0) setResumeInfo(s);
    }).catch(() => {});
  }, []);

  const resume = () => {
    setSession({ session_id: resumeInfo.session_id, questions: resumeInfo.questions, total: resumeInfo.total });
    setStartIndex(resumeInfo.current_index);
    setResumeInfo(null);
    setStep('interview');
  };

  return (
    <div className="wrap">
      {step === 'config' && <>
        {resumeInfo && (
          <div className="card resume">
            检测到上次面试进度 {resumeInfo.progress}（{resumeInfo.position}·{resumeInfo.difficulty}）
            <button className="primary" onClick={resume}>继续面试 →</button>
          </div>
        )}
        <ConfigPage onStart={(s) => { setSession(s); setSid(s.session_id); setStartIndex(0); setStep('interview'); }} />
      </>}
      {step === 'interview' && session && <InterviewPage session={session} startIndex={startIndex} onFinish={(id) => { setSid(id); setStep('report'); }} />}
      {step === 'report' && <ReportPage sessionId={sid} />}
    </div>
  );
}
// 语音播报默认关闭;演示时在浏览器控制台执行 __speech_on() 开启、__speech_off() 关闭
if (typeof window !== 'undefined') {
  window.__speech_on = () => api.setSpeech(true);
  window.__speech_off = () => api.setSpeech(false);
}
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
