import React, { useState } from 'react';
import ReactDOM from 'react-dom/client';
import './style.css';
import { ConfigPage, InterviewPage, ReportPage } from './pages';
import { api } from './api';

function App() {
  const [step, setStep] = useState('config');
  const [session, setSession] = useState(null);
  const [startIndex, setStartIndex] = useState(0);
  const [sid, setSid] = useState(localStorage.getItem('mianba_session') || '');
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
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
