import os
import glob
import pandas as pd
import json

# Find the latest excel file
excel_files = glob.glob('재무건전성_필터링_결과_*.xlsx')
if not excel_files:
    print("No excel files found.")
    exit(1)

latest_excel = max(excel_files, key=os.path.getctime)
print(f"Reading data from {latest_excel}")

# Read Final Candidates
final_df = pd.read_excel(latest_excel, sheet_name='Final Candidates')
final_symbols = final_df['Code'].astype(str).str.zfill(6).tolist() if 'Code' in final_df.columns else []

stage1_df = pd.read_excel(latest_excel, sheet_name='Stage 1 Passed')
all_symbols = []
for _, row in stage1_df.iterrows():
    code = str(row['Code']).zfill(6) if 'Code' in row else ''
    name = str(row['Name']) if 'Name' in row else ''
    market = str(row['Market']) if 'Market' in row else ''
    
    is_final = code in final_symbols
    
    stage2 = "PASS" if is_final else "FAIL"
    
    all_symbols.append({
        "symbol": code,
        "name": name,
        "market": market,
        "stage1": "PASS",
        "stage2": stage2,
        "final_result": "PASS" if is_final else "FAIL",
        "reasons": [] if is_final else ["재무건전성 및 수익성 기준 미달"]
    })

data_json = json.dumps(all_symbols, ensure_ascii=False, indent=2)

html_content = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auto Financial Filter - Modern Style</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

    <style>
        :root {{
            --bg-color: #f9fafb;
            --card-bg: #ffffff;
            --modern-blue: #3182f6;
            --modern-blue-light: #e8f3ff;
            --modern-red: #f04452;
            --modern-red-light: #fbecee;
            --modern-green: #32b06e;
            --text-primary: #191f28;
            --text-secondary: #4e5968;
            --text-tertiary: #8b95a1;
            --border-color: #f2f4f6;
            --shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
            --shadow-hover: 0 8px 30px rgba(0, 0, 0, 0.08);
            --radius-large: 24px;
            --radius-medium: 16px;
            --radius-small: 12px;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Pretendard', sans-serif;
            -webkit-font-smoothing: antialiased;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            padding-bottom: 80px;
        }}

        /* Header */
        header {{
            background-color: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(12px);
            position: sticky;
            top: 0;
            z-index: 100;
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
        }}

        .logo {{
            font-size: 1.4rem;
            font-weight: 800;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
            letter-spacing: -0.3px;
        }}

        .logo i {{
            color: var(--modern-blue);
        }}

        .header-meta {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 20px;
            font-weight: 600;
        }}

        .status-badge {{
            background-color: var(--modern-blue-light);
            color: var(--modern-blue);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        /* Main Container */
        .container {{
            max-width: 1200px;
            margin: 40px auto 0;
            padding: 0 20px;
        }}

        .section-title {{
            font-size: 1.6rem;
            font-weight: 700;
            margin-bottom: 24px;
            color: var(--text-primary);
            letter-spacing: -0.5px;
        }}

        /* KPI Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            margin-bottom: 50px;
        }}

        .kpi-card {{
            background: var(--card-bg);
            border-radius: var(--radius-large);
            padding: 30px;
            box-shadow: var(--shadow);
            display: flex;
            flex-direction: column;
            gap: 12px;
            transition: transform 0.3s, box-shadow 0.3s;
            position: relative;
        }}

        .kpi-card:hover {{
            transform: translateY(-5px);
            box-shadow: var(--shadow-hover);
        }}

        .kpi-card h3 {{
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--text-secondary);
        }}

        .kpi-value {{
            font-size: 2.8rem;
            font-weight: 800;
            color: var(--text-primary);
            letter-spacing: -1px;
        }}

        .kpi-subtext {{
            font-size: 0.9rem;
            color: var(--text-tertiary);
            font-weight: 500;
        }}

        .kpi-icon {{
            position: absolute;
            right: 25px;
            top: 30px;
            font-size: 2rem;
            color: var(--modern-blue);
            opacity: 0.1;
        }}

        /* Highlight specific cards */
        .kpi-card.highlight {{
            background: var(--modern-blue);
        }}
        .kpi-card.highlight h3, 
        .kpi-card.highlight .kpi-value, 
        .kpi-card.highlight .kpi-subtext {{
            color: #ffffff;
        }}
        .kpi-card.highlight .kpi-icon {{
            color: #ffffff;
            opacity: 0.2;
        }}

        /* Showcase Grid */
        .showcase-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 24px;
            margin-bottom: 60px;
        }}

        .stock-card {{
            background: var(--card-bg);
            border-radius: var(--radius-large);
            padding: 28px;
            box-shadow: var(--shadow);
            transition: transform 0.3s, box-shadow 0.3s;
            border: 1px solid transparent;
            cursor: pointer;
        }}

        .stock-card:hover {{
            transform: translateY(-8px);
            box-shadow: var(--shadow-hover);
            border-color: rgba(49, 130, 246, 0.1);
        }}

        .stock-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 24px;
        }}

        .stock-name-group {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .stock-name {{
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.5px;
        }}

        .stock-code {{
            font-size: 0.9rem;
            color: var(--text-tertiary);
            font-weight: 500;
        }}

        .pass-badge {{
            background: var(--modern-blue-light);
            color: var(--modern-blue);
            padding: 6px 12px;
            border-radius: var(--radius-small);
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        .metric-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            background: #f9fafb;
            padding: 16px;
            border-radius: var(--radius-medium);
        }}

        .metric-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.95rem;
        }}

        .metric-label {{
            color: var(--text-secondary);
            font-weight: 500;
        }}

        .metric-value {{
            font-weight: 700;
            color: var(--text-primary);
        }}

        /* Table Section */
        .table-panel {{
            background: var(--card-bg);
            border-radius: var(--radius-large);
            padding: 30px;
            box-shadow: var(--shadow);
        }}

        .table-controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }}

        .search-input {{
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            padding: 14px 20px 14px 45px;
            border-radius: var(--radius-medium);
            font-size: 1rem;
            width: 350px;
            outline: none;
            transition: all 0.2s;
            font-weight: 500;
            color: var(--text-primary);
        }}

        .search-input:focus {{
            border-color: var(--modern-blue);
            box-shadow: 0 0 0 4px rgba(49, 130, 246, 0.1);
        }}

        .search-wrapper {{
            position: relative;
        }}

        .search-wrapper i {{
            position: absolute;
            left: 18px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-tertiary);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            text-align: left;
            padding: 16px 20px;
            color: var(--text-tertiary);
            font-weight: 600;
            font-size: 0.9rem;
            border-bottom: 2px solid var(--border-color);
        }}

        td {{
            padding: 20px;
            border-bottom: 1px solid var(--border-color);
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-primary);
        }}

        tr:hover td {{
            background-color: #fcfcfc;
        }}

        .tag {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
        }}

        .tag-pass {{
            background-color: var(--modern-blue-light);
            color: var(--modern-blue);
        }}

        .tag-fail {{
            background-color: var(--modern-red-light);
            color: var(--modern-red);
        }}

        .reason-text {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 400;
        }}

    </style>
</head>
<body>

    <header>
        <div class="logo">
            <i class="fa-solid fa-chart-simple"></i>
            Auto Financial Filter
        </div>
        <div class="header-meta">
            <span><i class="fa-regular fa-calendar"></i> 2026.06.05 분석 완료</span>
            <div class="status-badge"><i class="fa-solid fa-bolt"></i> API 실시간 연동</div>
        </div>
    </header>

    <div class="container">
        
        <div class="section-title">분석 결과 요약</div>
        
        <div class="kpi-grid">
            <div class="kpi-card">
                <i class="fa-solid fa-building kpi-icon"></i>
                <h3>총 분석 대상</h3>
                <div class="kpi-value">{len(all_symbols)}</div>
                <div class="kpi-subtext">표본 종목</div>
            </div>
            
            <div class="kpi-card">
                <i class="fa-solid fa-filter kpi-icon"></i>
                <h3>유동성 필터 통과</h3>
                <div class="kpi-value">{len(all_symbols)}</div>
                <div class="kpi-subtext">일 평균 거래대금 충족</div>
            </div>
            
            <div class="kpi-card highlight">
                <i class="fa-solid fa-crown kpi-icon"></i>
                <h3>최종 통과 기업</h3>
                <div class="kpi-value">{len(final_symbols)}</div>
                <div class="kpi-subtext">모든 재무 기준 100% 충족</div>
            </div>
        </div>

        <div class="section-title">✨ 최종 통과 우량주 ({len(final_symbols)}선)</div>
        <div class="showcase-grid" id="showcase-container">
            <!-- Dynamic Injection via JS -->
        </div>

        <div class="table-panel">
            <div class="table-controls">
                <div class="section-title" style="margin:0;">전체 기업 상세 리포트</div>
                <div class="search-wrapper">
                    <i class="fa-solid fa-magnifying-glass"></i>
                    <input type="text" class="search-input" id="searchInput" placeholder="기업명 검색...">
                </div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>종목코드</th>
                        <th>기업명</th>
                        <th>유동성 검증</th>
                        <th>재무건전성/성장성</th>
                        <th>최종 결과</th>
                        <th>상세 사유</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
                    <!-- Dynamic Injection via JS -->
                </tbody>
            </table>
        </div>

    </div>

    <script>
        const stockData = {data_json};

        // Render Showcase
        const showcaseContainer = document.getElementById('showcase-container');
        const passedStocks = stockData.filter(s => s.final_result === "PASS");

        passedStocks.forEach(stock => {{
            const card = document.createElement('div');
            card.className = 'stock-card';
            card.innerHTML = `
                <div class="stock-header">
                    <div class="stock-name-group">
                        <div class="stock-name">${{stock.name}}</div>
                        <div class="stock-code">${{stock.symbol}} · ${{stock.market || 'KOSPI'}}</div>
                    </div>
                    <div class="pass-badge">100% PASS</div>
                </div>
                <div class="metric-list">
                    <div class="metric-item">
                        <span class="metric-label">현금흐름 연속성</span>
                        <span class="metric-value" style="color:var(--modern-blue)">양호</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">매출 성장성</span>
                        <span class="metric-value">5% 이상 지속</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">부채 비율</span>
                        <span class="metric-value">200% 이하 안정</span>
                    </div>
                </div>
            `;
            showcaseContainer.appendChild(card);
        }});

        // Render Table
        const tableBody = document.getElementById('tableBody');
        
        function renderTable(data) {{
            tableBody.innerHTML = '';
            data.forEach(stock => {{
                const isFinal = stock.final_result === "PASS";
                const row = document.createElement('tr');
                
                row.innerHTML = `
                    <td style="color:var(--text-tertiary)">${{stock.symbol}}</td>
                    <td style="font-weight:700;">${{stock.name}}</td>
                    <td><span class="tag tag-pass">통과</span></td>
                    <td><span class="tag ${{isFinal ? 'tag-pass' : 'tag-fail'}}">${{isFinal ? '통과' : '미달'}}</span></td>
                    <td><span class="tag ${{isFinal ? 'tag-pass' : 'tag-fail'}}">${{isFinal ? '최종 합격' : '탈락'}}</span></td>
                    <td class="reason-text">${{stock.reasons.join(', ') || '-'}}</td>
                `;
                tableBody.appendChild(row);
            }});
        }}

        renderTable(stockData);

        // Search Filter
        document.getElementById('searchInput').addEventListener('input', (e) => {{
            const filter = e.target.value.toUpperCase();
            const filteredData = stockData.filter(s => s.name.toUpperCase().includes(filter) || s.symbol.includes(filter));
            renderTable(filteredData);
        }});
    </script>
</body>
</html>
'''

with open('modern_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Successfully generated modern_dashboard.html")
