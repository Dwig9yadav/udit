import React, { useState, useEffect } from 'react';
import { memoryAPI } from '../services/api';
import './MemoryInsights.css';

const MemoryInsights = () => {
  const [status, setStatus] = useState('loading'); // 'loading', 'connected', 'disconnected'
  const [memories, setMemories] = useState([]);
  const [loadingAction, setLoadingAction] = useState(false);
  const [testQuery, setTestQuery] = useState('');
  const [reflectResult, setReflectResult] = useState('');

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const res = await memoryAPI.status();
      if (res && res.enabled) {
        setStatus('connected');
        // Fetch some initial empty/random recall to test
        handleRecall('');
      } else {
        setStatus('disconnected');
      }
    } catch (err) {
      console.error("Memory status error:", err);
      setStatus('disconnected');
    }
  };

  const handleRecall = async (query = '') => {
    setLoadingAction(true);
    setReflectResult('');
    try {
      const res = await memoryAPI.recall(query, 10);
      if (res && res.result && res.result.memories) {
        setMemories(res.result.memories);
      } else {
        setMemories([]);
      }
    } catch (err) {
      console.error("Recall error:", err);
    } finally {
      setLoadingAction(false);
    }
  };

  const handleReflect = async () => {
    if (!testQuery.trim()) return;
    setLoadingAction(true);
    try {
      const mission = "You are a helpful AI memory assistant. Summarize what you know based on the query.";
      const res = await memoryAPI.reflect(testQuery, mission);
      if (res && res.result && (res.result.answer || res.result.text)) {
        setReflectResult(res.result.answer || res.result.text);
      } else if (res && res.result && res.result.ok === false) {
        setReflectResult("Hindsight engine failed: " + (res.result.error || "Unknown error"));
      }
    } catch (err) {
      console.error("Reflect error:", err);
      setReflectResult("Error connecting to Hindsight engine.");
    } finally {
      setLoadingAction(false);
    }
  };

  return (
    <div className="memory-insights-container">
      <div className="memory-header">
        <h2>🧠 Hindsight Memory Bank</h2>
        <div className={`status-badge ${status}`}>
          <span className="status-dot"></span>
          {status === 'loading' ? 'Checking connection...' : 
           status === 'connected' ? 'Connected to Hindsight' : 'Integration Disabled'}
        </div>
      </div>

      <div className="action-bar">
        <button 
          className="memory-btn" 
          onClick={() => handleRecall('')}
          disabled={loadingAction || status !== 'connected'}
        >
          🔄 Refresh Recent Memories
        </button>
        
        <div className="recall-section">
          <input 
            type="text" 
            className="recall-input" 
            placeholder="Search specific memories..." 
            value={testQuery}
            onChange={(e) => setTestQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleRecall(testQuery)}
            disabled={status !== 'connected'}
          />
          <button 
            className="memory-btn" 
            onClick={() => handleRecall(testQuery)}
            disabled={loadingAction || status !== 'connected'}
          >
            🔍 Recall
          </button>
        </div>
      </div>

      <div className="memory-grid">
        {memories.length > 0 ? (
          memories.map((mem, idx) => (
            <div key={mem.id || idx} className="memory-card">
              <div className="memory-card-header">
                <span className="memory-type">{mem.fact_type || 'Experience'}</span>
                <span>{mem.created_at ? new Date(mem.created_at).toLocaleDateString() : 'Just now'}</span>
              </div>
              <div className="memory-content">
                "{mem.content}"
              </div>
              {mem.metadata && mem.metadata.source === 'chat' && (
                <div className="memory-meta">
                  <span>Source: Chatroom</span>
                </div>
              )}
              {mem.metadata && mem.metadata.source === 'rag_search' && (
                <div className="memory-meta">
                  <span>Source: Document Search</span>
                  {mem.metadata.language && <span>Lang: {mem.metadata.language}</span>}
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="no-memories">
            {status === 'connected' ? 'No memories found. Try interacting with the chat or searching PDFs first!' : 'Connect Hindsight to view memory logs.'}
          </div>
        )}
      </div>

      {status === 'connected' && (
        <div className="reflect-box">
          <h3>Test AI Reflection</h3>
          <p>Ask a question about the user (e.g. "What did I search for today?"). The agent will use its memory bank to answer.</p>
          <div className="recall-section" style={{ marginTop: '10px' }}>
            <input 
              type="text" 
              className="recall-input" 
              placeholder="e.g. What is my favorite language?" 
              value={testQuery}
              onChange={(e) => setTestQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleReflect()}
            />
            <button 
              className="memory-btn" 
              onClick={handleReflect}
              disabled={loadingAction || !testQuery.trim()}
            >
              🤔 Reflect
            </button>
          </div>
          {reflectResult && (
            <div className="reflect-result">
              {reflectResult}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MemoryInsights;
