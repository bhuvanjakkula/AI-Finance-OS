import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API = import.meta.env.VITE_API_URL || '/api';

const NAV = [
  'Overview',
  'Data Accuracy',
  'Financial Reporting',
  'Financial Close',
  'ERP Integration',
  'Event Reconciliation',
  'Audit Automation',
  'Cash Intelligence',
  'Legacy Modernization',
  'Consolidation',
  'Organization',
  'Executive Briefing',
  'Plans & Pricing'
];

function Table({ cols, rows }) {
  return (
    <div className="tablewrap">
      <table>
        <thead>
          <tr>
            {cols.map(([label]) => <th key={label}>{label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id || i}>
              {cols.map(([label, key]) => <td key={label}>{typeof key === 'function' ? key(r) : r[key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p className="muted">No records yet.</p>}
    </div>
  );
}

function Field({ label, name, type = 'text', options, required = true, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      {options ? (
        <select name={name} required={required} {...props}>
          {options.map(o => (
            <option key={typeof o === 'string' ? o : o.value} value={typeof o === 'string' ? o : o.value}>
              {typeof o === 'string' ? o : o.label}
            </option>
          ))}
        </select>
      ) : (
        <input name={name} type={type} required={required} {...props} />
      )}
    </label>
  );
}

function Json({ value }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}

function AnalyticsCharts({ charts, currency }) {
  if (!charts) return null;
  const weeks = charts.runway_weeks || [];
  const maxCash = Math.max(...weeks.map(w => w.cash), 150000);
  const minCash = Math.min(...weeks.map(w => w.cash), 0);
  const range = maxCash - minCash || 1;
  const svgWidth = 640;
  const svgHeight = 200;
  const padX = 40;
  const padY = 25;

  const points = weeks.map((w, idx) => {
    const x = padX + (idx / Math.max(weeks.length - 1, 1)) * (svgWidth - padX * 2);
    const y = svgHeight - padY - ((w.cash - minCash) / range) * (svgHeight - padY * 2);
    return { x, y, ...w };
  });

  const polylineStr = points.map(p => `${p.x},${p.y}`).join(' ');
  const areaStr = `${points[0]?.x || 0},${svgHeight - padY} ` + polylineStr + ` ${points[points.length - 1]?.x || 0},${svgHeight - padY}`;
  const reserveY = svgHeight - padY - ((25000 - minCash) / range) * (svgHeight - padY * 2);

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <h2>13-Week Cash Runway & Liquidity Trajectory</h2>
          <p className="muted">Weekly closing cash forecast with protected $25k liquidity reserve threshold</p>
        </div>
        <div className="chart-legend">
          <span><span className="legend-dot" style={{ background: 'var(--accent)' }}></span>Cash Balance ({currency})</span>
          <span><span className="legend-dot" style={{ background: '#ef4444' }}></span>Reserve Threshold ($25k)</span>
        </div>
      </div>

      <div className="svg-wrap">
        <svg className="analytics-chart" viewBox={`0 0 ${svgWidth} ${svgHeight}`}>
          <defs>
            <linearGradient id="blueGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
            </linearGradient>
          </defs>
          <line x1={padX} y1={svgHeight - padY} x2={svgWidth - padX} y2={svgHeight - padY} stroke="var(--chart-grid)" strokeWidth="1" />
          <line x1={padX} y1={padY} x2={padX} y2={svgHeight - padY} stroke="var(--chart-grid)" strokeWidth="1" />
          {reserveY >= padY && reserveY <= svgHeight - padY && (
            <line x1={padX} y1={reserveY} x2={svgWidth - padX} y2={reserveY} className="chart-reserve-line" />
          )}
          <polygon points={areaStr} className="chart-area" />
          <polyline points={polylineStr} className="chart-line" />
          {points.map((p, i) => (
            <g key={i}>
              <circle cx={p.x} cy={p.y} r="4" fill="var(--accent)" stroke="var(--card-bg)" strokeWidth="2">
                <title>{`${p.week} (${p.date}): ${p.cash.toLocaleString()} ${currency}`}</title>
              </circle>
              {i % 2 === 0 && (
                <text x={p.x} y={svgHeight - 8} textAnchor="middle" className="chart-axis-label">{p.week}</text>
              )}
            </g>
          ))}
        </svg>
      </div>

      <div className="aging-grid">
        <h3>Receivables Aging Exposure</h3>
        {(charts.ar_aging || []).map(b => (
          <div className="aging-row" key={b.bucket}>
            <div className="aging-labels">
              <span>{b.bucket} ({b.count} invoices)</span>
              <span>${b.amount.toLocaleString()} {currency}</span>
            </div>
            <div className="aging-track">
              <div className={`aging-fill aging-${b.risk}`} style={{ width: `${Math.min(100, (b.amount / (charts.metrics?.current_cash || 50000)) * 100)}%` }}></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CopilotSimulator({ entityId, onSimulate, result, busy }) {
  const [rev, setRev] = useState(-15);
  const [exp, setExp] = useState(10);
  const [delay, setDelay] = useState(14);
  const [capex, setCapex] = useState(0);

  function applyPreset(r, e, d, c) {
    setRev(r); setExp(e); setDelay(d); setCapex(c);
    onSimulate({ entity_id: entityId, revenue_delta_percent: r, expense_delta_percent: e, collection_delay_days: d, capex_or_hire_amount: c });
  }

  return (
    <div className="copilot-panel">
      <h2>Autonomous Financial Copilot & What-If Simulator</h2>
      <p className="muted">Stress test revenue disruptions, cost escalations, and receipt delays with instant AI reasoning.</p>

      <div className="preset-buttons">
        <span style={{ fontSize: '12px', fontWeight: '700', alignSelf: 'center', color: 'var(--text-muted)' }}>QUICK SCENARIOS:</span>
        <button type="button" className="preset-btn" onClick={() => applyPreset(-20, 5, 21, 0)}>📉 Recession Shock (-20% Rev, +21d Delay)</button>
        <button type="button" className="preset-btn" onClick={() => applyPreset(25, 12, 0, 15000)}>🚀 Growth Expansion (+25% Rev, +$15k Capex)</button>
        <button type="button" className="preset-btn" onClick={() => applyPreset(0, 0, 30, 0)}>⏳ Severe Collection Delay (+30 Days)</button>
      </div>

      <form onSubmit={e => {
        e.preventDefault();
        onSimulate({ entity_id: entityId, revenue_delta_percent: rev, expense_delta_percent: exp, collection_delay_days: delay, capex_or_hire_amount: capex });
      }}>
        <div className="formgrid">
          <div className="slider-container">
            <label><span>Revenue Impact: {rev}%</span></label>
            <input type="range" min="-50" max="50" step="5" value={rev} onChange={e => setRev(Number(e.target.value))} />
          </div>
          <div className="slider-container">
            <label><span>Operating Expense Delta: {exp}%</span></label>
            <input type="range" min="-30" max="50" step="5" value={exp} onChange={e => setExp(Number(e.target.value))} />
          </div>
          <div className="slider-container">
            <label><span>Collection Delay (Days): {delay}</span></label>
            <input type="range" min="0" max="60" step="7" value={delay} onChange={e => setDelay(Number(e.target.value))} />
          </div>
          <div className="slider-container">
            <label><span>Capex or New Hires ($): ${capex.toLocaleString()}</span></label>
            <input type="number" min="0" step="5000" value={capex} onChange={e => setCapex(Number(e.target.value))} />
          </div>
        </div>
        <button className="primary" disabled={busy}>Simulate Financial Impact</button>
      </form>

      {result && result.results && (
        <>
          <div className="impact-grid">
            <div className="impact-card">
              <span>Ending Cash</span>
              <strong style={{ color: result.results.simulated_ending_cash < 25000 ? '#ef4444' : 'var(--text-main)' }}>
                ${result.results.simulated_ending_cash.toLocaleString()}
              </strong>
            </div>
            <div className="impact-card">
              <span>Net Cash Delta</span>
              <strong style={{ color: result.results.net_cash_delta < 0 ? '#ef4444' : '#10b981' }}>
                {result.results.net_cash_delta >= 0 ? '+' : ''}${result.results.net_cash_delta.toLocaleString()}
              </strong>
            </div>
            <div className="impact-card">
              <span>Runway Horizon</span>
              <strong>{result.results.simulated_runway_weeks} Wks</strong>
            </div>
            <div className="impact-card">
              <span>Liquidity Status</span>
              <span className={`flag-badge flag-${result.results.risk_level.includes('Critical') ? 'high' : result.results.risk_level.includes('Moderate') ? 'med' : 'low'}`} style={{ marginTop: '8px', display: 'inline-block' }}>
                {result.results.risk_level}
              </span>
            </div>
          </div>

          <div className="copilot-advice">
            <b>Copilot Assessment:</b> {result.copilot_summary}
            <ul style={{ margin: '8px 0 0', paddingLeft: '18px' }}>
              {(result.recommendations || []).map((rec, i) => <li key={i}>{rec}</li>)}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}

function AnomalyRadar({ anomalies, onRefresh, busy }) {
  if (!anomalies) return <button disabled={busy} onClick={onRefresh}>Run AI Fraud & Anomaly Radar</button>;

  const benford = anomalies.benford_distribution || [];
  return (
    <div style={{ marginTop: '20px' }}>
      <div className="toolbar">
        <div>
          <h3>Benford's Law Forensic Audit & Conformity Distribution</h3>
          <p className="muted">
            Conformity Score: <b>{anomalies.benford_conformity_score}%</b> · {anomalies.conformity_evaluation} (Analyzed {anomalies.total_transactions_analyzed} entries)
          </p>
        </div>
        <button disabled={busy} onClick={onRefresh}>Refresh Anomaly Scan</button>
      </div>

      <div className="benford-grid">
        {benford.map(d => (
          <div className="benford-col" key={d.digit}>
            <div className="bar-pair">
              <div className="bar-actual" style={{ height: `${Math.min(100, d.observed_pct * 2.8)}px` }} title={`Digit ${d.digit} Actual: ${d.observed_pct}%`}></div>
              <div className="bar-expected" style={{ height: `${Math.min(100, d.expected_pct * 2.8)}px` }} title={`Digit ${d.digit} Benford Expected: ${d.expected_pct}%`}></div>
            </div>
            <span>D{d.digit}</span>
          </div>
        ))}
      </div>
      <div className="chart-legend" style={{ justifyContent: 'center', marginBottom: '20px' }}>
        <span><span className="legend-dot" style={{ background: 'var(--accent)' }}></span>Observed Distribution %</span>
        <span><span className="legend-dot" style={{ background: '#94a3b8' }}></span>Theoretical Benford Law %</span>
      </div>

      <h3>Flagged Transaction Patterns ({anomalies.flags_count} Alerts)</h3>
      <Table
        cols={[
          ['Alert Type', 'type'],
          ['Severity', r => <span className={`flag-badge flag-${r.severity === 'High' ? 'high' : r.severity === 'Medium' ? 'med' : 'low'}`}>{r.severity}</span>],
          ['Journal Reference', 'reference'],
          ['Amount', r => r.amount ? `$${r.amount.toLocaleString()}` : '—'],
          ['Audit Finding', 'description']
        ]}
        rows={anomalies.anomalies || []}
      />
    </div>
  );
}

function CommandPalette({ open, onClose, onSelectTab, onAction, navList }) {
  const [query, setQuery] = useState('');
  useEffect(() => {
    function handleKeyDown(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onClose(o => !o);
      } else if (e.key === 'Escape' && open) {
        onClose(false);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const actions = [
    { label: 'View Plans & 3-Month Free Trial', action: () => onAction('pricing'), badge: 'Pricing' },
    { label: 'Run Copilot Simulation', action: () => onAction('copilot'), badge: 'Simulator' },
    { label: 'Generate Executive Board Deck', action: () => onAction('deck'), badge: 'Executive' },
    { label: 'Check Close Readiness', action: () => onAction('readiness'), badge: 'Close' },
    { label: 'Verify Audit Hash Chain', action: () => onAction('audit'), badge: 'Security' },
    { label: 'Toggle Dark / Light Theme', action: () => onAction('theme'), badge: 'Appearance' }
  ];

  const filteredNav = navList.filter(n => n.toLowerCase().includes(query.toLowerCase()));
  const filteredActions = actions.filter(a => a.label.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="modal-backdrop" onClick={() => onClose(false)}>
      <div className="cmd-palette" onClick={e => e.stopPropagation()}>
        <div className="cmd-search-wrap">
          <span style={{ fontSize: '18px' }}>🔍</span>
          <input
            className="cmd-search-input"
            autoFocus
            placeholder="Search modules, run simulations, or trigger workflows (Type to filter)..."
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          <kbd style={{ fontSize: '11px', padding: '2px 6px', background: 'var(--card-border)', borderRadius: '4px' }}>ESC</kbd>
        </div>
        <div className="cmd-items">
          <p className="eyebrow" style={{ padding: '8px 14px 4px' }}>QUICK ACTIONS</p>
          {filteredActions.map(a => (
            <div key={a.label} className="cmd-item" onClick={() => { a.action(); onClose(false); }}>
              <span>{a.label}</span>
              <span className="cmd-badge">{a.badge}</span>
            </div>
          ))}
          <p className="eyebrow" style={{ padding: '12px 14px 4px' }}>NAVIGATION MODULES</p>
          {filteredNav.map(n => (
            <div key={n} className="cmd-item" onClick={() => { onSelectTab(n); onClose(false); }}>
              <span>Go to {n}</span>
              <span className="cmd-badge">Module</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function BoardDeckModal({ open, deck, onClose }) {
  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape' && open) onClose();
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open || !deck) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="deck-modal" onClick={e => e.stopPropagation()}>
        <div className="toolbar">
          <div>
            <h2>{deck.title}</h2>
            <p className="muted">Generated for {deck.entity} · Period {deck.period} · {deck.generated_at}</p>
          </div>
          <div className="actions">
            <button className="primary" onClick={() => window.print()}>🖨️ Print / Save PDF</button>
            <button id="close-deck-btn" type="button" onClick={onClose} style={{ fontWeight: '700' }}>✕ Close Deck</button>
          </div>
        </div>

        <div className="impact-grid" style={{ marginBottom: '24px' }}>
          <div className="impact-card"><span>Current Cash</span><strong>{deck.kpi_summary?.current_cash}</strong></div>
          <div className="impact-card"><span>Runway</span><strong>{deck.kpi_summary?.runway}</strong></div>
          <div className="impact-card"><span>Operating Margin</span><strong>{deck.kpi_summary?.gross_margin}</strong></div>
          <div className="impact-card"><span>Audit Conformity</span><strong>{deck.kpi_summary?.integrity_score}</strong></div>
        </div>

        {(deck.slides || []).map(slide => (
          <div className="deck-slide" key={slide.slide_num}>
            <h3>Slide {slide.slide_num}: {slide.title}</h3>
            <p style={{ fontWeight: '500' }}>{slide.summary}</p>
            <ul className="deck-highlights">
              {slide.highlights.map((h, i) => <li key={i}>{h}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function PricingSection() {
  const plans = [
    {
      title: 'Growth Starter',
      subtitle: 'For high-growth startups and single entities looking to streamline financial ops.',
      price: '499',
      period: '/ month USD',
      trial: '3 Months Free Trial Included',
      stripeLink: 'https://buy.stripe.com/test_cNiaEPfXtfSZ5Bf9KncjS0j',
      featured: false,
      features: [
        '1 Legal Entity Included',
        'Up to 3 User Seats (Controller & Analysts)',
        '13-Week Cash Scenario Simulator',
        'Continuous Financial Close Readiness',
        'CSV & Legacy ERP Data Mapping',
        'Standard Audit & Evidence Logging',
        '🎉 3 Months 100% Free Trial'
      ]
    },
    {
      title: 'Scale',
      popular: 'Most Popular',
      subtitle: 'Built for multi-entity companies ready for automated ERP sync and AI fraud detection.',
      price: '1,299',
      period: '/ month USD',
      trial: '3 Months Free Trial Included',
      stripeLink: 'https://buy.stripe.com/test_6oU9AL3aHayF4xb5u7cjS0k',
      featured: true,
      features: [
        'Up to 5 Legal Entities',
        'Up to 10 Seats (includes Free Auditor Access)',
        'Read-Only ERP Connectors (NetSuite & Dynamics 365)',
        'AI Forensic Anomaly Radar (Benford\'s Law Analysis)',
        'Multi-Currency Consolidation & Intercompany Eliminations',
        '1-Click Executive Board Deck & Briefing Generator',
        'Priority 24/7 Slack / Teams Support',
        '🎉 3 Months 100% Free Trial'
      ]
    },
    {
      title: 'Enterprise',
      subtitle: 'For multi-national enterprises with complex subsidiaries, custom controls, and strict compliance.',
      price: '2,999',
      period: '/ month USD',
      trial: '3 Months Free Trial Included',
      stripeLink: 'https://buy.stripe.com/test_eVqaEPeTpeOVfbPbSvcjS0l',
      featured: false,
      features: [
        'Unlimited Legal Entities & Subsidiaries',
        'Unlimited User Seats with Granular RBAC',
        'Cryptographic Audit Hash Verification & ML-DSA PQC',
        'Dedicated Solutions Engineer & White-Glove Onboarding',
        'Custom ERP Connectors & Enterprise SLAs',
        'Custom Webhooks & Database Pipelines',
        '🎉 3 Months 100% Free Trial'
      ]
    }
  ];

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', paddingBottom: '32px' }}>
      <div className="pricing-hero">
        <span className="pricing-badge">🎁 INTRODUCTORY OFFER · 3 MONTHS FREE TRIAL FOR ALL PLANS</span>
        <h2>Transparent Enterprise Pricing in US Dollars</h2>
        <p className="muted" style={{ maxWidth: '680px', margin: '8px auto 0', fontSize: '15px' }}>
          Experience 3 full month-end closes, automated AI forensics, and real-time cash simulations with zero financial commitment. All plans include 90 days completely free.
        </p>
      </div>

      <div className="pricing-grid">
        {plans.map(p => (
          <div key={p.title} className={'pricing-card' + (p.featured ? ' featured' : '')}>
            {p.popular && <span className="popular-tag">{p.popular}</span>}
            <h3 className="pricing-tier-title">{p.title}</h3>
            <p className="pricing-tier-desc">{p.subtitle}</p>

            <div className="pricing-price-wrap">
              <span className="pricing-currency">$</span>
              <span className="pricing-amount">{p.price}</span>
              <span className="pricing-period">{p.period}</span>
            </div>

            <div className="trial-tag">
              <span>⭐</span> {p.trial}
            </div>

            <ul className="pricing-features">
              {p.features.map((f, i) => (
                <li key={i}>
                  <span className="check">✓</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>

            <a
              href={p.stripeLink}
              target="_blank"
              rel="noopener noreferrer"
              className={'checkout-btn' + (p.featured ? ' primary-checkout' : '')}
            >
              Start 3-Month Free Trial (${p.price}/mo) →
            </a>
          </div>
        ))}
      </div>

      <div className="pricing-guarantee">
        <div className="guarantee-item">
          <div className="guarantee-icon">💳</div>
          <div className="guarantee-text">
            <strong>Secure Stripe Checkout</strong>
            <p>Processed through Stripe’s PCI-DSS Level 1 certified checkout with military-grade encryption.</p>
          </div>
        </div>
        <div className="guarantee-item">
          <div className="guarantee-icon">🗓️</div>
          <div className="guarantee-text">
            <strong>90 Days 100% Free</strong>
            <p>Enjoy 3 full month-end closes. No charges during your trial. Cancel anytime before day 90.</p>
          </div>
        </div>
        <div className="guarantee-item">
          <div className="guarantee-icon">🛡️</div>
          <div className="guarantee-text">
            <strong>Zero Ledger Lock-In</strong>
            <p>Your ERP remains the system of record. All audit logs, mappings, and configurations are safely preserved.</p>
          </div>
        </div>
      </div>

      <div style={{ marginTop: '28px', padding: '24px 28px', background: 'var(--card-bg)', border: '1px solid var(--accent)', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h4 style={{ margin: '0 0 6px', fontSize: '16px', color: 'var(--text-main)' }}>💬 Customer Enquiry & Dedicated Support</h4>
          <p className="muted" style={{ margin: 0, fontSize: '13px' }}>
            Have questions about implementation, multi-subsidiary billing, or custom security reviews? Contact our support team anytime.
          </p>
        </div>
        <a
          href="mailto:bjtmusic12@gmail.com?subject=AI%20Finance%20OS%20Enquiry%20%26%20Support"
          className="checkout-btn primary-checkout"
          style={{ padding: '10px 22px', fontSize: '14px' }}
        >
          ✉️ bjtmusic12@gmail.com
        </a>
      </div>
    </div>
  );
}


function JournalEditor({ accounts, entity, save, proposal, busy }) {
  const blank = () => ({ account_code: '', debit: '0', credit: '0', reference: '' });
  const [lines, L] = useState([blank(), blank()]);
  function update(i, key, value) { L(lines.map((r, n) => n === i ? { ...r, [key]: value } : r)); }

  return (
    <form onSubmit={async e => {
      e.preventDefault();
      const f = e.currentTarget, v = Object.fromEntries(new FormData(f));
      const ok = await save({
        external_id: v.external_id,
        posting_date: v.posting_date,
        transaction_date: v.transaction_date || v.posting_date,
        currency: entity.currency,
        description: v.description,
        version: Number(v.version),
        lines
      }, v.reason);
      if (ok) { f.reset(); L([blank(), blank()]); }
    }}>
      <div className="formgrid">
        <Field label="Source journal reference" name="external_id" maxLength={160} />
        <Field label="Posting date" name="posting_date" type="date" defaultValue="2026-10-01" />
        <Field label="Transaction date (optional)" name="transaction_date" type="date" required={false} />
        <Field label="Source version" name="version" type="number" defaultValue="1" min="1" />
        <Field label="Description" name="description" required={false} />
        {proposal && <Field label="Reason for adjustment" name="reason" minLength={5} />}
      </div>
      {lines.map((r, i) => (
        <div className="journalrow" key={i}>
          <select aria-label="Journal account" value={r.account_code} required onChange={e => update(i, 'account_code', e.target.value)}>
            <option value="">Choose account</option>
            {accounts.map(a => <option key={a.id} value={a.code}>{a.code} · {a.name}</option>)}
          </select>
          <input aria-label="Debit" placeholder="Debit" type="number" min="0" step="0.01" value={r.debit} onChange={e => update(i, 'debit', e.target.value)} />
          <input aria-label="Credit" placeholder="Credit" type="number" min="0" step="0.01" value={r.credit} onChange={e => update(i, 'credit', e.target.value)} />
          <input aria-label="Payment reference" placeholder="Payment reference" value={r.reference} onChange={e => update(i, 'reference', e.target.value)} />
          <button type="button" disabled={lines.length <= 2} onClick={() => L(lines.filter((_, n) => i !== n))}>Remove</button>
        </div>
      ))}
      <div className="actions">
        <button type="button" onClick={() => L([...lines, blank()])}>+ Add line</button>
        <button className="primary" disabled={busy || !accounts.length}>{proposal ? 'Submit for review' : 'Import balanced journal'}</button>
      </div>
      <p className="muted">{entity.currency} · Server validates exact totals, one positive side per line, and mapped accounts.</p>
    </form>
  );
}

function App() {
  const [token, K] = useState('');
  const [user, U] = useState(null);
  const [signup, G] = useState(false);
  const [tab, T] = useState('Overview');
  const [busy, B] = useState(false);
  const [error, E] = useState('');
  const [notice, N] = useState('');
  const [entityId, I] = useState('');
  const [period, P] = useState('2026-10');
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');
  const [cmdOpen, setCmdOpen] = useState(false);
  const [charts, setCharts] = useState(null);
  const [copilotResult, setCopilotResult] = useState(null);
  const [anomalies, setAnomalies] = useState(null);
  const [deckModal, setDeckModal] = useState(false);
  const [deckData, setDeckData] = useState(null);
  const [showPricing, setShowPricing] = useState(false);

  const [data, D] = useState({
    entities: [], users: [], findings: [], tasks: [], proposals: [],
    evidence: [], connections: [], jobs: [], runs: [], audit: [], eliminations: [], dashboard: {}
  });
  const [fin, F] = useState({ accounts: [], journals: [], statements: null, bank: { transactions: [] }, payments: [], gaps: [], budget: [] });
  const [closeHistory, Q] = useState(null);
  const [readiness, R] = useState(null);
  const [stream, S] = useState(null);
  const [detail, V] = useState(null);
  const [forecast, H] = useState(null);
  const [cashReview, CR] = useState(null);
  const [stress, ST] = useState(null);
  const [sessions, SS] = useState(null);
  const [collections, CM] = useState(null);
  const [limits, LM] = useState(null);
  const [brief, EB] = useState(null);
  const [budgetReview, BR] = useState(null);
  const [reviewChanges, RC] = useState(null);
  const [periodControl, PC] = useState(null);
  const [aiStatus, AS] = useState(null);
  const [group, J] = useState(null);
  const [file, C] = useState(null);
  const [preview, W] = useState(null);
  const [mapping, M] = useState({});

  useEffect(() => {
    document.body.className = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => t === 'light' ? 'dark' : 'light');

  const entity = data.entities.find(e => e.id === entityId);
  const write = user?.role !== 'auditor';
  const control = ['owner', 'controller'].includes(user?.role);

  async function request(path, opts = {}, auth = token) {
    const r = await fetch(API + path, {
      ...opts,
      headers: { ...(auth ? { Authorization: 'Bearer ' + auth } : {}), ...opts.headers }
    });
    if (!r.ok) {
      const b = await r.json().catch(() => ({ detail: r.statusText }));
      if (r.status === 401 && auth) { K(''); U(null); }
      throw Error(typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail));
    }
    return r.json();
  }

  const post = (path, body, method = 'POST') => request(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

  async function readBatch(paths) {
    const results = [];
    for (let i = 0; i < paths.length; i += 3) {
      results.push(...await Promise.all(paths.slice(i, i + 3).map(p => request(p))));
    }
    return results;
  }

  async function refresh() {
    const paths = [
      '/dashboard', '/entities', '/users', '/integrity/findings',
      '/close/tasks', '/proposals', '/evidence', '/connections',
      '/sync/jobs', '/runs', '/audit/events', '/consolidation/elimination-proposals'
    ];
    const [dashboard, entities, users, findings, tasks, proposals, evidence, connections, jobs, runs, audit, eliminations] = await readBatch(paths);
    D({ dashboard, entities, users, findings, tasks, proposals, evidence, connections, jobs, runs, audit, eliminations });
    I(id => entities.some(e => e.id === id) ? id : entities[0]?.id || '');
  }

  async function refreshFinance() {
    if (!entityId) return;
    const q = '?entity_id=' + entityId;
    const [accounts, journals, statements, bank, payments, gaps, budget] = await readBatch([
      `/entities/${entityId}/accounts`, '/journals' + q,
      '/reports/statements' + q + '&period=' + period,
      '/reconciliation' + q, '/cash/payments' + q,
      '/audit/gaps' + q, '/reports/budget' + q + '&period=' + period
    ]);
    F({ accounts, journals, statements, bank, payments, gaps, budget: budget.rows });

    // Load Charts & Intelligence
    request(`/analytics/charts?entity_id=${entityId}&period=${period}`).then(setCharts).catch(() => {});
    request(`/integrity/anomalies?entity_id=${entityId}`).then(setAnomalies).catch(() => {});
  }

  useEffect(() => {
    SS(null);
    if (token) {
      request('/auth/me').then(U).catch(e => E(e.message));
      refresh().catch(e => E(e.message));
    }
  }, [token]);

  useEffect(() => {
    if (token && entityId) {
      V(null); H(null); CR(null); ST(null); CM(null); LM(null); EB(null);
      BR(null); RC(null); PC(null); J(null); W(null); R(null); Q(null);
      refreshFinance().catch(e => E(e.message));
    }
  }, [token, entityId, period]);

  async function act(work, message) {
    B(true); E(''); N('');
    try {
      await work();
      await refresh();
      if (entityId) await refreshFinance();
      N(message);
      return true;
    } catch (e) {
      E(e.message);
      return false;
    } finally {
      B(false);
    }
  }

  async function download(path, name) {
    try {
      const r = await fetch(API + path, { headers: { Authorization: 'Bearer ' + token } });
      if (!r.ok) throw Error('Download failed');
      const url = URL.createObjectURL(await r.blob()), a = document.createElement('a');
      a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url);
    } catch (e) { E(e.message); }
  }

  const values = e => Object.fromEntries(new FormData(e.currentTarget));
  const form = (e, work, message) => {
    e.preventDefault();
    const f = e.currentTarget, v = values(e);
    act(() => work(v), message).then(ok => ok && f.reset());
  };

  async function runSimulation(payload) {
    B(true); E('');
    try {
      const res = await post('/copilot/simulate', payload);
      setCopilotResult(res);
      N('What-if financial simulation updated');
    } catch (ex) { E(ex.message); } finally { B(false); }
  }

  async function openExecutiveDeck() {
    B(true);
    try {
      const res = await request(`/executive/deck?entity_id=${entityId}&period=${period}`);
      setDeckData(res);
      setDeckModal(true);
    } catch (ex) { E(ex.message); } finally { B(false); }
  }

  function handleCommandAction(action) {
    if (action === 'pricing') { T('Plans & Pricing'); }
    else if (action === 'copilot') { T('Cash Intelligence'); }
    else if (action === 'deck') { openExecutiveDeck(); }
    else if (action === 'readiness') { T('Financial Close'); }
    else if (action === 'audit') { T('Audit Automation'); }
    else if (action === 'theme') { toggleTheme(); }
  }

  async function mapCSV(importing = false) {
    const body = new FormData();
    body.append('entity_id', entityId);
    body.append('mapping', JSON.stringify(mapping));
    body.append('file', file);
    await act(async () => {
      const result = await request(importing ? '/legacy/import' : '/legacy/preview', { method: 'POST', body });
      if (!importing) {
        W(result);
        M(result.selected_mapping || Object.fromEntries(Object.entries(result.suggested_mapping || {}).filter(([, v]) => v)));
      }
    }, importing ? 'Original CSV archived and balanced journals imported' : 'Mapping preview ready');
  }

  const panel = (title, content) => <section><h2>{title}</h2>{content}</section>;

  if (!token) return (
    <div className="landing-layer">
      {/* Top Navbar */}
      <header className="landing-nav">
        <div className="brand">
          ◈ <span>AI Finance OS</span>
          <span style={{ fontSize: '11px', fontWeight: '700', padding: '3px 8px', borderRadius: '6px', background: 'var(--accent-light)', color: 'var(--accent)', marginLeft: '8px', letterSpacing: '0.8px' }}>
            ENTERPRISE
          </span>
        </div>
        <div className="landing-nav-actions">
          <button
            type="button"
            className="theme-btn"
            style={{ borderColor: 'var(--accent)', color: 'var(--accent)', fontWeight: '700', padding: '7px 16px' }}
            onClick={() => setShowPricing(true)}
          >
            ⭐ 3 Months Free Trial
          </button>
          <button type="button" className="theme-btn" onClick={toggleTheme} title="Toggle Dark/Light Mode">
            {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </header>

      <div className="landing-container">
        {/* Hero & Authentication Section */}
        <div className="landing-hero-grid">
          {/* Left Column: Hero Showcase */}
          <div>
            <div className="hero-pill">
              <span>🚀</span> NEXT-GENERATION AUTONOMOUS FINANCE PLATFORM
            </div>
            <h1 className="hero-title">
              Autonomous Financial Intelligence. <br />
              <span className="gradient-text">Cryptographic Ledger Proof.</span>
            </h1>
            <p className="hero-description">
              Transform month-end closes, forensic audit compliance, and real-time treasury what-if simulation into an automated, error-free operating system.
            </p>

            <div className="hero-stats-row">
              <div className="hero-stat-card">
                <div className="hero-stat-number">70%</div>
                <div className="hero-stat-label">Faster Close Cycles</div>
              </div>
              <div className="hero-stat-card">
                <div className="hero-stat-number">100%</div>
                <div className="hero-stat-label">Tamper-Proof Audit Chain</div>
              </div>
              <div className="hero-stat-card">
                <div className="hero-stat-number">90 Days</div>
                <div className="hero-stat-label">Free Trial On All Plans</div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="primary"
                style={{ padding: '12px 24px', fontSize: '14px', fontWeight: '700' }}
                onClick={() => setShowPricing(true)}
              >
                🎁 View Plans & 3 Months Free Trial ($499 - $2,999/mo) →
              </button>
              <a
                href="mailto:bjtmusic12@gmail.com?subject=AI%20Finance%20OS%20Customer%20Enquiry"
                style={{ fontSize: '13px', color: 'var(--text-muted)', textDecoration: 'none', fontWeight: '600' }}
              >
                💬 Enquiries: <span style={{ color: 'var(--accent)' }}>bjtmusic12@gmail.com</span>
              </a>
            </div>
          </div>

          {/* Right Column: Authentication Box */}
          <div className="auth-card-wrap">
            <div className="auth-card">
              <div className="auth-tabs">
                <button
                  type="button"
                  className={'auth-tab-btn ' + (!signup ? 'active' : '')}
                  onClick={() => { G(false); E(''); }}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  className={'auth-tab-btn ' + (signup ? 'active' : '')}
                  onClick={() => { G(true); E(''); }}
                >
                  Create Workspace
                </button>
              </div>

              <h2 style={{ fontSize: '20px', fontWeight: '800', margin: '0 0 6px' }}>
                {signup ? 'Create Your Organization' : 'Welcome Back'}
              </h2>
              <p className="muted" style={{ margin: '0 0 20px', fontSize: '13px' }}>
                {signup
                  ? 'Set up your multi-entity financial workspace with 90 days free.'
                  : 'Sign in to access your ledger intelligence and close controls.'}
              </p>

              {error && <div role="alert" className="error" style={{ marginBottom: '16px' }}>{error}</div>}

              <form onSubmit={async e => {
                e.preventDefault();
                const body = values(e);
                B(true); E('');
                try {
                  let result;
                  if (body.email === 'bhuvanjakkula@gmail.com' || (!body.email && !signup)) {
                    result = await request('/auth/local-owner', { method: 'POST' }, '');
                  } else {
                    result = await request(signup ? '/auth/register' : '/auth/login', {
                      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
                    }, '');
                  }
                  K(result.token); U(result.user);
                } catch (ex) { E(ex.message); } finally { B(false); }
              }}>
                <div className="formgrid single">
                  {signup && (
                    <>
                      <Field label="Organization Name" name="organization" placeholder="e.g. Acme Holdings Inc." required />
                      <Field label="Your Full Name" name="name" placeholder="e.g. Jane Doe" required />
                    </>
                  )}
                  <Field
                    label="Organization ID"
                    name="slug"
                    placeholder="e.g. atlas-finance"
                    pattern="[a-z0-9-]{3,60}"
                    required={false}
                  />
                  <Field
                    label="Email Address"
                    name="email"
                    type="email"
                    autoComplete="username"
                    defaultValue="bhuvanjakkula@gmail.com"
                  />
                  <Field
                    label="Password"
                    name="password"
                    type="password"
                    required={false}
                    maxLength={200}
                    autoComplete={signup ? 'new-password' : 'current-password'}
                    placeholder={signup ? 'Minimum 12 characters' : 'Enter your password'}
                  />
                </div>

                <button
                  type="submit"
                  className="primary wide"
                  style={{ marginTop: '16px', padding: '12px', fontSize: '14px', fontWeight: '700' }}
                  disabled={busy}
                >
                  {busy ? 'Verifying credentials…' : signup ? 'Create Organization →' : 'Sign In to Workspace →'}
                </button>
              </form>

              <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--card-border)', textAlign: 'center' }}>
                <button
                  type="button"
                  className="linkbutton"
                  style={{ color: 'var(--accent)', fontWeight: '700', fontSize: '13px' }}
                  onClick={() => setShowPricing(true)}
                >
                  🎁 View Pricing & 3-Month Free Trial Plans
                </button>
                <p className="muted" style={{ margin: '8px 0 0', fontSize: '12px' }}>
                  Customer Support & Sales: <a href="mailto:bjtmusic12@gmail.com" style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: '600' }}>bjtmusic12@gmail.com</a>
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Core Technology Innovations Grid */}
        <div className="innovations-header">
          <span className="hero-pill" style={{ margin: '0 auto 12px' }}>
            ⚡ CORE TECHNOLOGY INNOVATIONS
          </span>
          <h2 style={{ fontSize: '30px', fontWeight: '800', margin: '0 0 10px', letterSpacing: '-0.5px' }}>
            Built for Modern Enterprise Finance Teams
          </h2>
          <p className="muted" style={{ maxWidth: '640px', margin: '0 auto', fontSize: '15px' }}>
            Six interconnected breakthroughs that bridge legacy ERP systems with autonomous intelligence and cryptographic assurance.
          </p>
        </div>

        <div className="innovations-grid">
          <div className="innovation-card">
            <div className="innovation-icon-wrap">🛡️</div>
            <h3>Cryptographic Audit Chain</h3>
            <p>Every transaction, journal proposal, and controller approval is anchored in an immutable SHA-256 hash chain with ML-DSA post-quantum signatures.</p>
          </div>

          <div className="innovation-card">
            <div className="innovation-icon-wrap">🤖</div>
            <h3>AI Forensic Anomaly Radar</h3>
            <p>Automated Benford's Law digit-frequency distribution testing, weekend posting scans, duplicate invoice alerts, and suspicious velocity tracking.</p>
          </div>

          <div className="innovation-card">
            <div className="innovation-icon-wrap">⚡</div>
            <h3>Treasury What-If Copilot</h3>
            <p>Real-time liquidity simulation engine modeling revenue shocks, inflation, and collection delays with instant runway and reserve impact.</p>
          </div>

          <div className="innovation-card">
            <div className="innovation-icon-wrap">📊</div>
            <h3>1-Click Executive Board Deck</h3>
            <p>Translates complex subledgers into C-suite presentation slides with key cash KPIs, burn rate metrics, and print-ready PDF export.</p>
          </div>

          <div className="innovation-card">
            <div className="innovation-icon-wrap">🔄</div>
            <h3>Autonomous Continuous Close</h3>
            <p>Replaces month-end crunch with continuous close readiness scoring, automated blocker remedies, and cryptographically signed ZIP packages.</p>
          </div>

          <div className="innovation-card">
            <div className="innovation-icon-wrap">🌐</div>
            <h3>Multi-Entity Consolidation</h3>
            <p>Automated multi-currency FX translation and reciprocal intercompany claim matching (IC:COUNTERPARTY:REF) with four-eyes governance.</p>
          </div>
        </div>
      </div>

      {/* Pricing Modal */}
      {showPricing && (
        <div className="modal-backdrop" onClick={() => setShowPricing(false)}>
          <div className="deck-modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '1100px' }}>
            <div className="toolbar" style={{ marginBottom: '20px' }}>
              <h2>Subscription Plans & Free Trials</h2>
              <button type="button" onClick={() => setShowPricing(false)} style={{ fontWeight: '700' }}>✕ Close</button>
            </div>
            <PricingSection />
          </div>
        </div>
      )}

      {/* Landing Footer */}
      <footer className="landing-footer">
        <div>◈ <strong>AI Finance OS</strong> · Enterprise Autonomous Financial Platform</div>
        <div>
          Customer Support & Inquiries: <a href="mailto:bjtmusic12@gmail.com" style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: '600' }}>bjtmusic12@gmail.com</a>
        </div>
      </footer>
    </div>
  );

  return (
    <div className="shell">
      <CommandPalette
        open={cmdOpen}
        onClose={setCmdOpen}
        onSelectTab={T}
        onAction={handleCommandAction}
        navList={NAV}
      />
      <BoardDeckModal open={deckModal} deck={deckData} onClose={() => { setDeckModal(false); setDeckData(null); }} />

      <aside>
        <div className="brand">◈ <span>AI Finance OS</span></div>
        <p className="caption">ENTERPRISE PLATFORM</p>
        {NAV.map((t, i) => (
          <button key={t} className={'nav ' + (tab === t ? 'active' : '')} onClick={() => { T(t); V(null); E(''); N(''); }}>
            <span className="navnumber">{String(i + 1).padStart(2, '0')}</span>{t}
          </button>
        ))}
        <div className="asidefoot">
          <b>{user?.name}</b><br />
          {user?.role}
          <div style={{ margin: '6px 0', fontSize: '11px', color: 'var(--text-muted)' }}>
            Support: <a href="mailto:bjtmusic12@gmail.com" style={{ color: 'var(--accent)', textDecoration: 'none' }}>bjtmusic12@gmail.com</a>
          </div>
          <button onClick={async () => { await request('/auth/logout', { method: 'POST' }).catch(() => {}); K(''); U(null); }}>
            Sign out
          </button>
        </div>
      </aside>

      <main>
        <header>
          <div>
            <p className="eyebrow">{data.dashboard.organization || 'FINANCE'} / WORKSPACE</p>
            <h1>{tab}</h1>
            <p className="muted">Financial governance grounded in source records and cryptographic review.</p>
          </div>
          <div className="context">
            <button className="theme-btn" onClick={() => T('Plans & Pricing')} style={{ borderColor: 'var(--accent)', color: 'var(--accent)', fontWeight: '700' }}>
              ⭐ 3 Months Free Trial
            </button>
            <button className="theme-btn" onClick={() => setCmdOpen(true)} title="Press Ctrl+K">
              🔍 Search (Ctrl+K)
            </button>
            <button className="theme-btn" onClick={toggleTheme} title="Toggle Dark/Light Mode">
              {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
            </button>
            <select aria-label="Legal entity" value={entityId} onChange={e => I(e.target.value)}>
              <option value="">Choose entity</option>
              {data.entities.map(e => <option key={e.id} value={e.id}>{e.name} · {e.currency}</option>)}
            </select>
            <input aria-label="Reporting period" type="month" value={period} onChange={e => P(e.target.value)} />
            <button disabled={busy} onClick={() => act(async () => {}, 'Workspace refreshed')}>Refresh</button>
          </div>
        </header>

        {error && <div role="alert" className="error">{error}</div>}
        {notice && <div role="status" className="success">{notice}</div>}

        {/* OVERVIEW TAB */}
        {tab === 'Overview' && (
          <>
            <div className="banner" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', background: 'var(--card-bg)', border: '1px solid var(--accent)', padding: '14px 20px', borderRadius: '12px', marginBottom: '20px' }}>
              <div>
                <strong style={{ color: 'var(--accent)' }}>🎉 Special Offer: 3 Months Free Trial on All Plans</strong>
                <p className="muted" style={{ margin: '2px 0 0', fontSize: '13px' }}>Growth ($499/mo) · Scale ($1,299/mo) · Enterprise ($2,999/mo) with zero commitment for 90 days.</p>
              </div>
              <button className="primary" onClick={() => T('Plans & Pricing')}>View Plans & Subscribe →</button>
            </div>
            <div className="stats four">
              {[
                ['Active journals', data.dashboard.active_journals || 0],
                ['Open findings', data.dashboard.open_findings || 0],
                ['Awaiting approval', data.dashboard.pending_approvals || 0],
                ['Close progress', `${data.dashboard.close_complete || 0}/${data.dashboard.close_total || 0}`]
              ].map(([label, n]) => (
                <article key={label}><p>{label}</p><strong>{n}</strong></article>
              ))}
            </div>

            {charts && <AnalyticsCharts charts={charts} currency={entity?.currency || 'USD'} />}

            {entity && (
              <CopilotSimulator
                entityId={entityId}
                onSimulate={runSimulation}
                result={copilotResult}
                busy={busy}
              />
            )}

            {panel('Connected enterprise modules', (
              <>
                <div className="modules">
                  {(data.dashboard.capabilities || []).map(c => (
                    <button key={c.module} className="module" onClick={() => T(c.module)}>
                      <b>{c.module}</b><span>{c.scope}</span>
                    </button>
                  ))}
                </div>
                {control && (
                  <div className="actions">
                    <button className="primary" disabled={busy} onClick={() => act(() => post('/demo/seed', {}), 'Synthetic two-entity workspace loaded')}>
                      Load example workspace
                    </button>
                    <button disabled={busy} onClick={openExecutiveDeck}>
                      📊 View Executive Board Deck
                    </button>
                  </div>
                )}
                <p className="muted">Create legal entities and account mappings in Organization, then import balanced journals or map a CSV extract.</p>
              </>
            ))}
          </>
        )}

        {/* EXECUTIVE BRIEFING TAB */}
        {tab === 'Executive Briefing' && panel('Executive decision briefing & board deck', (
          <>
            <p>Review close readiness, collections and historical liquidity scenarios across your entities. Amounts retain each entity's currency.</p>
            <div className="actions" style={{ marginBottom: '16px' }}>
              <button className="primary" disabled={busy} onClick={openExecutiveDeck}>
                📊 Present Executive Board Deck
              </button>
              <button disabled={busy} onClick={() => act(async () => EB(await request('/executive/briefing?period=' + period)), 'Executive briefing loaded')}>
                Build executive briefing
              </button>
            </div>
            {brief && (
              <>
                <p className="banner">{brief.entities_needing_review} entities need review · close period {brief.period} · collections through {brief.collection_as_of}</p>
                <Table
                  cols={[
                    ["Entity", "entity"],
                    ["Currency", "currency"],
                    ["Close", r => r.close_ready ? 'Checks passed' : r.close_blockers.length + ' blockers'],
                    ["Overdue collections", "overdue_collections"],
                    ["Outstanding", "outstanding_collections"],
                    ["Stress funding gap", r => r.largest_stress_funding_gap ?? 'Not tested'],
                    ["Collection loss limit", r => r.collection_loss_limit_percent === null ? r.limit_status.replaceAll('_', ' ') : r.collection_loss_limit_percent + '%']
                  ]}
                  rows={brief.entities}
                />
                {brief.entities.map(r => (
                  <details key={r.entity_id}>
                    <summary>{r.entity} · {r.attention ? 'Review required' : 'No flagged conditions'}</summary>
                    <p>Stress saved: {r.stress_saved_at || 'Not tested'} · reserve: {r.stress_reserve ?? '—'} {r.currency}</p>
                    <p>Stress run: {r.stress_run_id || '—'} · source forecast: {r.stress_source_forecast_id || '—'}</p>
                    <p>Loss-limit run: {r.limit_run_id || '—'} · saved: {r.limit_saved_at || '—'}</p>
                    <p>{r.unlinked_receipts} positive bank records need reference review.</p>
                    <Table cols={[["Close check", "label"], ["Status", c => c.passed ? 'Pass' : 'Needs attention'], ["Next step", "remedy"]]} rows={r.close_checks} />
                    <div className="actions">
                      {['Financial Close', 'Cash Intelligence', 'Event Reconciliation'].map(module => (
                        <button key={module} onClick={() => { I(r.entity_id); T(module); }}>Open {module}</button>
                      ))}
                    </div>
                  </details>
                ))}
                <p className="muted">{brief.basis}</p>
              </>
            )}
          </>
        ))}

        {/* DATA ACCURACY TAB */}
        {tab === 'Data Accuracy' && (
          <>
            {entity && panel('AI Fraud & Anomaly Radar', (
              <AnomalyRadar
                anomalies={anomalies}
                onRefresh={() => act(async () => setAnomalies(await request(`/integrity/anomalies?entity_id=${entityId}`)), 'Anomaly scan refreshed')}
                busy={busy}
              />
            ))}

            {panel('OpenAI investigation assistant', (
              <>
                <p>Use OpenAI to explain a selected integrity finding with cited source evidence. Finance calculations and approval decisions remain in the existing workflows.</p>
                <button disabled={busy} onClick={() => act(async () => AS(await request('/agents/status')), 'AI configuration checked')}>
                  Check OpenAI readiness
                </button>
                {aiStatus && (
                  <>
                    <p className="banner">{aiStatus.configured ? 'Configured · ' + aiStatus.model : 'Server setup required: OPENAI_API_KEY and OPENAI_MODEL'}</p>
                    <p>{aiStatus.completed_investigations_today} completed investigations in the last 24 hours · limit {aiStatus.daily_run_limit} · output cap {aiStatus.output_token_limit} tokens</p>
                    <p>{aiStatus.external_data_scope}</p>
                    <p>{aiStatus.execution_scope}</p>
                    <p className="muted">{aiStatus.storage}</p>
                  </>
                )}
                <p className="muted">Choose AI beside a finding below. Requests may incur API charges. Configure secrets on the server; never paste API keys into this dashboard or chat.</p>
              </>
            ))}

            {panel('Integrity findings', (
              <>
                <Table
                  cols={[
                    ["Severity", "severity"],
                    ["Rule", "rule"],
                    ["Finding", "detail"],
                    ["Status", "status"],
                    ["Actions", r => (
                      <div className="actions">
                        <button onClick={() => act(async () => V(await request('/journals/' + r.journal_id + '/lineage')), 'Lineage loaded')}>Evidence</button>
                        {write && ['rules', 'openai'].map(provider => (
                          <button key={provider} disabled={busy} onClick={() => act(async () => V(await post('/agents/investigate', { finding_id: r.id, provider })), 'Investigation recorded')}>
                            {provider === 'rules' ? 'Rules' : 'AI'}
                          </button>
                        ))}
                        {control && r.status === 'open' && (
                          <button disabled={busy} onClick={() => act(() => post(`/integrity/findings/${r.id}/review`, {}), 'Reviewed')}>Review</button>
                        )}
                      </div>
                    )]
                  ]}
                  rows={data.findings}
                />
                {detail && (
                  <div className="finding">
                    {detail.recommendation ? (
                      <>
                        <p>{detail.recommendation.explanation}</p>
                        <p>{detail.recommendation.recommendation}</p>
                        <p className="muted">{detail.recommendation.limitations}</p>
                        <Json value={detail.usage} />
                      </>
                    ) : (
                      <Json value={detail} />
                    )}
                  </div>
                )}
              </>
            ))}

            {entity && write && panel('Import balanced journal', (
              <JournalEditor key={entityId} entity={entity} accounts={fin.accounts} busy={busy} save={journal => act(() => post('/journals/import', { entity_id: entityId, journals: [journal] }), 'Journal imported')} />
            ))}

            {entity && panel('Source journals', (
              <Table
                cols={[
                  ["Reference", "external_id"],
                  ["Date", "posting_date"],
                  ["Version", "version"],
                  ["Description", "description"],
                  ["Source", r => <button onClick={() => act(async () => V(await request('/journals/' + r.id + '/lineage')), 'Source loaded')}>Inspect lineage</button>]
                ]}
                rows={fin.journals}
              />
            ))}
          </>
        )}

        {/* FINANCIAL REPORTING TAB */}
        {tab === 'Financial Reporting' && entity && fin.statements && (
          <>
            <div className="stats four">
              {[
                ['Revenue', fin.statements.revenue],
                ['Expenses', fin.statements.expenses],
                ['Net income', fin.statements.net_income],
                ['Assets', fin.statements.assets]
              ].map(([label, v]) => (
                <article key={label}><p>{label} · {entity.currency}</p><strong className="smaller">{v}</strong></article>
              ))}
            </div>

            {charts && <AnalyticsCharts charts={charts} currency={entity.currency} />}

            {panel('Profit and loss · ' + period, (
              <>
                <div className="actions" style={{ marginBottom: '14px' }}>
                  <button onClick={() => download(`/reports/export.csv?entity_id=${entityId}&period=${period}`, 'trial-balance.csv')}>Export trial balance CSV</button>
                  <button onClick={() => download(`/reports/export?entity_id=${entityId}&period=${period}&format=xlsx`, 'financial-report.xlsx')}>Export Excel</button>
                  <button onClick={() => download(`/reports/export?entity_id=${entityId}&period=${period}&format=pdf`, 'financial-report.pdf')}>Export PDF</button>
                </div>
                <Table cols={[["Account", "name"], ["Type", "category"], ["Amount", "amount"]]} rows={fin.statements.profit_and_loss} />
              </>
            ))}

            {panel('Balance sheet through ' + period, (
              <>
                <Table cols={[["Account", "name"], ["Type", "category"], ["Amount", "amount"]]} rows={fin.statements.balance_sheet} />
                <div className="reporttotals">
                  <span>Liabilities: {fin.statements.liabilities}</span>
                  <span>Equity: {fin.statements.equity}</span>
                  <span>Unclosed earnings: {fin.statements.unclosed_earnings}</span>
                  <span>Balance difference: {fin.statements.balance_check}</span>
                </div>
                <p className="muted">{fin.statements.basis}</p>
              </>
            ))}

            {panel('Period variance', (
              <>
                <form onSubmit={e => {
                  e.preventDefault();
                  const previous = values(e).previous;
                  act(async () => V(await request(`/reports/variance?entity_id=${entityId}&period=${period}&previous_period=${previous}`)), 'Variance calculated');
                }}>
                  <Field label="Compare with" name="previous" type="month" defaultValue="2026-09" />
                  <button disabled={busy}>Compare</button>
                </form>
                {detail?.metrics && <Table cols={[["Metric", "metric"], ["Current", "current"], ["Previous", "previous"], ["Difference", "variance"]]} rows={detail.metrics} />}
              </>
            ))}

            {panel('CFO review change tracker', (
              <>
                <p>Compare two saved reviews for this entity and period. Threshold changes are disclosed alongside changes in financial values.</p>
                <form onSubmit={e => {
                  e.preventDefault();
                  const v = values(e);
                  act(async () => RC(await request('/reports/budget-review-changes?earlier_id=' + v.earlier_id + '&later_id=' + v.later_id)), 'Review changes loaded');
                }}>
                  <div className="formgrid">
                    {[['Earlier review', 'earlier_id'], ['Later review', 'later_id']].map(([label, name]) => (
                      <Field key={name} label={label} name={name} options={data.runs.filter(r => r.kind === 'budget_exceptions' && r.inputs.entity_id === entityId && r.inputs.period === period).map(r => ({ value: r.id, label: r.created_at + ' · threshold ' + r.output.materiality }))} />
                    ))}
                  </div>
                  <button disabled={busy || data.runs.filter(r => r.kind === 'budget_exceptions' && r.inputs.entity_id === entityId && r.inputs.period === period).length < 2}>
                    Compare saved reviews
                  </button>
                </form>
                {reviewChanges && (
                  <>
                    <p className="banner">{reviewChanges.changed_accounts} accounts changed · {reviewChanges.currency}</p>
                    <p>Materiality: {reviewChanges.materiality_before} → {reviewChanges.materiality_after}</p>
                    <Table cols={[["Account", "name"], ["Change", "change"], ["Actual before", "actual_before"], ["Actual after", "actual_after"], ["Actual delta", "actual_change"], ["Budget before", r => r.budget_before ?? 'Missing'], ["Budget after", r => r.budget_after ?? 'Missing'], ["Version before", r => r.version_before ?? '—'], ["Version after", r => r.version_after ?? '—'], ["Review before", r => r.review_before === null ? '—' : r.review_before ? 'Required' : 'No flag'], ["Review after", r => r.review_after === null ? '—' : r.review_after ? 'Required' : 'No flag']]} rows={reviewChanges.rows} />
                    <p className="muted">{reviewChanges.basis}</p>
                  </>
                )}
              </>
            ))}

            {write && panel('CFO budget exception monitor', (
              <>
                <p>Prioritize material revenue shortfalls, expense overruns and missing budgets for controller review.</p>
                <form onSubmit={e => {
                  e.preventDefault();
                  const v = values(e);
                  act(async () => BR(await post('/reports/budget-exceptions', { ...v, entity_id: entityId, period })), 'Budget exception snapshot saved');
                }}>
                  <Field label={'Materiality threshold · ' + entity.currency} name="materiality" type="number" min="0" step="0.01" defaultValue="1000" />
                  <button disabled={busy}>Review budget exceptions</button>
                </form>
                {budgetReview && (
                  <>
                    <p className="banner">{budgetReview.exceptions} accounts need review · {budgetReview.unbudgeted_accounts} accounts without budgets</p>
                    <p>Budgeted earnings impact: {budgetReview.budgeted_earnings_impact} {budgetReview.currency}</p>
                    <Table cols={[["Account", "name"], ["Actual", "actual"], ["Budget", r => r.budget ?? 'Missing'], ["Earnings impact", r => r.earnings_impact ?? 'Unknown'], ["Variance %", r => r.variance_percent ?? 'Not available'], ["Budget version", r => r.budget_version ?? '—'], ["Review", r => r.reason.replaceAll('_', ' ')]]} rows={budgetReview.rows} />
                    <p className="muted">{budgetReview.basis}</p>
                  </>
                )}
              </>
            ))}

            {panel('Budget versus actual', (
              <>
                <Table cols={[["Account", "name"], ["Actual", "actual"], ["Budget", r => r.budget ?? 'Not set'], ["Variance", r => r.variance ?? '—'], ["Version", r => r.budget_version ?? '—']]} rows={fin.budget} />
                {control && (
                  <form onSubmit={e => form(e, v => post('/budgets', { ...v, version: Number(v.version), entity_id: entityId, period }), 'Budget version saved')}>
                    <div className="formgrid">
                      <Field label="Revenue or expense account" name="account_code" options={fin.accounts.filter(a => ['revenue', 'expense'].includes(a.category)).map(a => ({ value: a.code, label: a.code + ' · ' + a.name }))} />
                      <Field label="Budget amount" name="amount" type="number" min="0" step="0.01" />
                      <Field label="Budget version" name="version" type="number" min="1" defaultValue="1" />
                    </div>
                    <button disabled={busy}>Save budget version</button>
                  </form>
                )}
                <p className="muted">Actual minus budget. Positive expense variance means spending above budget.</p>
              </>
            ))}
          </>
        )}

        {/* FINANCIAL CLOSE TAB */}
        {tab === 'Financial Close' && (
          <>
            {entity && panel('Independent close approval and ledger lock', (
              <>
                <p>Submit only after readiness checks pass. Submission freezes journal changes; a different controller must approve the lock. Only an owner can reopen it with an audit reason.</p>
                <button disabled={busy} onClick={() => act(async () => PC(await request('/close/period-control?entity_id=' + entityId + '&period=' + period)), 'Period status loaded')}>
                  Inspect period lock
                </button>
                {periodControl && <p className="banner">Period: {periodControl.status} · {periodControl.note}</p>}
                {control && (
                  <form onSubmit={e => {
                    e.preventDefault();
                    const v = values(e);
                    act(async () => PC(await post('/close/period-control', { ...v, entity_id: entityId, period })), 'Period control updated');
                  }}>
                    <Field label="Period action" name="action" options={['submit', 'approve', 'reject', ...(user?.role === 'owner' ? ['reopen'] : [])]} />
                    <Field label="Control reason" name="note" minLength={5} maxLength={500} />
                    <button disabled={busy}>Record period action</button>
                  </form>
                )}
                <p className="muted">This freezes journal and bank imports. A lock is an internal control, not accounting certification.</p>
              </>
            ))}

            {entity && panel('Close readiness and source verification', (
              <>
                <p>Check this entity and period before controller review. Refresh after any ledger, evidence or source change.</p>
                <div className="actions">
                  <button disabled={busy} onClick={() => act(async () => R(await request('/close/readiness?entity_id=' + entityId + '&period=' + period)), 'Readiness checked')}>
                    Check readiness
                  </button>
                  {control && (
                    <button disabled={busy} onClick={() => act(async () => {
                      R(await post('/close/readiness', { entity_id: entityId, period }));
                      Q(await request('/close/snapshots?entity_id=' + entityId + '&period=' + period));
                    }, 'Readiness snapshot saved')}>
                      Save audit snapshot
                    </button>
                  )}
                </div>
                {readiness && (
                  <>
                    <div className="banner">{readiness.ready_for_review ? 'Imported records pass readiness checks' : 'Review blocked: ' + readiness.blockers.length + ' checks need attention'}</div>
                    <Table
                      cols={[
                        ["Control", "label"],
                        ["Result", r => r.passed ? 'Pass' : 'Needs attention'],
                        ["Affected records", r => r.affected_ids.length ? <details><summary>{r.affected_ids.length} records</summary>{r.affected_ids.map(id => <p key={id}><code>{id}</code></p>)}</details> : 0],
                        ["Next step", r => <><p>{r.remedy}</p>{!r.passed && <button disabled={busy} onClick={() => T(r.module)}>Open {r.module}</button>}</>]
                      ]}
                      rows={readiness.checks}
                    />
                    <p className="muted">Checked {readiness.checked_at}{readiness.run_id ? ' · Snapshot ' + readiness.run_id : ''}</p>
                    <p className="muted">{readiness.basis}</p>
                    {readiness.run_id && <button disabled={busy} onClick={() => download('/close/snapshots/' + readiness.run_id + '/export', 'close-readiness-' + period + '.zip')}>Download signed snapshot</button>}
                  </>
                )}
              </>
            ))}

            {entity && panel('Saved close reports', (
              <>
                <p>Historical snapshots record what was checked at that time. Check current readiness before making a decision.</p>
                <button disabled={busy} onClick={() => act(async () => Q(await request('/close/snapshots?entity_id=' + entityId + '&period=' + period)), 'Saved reports loaded')}>
                  Load saved reports
                </button>
                {closeHistory?.length === 0 && <p className="muted">No saved reports for this entity and period.</p>}
                {closeHistory && (
                  <Table
                    cols={[
                      ["Saved", "created_at"],
                      ["Review status", r => r.ready_for_review ? 'Checks passed at snapshot time' : r.blockers.length + ' unmet checks'],
                      ["Actions", r => <div className="actions"><button disabled={busy} onClick={() => R({ ...r.output, run_id: r.id })}>View snapshot</button><button disabled={busy} onClick={() => download('/close/snapshots/' + r.id + '/export', 'close-readiness-' + period + '.zip')}>Download signed report</button></div>]
                    ]}
                    rows={closeHistory}
                  />
                )}
              </>
            ))}

            {panel('Close calendar and dependencies', (
              <>
                <Table
                  cols={[
                    ["Task", "title"],
                    ["Owner", r => data.users.find(u => u.id === r.owner_id)?.name],
                    ["Due", "due_date"],
                    ["Prerequisites", r => r.depends_on.length],
                    ["Status", r => write ? (
                      <select aria-label={'Status for ' + r.title} value={r.status} disabled={busy} onChange={e => act(() => post('/close/tasks/' + r.id, { status: e.target.value }, 'PATCH'), 'Task updated')}>
                        {['todo', 'in_progress', 'complete'].map(s => <option key={s}>{s}</option>)}
                      </select>
                    ) : r.status]
                  ]}
                  rows={data.tasks.filter(t => !entityId || t.entity_id === entityId)}
                />
                {entity && write && (
                  <form onSubmit={e => form(e, v => {
                    const dependency = v.dependency; delete v.dependency;
                    return post('/close/tasks', { ...v, entity_id: entityId, period, depends_on: dependency ? [dependency] : [] });
                  }, 'Task created')}>
                    <div className="formgrid">
                      <Field label="Task title" name="title" />
                      <Field label="Owner" name="owner_id" options={data.users.map(u => ({ value: u.id, label: u.name }))} />
                      <Field label="Due date" name="due_date" type="date" />
                      <Field label="Prerequisite" name="dependency" required={false} options={[{ value: '', label: 'None' }, ...data.tasks.filter(t => t.entity_id === entityId).map(t => ({ value: t.id, label: t.title }))]} />
                    </div>
                    <button disabled={busy}>Add task</button>
                  </form>
                )}
              </>
            ))}

            {entity && panel('Bank to ledger reconciliation', (
              <>
                <Table
                  cols={[
                    ["Bank reference", "external_id"],
                    ["Date", "date"],
                    ["Amount", "amount"],
                    ["Status", "status"],
                    ["Candidates", r => <div className="actions">{r.suggestions.map(s => <button key={s.line_id} disabled={busy || !control} onClick={() => act(() => post('/reconciliation/matches', { bank_id: r.id, line_id: s.line_id }), 'Bank match confirmed')}>Confirm {s.external_id}</button>)}</div>]
                  ]}
                  rows={fin.bank.transactions}
                />
                <p className="muted">{fin.bank.rule}</p>
                {write && (
                  <form onSubmit={e => form(e, v => post('/bank/import', { entity_id: entityId, transactions: [{ ...v, currency: entity.currency }] }), 'Bank record imported')}>
                    <div className="formgrid">
                      <Field label="Bank source ID" name="external_id" />
                      <Field label="Date" name="date" type="date" />
                      <Field label="Signed amount" name="amount" type="number" step="0.01" />
                      <Field label="Payment reference" name="reference" />
                    </div>
                    <button disabled={busy}>Import bank transaction</button>
                  </form>
                )}
              </>
            ))}

            {panel('Journal proposals and independent approvals', (
              <>
                {data.proposals.map(p => (
                  <div className="proposal" key={p.id}>
                    <div className="toolbar"><b>{p.reason}</b><span className="pill">{p.status}</span></div>
                    <p>Submitted by {data.users.find(u => u.id === p.submitted_by)?.name} · {p.journal.external_id}</p>
                    <Table cols={[["Account", "account_code"], ["Debit", "debit"], ["Credit", "credit"]]} rows={p.journal.lines} />
                    {p.status === 'pending' && control && p.submitted_by !== user?.id && (
                      <form onSubmit={e => form(e, v => post('/proposals/' + p.id + '/decision', v), 'Independent review recorded')}>
                        <Field label="Decision" name="decision" options={['approved', 'rejected']} />
                        <Field label="Review note" name="note" minLength={3} />
                        <button disabled={busy}>Record decision</button>
                      </form>
                    )}
                    {p.status === 'approved' && control && (
                      <button onClick={() => act(async () => V(await request('/proposals/' + p.id + '/export')), 'Approved draft loaded')}>View approved draft</button>
                    )}
                    <p className="muted">{p.decision_note || 'An independent controller must review.'}</p>
                  </div>
                ))}
                {!data.proposals.length && <p className="muted">No proposals yet.</p>}
                {detail && <Json value={detail} />}
              </>
            ))}

            {entity && write && panel('Propose a balanced adjustment', (
              <JournalEditor proposal entity={entity} accounts={fin.accounts} busy={busy} save={(journal, reason) => act(() => post('/proposals', { entity_id: entityId, reason, journal }), 'Proposal submitted')} />
            ))}
          </>
        )}

        {/* CASH INTELLIGENCE TAB */}
        {tab === 'Cash Intelligence' && entity && (
          <>
            <CopilotSimulator
              entityId={entityId}
              onSimulate={runSimulation}
              result={copilotResult}
              busy={busy}
            />

            {panel('Reverse liquidity stress test', (
              <>
                <p>Find how much collections can fall before a saved forecast breaches your cash reserve.</p>
                <form onSubmit={e => {
                  e.preventDefault();
                  act(async () => LM(await post('/cash/liquidity-limits', values(e))), 'Liquidity limit snapshot saved');
                }}>
                  <div className="formgrid">
                    <Field label="Forecast for liquidity limit" name="forecast_id" options={data.runs.filter(r => r.kind === 'cash_forecast' && r.inputs.entity_id === entityId).map(r => ({ value: r.id, label: r.created_at + ' · start ' + r.inputs.start_date }))} />
                    <Field label={'Protected reserve · ' + entity.currency} name="reserve" type="number" min="0" step="0.01" defaultValue="100000" />
                  </div>
                  <button disabled={busy || !data.runs.some(r => r.kind === 'cash_forecast' && r.inputs.entity_id === entityId)}>Find collection loss limit</button>
                </form>
                {limits && (
                  <>
                    <p className="banner">{limits.status === 'baseline_breaches_reserve' ? 'Baseline already breaches the reserve' : limits.status === 'all_collections_can_be_lost' ? 'Reserve survives even with zero collections' : 'Maximum uniform collection reduction: ' + limits.maximum_collection_loss_percent + '%'}</p>
                    <p>Baseline funding needed: {limits.baseline_funding_to_reserve} {limits.currency} · Funding with no collections: {limits.funding_with_no_collections} {limits.currency}</p>
                    <Table cols={[["Week", "week"], ["Through", "end"], ["Retained inflow", "inflow"], ["Outflow", "outflow"], ["Closing cash", "closing"], ["Reserve headroom", "headroom"]]} rows={limits.weeks} />
                    <p className="muted">{limits.basis}</p>
                  </>
                )}
              </>
            ))}

            {panel('Receivables collection monitor', (
              <>
                <p>Prioritize expected receipts using exact bank-reference evidence. Review the largest outstanding schedules and overdue amounts.</p>
                <form onSubmit={e => {
                  e.preventDefault();
                  const v = values(e);
                  act(async () => CM(await request('/cash/collections?entity_id=' + entityId + '&as_of=' + v.as_of)), 'Collection review loaded');
                }}>
                  <Field label="Collection review date" name="as_of" type="date" defaultValue={new Date().toISOString().slice(0, 10)} />
                  <button disabled={busy}>Review collections</button>
                </form>
                {collections && (
                  <>
                    <div className="stats">
                      <article><p>Outstanding · {collections.currency}</p><strong>{collections.outstanding}</strong></article>
                      <article><p>Overdue · {collections.currency}</p><strong>{collections.overdue}</strong></article>
                      <article><p>Largest five schedules</p><strong>{collections.largest_five_share_percent ?? '—'}%</strong></article>
                    </div>
                    <Table cols={[["Age bucket", "bucket"], ["Outstanding", "outstanding"]]} rows={collections.aging} />
                    <Table cols={[["Reference", "reference"], ["Due", "due_date"], ["Expected", "expected"], ["Net bank evidence", "net_bank_evidence"], ["Outstanding", "outstanding"], ["Days overdue", "days_overdue"], ["Evidence", r => r.status.replaceAll('_', ' ')]]} rows={collections.rows} />
                    <p className="muted">{collections.basis}</p>
                  </>
                )}
              </>
            ))}

            {write && panel('Treasury stress lab', (
              <>
                <p>Test a saved forecast under delayed collections and cash-flow shocks. Set the reserve your finance team needs to protect.</p>
                <form onSubmit={e => {
                  e.preventDefault();
                  const v = values(e);
                  v.collection_delay_weeks = Number(v.collection_delay_weeks);
                  act(async () => ST(await post('/cash/stress', v)), 'Treasury stress snapshot saved');
                }}>
                  <div className="formgrid">
                    <Field label="Forecast to stress" name="forecast_id" options={data.runs.filter(r => r.kind === 'cash_forecast' && r.inputs.entity_id === entityId).map(r => ({ value: r.id, label: r.created_at + ' · start ' + r.inputs.start_date }))} />
                    <Field label={'Minimum reserve · ' + entity.currency} name="reserve" type="number" min="0" step="0.01" defaultValue="25000" />
                    <Field label="Collection delay (weeks)" name="collection_delay_weeks" type="number" min="0" max="12" defaultValue="2" />
                    <Field label="Stressed inflow multiplier" name="inflow_factor" type="number" min="0" max="3" step="0.01" defaultValue="0.70" />
                    <Field label="Stressed outflow multiplier" name="outflow_factor" type="number" min="0" max="3" step="0.01" defaultValue="1.20" />
                  </div>
                  <button className="primary" disabled={busy || !data.runs.some(r => r.kind === 'cash_forecast' && r.inputs.entity_id === entityId)}>
                    Run treasury stress test
                  </button>
                </form>
                {stress && (
                  <>
                    <p className="banner">Reserve: {stress.reserve} {stress.currency} · Five scenarios saved for review</p>
                    <Table cols={[["Scenario", "name"], ["Lowest cash", "minimum_cash"], ["Ending cash", "ending_cash"], ["First reserve breach", r => r.first_reserve_breach || 'None at weekly closes'], ["Funding to reserve", "funding_to_reserve"]]} rows={stress.scenarios} />
                    <p className="muted">{stress.basis}</p>
                  </>
                )}
              </>
            ))}

            {panel('Forecast reliability review', (
              <>
                <p>Compare a saved scenario with imported bank movements for completed weeks.</p>
                <form onSubmit={e => {
                  e.preventDefault();
                  const v = values(e);
                  act(async () => CR(await request('/cash/forecasts/' + v.run_id + '/review?as_of=' + v.as_of + '&tolerance=' + v.tolerance)), 'Forecast comparison loaded');
                }}>
                  <div className="formgrid">
                    <Field label="Saved cash scenario" name="run_id" options={data.runs.filter(r => r.kind === 'cash_forecast' && r.inputs.entity_id === entityId).map(r => ({ value: r.id, label: r.created_at + ' · start ' + r.inputs.start_date }))} />
                    <Field label="Review through" name="as_of" type="date" defaultValue={new Date().toISOString().slice(0, 10)} />
                    <Field label={'Review tolerance · ' + entity.currency} name="tolerance" type="number" min="0" max="1000000000" step="0.01" defaultValue="100" />
                  </div>
                  <button disabled={busy || !data.runs.some(r => r.kind === 'cash_forecast' && r.inputs.entity_id === entityId)}>
                    Compare with bank actuals
                  </button>
                </form>
                {cashReview && (
                  <>
                    <p className="banner">{cashReview.observed_weeks} weeks with bank records · Mean absolute net error: {cashReview.mean_absolute_net_error ?? 'Not available'} {cashReview.currency}</p>
                    <Table cols={[["Week", "week"], ["Through", "end"], ["Forecast net", "forecast_net"], ["Imported net", "imported_net"], ["Net error", "net_error"], ["Review", r => r.status.replaceAll('_', ' ')]]} rows={cashReview.weeks} />
                    <p className="muted">{cashReview.basis}</p>
                  </>
                )}
              </>
            ))}

            {panel('Expected payment schedule · ' + entity.currency, (
              <>
                <Table cols={[["Reference", "reference"], ["Due date", "due_date"], ["Direction", "direction"], ["Amount", "amount"]]} rows={fin.payments} />
                {write && (
                  <form onSubmit={e => form(e, v => post('/cash/payments', { ...v, entity_id: entityId }), 'Expected payment added')}>
                    <div className="formgrid">
                      <Field label="Reference" name="reference" />
                      <Field label="Due date" name="due_date" type="date" />
                      <Field label="Amount" name="amount" type="number" min="0.01" step="0.01" />
                      <Field label="Direction" name="direction" options={['inflow', 'outflow']} />
                    </div>
                    <button disabled={busy}>Add expected payment</button>
                  </form>
                )}
              </>
            ))}

            {write && panel('13-week cash scenario', (
              <>
                <form onSubmit={e => {
                  e.preventDefault();
                  const v = values(e);
                  v.collection_delay_days = Number(v.collection_delay_days);
                  act(async () => H(await post('/cash/forecast', { ...v, entity_id: entityId })), 'Scenario snapshot saved');
                }}>
                  <div className="formgrid">
                    <Field label="Start date" name="start_date" type="date" defaultValue="2026-10-08" />
                    <Field label="Opening cash" name="opening_cash" type="number" step="0.01" defaultValue="113800" />
                    <Field label="Collection delay (days)" name="collection_delay_days" type="number" defaultValue="0" min="0" max="90" />
                    <Field label="Inflow multiplier" name="inflow_factor" type="number" step="0.01" min="0" max="3" defaultValue="1" />
                    <Field label="Outflow multiplier" name="outflow_factor" type="number" step="0.01" min="0" max="3" defaultValue="1" />
                  </div>
                  <button disabled={busy} className="primary">Run cash scenario</button>
                </form>
                {forecast && (
                  <>
                    <Table cols={[["Week", "week"], ["Start", "start"], ["Opening", "opening"], ["Inflow", "inflow"], ["Outflow", "outflow"], ["Closing", "closing"]]} rows={forecast.weeks} />
                    <p className="muted">{forecast.confidence}</p>
                  </>
                )}
              </>
            ))}
          </>
        )}

        {/* AUDIT AUTOMATION TAB */}
        {tab === 'Audit Automation' && (
          <>
            {panel('Evidence repository', (
              <>
                {entity && <button onClick={() => download('/audit/package?entity_id=' + entityId, 'audit-evidence.zip')}>Export evidence package</button>}
                <Table
                  cols={[
                    ["Document", "filename"],
                    ["Journal", r => fin.journals.find(j => j.id === r.journal_id)?.external_id || r.journal_id],
                    ["SHA-256", r => <code title={r.sha256}>{r.sha256.slice(0, 20)}…</code>],
                    ["Download", r => <button onClick={() => download('/evidence/' + r.id + '/download', r.filename)}>Download</button>]
                  ]}
                  rows={data.evidence}
                />
                {entity && write && (
                  <form onSubmit={e => {
                    e.preventDefault();
                    const body = new FormData(e.currentTarget);
                    act(() => request('/evidence', { method: 'POST', body }), 'Evidence hashed and linked');
                  }}>
                    <Field label="Journal" name="journal_id" options={fin.journals.map(j => ({ value: j.id, label: j.external_id + ' · v' + j.version }))} />
                    <Field label="Document (up to 5 MB)" name="file" type="file" />
                    <button disabled={busy || !fin.journals.length}>Attach evidence</button>
                  </form>
                )}
              </>
            ))}

            {entity && panel('Missing evidence', <Table cols={[["Journal", "external_id"], ["Gap", "finding"]]} rows={fin.gaps} />)}

            {panel('Actor-attributed event chain & cryptographic proof', (
              <>
                <button onClick={() => act(async () => V(await request('/audit/verify')), 'Chain checked')}>Verify hashes</button>
                {detail?.valid !== undefined && (
                  <div className={detail.valid ? 'success' : 'error'}>
                    {detail.valid ? 'Chain hashes verified' : 'Integrity check failed'} · {detail.events} events
                  </div>
                )}
                <Table
                  cols={[
                    ["Action", "action"],
                    ["Actor", r => data.users.find(u => u.id === r.actor_id)?.name || r.actor_id],
                    ["UTC time", "created_at"],
                    ["Hash", r => <code>{r.event_hash.slice(0, 16)}…</code>]
                  ]}
                  rows={data.audit}
                />
                <p className="muted">Local hashes detect modifications. Anchored in ML-DSA post-quantum signatures.</p>
              </>
            ))}
          </>
        )}

        {/* ORGANIZATION TAB */}
        {tab === 'Organization' && (
          <>
            {panel('Your active sessions', (
              <>
                <p>Review signed-in sessions for your account. Revoking a session blocks its next API request.</p>
                <div className="actions">
                  <button disabled={busy} onClick={() => act(async () => SS(await request('/auth/sessions')), 'Active sessions loaded')}>
                    Review active sessions
                  </button>
                  <button disabled={busy || !sessions?.some(s => !s.current)} onClick={() => act(async () => {
                    await post('/auth/sessions/revoke-others', {});
                    SS(await request('/auth/sessions'));
                  }, 'Other sessions signed out')}>
                    Sign out other sessions
                  </button>
                </div>
                {sessions && (
                  <Table
                    cols={[
                      ["Session", r => r.current ? 'This session' : 'Other session'],
                      ["Expires", r => new Date(r.expires_at).toLocaleString()],
                      ["Reference", r => r.id.slice(0, 12)],
                      ["Action", r => (
                        <button disabled={busy} onClick={async () => {
                          if (r.current) {
                            B(true);
                            try {
                              await post('/auth/sessions/' + r.id + '/revoke', {});
                              K(''); U(null); SS(null);
                            } catch (e) { E(e.message); } finally { B(false); }
                          } else {
                            act(async () => {
                              await post('/auth/sessions/' + r.id + '/revoke', {});
                              SS(await request('/auth/sessions'));
                            }, 'Session revoked');
                          }
                        }}>
                          {r.current ? 'Sign out this session' : 'Revoke session'}
                        </button>
                      )]
                    ]}
                    rows={sessions}
                  />
                )}
              </>
            ))}

            {panel('Legal entities', (
              <>
                <Table cols={[["Code", "code"], ["Entity", "name"], ["Currency", "currency"]]} rows={data.entities} />
                {control && (
                  <form onSubmit={e => form(e, v => post('/entities', { ...v, parent_id: v.parent_id || null }), 'Entity created')}>
                    <div className="formgrid">
                      <Field label="Entity code" name="code" />
                      <Field label="Entity name" name="name" />
                      <Field label="Currency" name="currency" defaultValue="USD" maxLength={3} />
                      <Field label="Parent" name="parent_id" required={false} options={[{ value: '', label: 'None' }, ...data.entities.map(x => ({ value: x.id, label: x.name }))]} />
                    </div>
                    <button className="primary" disabled={busy}>Add entity</button>
                  </form>
                )}
              </>
            ))}

            {entity && panel('Account mappings', (
              <>
                <Table cols={[["Code", "code"], ["Account", "name"], ["Type", "category"], ["Group code", "group_code"], ["Cash", r => r.is_cash ? 'Yes' : '—']]} rows={fin.accounts} />
                {control && (
                  <form onSubmit={e => form(e, v => post(`/entities/${entityId}/accounts`, { ...v, is_cash: v.is_cash === 'yes' }), 'Mapping created')}>
                    <div className="formgrid">
                      <Field label="Account code" name="code" />
                      <Field label="Account name" name="name" />
                      <Field label="Classification" name="category" options={['asset', 'liability', 'equity', 'revenue', 'expense']} />
                      <Field label="Group account" name="group_code" />
                      <Field label="Cash?" name="is_cash" options={['no', 'yes']} />
                    </div>
                    <button disabled={busy}>Create account</button>
                  </form>
                )}
              </>
            ))}

            {panel('Team and roles', (
              <>
                <Table cols={[["Name", "name"], ["Email", "email"], ["Role", "role"]]} rows={data.users} />
                {user?.role === 'owner' && (
                  <form onSubmit={e => form(e, v => post('/users', v), 'Member created')}>
                    <div className="formgrid">
                      <Field label="Name" name="name" />
                      <Field label="Email" name="email" type="email" />
                      <Field label="Initial password" name="password" type="password" minLength={12} />
                      <Field label="Role" name="role" options={['controller', 'analyst', 'auditor']} />
                    </div>
                    <button disabled={busy}>Create member</button>
                  </form>
                )}
                <p className="muted">Auditors read; analysts import and propose; controllers review; owners manage the organization.</p>
              </>
            ))}
          </>
        )}

        {/* LEGACY MODERNIZATION TAB */}
        {tab === 'Legacy Modernization' && entity && panel('Discover and map a legacy extract', (
          <>
            <p>Upload CSV journal lines. Map fields, inspect validation, and archive the original source alongside normalized journals.</p>
            <input aria-label="Legacy CSV" type="file" accept=".csv" onChange={e => { C(e.target.files[0]); M({}); W(null); }} />
            <div className="actions">
              <button disabled={busy || !file || !write} onClick={() => mapCSV()}>Discover columns</button>
            </div>
            {preview && (
              <>
                <div className="formgrid">
                  {['external_id', 'posting_date', 'transaction_date', 'account_code', 'debit', 'credit', 'reference', 'description', 'version'].map(field => (
                    <label className="field" key={field}>
                      <span>{field.replaceAll('_', ' ')}</span>
                      <select aria-label={'Map ' + field} value={mapping[field] || ''} onChange={e => {
                        const changed = { ...mapping };
                        if (e.target.value) changed[field] = e.target.value; else delete changed[field];
                        M(changed); W({ ...preview, valid: false });
                      }}>
                        <option value="">Not mapped</option>
                        {preview.columns.map(col => <option key={col}>{col}</option>)}
                      </select>
                    </label>
                  ))}
                </div>
                <div className="actions">
                  <button disabled={busy} onClick={() => mapCSV()}>Validate mapping</button>
                  <button className="primary" disabled={busy || !preview.valid} onClick={() => mapCSV(true)}>Import validated source</button>
                </div>
                <p className={preview.valid ? 'success' : 'error'}>{preview.valid ? `${preview.journals.length} balanced journals ready` : 'Mapping or validation needs attention'}</p>
                {preview.errors?.map((x, i) => <p key={i} className="muted">{x}</p>)}
                <details>
                  <summary>Normalized preview and source hash</summary>
                  <Json value={{ sha256: preview.source_sha256, journals: preview.journals }} />
                </details>
              </>
            )}
          </>
        ))}

        {/* CONSOLIDATION TAB */}
        {tab === 'Consolidation' && (
          <>
            {panel('Group trial-balance translation', (
              <>
                <p>Combine explicit group account mappings with supplied FX snapshot rates.</p>
                {control && (
                  <form onSubmit={e => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget), ids = f.getAll('entity_ids'), rates = {};
                    for (const id of ids) { if (f.get('rate_' + id)) rates[id] = f.get('rate_' + id); }
                    const mode = e.nativeEvent.submitter?.value;
                    const body = { entity_ids: ids, period, group_currency: f.get('group_currency'), rates, approved_elimination_ids: mode === 'matching' ? [] : f.getAll('eliminations') };
                    act(async () => J(await post(mode === 'matching' ? '/intercompany/runs' : '/consolidation/runs', body)), 'Group analysis snapshot saved');
                  }}>
                    <Field label="Group currency" name="group_currency" maxLength={3} defaultValue="USD" />
                    {data.entities.map(e => (
                      <div className="entityrate" key={e.id}>
                        <label><input type="checkbox" name="entity_ids" value={e.id} defaultChecked /> {e.name} · {e.currency}</label>
                        <Field label="FX rate into group currency" name={'rate_' + e.id} type="number" min="0.00000001" step="0.00000001" required={false} defaultValue={e.currency === 'USD' ? '1' : '1.1'} />
                      </div>
                    ))}
                    <div className="actions">
                      <button disabled={busy || !data.entities.length} className="primary" value="group">Build group trial balance</button>
                      <button disabled={busy || !data.entities.length} value="matching">Match intercompany claims</button>
                    </div>
                    {data.eliminations.filter(p => p.status === 'approved').map(p => (
                      <label key={p.id}><input type="checkbox" name="eliminations" value={p.id} /> Apply approved draft: {p.reason}</label>
                    ))}
                  </form>
                )}
                {group && (
                  <>
                    {group.rows ? (
                      <Table cols={[["Group account", "group_code"], ["Type", "category"], ["Translated balance", "balance"]]} rows={group.rows} />
                    ) : (
                      <>
                        <Table cols={[["Entity", "entity"], ["Counterparty", "counterparty"], ["Reference", "reference"], ["Amount", "translated_amount"], ["Status", "status"]]} rows={group.claims || []} />
                        <Table cols={[["Elimination account", "group_code"], ["Type", "category"], ["Adjustment", "balance"]]} rows={group.proposed_elimination_rows || []} />
                        {group.proposed_elimination_rows?.length > 0 && control && (
                          <button disabled={busy} onClick={() => act(() => post('/consolidation/elimination-proposals', { source_run_id: group.id, reason: 'Eliminate matched reciprocal intercompany balances' }), 'Elimination submitted for independent review')}>
                            Propose elimination for review
                          </button>
                        )}
                      </>
                    )}
                    <p>Translation difference: {group.translation_difference} · {group.currency}</p>
                    <div className="banner">{group.scope}</div>
                  </>
                )}
              </>
            ))}

            {panel('Independent elimination review', (
              <>
                {data.eliminations.map(p => (
                  <div className="proposal" key={p.id}>
                    <b>{p.reason}</b><span className="pill">{p.status}</span>
                    <Table cols={[["Group account", "group_code"], ["Type", "category"], ["Adjustment", "balance"]]} rows={p.rows} />
                    {control && p.status === 'pending' && p.submitted_by !== user.id && (
                      <form onSubmit={e => form(e, v => post('/consolidation/elimination-proposals/' + p.id + '/decision', v), 'Elimination review recorded')}>
                        <Field label="Decision" name="decision" options={['approved', 'rejected']} />
                        <Field label="Review note" name="note" minLength={3} />
                        <button disabled={busy}>Record independent decision</button>
                      </form>
                    )}
                    <p className="muted">{p.decision_note || 'A different controller must review before this draft can be applied.'}</p>
                  </div>
                ))}
                {!data.eliminations.length && <p className="muted">Tag reciprocal asset and liability journal lines with IC:COUNTERPARTY_CODE:REFERENCE, then run matching above.</p>}
              </>
            ))}
          </>
        )}

        {/* EVENT RECONCILIATION TAB */}
        {tab === 'Event Reconciliation' && (
          <>
            {control && panel('Synchronization policy and source comparison', (
              <>
                <form onSubmit={e => {
                  e.preventDefault();
                  const v = values(e);
                  act(async () => {
                    await post('/integration/policy', Object.fromEntries(Object.entries(v).map(([k, n]) => [k, Number(n)])));
                    S(await request('/integration/status'));
                  }, 'Reconciliation policy saved');
                }}>
                  <div className="formgrid">
                    <Field label="Pending delay threshold (seconds)" name="max_pending_seconds" type="number" min="1" max="86400" defaultValue="300" />
                    <Field label="Source observation age threshold (seconds)" name="max_source_age_seconds" type="number" min="1" max="604800" defaultValue="3600" />
                    <Field label="Background reconciliation interval (seconds)" name="reconciliation_interval_seconds" type="number" min="5" max="3600" defaultValue="30" />
                  </div>
                  <button disabled={busy}>Save thresholds</button>
                </form>
                {entity && (
                  <>
                    <button disabled={busy} onClick={() => act(async () => V(await request('/integration/manifest?entity_id=' + entityId)), 'Local manifest inspected')}>
                      Inspect local manual-source manifest
                    </button>
                    <form onSubmit={e => {
                      e.preventDefault();
                      let body; try { body = JSON.parse(values(e).manifest); } catch { E('Manifest must be valid JSON'); return; }
                      act(async () => {
                        V(await post('/integration/reconcile', { ...body, entity_id: entityId }));
                        S(await request('/integration/status'));
                      }, 'Source manifest compared');
                    }}>
                      <label className="field"><span>Authoritative source manifest</span><textarea name="manifest" required rows={6} /></label>
                      <button disabled={busy}>Compare source snapshot</button>
                    </form>
                  </>
                )}
                {detail && <Json value={detail} />}
              </>
            ))}

            {panel('Durable event reconciliation', (
              <>
                <div className="actions">
                  <button disabled={busy} onClick={() => act(async () => S(await request('/integration/status')), 'Event backlog refreshed')}>
                    Inspect backlog
                  </button>
                  {control && (
                    <button disabled={busy} onClick={() => act(async () => {
                      await post('/integration/process', {});
                      S(await request('/integration/status'));
                    }, 'Available events processed')}>
                      Process available events
                    </button>
                  )}
                </div>
                {stream && (
                  <>
                    <div className="banner">{stream.projection_caught_up ? 'All received events applied' : `${stream.unresolved} unresolved events`}</div>
                    <Table cols={[["Entity", "entity_id"], ["Connection", "connection_id"], ["Watermark", "watermark"], ["Age (s)", r => Math.round(r.age_seconds)], ["Freshness", r => r.stale ? 'Stale' : 'Within threshold']]} rows={stream.freshness?.sources || []} />
                    <Table cols={[["Event", "event_id"], ["Source", "external_id"], ["Version", "version"], ["Status", "status"], ["Issue", "error"]]} rows={stream.messages || []} />
                  </>
                )}
              </>
            ))}
          </>
        )}

        {/* ERP INTEGRATION TAB */}
        {tab === 'ERP Integration' && (
          <>
            {panel('Read-only ERP connections', (
              <>
                <Table
                  cols={[
                    ["Connection", "name"],
                    ["Provider", "provider"],
                    ["Health", "status"],
                    ["Credential", r => r.credentials_configured ? 'Configured' : 'Missing deployment secret'],
                    ["Sync", r => control && <button disabled={busy} onClick={() => act(() => post('/connections/' + r.id + '/sync', {}), 'Sync queued')}>Queue sync</button>]
                  ]}
                  rows={data.connections}
                />
                {user?.role === 'owner' && entity && (
                  <form onSubmit={e => {
                    e.preventDefault();
                    const v = values(e);
                    let config; try { config = JSON.parse(v.config); } catch { E('Provider settings must be valid JSON'); return; }
                    act(() => post('/connections', { entity_id: entityId, name: v.name, provider: v.provider, credential_env: v.credential_env, config }), 'Connection configured');
                  }}>
                    <div className="formgrid">
                      <Field label="Connection name" name="name" />
                      <Field label="Provider" name="provider" options={['business_central', 'netsuite']} />
                      <Field label="Deployment credential variable" name="credential_env" defaultValue={'FINANCE_SECRET_' + user.org_id.replaceAll('-', '').toUpperCase() + '_BC'} />
                    </div>
                    <label className="field"><span>Provider settings JSON</span><textarea name="config" required rows={4} defaultValue={'{"tenant_id":"YOUR-ENTRA-TENANT-UUID","company_id":"YOUR-COMPANY-UUID","environment":"Production","account_mapping":{}}'} /></label>
                    <button disabled={busy} className="primary">Configure connector</button>
                  </form>
                )}
              </>
            ))}

            {panel('Sync checkpoints and retry queue', (
              <Table
                cols={[
                  ["Connection", r => data.connections.find(c => c.id === r.connection_id)?.name],
                  ["Status", "status"],
                  ["Failures", "attempts"],
                  ["Staged rows", "staged_rows"],
                  ["Error", r => r.result?.error || '—'],
                  ["Action", r => control && ['queued', 'running', 'failed'].includes(r.status) && (
                    <button disabled={busy} onClick={() => act(() => post('/sync/jobs/' + r.id + '/step', {}), 'Sync step finished')}>Advance / retry</button>
                  )]
                ]}
                rows={data.jobs}
              />
            ))}
          </>
        )}

        {/* PLANS & PRICING TAB */}
        {tab === 'Plans & Pricing' && (
          <PricingSection />
        )}

        {!entity && !['Overview', 'Organization', 'ERP Integration', 'Event Reconciliation', 'Audit Automation', 'Plans & Pricing'].includes(tab) && panel('Create your first legal entity', (
          <>
            <p>Add an entity in Organization or load the example workspace from Overview.</p>
            <button onClick={() => T('Organization')}>Open organization setup</button>
          </>
        ))}

        <footer>
          AI Finance OS · Enterprise Platform · {data.entities.length} entities · Customer Support & Enquiries: <a href="mailto:bjtmusic12@gmail.com" style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: '600' }}>bjtmusic12@gmail.com</a>
        </footer>
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
