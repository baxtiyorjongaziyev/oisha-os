import { useState, useEffect } from 'react'
import './App.css'

interface Summary {
  amount_spent: number;
  revenue: number;
  roas: number;
  cac: number;
  conversion_rate: number;
  deal_time: string;
  arpl: number;
  revenue_growth: number;
}

interface AdSet {
  name: string;
  spend: number;
  impressions: number;
  frequency: number;
  clicks: number;
  ctr: number;
  cpm: number;
  cpc: number;
  leads: number;
  cpl: number;
  q_leads: number;
  ql_percentage: number;
  cpql: number;
  purchases: number;
  cost_per_purchase: number;
  revenue: number;
  roas: number;
  status: string;
}

interface DashboardData {
  summary: Summary;
  ad_sets: AdSet[];
}

function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [authStatus, setAuthStatus] = useState<boolean | null>(null);

  useEffect(() => {
    // Check auth status first
    fetch('http://localhost:8000/api/auth/status')
      .then(res => res.json())
      .then(auth => {
        setAuthStatus(auth.connected);
        if (auth.connected) {
          fetchData();
        } else {
          setLoading(false);
        }
      })
      .catch(err => {
        console.error("Auth check failed", err);
        setLoading(false);
      });
  }, []);

  const fetchData = () => {
    fetch('http://localhost:8000/api/performance')
      .then(res => res.json())
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  };

  if (loading) return <div className="loading">Ma'lumotlar yuklanmoqda...</div>;

  if (authStatus === false) {
    return (
      <div className="dashboard-container" style={{ textAlign: 'center', paddingTop: '100px' }}>
        <h1>Marketing OS ga xush kelibsiz</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: '30px' }}>Haqiqiy ma'lumotlarni ko'rish uchun Meta akkauntingizni ulang.</p>
        <a 
          href="http://localhost:8000/api/auth/login" 
          style={{
            background: '#1877F2',
            color: 'white',
            padding: '12px 24px',
            borderRadius: '8px',
            textDecoration: 'none',
            fontWeight: 'bold',
            display: 'inline-block'
          }}
        >
          Connect Meta / Instagram
        </a>
      </div>
    );
  }

  if (!data) return <div className="error">API bilan ulanishda xatolik yuz berdi. Backend serverni tekshiring.</div>;

  return (
    <div className="dashboard-container">
      <div className="header">
        <div>
          <h1>Marketing Analytics</h1>
          <p>Ad performance overview (Meta Ads + AmoCRM)</p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <div className="date-badge">
            1 May 2026 - 31 May 2026
          </div>
          <button 
            onClick={() => {
              fetch('http://localhost:8000/api/auth/logout').then(() => window.location.reload());
            }}
            style={{
              background: '#ef4444',
              color: 'white',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 600
            }}
          >
            Chiqish
          </button>
        </div>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-title">Amount Spent</div>
          <div className="kpi-value">${data.summary.amount_spent.toLocaleString()}</div>
        </div>
        <div className="kpi-card span-2">
          <div className="kpi-title">Revenue</div>
          <div className="kpi-value">${data.summary.revenue.toLocaleString()}</div>
          <div className="kpi-subtext">71% from Meta ads</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-title">ROAS</div>
          <div className="kpi-value">{data.summary.roas}x</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-title">CAC</div>
          <div className="kpi-value">${data.summary.cac}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-title">Conv. Rate</div>
          <div className="kpi-value">{data.summary.conversion_rate}%</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-title">Deal Time</div>
          <div className="kpi-value">{data.summary.deal_time}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-title">Rev. Growth</div>
          <div className="kpi-value success">+{data.summary.revenue_growth}%</div>
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Spend</th>
              <th>Impressions</th>
              <th>Clicks</th>
              <th>Leads</th>
              <th>CPL</th>
              <th>Q. Leads</th>
              <th>CPQL</th>
              <th>Purchases</th>
              <th>Revenue</th>
              <th>ROAS</th>
            </tr>
          </thead>
          <tbody>
            {data.ad_sets.map((row, i) => (
              <tr key={i}>
                <td>
                  <span className="status-dot"></span>
                  {row.name}
                </td>
                <td>${row.spend.toFixed(2)}</td>
                <td>{row.impressions.toLocaleString()}</td>
                <td>{row.clicks}</td>
                <td>{row.leads}</td>
                <td>${row.cpl.toFixed(2)}</td>
                <td>{row.q_leads || '-'}</td>
                <td>{row.cpql ? `$${row.cpql.toFixed(2)}` : '-'}</td>
                <td>{row.purchases || '-'}</td>
                <td>{row.revenue ? `$${row.revenue.toLocaleString()}` : '-'}</td>
                <td>
                  {row.roas > 0 ? (
                    <span className={`badge ${row.roas > 5 ? 'success' : 'warning'}`}>
                      {row.roas.toFixed(2)}x
                    </span>
                  ) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default App
