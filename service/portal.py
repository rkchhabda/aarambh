"""Portal HTML — served directly from Python, no StaticFiles needed."""

PORTAL_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aarambh_Quant Signals</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #0f172a;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --card-bg: #ffffff;
            --card-text: #1e293b;
            --card-border: #e2e8f0;
            --body-bg: #f1f5f9;
            --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.04);
            --shadow-lg: 0 4px 24px rgba(0,0,0,0.1);
            --radius: 12px;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: var(--body-bg); color: var(--card-text); min-height: 100vh; }
        .header { background: linear-gradient(135deg, var(--primary) 0%, #1a2744 100%); padding: 1.5rem 2rem; box-shadow: 0 2px 12px rgba(0,0,0,0.2); position: sticky; top: 0; z-index: 100; }
        .header-inner { max-width: 1200px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; }
        .logo { display: flex; align-items: center; gap: 0.75rem; }
        .logo-icon { width: 40px; height: 40px; background: var(--accent); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.25rem; color: white; font-weight: 700; }
        .logo h1 { color: var(--text); font-size: 1.35rem; font-weight: 700; letter-spacing: -0.02em; }
        .logo h1 span { color: var(--accent); }
        .header-badge { background: rgba(59,130,246,0.15); color: var(--accent); padding: 0.35rem 0.85rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.05em; }
        .main { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
        .search-card { background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow); padding: 2rem; margin-bottom: 2rem; }
        .search-card h2 { font-size: 1rem; font-weight: 600; color: var(--card-text); margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem; }
        .search-wrapper { position: relative; }
        .search-input { width: 100%; padding: 1rem 1.25rem 1rem 3rem; border: 2px solid var(--card-border); border-radius: 10px; font-size: 1rem; font-family: inherit; color: var(--card-text); background: #f8fafc; transition: border-color 0.2s, box-shadow 0.2s; outline: none; }
        .search-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(59,130,246,0.12); background: white; }
        .search-input::placeholder { color: var(--text-muted); }
        .search-icon { position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); color: var(--text-muted); font-size: 1.1rem; pointer-events: none; }
        .dropdown { position: absolute; top: calc(100% + 4px); left: 0; right: 0; background: white; border: 1px solid var(--card-border); border-radius: 10px; box-shadow: var(--shadow-lg); max-height: 300px; overflow-y: auto; display: none; z-index: 50; }
        .dropdown.active { display: block; }
        .dropdown-item { padding: 0.75rem 1.25rem; cursor: pointer; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #f1f5f9; transition: background 0.15s; }
        .dropdown-item:last-child { border-bottom: none; }
        .dropdown-item:hover, .dropdown-item.selected { background: #eff6ff; }
        .dropdown-item .ticker-name { font-weight: 600; color: var(--card-text); }
        .dropdown-item .company-name { font-size: 0.8rem; color: var(--text-muted); }
        .dropdown-item .sector-badge { font-size: 0.7rem; background: #f1f5f9; color: var(--text-muted); padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 500; }
        .no-results { padding: 1.25rem; text-align: center; color: var(--text-muted); font-size: 0.9rem; }
        .get-btn { margin-top: 1rem; width: 100%; padding: 0.9rem; background: var(--accent); color: white; border: none; border-radius: 10px; font-size: 1rem; font-weight: 600; font-family: inherit; cursor: pointer; transition: background 0.2s, transform 0.1s; }
        .get-btn:hover { background: var(--accent-hover); }
        .get-btn:active { transform: scale(0.98); }
        .get-btn:disabled { background: #cbd5e1; cursor: not-allowed; }
        .get-btn .spinner { display: inline-block; width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 0.5rem; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .signal-card { background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; margin-bottom: 2rem; display: none; animation: slideUp 0.4s ease; }
        .signal-card.active { display: block; }
        @keyframes slideUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
        .signal-header { padding: 1.5rem 2rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; border-bottom: 1px solid var(--card-border); }
        .signal-ticker-group { display: flex; align-items: center; gap: 1rem; }
        .signal-ticker-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem; color: white; }
        .signal-ticker-icon.buy { background: linear-gradient(135deg, #10b981, #059669); }
        .signal-ticker-icon.sell { background: linear-gradient(135deg, #ef4444, #dc2626); }
        .signal-ticker-icon.hold { background: linear-gradient(135deg, #94a3b8, #64748b); }
        .signal-ticker h3 { font-size: 1.1rem; font-weight: 700; color: var(--card-text); }
        .signal-ticker .regime { font-size: 0.8rem; color: var(--text-muted); margin-top: 2px; }
        .signal-badge { padding: 0.5rem 1.25rem; border-radius: 8px; font-weight: 700; font-size: 0.95rem; letter-spacing: 0.04em; }
        .signal-badge.buy { background: #d1fae5; color: #065f46; }
        .signal-badge.sell { background: #fee2e2; color: #991b1b; }
        .signal-badge.hold { background: #f1f5f9; color: #475569; }
        .signal-body { padding: 2rem; }
        .signal-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1.5rem; margin-bottom: 1.75rem; }
        .metric-card { text-align: center; }
        .metric-card .label { font-size: 0.75rem; font-weight: 500; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.4rem; }
        .metric-card .value { font-size: 1.5rem; font-weight: 700; color: var(--card-text); }
        .metric-card .value.price { color: var(--accent); }
        .metric-card .value.sma { color: #8b5cf6; }
        .metric-card .sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem; }
        .confidence-section { background: #f8fafc; border-radius: 10px; padding: 1.25rem 1.5rem; }
        .confidence-label { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
        .confidence-label .left { font-size: 0.85rem; font-weight: 600; color: var(--card-text); }
        .confidence-label .right { font-size: 0.85rem; font-weight: 700; }
        .confidence-bar-bg { width: 100%; height: 10px; background: #e2e8f0; border-radius: 10px; overflow: hidden; }
        .confidence-bar-fill { height: 100%; border-radius: 10px; transition: width 0.8s ease; }
        .confidence-bar-fill.buy { background: linear-gradient(90deg, #10b981, #34d399); }
        .confidence-bar-fill.sell { background: linear-gradient(90deg, #ef4444, #f87171); }
        .confidence-bar-fill.hold { background: linear-gradient(90deg, #94a3b8, #cbd5e1); }
        .signal-footer { padding: 1rem 2rem; background: #f8fafc; border-top: 1px solid var(--card-border); font-size: 0.78rem; color: var(--text-muted); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; }
        .error-msg { background: #fef2f2; border: 1px solid #fecaca; border-radius: 10px; padding: 1rem 1.5rem; color: #991b1b; font-size: 0.9rem; display: none; margin-bottom: 1.5rem; }
        .error-msg.active { display: flex; align-items: center; gap: 0.75rem; }
        .error-icon { font-size: 1.2rem; }
        .stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .stat-card { background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow); padding: 1.25rem 1.5rem; display: flex; align-items: center; gap: 1rem; }
        .stat-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; }
        .stat-icon.blue { background: #dbeafe; color: #2563eb; }
        .stat-icon.green { background: #d1fae5; color: #059669; }
        .stat-icon.purple { background: #ede9fe; color: #7c3aed; }
        .stat-content .stat-val { font-size: 1.35rem; font-weight: 700; color: var(--card-text); }
        .stat-content .stat-label { font-size: 0.78rem; color: var(--text-muted); }
        .quick-section { background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow); padding: 1.5rem 2rem; margin-bottom: 2rem; }
        .quick-section h3 { font-size: 0.9rem; font-weight: 600; color: var(--card-text); margin-bottom: 1rem; }
        .quick-chips { display: flex; flex-wrap: wrap; gap: 0.5rem; }
        .chip { padding: 0.45rem 0.9rem; background: #f1f5f9; border: 1px solid var(--card-border); border-radius: 8px; font-size: 0.8rem; font-weight: 500; color: var(--card-text); cursor: pointer; transition: all 0.15s; }
        .chip:hover { background: #eff6ff; border-color: var(--accent); color: var(--accent); }
        .footer { text-align: center; padding: 1.5rem; font-size: 0.78rem; color: var(--text-muted); }
        .dropdown::-webkit-scrollbar { width: 6px; }
        .dropdown::-webkit-scrollbar-track { background: transparent; }
        .dropdown::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
    </style>
</head>
<body>
<div class="header">
    <div class="header-inner">
        <div class="logo">
            <div class="logo-icon">A</div>
            <h1>Aarambh_<span>Quant</span> Signals</h1>
        </div>
        <div class="header-badge">NSE NIFTY 100</div>
    </div>
</div>
<div class="main">
    <div class="stats-row">
        <div class="stat-card"><div class="stat-icon blue">&#9878;</div><div class="stat-content"><div class="stat-val">138</div><div class="stat-label">Nifty 100 Stocks</div></div></div>
        <div class="stat-card"><div class="stat-icon green">&#9889;</div><div class="stat-content"><div class="stat-val">Ensemble</div><div class="stat-label">XGB + RF + LR + Meta</div></div></div>
        <div class="stat-card"><div class="stat-icon purple">&#9733;</div><div class="stat-content"><div class="stat-val">61%</div><div class="stat-label">Walk-Forward Accuracy</div></div></div>
    </div>
    <div class="search-card">
        <h2>&#128269; Search Stock</h2>
        <div class="search-wrapper">
            <span class="search-icon">&#128270;</span>
            <input type="text" id="searchInput" class="search-input" placeholder="Type to search Nifty 100 stocks (e.g., RELIANCE, TCS, INFY)" autocomplete="off">
            <div id="dropdown" class="dropdown"></div>
        </div>
        <button id="getSignalBtn" class="get-btn">Get Signal</button>
    </div>
    <div id="errorMsg" class="error-msg"><span class="error-icon">&#9888;</span><span id="errorText"></span></div>
    <div id="signalCard" class="signal-card">
        <div class="signal-header">
            <div class="signal-ticker-group">
                <div id="signalIcon" class="signal-ticker-icon hold">--</div>
                <div class="signal-ticker"><h3 id="signalTickerName">--</h3><div id="signalRegime" class="regime">--</div></div>
            </div>
            <div id="signalBadge" class="signal-badge hold">HOLD</div>
        </div>
        <div class="signal-body">
            <div class="signal-grid">
                <div class="metric-card"><div class="label">Current Price</div><div id="signalPrice" class="value price">--</div><div class="sub">NSE Exchange</div></div>
                <div class="metric-card"><div class="label">200-Day SMA</div><div id="signalSma" class="value sma">--</div><div class="sub">Long-term trend</div></div>
                <div class="metric-card"><div class="label">Signal</div><div id="signalAction" class="value">--</div><div class="sub">Regime filtered</div></div>
                <div class="metric-card"><div class="label">Confidence</div><div id="signalConfVal" class="value">--</div><div class="sub">Ensemble probability</div></div>
            </div>
            <div class="confidence-section">
                <div class="confidence-label"><span class="left">Model Confidence</span><span id="confidenceText" class="right">--</span></div>
                <div class="confidence-bar-bg"><div id="confidenceBar" class="confidence-bar-fill hold" style="width: 0%"></div></div>
            </div>
        </div>
        <div class="signal-footer"><span id="footerTicker">--</span><span id="footerTimestamp">--</span></div>
    </div>
    <div class="quick-section">
        <h3>Quick Access - Top Nifty 100</h3>
        <div class="quick-chips" id="quickChips"></div>
    </div>
</div>
<div class="footer">Aarambh_Quant Signals &mdash; Ensemble ML + 200-Day SMA Regime Filter &mdash; Not investment advice.</div>
<script>
const TICKERS=[{s:"RELIANCE.NS",n:"Reliance Industries",g:"Oil & Gas"},{s:"TCS.NS",n:"Tata Consultancy Services",g:"IT"},{s:"INFY.NS",n:"Infosys",g:"IT"},{s:"HDFCBANK.NS",n:"HDFC Bank",g:"Banking"},{s:"ICICIBANK.NS",n:"ICICI Bank",g:"Banking"},{s:"HINDUNILVR.NS",n:"Hindustan Unilever",g:"FMCG"},{s:"SBIN.NS",n:"State Bank of India",g:"Banking"},{s:"BHARTIARTL.NS",n:"Bharti Airtel",g:"Telecom"},{s:"ITC.NS",n:"ITC Limited",g:"FMCG"},{s:"KOTAKBANK.NS",n:"Kotak Mahindra Bank",g:"Banking"},{s:"LT.NS",n:"Larsen & Toubro",g:"Infra"},{s:"WIPRO.NS",n:"Wipro",g:"IT"},{s:"HCLTECH.NS",n:"HCL Technologies",g:"IT"},{s:"ASIANPAINT.NS",n:"Asian Paints",g:"Consumer"},{s:"MARUTI.NS",n:"Maruti Suzuki",g:"Auto"},{s:"TITAN.NS",n:"Titan Company",g:"Consumer"},{s:"BAJFINANCE.NS",n:"Bajaj Finance",g:"NBFC"},{s:"NTPC.NS",n:"NTPC",g:"Power"},{s:"ONGC.NS",n:"Oil & Natural Gas Corp",g:"Oil & Gas"},{s:"POWERGRID.NS",n:"Power Grid Corp",g:"Power"},{s:"ULTRACEMCO.NS",n:"UltraTech Cement",g:"Cement"},{s:"AXISBANK.NS",n:"Axis Bank",g:"Banking"},{s:"ADANIPORTS.NS",n:"Adani Ports",g:"Infra"},{s:"JSWSTEEL.NS",n:"JSW Steel",g:"Metals"},{s:"TATASTEEL.NS",n:"Tata Steel",g:"Metals"},{s:"TECHM.NS",n:"Tech Mahindra",g:"IT"},{s:"INDUSINDBK.NS",n:"IndusInd Bank",g:"Banking"},{s:"HDFCLIFE.NS",n:"HDFC Life Insurance",g:"Insurance"},{s:"SBILIFE.NS",n:"SBI Life Insurance",g:"Insurance"},{s:"BAJAJFINSV.NS",n:"Bajaj Finserv",g:"NBFC"},{s:"M&M.NS",n:"Mahindra & Mahindra",g:"Auto"},{s:"ADANIENT.NS",n:"Adani Enterprises",g:"Conglomerate"},{s:"COALINDIA.NS",n:"Coal India",g:"Mining"},{s:"SUNPHARMA.NS",n:"Sun Pharma",g:"Pharma"},{s:"TATAMOTORS.NS",n:"Tata Motors",g:"Auto"},{s:"VEDL.NS",n:"Vedanta",g:"Metals"},{s:"BRITANNIA.NS",n:"Britannia Industries",g:"FMCG"},{s:"GRASIM.NS",n:"Grasim Industries",g:"Cement"},{s:"APOLLOHOSP.NS",n:"Apollo Hospitals",g:"Healthcare"},{s:"CIPLA.NS",n:"Cipla",g:"Pharma"},{s:"DIVISLAB.NS",n:"Divi's Laboratories",g:"Pharma"},{s:"DRREDDY.NS",n:"Dr. Reddy's Labs",g:"Pharma"},{s:"EICHERMOT.NS",n:"Eicher Motors",g:"Auto"},{s:"HINDALCO.NS",n:"Hindalco Industries",g:"Metals"},{s:"INDIGO.NS",n:"InterGlobe Aviation",g:"Aviation"},{s:"PIDILITIND.NS",n:"Pidilite Industries",g:"Chemicals"},{s:"SHREECEM.NS",n:"Shree Cement",g:"Cement"},{s:"SIEMENS.NS",n:"Siemens India",g:"Industrial"},{s:"TATACONSUM.NS",n:"Tata Consumer Products",g:"FMCG"},{s:"TATAPOWER.NS",n:"Tata Power",g:"Power"},{s:"UPL.NS",n:"UPL Limited",g:"Chemicals"},{s:"BAJAJ-AUTO.NS",n:"Bajaj Auto",g:"Auto"},{s:"BOSCHLTD.NS",n:"Bosch India",g:"Auto Anc"},{s:"COFORGE.NS",n:"Coforge",g:"IT"},{s:"DABUR.NS",n:"Dabur India",g:"FMCG"},{s:"GODREJCP.NS",n:"Godrej Consumer Products",g:"FMCG"},{s:"HAVELLS.NS",n:"Havells India",g:"Consumer"},{s:"IGL.NS",n:"Indraprastha Gas",g:"Gas"},{s:"JUBLFOOD.NS",n:"Jubilant Foodworks",g:"QSR"},{s:"MARICO.NS",n:"Marico",g:"FMCG"},{s:"PIIND.NS",n:"PI Industries",g:"Chemicals"},{s:"TORNTPHARM.NS",n:"Torrent Pharma",g:"Pharma"},{s:"VOLTAS.NS",n:"Voltas",g:"Consumer"},{s:"WHIRLPOOL.NS",n:"Whirlpool India",g:"Consumer"},{s:"NHPC.NS",n:"NHPC Limited",g:"Power"},{s:"PFC.NS",n:"Power Finance Corp",g:"NBFC"},{s:"RECLTD.NS",n:"REC Limited",g:"NBFC"},{s:"SAIL.NS",n:"Steel Authority of India",g:"Metals"},{s:"BANKBARODA.NS",n:"Bank of Baroda",g:"Banking"},{s:"CANBK.NS",n:"Canara Bank",g:"Banking"},{s:"PNB.NS",n:"Punjab National Bank",g:"Banking"},{s:"UNIONBANK.NS",n:"Union Bank of India",g:"Banking"},{s:"FEDERALBNK.NS",n:"Federal Bank",g:"Banking"},{s:"IDFCFIRSTB.NS",n:"IDFC First Bank",g:"Banking"},{s:"RBLBANK.NS",n:"RBL Bank",g:"Banking"},{s:"MUTHOOTFIN.NS",n:"Muthoot Finance",g:"NBFC"},{s:"LUPIN.NS",n:"Lupin",g:"Pharma"},{s:"PAGEIND.NS",n:"Page Industries",g:"Textiles"},{s:"BANDHANBNK.NS",n:"Bandhan Bank",g:"Banking"},{s:"GODREJPROP.NS",n:"Godrej Properties",g:"Real Estate"},{s:"DLF.NS",n:"DLF Limited",g:"Real Estate"},{s:"OBEROIRLTY.NS",n:"Oberoi Realty",g:"Real Estate"},{s:"TVSMOTOR.NS",n:"TVS Motor",g:"Auto"},{s:"ASHOKLEY.NS",n:"Ashok Leyland",g:"Auto"},{s:"ESCORTS.NS",n:"Escorts Kubota",g:"Auto"},{s:"AMBUJACEM.NS",n:"Ambuja Cements",g:"Cement"},{s:"RAMCOCEM.NS",n:"Ramco Cements",g:"Cement"},{s:"ADANIGREEN.NS",n:"Adani Green Energy",g:"Power"},{s:"BHEL.NS",n:"Bharat Heavy Electricals",g:"Industrial"},{s:"BEL.NS",n:"Bharat Electronics",g:"Defence"},{s:"CHOLAFIN.NS",n:"Cholamandalam Invest",g:"NBFC"},{s:"COLPAL.NS",n:"Colgate-Palmolive",g:"FMCG"},{s:"CONCOR.NS",n:"Container Corp",g:"Logistics"},{s:"CROMPTON.NS",n:"Crompton Greaves CE",g:"Consumer"},{s:"CUMMINSIND.NS",n:"Cummins India",g:"Industrial"},{s:"DALBHARAT.NS",n:"Dalmia Bharat",g:"Cement"},{s:"DEEPAKNTR.NS",n:"Deepak Nitrite",g:"Chemicals"},{s:"EMAMILTD.NS",n:"Emami",g:"FMCG"},{s:"ENDURANCE.NS",n:"Endurance Tech",g:"Auto Anc"},{s:"EXIDEIND.NS",n:"Exide Industries",g:"Auto Anc"},{s:"GLENMARK.NS",n:"Glenmark Pharma",g:"Pharma"},{s:"GRANULES.NS",n:"Granules India",g:"Pharma"},{s:"HINDPETRO.NS",n:"Hindustan Petroleum",g:"Oil & Gas"},{s:"ICICIGI.NS",n:"ICICI General Insurance",g:"Insurance"},{s:"ICICIPRULI.NS",n:"ICICI Prudential Life",g:"Insurance"},{s:"IDEA.NS",n:"Vodafone Idea",g:"Telecom"},{s:"INDUSTOWER.NS",n:"Indus Towers",g:"Telecom"},{s:"JINDALSTEL.NS",n:"Jindal Steel & Power",g:"Metals"},{s:"LICHSGFIN.NS",n:"LIC Housing Finance",g:"NBFC"},{s:"MAXHEALTH.NS",n:"Max Healthcare",g:"Healthcare"},{s:"MFSL.NS",n:"Max Financial Services",g:"Insurance"},{s:"MOTHERSON.NS",n:"Motherson Sumi",g:"Auto Anc"},{s:"MPHASIS.NS",n:"Mphasis",g:"IT"},{s:"MRF.NS",n:"MRF Limited",g:"Tyres"},{s:"NAUKRI.NS",n:"Info Edge (India)",g:"Internet"},{s:"NBCC.NS",n:"NBCC India",g:"Infra"},{s:"NMDC.NS",n:"NMDC Limited",g:"Mining"},{s:"PERSISTENT.NS",n:"Persistent Systems",g:"IT"},{s:"PETRONET.NS",n:"Petronet LNG",g:"Oil & Gas"},{s:"POLYCAB.NS",n:"Polycab India",g:"Cables"},{s:"PVRINOX.NS",n:"PVR Inox Cinemas",g:"Media"},{s:"SRF.NS",n:"SRF Limited",g:"Chemicals"},{s:"SYNGENE.NS",n:"Syngene International",g:"Pharma"},{s:"TATACHEM.NS",n:"Tata Chemicals",g:"Chemicals"},{s:"TATACOMM.NS",n:"Tata Communications",g:"Telecom"},{s:"TRENT.NS",n:"Trent Limited",g:"Retail"},{s:"UBL.NS",n:"United Breweries",g:"Beverages"},{s:"VBL.NS",n:"Varun Beverages",g:"Beverages"},{s:"ZYDUSLIFE.NS",n:"Zydus Lifesciences",g:"Pharma"},{s:"ACC.NS",n:"ACC Limited",g:"Cement"},{s:"BIOCON.NS",n:"Biocon",g:"Pharma"},{s:"BALKRISIND.NS",n:"Balkrishna Industries",g:"Tyres"},{s:"HEROMOTOCO.NS",n:"Hero MotoCorp",g:"Auto"},{s:"NAVINFLUOR.NS",n:"Navin Fluorine",g:"Chemicals"},{s:"TORNTPOWER.NS",n:"Torrent Power",g:"Power"},{s:"ASTRAL.NS",n:"Astral Ltd",g:"Building"},{s:"AUROPHARMA.NS",n:"Aurobindo Pharma",g:"Pharma"},{s:"EIDPARRY.NS",n:"EID Parry",g:"Sugar"},{s:"GAIL.NS",n:"GAIL India",g:"Oil & Gas"},{s:"SUNTV.NS",n:"Sun TV Network",g:"Media"},{s:"YESBANK.NS",n:"Yes Bank",g:"Banking"},{s:"ZEEL.NS",n:"Zee Entertainment",g:"Media"},{s:"PHOENIXLTD.NS",n:"Phoenix Mills",g:"Real Estate"},{s:"PRESTIGE.NS",n:"Prestige Estates",g:"Real Estate"},{s:"SOBHA.NS",n:"Sobha Ltd",g:"Real Estate"},{s:"SRTRANSFIN.NS",n:"Shriram Finance",g:"NBFC"},{s:"MANAPPURAM.NS",n:"Manappuram Finance",g:"NBFC"}];
const TICKER_MAP={};TICKERS.forEach(t=>TICKER_MAP[t.s]=t);
const QUICK=["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","BHARTIARTL.NS","ITC.NS","WIPRO.NS","HCLTECH.NS"];
const searchInput=document.getElementById('searchInput'),dropdown=document.getElementById('dropdown'),getBtn=document.getElementById('getSignalBtn'),signalCard=document.getElementById('signalCard'),errorMsg=document.getElementById('errorMsg');
let selectedTicker=null;
const chipsEl=document.getElementById('quickChips');QUICK.forEach(t=>{const chip=document.createElement('div');chip.className='chip';chip.textContent=t.replace('.NS','');chip.onclick=()=>selectTicker(t);chipsEl.appendChild(chip);});
searchInput.addEventListener('input',()=>{const q=searchInput.value.trim().toUpperCase();if(q.length<1){dropdown.classList.remove('active');return;}const matches=TICKERS.filter(t=>t.s.includes(q)||t.n.toUpperCase().includes(q)||t.g.toUpperCase().includes(q)).slice(0,12);if(matches.length===0){dropdown.innerHTML='<div class="no-results">No stocks found</div>';}else{dropdown.innerHTML=matches.map(t=>'<div class="dropdown-item" data-ticker="'+t.s+'"><div><div class="ticker-name">'+t.s.replace('.NS','')+'</div><div class="company-name">'+t.n+'</div></div><span class="sector-badge">'+t.g+'</span></div>').join('');}dropdown.classList.add('active');dropdown.querySelectorAll('.dropdown-item').forEach(el=>{el.addEventListener('click',()=>selectTicker(el.dataset.ticker));});});
searchInput.addEventListener('focus',()=>{if(searchInput.value.trim().length>=1)dropdown.classList.add('active');});
document.addEventListener('click',e=>{if(!e.target.closest('.search-wrapper'))dropdown.classList.remove('active');});
function selectTicker(t){selectedTicker=t;searchInput.value=t.replace('.NS','')+' ('+t+')';dropdown.classList.remove('active');getSignal();}
async function getSignal(){const ticker=selectedTicker||searchInput.value.trim().toUpperCase();if(!ticker)return;getBtn.disabled=true;getBtn.innerHTML='<span class="spinner"></span>Fetching...';signalCard.classList.remove('active');errorMsg.classList.remove('active');try{const res=await fetch('/v1/signal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticker})});const data=await res.json();if(!res.ok)throw new Error(data.detail||'Request failed');renderSignal(data);}catch(err){document.getElementById('errorText').textContent=err.message;errorMsg.classList.add('active');}finally{getBtn.disabled=false;getBtn.textContent='Get Signal';}}
getBtn.addEventListener('click',getSignal);searchInput.addEventListener('keydown',e=>{if(e.key==='Enter')getSignal();});
function renderSignal(d){const sig=(d.signal||'HOLD').toUpperCase();const sigClass=sig==='BUY'?'buy':sig==='SELL'?'sell':'hold';const conf=((d.confidence||0.5)*100).toFixed(1);const info=TICKER_MAP[d.ticker]||{n:d.ticker,g:''};document.getElementById('signalIcon').className='signal-ticker-icon '+sigClass;document.getElementById('signalIcon').textContent=sig;document.getElementById('signalTickerName').textContent=d.ticker.replace('.NS','')+'  |  '+info.n;document.getElementById('signalRegime').textContent='Regime: '+(d.regime||'--')+(info.g?'  |  '+info.g:'');const badge=document.getElementById('signalBadge');badge.className='signal-badge '+sigClass;badge.textContent=sig;document.getElementById('signalPrice').textContent='\u20B9'+Number(d.price).toLocaleString('en-IN',{minimumFractionDigits:2});document.getElementById('signalSma').textContent='\u20B9'+Number(d.sma_200).toLocaleString('en-IN',{minimumFractionDigits:2});document.getElementById('signalAction').textContent=sig;document.getElementById('signalAction').style.color=sigClass==='buy'?'#059669':sigClass==='sell'?'#dc2626':'#475569';document.getElementById('signalConfVal').textContent=conf+'%';document.getElementById('confidenceText').textContent=conf+'%';document.getElementById('confidenceText').style.color=sigClass==='buy'?'#059669':sigClass==='sell'?'#dc2626':'#475569';const bar=document.getElementById('confidenceBar');bar.className='confidence-bar-fill '+sigClass;bar.style.width='0%';setTimeout(()=>{bar.style.width=conf+'%';},100);document.getElementById('footerTicker').textContent='Ticker: '+d.ticker;document.getElementById('footerTimestamp').textContent='Updated: '+new Date(d.timestamp).toLocaleString();signalCard.classList.add('active');signalCard.scrollIntoView({behavior:'smooth',block:'nearest'});}
</script>
</body>
</html>"""
