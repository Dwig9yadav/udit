/**
 * TestGenerator.js - AI Exam Mode component for EduRag.
 *
 * Allows students to generate AI-powered tests (MCQs, short & long questions)
 * from an indexed PDF using the Gemini RAG backend.
 */
import React, { useState, useEffect } from 'react';
import { ragAPI } from '../services/api';
import './TestGenerator.css';

const TestGenerator = () => {
  const [pdfs, setPdfs] = useState([]);
  const [selectedPdfId, setSelectedPdfId] = useState('');
  const [difficulty, setDifficulty] = useState('medium');
  const [loading, setLoading] = useState(false);
  const [loadingPdfs, setLoadingPdfs] = useState(true);
  const [testData, setTestData] = useState(null);
  const [error, setError] = useState('');
  const [userAnswers, setUserAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [score, setScore] = useState(null);

  useEffect(() => {
    const fetchPdfs = async () => {
      try {
        const data = await ragAPI.getPDFs();
        const indexed = (data || []).filter(p => p.status === 'indexed');
        setPdfs(indexed);
      } catch (err) {
        setError('Failed to load PDFs. Please refresh.');
      } finally {
        setLoadingPdfs(false);
      }
    };
    fetchPdfs();
  }, []);

  const handleGenerateTest = async () => {
    if (!selectedPdfId) {
      setError('Please select a PDF to generate a test from.');
      return;
    }
    setError('');
    setTestData(null);
    setUserAnswers({});
    setSubmitted(false);
    setScore(null);
    setLoading(true);

    try {
      const result = await ragAPI.generateTest(parseInt(selectedPdfId), difficulty);
      setTestData(result);
    } catch (err) {
      setError(err.message || 'Failed to generate test. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerSelect = (questionIndex, option) => {
    if (submitted) return;
    setUserAnswers(prev => ({ ...prev, [questionIndex]: option }));
  };

  const handleSubmitTest = () => {
    if (!testData) return;
    let correct = 0;
    testData.mcqs.forEach((mcq, idx) => {
      if (userAnswers[idx] === mcq.answer) correct++;
    });
    setScore({ correct, total: testData.mcqs.length });
    setSubmitted(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleReset = () => {
    setTestData(null);
    setUserAnswers({});
    setSubmitted(false);
    setScore(null);
    setError('');
  };

  const getOptionClass = (questionIndex, option, correctAnswer) => {
    if (!submitted) {
      return userAnswers[questionIndex] === option ? 'option-btn selected' : 'option-btn';
    }
    if (option === correctAnswer) return 'option-btn correct';
    if (userAnswers[questionIndex] === option && option !== correctAnswer) return 'option-btn wrong';
    return 'option-btn';
  };

  return (
    <div className="test-generator-container">
      {/* --- Header --- */}
      <div className="tg-header">
        <div className="tg-header-icon">🎓</div>
        <div>
          <h2 className="tg-title">AI Exam Mode</h2>
          <p className="tg-subtitle">Generate a smart test from your course PDFs using Gemini AI</p>
        </div>
      </div>

      {/* --- Score Banner (after submission) --- */}
      {submitted && score !== null && (
        <div className={`score-banner ${score.correct === score.total ? 'perfect' : score.correct >= score.total / 2 ? 'good' : 'retry'}`}>
          <span className="score-emoji">
            {score.correct === score.total ? '🏆' : score.correct >= score.total / 2 ? '👍' : '📚'}
          </span>
          <div>
            <p className="score-main">You scored <strong>{score.correct}/{score.total}</strong> on MCQs</p>
            <p className="score-sub">
              {score.correct === score.total
                ? 'Perfect score! Outstanding performance!'
                : score.correct >= score.total / 2
                  ? 'Good effort! Review the highlighted questions.'
                  : 'Keep practicing — review the correct answers below.'}
            </p>
          </div>
          <button className="retry-btn" onClick={handleReset}>🔄 Try Again</button>
        </div>
      )}

      {/* --- Controls Panel --- */}
      {!testData && (
        <div className="tg-controls-card">
          <div className="tg-controls-grid">
            <div className="tg-field">
              <label className="tg-label">📄 Select PDF</label>
              {loadingPdfs ? (
                <div className="tg-skeleton" />
              ) : (
                <select
                  className="tg-select"
                  value={selectedPdfId}
                  onChange={e => setSelectedPdfId(e.target.value)}
                >
                  <option value="">-- Choose an indexed PDF --</option>
                  {pdfs.map(pdf => (
                    <option key={pdf.id} value={pdf.id}>{pdf.filename}</option>
                  ))}
                </select>
              )}
              {!loadingPdfs && pdfs.length === 0 && (
                <p className="tg-hint">⚠️ No indexed PDFs available. Ask your teacher to upload and index one.</p>
              )}
            </div>

            <div className="tg-field">
              <label className="tg-label">⚡ Difficulty Level</label>
              <div className="difficulty-pills">
                {['easy', 'medium', 'hard'].map(level => (
                  <button
                    key={level}
                    className={`diff-pill ${difficulty === level ? 'active ' + level : ''}`}
                    onClick={() => setDifficulty(level)}
                  >
                    {level === 'easy' ? '🌱 Easy' : level === 'medium' ? '🔥 Medium' : '⚡ Hard'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {error && <div className="tg-error">{error}</div>}

          <button
            className="tg-generate-btn"
            onClick={handleGenerateTest}
            disabled={loading || !selectedPdfId}
          >
            {loading ? (
              <span className="btn-loading">
                <span className="spinner" /> Generating Test...
              </span>
            ) : '✨ Generate Test'}
          </button>
        </div>
      )}

      {/* --- Loading Skeleton --- */}
      {loading && (
        <div className="tg-loading-panel">
          <div className="ai-thinking">
            <div className="thinking-dots">
              <span /><span /><span />
            </div>
            <p>Gemini AI is reading your PDF and crafting questions...</p>
          </div>
        </div>
      )}

      {/* --- Test Content --- */}
      {testData && !loading && (
        <div className="test-content">
          <div className="test-meta-bar">
            <span>📄 {pdfs.find(p => String(p.id) === String(selectedPdfId))?.filename || 'PDF'}</span>
            <span>⚡ {difficulty.charAt(0).toUpperCase() + difficulty.slice(1)}</span>
            <span>📝 {testData.mcqs?.length || 0} MCQs · {testData.short_questions?.length || 0} Short · {testData.long_questions?.length || 0} Long</span>
            {!submitted && (
              <button className="tg-reset-link" onClick={handleReset}>← Generate New Test</button>
            )}
          </div>

          {/* MCQs Section */}
          {testData.mcqs?.length > 0 && (
            <section className="test-section">
              <div className="section-header mcq-header">
                <span className="section-icon">🔘</span>
                <h3>Part A — Multiple Choice Questions</h3>
                <span className="section-badge">{testData.mcqs.length} Questions</span>
              </div>
              <div className="questions-list">
                {testData.mcqs.map((mcq, idx) => (
                  <div key={idx} className={`question-card ${submitted ? (userAnswers[idx] === mcq.answer ? 'q-correct' : 'q-wrong') : ''}`}>
                    <p className="q-number">Q{idx + 1}</p>
                    <p className="q-text">{mcq.question}</p>
                    <div className="options-grid">
                      {mcq.options.map((option, oIdx) => (
                        <button
                          key={oIdx}
                          className={getOptionClass(idx, option, mcq.answer)}
                          onClick={() => handleAnswerSelect(idx, option)}
                        >
                          <span className="option-label">{String.fromCharCode(65 + oIdx)}</span>
                          {option}
                        </button>
                      ))}
                    </div>
                    {submitted && (
                      <div className="answer-reveal">
                        <span className="correct-tag">✓ Correct Answer:</span> {mcq.answer}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Short Questions Section */}
          {testData.short_questions?.length > 0 && (
            <section className="test-section">
              <div className="section-header short-header">
                <span className="section-icon">✏️</span>
                <h3>Part B — Short Answer Questions</h3>
                <span className="section-badge">{testData.short_questions.length} Questions</span>
              </div>
              <div className="questions-list">
                {testData.short_questions.map((q, idx) => (
                  <div key={idx} className="question-card short-q">
                    <p className="q-number">Q{(testData.mcqs?.length || 0) + idx + 1}</p>
                    <p className="q-text">{q}</p>
                    <textarea
                      className="short-answer-box"
                      placeholder="Write your answer here (2–4 sentences)..."
                      rows={3}
                    />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Long Questions Section */}
          {testData.long_questions?.length > 0 && (
            <section className="test-section">
              <div className="section-header long-header">
                <span className="section-icon">📝</span>
                <h3>Part C — Long Answer Questions</h3>
                <span className="section-badge">{testData.long_questions.length} Questions</span>
              </div>
              <div className="questions-list">
                {testData.long_questions.map((q, idx) => (
                  <div key={idx} className="question-card long-q">
                    <p className="q-number">Q{(testData.mcqs?.length || 0) + (testData.short_questions?.length || 0) + idx + 1}</p>
                    <p className="q-text">{q}</p>
                    <textarea
                      className="long-answer-box"
                      placeholder="Write a detailed answer here (minimum 5–8 sentences)..."
                      rows={6}
                    />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Submit Button */}
          {!submitted && (
            <div className="submit-row">
              <button
                className="tg-submit-btn"
                onClick={handleSubmitTest}
                disabled={Object.keys(userAnswers).length < (testData.mcqs?.length || 0)}
              >
                🎯 Submit & Check MCQ Answers
                {Object.keys(userAnswers).length < (testData.mcqs?.length || 0) && (
                  <span className="submit-hint"> ({Object.keys(userAnswers).length}/{testData.mcqs?.length} answered)</span>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TestGenerator;
