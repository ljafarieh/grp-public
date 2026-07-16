"""
Convert substack_post_1.md to a styled HTML file with charts embedded.

Open substack_post_1.html in Chrome, Cmd+A, Cmd+C, paste into Substack.
"""

from pathlib import Path

DEST = Path(__file__).parent / "substack_post_1.html"

QUEUE_CHART = """
<div style="margin: 24px 0;">
  <p style="font-size:13px;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin:0 0 4px">AEP Ohio — Columbus data center queue</p>
  <p style="font-size:12px;color:#888;margin:0 0 16px">After implementation of take-or-pay tariff</p>
  <div style="display:flex;gap:16px;margin-bottom:8px;font-size:12px;color:#888;">
    <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#3d7eaa;margin-right:4px;vertical-align:middle"></span>Bankable demand (stayed)</span>
    <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#d85a30;margin-right:4px;vertical-align:middle"></span>Withdrew after tariff</span>
  </div>
  <div style="position:relative;width:100%;height:260px;">
    <canvas id="queueChart" role="img" aria-label="Bar chart: AEP Ohio queue before tariff = 30,000 MW, after = 5,700 MW. 24,300 MW (81%) withdrew.">Before: 30,000 MW. After: 5,700 MW. 24,300 MW withdrew (81%).</canvas>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
new Chart(document.getElementById('queueChart'), {
  type: 'bar',
  data: {
    labels: ['Before tariff', 'After tariff'],
    datasets: [
      { label: 'Bankable demand', data: [5700, 5700], backgroundColor: '#3d7eaa', borderWidth: 0,
        borderRadius: {topLeft:0,topRight:0,bottomLeft:4,bottomRight:4}, borderSkipped: false },
      { label: 'Withdrew after tariff', data: [24300, 0], backgroundColor: '#d85a30', borderWidth: 0,
        borderRadius: {topLeft:4,topRight:4,bottomLeft:0,bottomRight:0}, borderSkipped: false }
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: c => ' ' + c.dataset.label + ': ' + c.parsed.y.toLocaleString() + ' MW' } }
    },
    scales: {
      x: { stacked: true, grid: { display: false }, ticks: { font: { size: 13 }, color: '#888' } },
      y: { stacked: true, min: 0, max: 35000,
           ticks: { color: '#888', font: { size: 11 }, callback: v => (v/1000).toFixed(0) + 'K MW' },
           grid: { color: 'rgba(0,0,0,0.06)' } }
    }
  },
  plugins: [{
    id: 'labels',
    afterDraw(chart) {
      const ctx = chart.ctx;
      const m0 = chart.getDatasetMeta(0), m1 = chart.getDatasetMeta(1);
      ctx.save();
      ctx.textAlign = 'center';
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 12px sans-serif';
      if (m0.data[0]) ctx.fillText('5,700 MW', m0.data[0].x, m0.data[0].y + 16);
      if (m1.data[0]) ctx.fillText('24,300 MW', m1.data[0].x, m1.data[0].y + 16);
      if (m0.data[1]) ctx.fillText('5,700 MW', m0.data[1].x, m0.data[1].y + 16);
      ctx.fillStyle = '#d85a30';
      ctx.font = 'bold 14px sans-serif';
      if (m1.data[0]) ctx.fillText('−81%', m1.data[0].x, m1.data[0].y - 10);
      ctx.restore();
    }
  }]
});
</script>
"""

PJM_GRID = """
<div style="margin: 24px 0;">
  <p style="font-size:13px;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin:0 0 4px">PJM interconnection — take-or-pay tariff spread</p>
  <p style="font-size:12px;color:#888;margin:0 0 16px">13 states, 65 million people</p>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px;">
    <div style="background:#fcebeb;border:1px solid #f09595;border-radius:8px;padding:12px 14px;">
      <div style="font-size:10px;font-weight:700;color:#a32d2d;letter-spacing:.06em;margin-bottom:6px;">COLLAPSED</div>
      <div style="font-size:14px;font-weight:600;color:#501313;">Ohio</div>
      <div style="font-size:11px;color:#a32d2d;margin-top:3px;">$AEP — 81% withdrew</div>
    </div>
    <div style="background:#fdf3dc;border:1px solid #e8b84b;border-radius:8px;padding:12px 14px;">
      <div style="font-size:10px;font-weight:700;color:#854f0b;letter-spacing:.06em;margin-bottom:6px;">ENACTED</div>
      <div style="font-size:14px;font-weight:600;color:#412402;">Maryland</div>
      <div style="font-size:11px;color:#854f0b;margin-top:3px;">$EXC — BGE/Pepco/Delmarva</div>
    </div>
    <div style="background:#fdf3dc;border:1px solid #e8b84b;border-radius:8px;padding:12px 14px;">
      <div style="font-size:10px;font-weight:700;color:#854f0b;letter-spacing:.06em;margin-bottom:6px;">PASSED LEGISLATURE</div>
      <div style="font-size:14px;font-weight:600;color:#412402;">New Jersey</div>
      <div style="font-size:11px;color:#854f0b;margin-top:3px;">$PEG, $FE — pending governor</div>
    </div>
    <div style="background:#f5f5f3;border:1px solid #ddd;border-radius:8px;padding:12px 14px;">
      <div style="font-size:10px;font-weight:700;color:#666;letter-spacing:.06em;margin-bottom:6px;">NOT YET</div>
      <div style="font-size:14px;font-weight:600;color:#222;">Pennsylvania</div>
      <div style="font-size:11px;color:#666;margin-top:3px;">$PPL — 9 GW pipeline</div>
    </div>
    <div style="background:#f5f5f3;border:1px solid #ddd;border-radius:8px;padding:12px 14px;">
      <div style="font-size:10px;font-weight:700;color:#666;letter-spacing:.06em;margin-bottom:6px;">NOT YET</div>
      <div style="font-size:14px;font-weight:600;color:#222;">Virginia</div>
      <div style="font-size:11px;color:#666;margin-top:3px;">$D — Dominion</div>
    </div>
    <div style="background:#f5f5f3;border:1px solid #ddd;border-radius:8px;padding:12px 14px;">
      <div style="font-size:10px;font-weight:700;color:#666;letter-spacing:.06em;margin-bottom:6px;">NOT YET</div>
      <div style="font-size:14px;font-weight:600;color:#222;">IL / IN / MI / WV / DE / DC</div>
      <div style="font-size:11px;color:#666;margin-top:3px;">PJM signatories</div>
    </div>
  </div>
  <div style="background:#f5f5f3;border-left:3px solid #d85a30;border-radius:0 6px 6px 0;padding:10px 14px;font-size:12px;color:#666;line-height:1.6;">
    All 13 PJM governors signed a joint Statement of Principles, January 2026: data centers pay for their own grid upgrades.
  </div>
</div>
"""

body = f"""
<h1>81% of AEP's Data Center Backlog Just Evaporated. My Bot Found It First.</h1>
<p><em>By Luke Jafarieh — Grid Realization Pipeline</em></p>
<hr>
<p><strong>In short:</strong> A public regulatory filing revealed that 24,300 MW of data center demand behind AEP's Ohio grid quietly withdrew after a new tariff forced developers to put money down. The queue went from 30,000 MW to 5,700 MW overnight. Wall Street still hasn't connected the dots.</p>
<hr>
<p>Three weeks ago, a filing hit the Ohio public utility commission docket. Nobody was reading it.</p>
<p>My pipeline was.</p>
<p>It flagged the document at 2:47 AM. By morning I had read it twice.</p>
<hr>

<h2>The Finding</h2>
<p>Here is the exact language from the filing, verbatim:</p>
<blockquote>
<p><em>"The Columbus data center interconnection cluster has withdrawn 24,300 MW of uncommitted capacity requests following implementation of the take-or-pay tariff. Expected commercial operation dates have been extended by an average of 14 months across the affected queue positions. AEP projects that confirmed contracted load has declined from 30,000 MW to 5,700 MW of bankable demand."</em></p>
<p>— American Electric Power, Ohio PUC System Impact Study Update</p>
</blockquote>
<p>AEP had 30,000 megawatts of data centers in line to connect to its Ohio grid. When regulators forced those developers to financially commit — pay a deposit or give up their spot — <strong>81% of them walked.</strong> The 30,000 MW of demand AEP has been telling investors about? The real number is 5,700 MW.</p>

{QUEUE_CHART}

<hr>

<h2>Why This Gets More Dangerous From Here</h2>
<p>This is not an AEP-specific problem. The tariff that triggered Ohio's collapse is now spreading across the entire PJM grid — 13 states, 65 million people, the electricity backbone of the Mid-Atlantic and Midwest.</p>
<p><strong>The policy timeline:</strong></p>
<ol>
<li><strong>Ohio (done):</strong> AEP implements take-or-pay. 81% of the Columbus data center queue withdraws.</li>
<li><strong>Maryland (enacted 2025–2026):</strong> Two laws passed forcing BGE, Pepco, and Delmarva (all Exelon, $EXC) to create take-or-pay tariffs for loads over 25 MW. Maryland's ratepayer advocate is in federal court over $1.6 billion in grid upgrades built for data centers that may not show up.</li>
<li><strong>New Jersey (passed June 30, 2026):</strong> 85% commitment required, 10-year term, projects over 50 MW. Pending Governor Sherrill. PSE&amp;G ($PEG) and JCP&amp;L ($FE) exposed.</li>
<li><strong>All 13 PJM governors:</strong> Joint Statement of Principles, January 2026. Data centers pay for their own grid upgrades. Full stop.</li>
</ol>

{PJM_GRID}

<hr>

<h2>The Specific Stocks to Watch</h2>
<table>
<thead><tr><th>Utility</th><th>Ticker</th><th>Signal</th></tr></thead>
<tbody>
<tr><td>American Electric Power (Ohio)</td><td><strong>$AEP</strong></td><td>Negative. Queue collapsed 81%. Load growth guidance likely overstated. Watch Q3 earnings.</td></tr>
<tr><td>Exelon — BGE / Pepco / Delmarva (Maryland)</td><td><strong>$EXC</strong></td><td>Caution. Tariff enacted. Queue collapse data not yet public.</td></tr>
<tr><td>PSEG / PSE&amp;G (New Jersey)</td><td><strong>$PEG</strong></td><td>Watch. Tariff standards set within 12 months of governor signature.</td></tr>
<tr><td>FirstEnergy / JCP&amp;L (New Jersey)</td><td><strong>$FE</strong></td><td>Watch. Same NJ exposure as PEG.</td></tr>
<tr><td>PPL Electric (Pennsylvania)</td><td><strong>$PPL</strong></td><td>Positive for now. 9 GW active pipeline, no take-or-pay yet. But Ohio had 30,000 MW.</td></tr>
</tbody>
</table>

<hr>

<h2>The Information Gap Is the Point</h2>
<p>The filing was publicly available the same morning it was submitted. It sat in a government portal, in a docket, behind search filters that most people don't know how to navigate.</p>
<p>Here is the step-by-step information lag:</p>
<table>
<thead><tr><th>Step</th><th>What happens</th><th>Who knows</th></tr></thead>
<tbody>
<tr style="background:#eaf3de"><td><strong>1</strong></td><td>Filing hits Ohio PUC docket</td><td><strong>GRP flags it at 2:47 AM</strong></td></tr>
<tr><td>2</td><td>Regulatory analysts read it</td><td>Days to weeks later</td></tr>
<tr><td>3</td><td>Sell-side picks it up</td><td>Weeks later, if at all</td></tr>
<tr><td>4</td><td>Management addresses it</td><td>Next earnings call</td></tr>
<tr><td>5</td><td>Consensus estimates revise</td><td>Months after the filing</td></tr>
</tbody>
</table>
<p>Grid data is informationally rich and operationally inaccessible. That gap is the edge.</p>

<hr>

<h2>What I Built (and How It Found This)</h2>
<p>GRP is a Python ETL pipeline I built from scratch. It hits regulatory APIs on a schedule, extracts PDFs, scans for keywords, and runs Z-score anomaly detection on live electricity demand data from the EIA. When enough signal keywords appear in the same document, it fires a flag.</p>
<p>The Ohio filing matched five: <em>take-or-pay, queue withdrawal, bankable demand, commercial operation date, cost allocation.</em></p>
<p>I'm a student. I taught myself Python building this, using Claude as a coding partner to understand what I was writing and debug what wasn't working. No formal CS background. Just a thesis and enough stubbornness to see it through.</p>
<p>The thesis: regulatory filings describe the physical state of the grid in real time. They lead earnings guidance by weeks or months. If you can read them at scale, you know before the market does.</p>
<p>Four standalone scripts showing exactly how GRP works — no proprietary code, runnable with a free EIA API key:</p>
<p><a href="https://github.com/ljafarieh/grp-public"><strong>github.com/ljafarieh/grp-public</strong></a></p>
<p>The core loop, simplified:</p>
<pre><code># 1. Pull live demand from EIA
demand = pull_hourly_demand(ba_code="AEP", days_back=30)

# 2. Flag anomalies with rolling Z-score
spikes = detect_anomalies(demand)   # threshold: 2.0σ over 168-hr window

# 3. Pull new regulatory filings
docs = get_new_documents(participant="American Electric Power")

# 4. Scan each PDF for signal keywords
for doc in docs:
    result = scan_pdf_url(doc["pdf_url"])
    if result.has_signal:
        alert(doc, result)          # 5+ keywords → flag
</code></pre>

<hr>

<h2>What I'm Watching Next</h2>
<ul>
<li><strong>Maryland BGE/Pepco dockets</strong> — tariff is enacted. When does the queue move?</li>
<li><strong>New Jersey BPU</strong> — once Governor Sherrill signs, the BPU has 12 months to set tariff standards. First filings from PSE&amp;G and JCP&amp;L will be the tell.</li>
<li><strong>AEP Q3 2026 earnings</strong> — does management revise its data center load growth guidance? That's when this filing becomes a market event for retail investors.</li>
<li><strong>Pennsylvania</strong> — PPL has 9 GW of active data center pipeline and no take-or-pay tariff yet. Ohio's 30,000 MW looked real too.</li>
</ul>

<hr>

<p>The grid is the biggest infrastructure story of the decade. It plays out in documents nobody reads. I'm trying to change that.</p>
<p><strong>Subscribe to get the next one</strong> — I'll be posting every time GRP flags something worth writing about.</p>

<hr>
<p><em>Not financial advice. All sources are fully public: Ohio PUCO, Maryland PSC, NJ BPU, VA SCC, FERC eLibrary, EIA Open Data.</em></p>
"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GRP — Substack Post 1</title>
<style>
  body {{
    font-family: Georgia, serif;
    font-size: 18px;
    line-height: 1.75;
    color: #111;
    max-width: 700px;
    margin: 60px auto;
    padding: 0 24px;
    background: #fff;
  }}
  h1 {{ font-size: 2em; line-height: 1.2; margin: 0.8em 0 0.3em; }}
  h2 {{ font-size: 1.35em; margin: 1.8em 0 0.4em; border-bottom: 1px solid #eee; padding-bottom: 6px; }}
  p  {{ margin: 0 0 1em; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 2em 0; }}
  blockquote {{
    margin: 1.5em 0;
    padding: 16px 24px;
    background: #f7f7f5;
    border-left: 4px solid #ccc;
    font-style: italic;
    color: #333;
    font-size: 0.95em;
  }}
  blockquote p {{ margin: 0 0 0.5em; }}
  blockquote p:last-child {{ margin: 0; }}
  pre {{
    background: #f4f4f2;
    border-radius: 6px;
    padding: 18px 20px;
    overflow-x: auto;
    font-size: 14px;
    line-height: 1.6;
    margin: 1.2em 0;
  }}
  code {{ font-family: 'Courier New', monospace; font-size: 0.85em; background: #f0f0ee; padding: 1px 4px; border-radius: 3px; }}
  pre code {{ background: none; padding: 0; font-size: 13px; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 15px;
    margin: 1.4em 0;
  }}
  th, td {{ border: 1px solid #ddd; padding: 10px 14px; text-align: left; vertical-align: top; }}
  th {{ background: #f5f5f3; font-weight: 700; }}
  tr:nth-child(even) {{ background: #fafaf8; }}
  ul, ol {{ padding-left: 24px; }}
  li {{ margin-bottom: 0.6em; }}
  a {{ color: #1a5276; }}
  strong {{ font-weight: 700; }}
</style>
</head>
<body>
{body}
</body>
</html>"""

DEST.write_text(html)
print(f"Written -> {DEST}")
print()
print("Next steps:")
print("  1. Open substack_post_1.html in Chrome (refresh if already open)")
print("  2. Cmd+A, Cmd+C")
print("  3. Paste into Substack editor")
