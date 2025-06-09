import React, { useState, useEffect } from 'react';
import './CostTracker.css';

const CostTracker = () => {
  const [usageData, setUsageData] = useState(null);
  const [dailyData, setDailyData] = useState([]);
  const [typeData, setTypeData] = useState([]);
  const [limitsData, setLimitsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    fetchUsageData();
  }, []);

  const fetchUsageData = async () => {
    try {
      setLoading(true);
      
      // Fetch all usage data
      const [overallRes, dailyRes, typeRes, limitsRes] = await Promise.all([
        fetch('/api/cost/usage/overall'),
        fetch('/api/cost/usage/daily?days=7'),
        fetch('/api/cost/usage/by-type'),
        fetch('/api/cost/limits/check')
      ]);

      const [overall, daily, byType, limits] = await Promise.all([
        overallRes.json(),
        dailyRes.json(),
        typeRes.json(),
        limitsRes.json()
      ]);

      setUsageData(overall.data);
      setDailyData(daily.data);
      setTypeData(byType.data);
      setLimitsData(limits.data);
      setError(null);
    } catch (err) {
      console.error('Error fetching usage data:', err);
      setError('Failed to load usage data');
    } finally {
      setLoading(false);
    }
  };

  const formatCost = (cost) => {
    return `$${cost.toFixed(4)}`;
  };

  const formatTokens = (tokens) => {
    return tokens.toLocaleString();
  };

  if (loading) {
    return (
      <div className="cost-tracker">
        <div className="loading">Loading usage data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="cost-tracker">
        <div className="error">
          <p>{error}</p>
          <button onClick={fetchUsageData}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="cost-tracker">
      <div className="cost-tracker-header">
        <h2>API Usage & Cost Tracking</h2>
        <button onClick={fetchUsageData} className="refresh-btn">
          Refresh
        </button>
      </div>

      {/* Warnings */}
      {limitsData && limitsData.warnings.length > 0 && (
        <div className="warnings">
          <h3>⚠️ Usage Warnings</h3>
          {limitsData.warnings.map((warning, index) => (
            <div key={index} className="warning-item">
              {warning}
            </div>
          ))}
        </div>
      )}

      {/* Tab Navigation */}
      <div className="tab-navigation">
        <button 
          className={activeTab === 'overview' ? 'active' : ''}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button 
          className={activeTab === 'daily' ? 'active' : ''}
          onClick={() => setActiveTab('daily')}
        >
          Daily Usage
        </button>
        <button 
          className={activeTab === 'by-type' ? 'active' : ''}
          onClick={() => setActiveTab('by-type')}
        >
          By Query Type
        </button>
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        {activeTab === 'overview' && usageData && (
          <div className="overview-tab">
            <div className="stats-grid">
              <div className="stat-card">
                <h3>Total Cost</h3>
                <div className="stat-value">{formatCost(usageData.total_cost)}</div>
              </div>
              <div className="stat-card">
                <h3>Total Tokens</h3>
                <div className="stat-value">{formatTokens(usageData.total_tokens)}</div>
              </div>
              <div className="stat-card">
                <h3>Total Requests</h3>
                <div className="stat-value">{usageData.total_requests}</div>
              </div>
              <div className="stat-card">
                <h3>Avg Cost/Request</h3>
                <div className="stat-value">
                  {usageData.total_requests > 0 
                    ? formatCost(usageData.total_cost / usageData.total_requests)
                    : '$0.0000'
                  }
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'daily' && (
          <div className="daily-tab">
            <h3>Last 7 Days Usage</h3>
            <div className="daily-chart">
              {dailyData.map((day, index) => (
                <div key={index} className="daily-item">
                  <div className="daily-date">{day.date}</div>
                  <div className="daily-stats">
                    <span>Cost: {formatCost(day.total_cost)}</span>
                    <span>Tokens: {formatTokens(day.total_tokens)}</span>
                    <span>Requests: {day.total_requests}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'by-type' && (
          <div className="by-type-tab">
            <h3>Usage by Query Type</h3>
            <div className="type-stats">
              {typeData.map((type, index) => (
                <div key={index} className="type-item">
                  <div className="type-header">
                    <h4>{type.query_type}</h4>
                    <span className="type-cost">{formatCost(type.total_cost)}</span>
                  </div>
                  <div className="type-details">
                    <span>Tokens: {formatTokens(type.total_tokens)}</span>
                    <span>Requests: {type.total_requests}</span>
                    <span>Avg Cost: {formatCost(type.avg_cost_per_request)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Current Limits */}
      {limitsData && (
        <div className="limits-info">
          <h3>Current Usage vs Limits</h3>
          <div className="limits-grid">
            <div className="limit-item">
              <span>Today's Cost:</span>
              <span>{formatCost(limitsData.current_usage.today_cost)} / {formatCost(limitsData.limits.daily_cost_limit)}</span>
            </div>
            <div className="limit-item">
              <span>Today's Tokens:</span>
              <span>{formatTokens(limitsData.current_usage.today_tokens)} / {formatTokens(limitsData.limits.daily_token_limit)}</span>
            </div>
            <div className="limit-item">
              <span>Total Cost:</span>
              <span>{formatCost(limitsData.current_usage.total_cost)} / {formatCost(limitsData.limits.monthly_cost_limit)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CostTracker;