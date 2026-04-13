import React, { useState, useEffect } from 'react';
import { ragAPI } from '../services/api';

/**
 * Logbook to show read-only data about all uploaded PDFs.
 */
const PdfLogBook = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await ragAPI.getPdfLogbook();
      setLogs(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch PDF logbook');
    } finally {
      setLoading(false);
    }
  };

  // Filter logs locally based on search term
  const filteredLogs = logs.filter(log => 
    log.title.toLowerCase().includes(searchTerm.toLowerCase()) || 
    log.faculty_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="pdf-logbook-container fade-in">
      <div className="pdf-logbook-header">
        <h2><span className="logbook-icon">🗂️</span> PDF Log Book</h2>
        <p>Directory of all indexed course material across the platform.</p>
      </div>

      {/* Action Bar */}
      <div className="pdf-logbook-actions">
        <div className="search-wrapper">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            className="logbook-search-input"
            placeholder="Search by PDF Name or Faculty..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        
        <button 
          className="refresh-log-btn"
          onClick={fetchLogs}
          disabled={loading}
        >
          {loading ? '🔄 Refreshing...' : '🔄 Refresh Log'}
        </button>
      </div>

      {/* Main Content Area */}
      <div className="pdf-logbook-content">
        {loading ? (
          <div className="logbook-state-card">
            <div className="spinner-icon">⚙️</div>
            <p>Fetching PDFs securely...</p>
          </div>
        ) : error ? (
          <div className="logbook-state-card error-card">
            <h3>Error Loading Logs</h3>
            <p>{error}</p>
            <button className="error-retry-btn" onClick={fetchLogs}>Try Again</button>
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="logbook-state-card empty-card">
            <div className="empty-icon">📭</div>
            <h3>No PDFs Found</h3>
            <p>
              {searchTerm 
                ? `No results matching "${searchTerm}".` 
                : "The log book is currently empty. Wait for faculty to upload materials."}
            </p>
          </div>
        ) : (
          <div className="logbook-table-container custom-scrollbar">
            <table className="logbook-table">
              <thead>
                <tr>
                  <th>📄 PDF Name</th>
                  <th>👨‍🏫 Faculty Name</th>
                  <th>⏱ Uploaded Time</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log) => (
                  <tr key={log.id}>
                    <td>
                      <div className="pdf-name-cell">
                        <div className="pdf-doc-icon">📑</div>
                        <span>{log.title}</span>
                      </div>
                    </td>
                    <td>
                      <span className="faculty-badge">{log.faculty_name}</span>
                    </td>
                    <td className="time-cell">
                      {new Date(log.uploaded_at).toLocaleString('en-US', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default PdfLogBook;
