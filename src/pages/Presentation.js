import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import './Presentation.css';

const slides = [
  {
    title: "EduRag",
    subtitle: "AI-Powered Educational RAG Platform. Bridging the gap between static documents and dynamic knowledge.",
    content: (
      <div className="tech-badges">
        <span className="tech-badge">Gemini AI</span>
        <span className="tech-badge">FastAPI</span>
        <span className="tech-badge">React</span>
        <span className="tech-badge">Supabase</span>
      </div>
    )
  },
  {
    title: "The Problem",
    subtitle: "Students and teachers are overwhelmed by scattered PDFs. Manual searching is slow, and extracting insights from technical documents is difficult.",
    content: (
      <div className="feature-grid">
        <div className="feature-card">
          <h3>Information Overload</h3>
          <p>Too many documents, not enough time to read them all.</p>
        </div>
        <div className="feature-card">
          <h3>Knowledge Silos</h3>
          <p>Important insights are buried deep within long PDFs.</p>
        </div>
      </div>
    )
  },
  {
    title: "The Solution",
    subtitle: "EduRag uses Retrieval-Augmented Generation (RAG) to transform static PDFs into an interactive knowledge base.",
    content: (
      <div className="feature-grid">
        <div className="feature-card">
          <h3>Semantic Search</h3>
          <p>Ask questions in plain English (or Hindi/Hinglish) and get direct answers.</p>
        </div>
        <div className="feature-card">
          <h3>Source Citations</h3>
          <p>Every answer includes direct links to the source document and page.</p>
        </div>
      </div>
    )
  },
  {
    title: "Student Experience",
    subtitle: "Empowering learners with AI-driven discovery and collaboration tools.",
    content: (
      <div className="feature-grid">
        <div className="feature-card">
          <h3>Adaptive Study Plans</h3>
          <p>AI-generated 7-day schedules tailored to specific topics.</p>
        </div>
        <div className="feature-card">
          <h3>Peer Buddy Discovery</h3>
          <p>Connect with classmates studying similar topics for collaborative learning.</p>
        </div>
      </div>
    )
  },
  {
    title: "Teacher Dashboard",
    subtitle: "Data-driven insights to help educators understand student needs better.",
    content: (
      <div className="feature-grid">
        <div className="feature-card">
          <h3>Trending Topics</h3>
          <p>See what students are searching for in real-time to identify knowledge gaps.</p>
        </div>
        <div className="feature-card">
          <h3>Content Indexing</h3>
          <p>Easily upload and vector-index new curriculum materials in seconds.</p>
        </div>
      </div>
    )
  },
  {
    title: "Technical Excellence",
    subtitle: "A modern, scalable architecture built for performance and security.",
    content: (
      <div className="feature-grid">
        <div className="feature-card">
          <h3>Hybrid Search</h3>
          <p>Combines vector similarity with keyword fallback for 100% reliability.</p>
        </div>
        <div className="feature-card">
          <h3>RBAC Security</h3>
          <p>Strict Role-Based Access Control for Students, Teachers, and Admins.</p>
        </div>
      </div>
    )
  },
  {
    title: "The Future",
    subtitle: "Expanding the horizons of AI-integrated education.",
    content: (
      <div className="tech-badges">
        <span className="tech-badge">Google OAuth</span>
        <span className="tech-badge">Mobile App</span>
        <span className="tech-badge">Video Analysis</span>
        <span className="tech-badge">Real-time Collaboration</span>
      </div>
    )
  }
];

const Presentation = () => {
  const [currentSlide, setCurrentSlide] = useState(0);
  const navigate = useNavigate();

  const nextSlide = () => {
    if (currentSlide < slides.length - 1) {
      setCurrentSlide(prev => prev + 1);
    }
  };

  const prevSlide = () => {
    if (currentSlide > 0) {
      setCurrentSlide(prev => prev - 1);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ') nextSlide();
      if (e.key === 'ArrowLeft') prevSlide();
      if (e.key === 'Escape') navigate('/');
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentSlide]);

  return (
    <div className="presentation-container">
      <button className="close-btn" onClick={() => navigate('/')}>×</button>
      
      <AnimatePresence mode="wait">
        <motion.div
          key={currentSlide}
          initial={{ opacity: 0, x: 100 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -100 }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
          className="slide"
        >
          <div className="slide-content">
            <h1 className="presentation-title">{slides[currentSlide].title}</h1>
            <p className="presentation-subtitle">{slides[currentSlide].subtitle}</p>
            {slides[currentSlide].content}
          </div>
        </motion.div>
      </AnimatePresence>

      <div className="progress-bar">
        <div 
          className="progress-fill" 
          style={{ width: `${((currentSlide + 1) / slides.length) * 100}%` }}
        ></div>
      </div>

      <div className="nav-controls">
        <button className="nav-btn" onClick={prevSlide} disabled={currentSlide === 0}>
          ←
        </button>
        <span style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
          {currentSlide + 1} / {slides.length}
        </span>
        <button className="nav-btn" onClick={nextSlide} disabled={currentSlide === slides.length - 1}>
          →
        </button>
      </div>
    </div>
  );
};

export default Presentation;
