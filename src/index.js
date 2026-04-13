/**
 * index.js - React application bootstrap for MINI-RAG frontend.
 *
 * Renders the App component into the root DOM node.
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
