#!/usr/bin/env python3
"""
生成股票分析结果的HTML报告
支持每日生成独立文件，保留一周历史记录
"""

import json
import datetime
import re
from pathlib import Path
from typing import Dict, List, Any
from stock_info_cache import get_stock_display_info, StockInfoCache
from get_datasource import get_current_datasource


def read_file_safe(filepath: str) -> str:
    """安全读取文件内容"""
    try:
        if Path(filepath).exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        print(f"读取文件 {filepath} 失败: {e}")
    return ""


def parse_stock_results(content: str) -> Dict[str, Any]:
    """解析选股结果，提取每个战法的详细信息"""
    results = {}
    if not content:
        return results
    
    lines = content.split('\n')
    current_strategy = None
    
    for line in lines:
        line = line.strip()
        if "选股结果" in line and "[" in line and "]" in line:
            # 提取策略名称，跳过日志级别的[INFO]等
            # 查找"选股结果"后面的第一个[...] 
            results_pos = line.find("选股结果")
            if results_pos >= 0:
                # 从"选股结果"后面开始查找
                search_start = results_pos
                start = line.find('[', search_start) + 1
                end = line.find(']', start)
                if start > search_start and end > start:
                    current_strategy = line[start:end]
                results[current_strategy] = {
                    'alias': current_strategy,
                    'date': '',
                    'count': 0,
                    'stocks': [],
                    'raw_output': []
                }
        elif current_strategy and "交易日:" in line:
            date_part = line.split("交易日:")[-1].strip()
            results[current_strategy]['date'] = date_part
        elif current_strategy and "符合条件股票数:" in line:
            try:
                count = int(line.split(":")[-1].strip())
                results[current_strategy]['count'] = count
            except:
                pass
        elif current_strategy and line:
            # 这可能是股票代码行，需要从日志行中提取实际内容
            # 移除日志前缀（时间戳和级别）
            clean_line = line
            if "[INFO]" in line:
                clean_line = line.split("[INFO]", 1)[-1].strip()
            elif "[ERROR]" in line:
                clean_line = line.split("[ERROR]", 1)[-1].strip()
            elif "[WARNING]" in line:
                clean_line = line.split("[WARNING]", 1)[-1].strip()
            
            # 检查是否是股票代码行（排除特殊标记行）
            if clean_line and not any(x in clean_line for x in ["===", "选股结果", "交易日:", "符合条件股票数:", "无符合条件股票"]):
                if ',' in clean_line or (len(clean_line) == 6 and clean_line.isdigit()):
                    stocks = [s.strip() for s in clean_line.split(',') if s.strip() and len(s.strip()) == 6 and s.strip().isdigit()]
                    if stocks:
                        results[current_strategy]['stocks'] = stocks
        
        # 保存原始输出用于调试
        if current_strategy and line:
            results[current_strategy]['raw_output'].append(line)
    
    return results


def get_strategy_icon(strategy_name: str) -> str:
    """根据战法名称返回对应的图标"""
    icons = {
        "少妇战法": "👩‍💼",
        "SuperB1战法": "🚀", 
        "补票战法": "🎫",
        "TePu战法": "⚡",
        "填坑战法": "🕳️"
    }
    return icons.get(strategy_name, "📈")


def get_strategy_color(strategy_name: str) -> str:
    """根据战法名称返回对应的颜色"""
    colors = {
        "少妇战法": "#e74c3c",
        "SuperB1战法": "#3498db", 
        "补票战法": "#f39c12",
        "TePu战法": "#9b59b6",
        "填坑战法": "#27ae60"
    }
    return colors.get(strategy_name, "#34495e")


def generate_stock_item(stock_code: str) -> str:
    """生成单个股票展示项的HTML"""
    try:
        datasource = get_current_datasource()
        stock_info = get_stock_display_info(stock_code, datasource)
        name = stock_info['name']
        industry = stock_info['industry']
        market = stock_info['market']
        
        return f"""
        <div class="stock-item" data-stock="{stock_code}" onclick="searchStock('{stock_code}')">
            <div class="stock-main">
                <span class="stock-code">{stock_code}</span>
                <span class="stock-name">{name}</span>
            </div>
            <div class="stock-meta">
                <span class="stock-industry">{industry}</span>
                <span class="stock-market">{market}</span>
            </div>
        </div>
        """
    except Exception as e:
        # 如果获取信息失败，使用基本格式
        return f"""
        <div class="stock-item" data-stock="{stock_code}" onclick="searchStock('{stock_code}')">
            <div class="stock-main">
                <span class="stock-code">{stock_code}</span>
                <span class="stock-name">股票{stock_code}</span>
            </div>
            <div class="stock-meta">
                <span class="stock-industry">未知行业</span>
            </div>
        </div>
        """


def get_industry_distribution(stocks: List[str]) -> Dict[str, int]:
    """获取行业分布统计"""
    industry_count = {}
    datasource = get_current_datasource()
    
    for stock in stocks:
        try:
            stock_info = get_stock_display_info(stock, datasource)
            industry = stock_info['industry']
            industry_count[industry] = industry_count.get(industry, 0) + 1
        except Exception:
            industry_count['未知行业'] = industry_count.get('未知行业', 0) + 1
    
    return dict(sorted(industry_count.items(), key=lambda x: x[1], reverse=True))


def generate_strategy_card(strategy_name: str, data: Dict[str, Any], index: int) -> str:
    """生成单个战法的卡片HTML"""
    icon = get_strategy_icon(strategy_name)
    color = get_strategy_color(strategy_name)
    
    # 处理股票列表
    if data['stocks']:
        stocks_html = ""
        for stock in data['stocks']:
            stocks_html += generate_stock_item(stock)
        
        # 获取行业分布
        industry_dist = get_industry_distribution(data['stocks'])
        industry_summary = "、".join([f"{industry}({count})" for industry, count in list(industry_dist.items())[:3]])
        if len(industry_dist) > 3:
            industry_summary += f" 等{len(industry_dist)}个行业"
    else:
        stocks_html = '<div class="no-stocks">暂无选中股票</div>'
        industry_summary = "暂无"
    
    return f"""
    <div class="strategy-card" style="animation-delay: {index * 0.1}s;">
        <div class="strategy-header" style="background: {color};">
            <div class="strategy-icon">{icon}</div>
            <div class="strategy-info">
                <h3>{strategy_name}</h3>
                <div class="strategy-meta">
                    <span class="date">📅 {data['date']}</span>
                    <span class="count">📊 {data['count']} 支股票</span>
                </div>
            </div>
        </div>
        <div class="strategy-content">
            <div class="stocks-container">
                <div class="stocks-header">
                    <h4>选中股票</h4>
                    <div class="industry-summary">行业分布: {industry_summary}</div>
                </div>
                <div class="stocks-list">
                    {stocks_html}
                </div>
            </div>
        </div>
    </div>
    """


def get_available_dates(html_dir: Path = None) -> List[str]:
    """获取可用的历史日期列表（最近一周）"""
    if html_dir is None:
        html_dir = Path("reports")
    
    dates = []
    
    if html_dir.exists():
        # 查找所有日期格式的HTML文件
        for file in html_dir.glob('report-*.html'):
            match = re.match(r'report-(\d{4}-\d{2}-\d{2})\.html', file.name)
            if match:
                dates.append(match.group(1))
    
    # 按日期排序，最新的在前
    dates.sort(reverse=True)
    return dates[:7]  # 只保留最近7天


def cleanup_old_reports(html_dir: Path = None):
    """清理超过一周的旧报告文件"""
    if html_dir is None:
        html_dir = Path("reports")
    
    if not html_dir.exists():
        return
        
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=7)
    
    for file in html_dir.glob('report-*.html'):
        match = re.match(r'report-(\d{4}-\d{2}-\d{2})\.html', file.name)
        if match:
            file_date = datetime.datetime.strptime(match.group(1), '%Y-%m-%d')
            if file_date < cutoff_date:
                try:
                    file.unlink()
                    print(f"已删除过期文件: {file.name}")
                except Exception as e:
                    print(f"删除文件 {file.name} 失败: {e}")


def get_summary_stats(results: Dict[str, Any]) -> Dict[str, int]:
    """获取汇总统计信息"""
    total_strategies = len(results)
    total_stocks = sum(len(data['stocks']) for data in results.values())
    active_strategies = sum(1 for data in results.values() if data['stocks'])
    
    return {
        'total_strategies': total_strategies,
        'total_stocks': total_stocks,
        'active_strategies': active_strategies
    }


def generate_daily_report(date_str: str = None, html_dir: Path = None):
    """生成指定日期的HTML报告"""
    if date_str is None:
        date_str = datetime.datetime.now().strftime('%Y-%m-%d')
    
    if html_dir is None:
        html_dir = Path("reports")
    
    # 确保输出目录存在
    html_dir.mkdir(exist_ok=True)
    
    # 读取选股结果
    console_output = read_file_safe('select_results.log')
    stock_results = parse_stock_results(console_output)
    
    # 获取统计信息
    stats = get_summary_stats(stock_results)
    
    # 生成策略卡片
    strategies_html = ""
    if stock_results:
        for index, (strategy_name, data) in enumerate(stock_results.items()):
            strategies_html += generate_strategy_card(strategy_name, data, index)
    else:
        strategies_html = '<div class="no-data">暂无选股结果数据</div>'
    
    # 生成HTML内容
    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Analysis - {date_str} | StockTradebyZ</title>
    <style>
        * {{ 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
        }}
        
        body {{
            font-family: 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .header {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            padding: 20px 0;
            margin-bottom: 30px;
        }}
        
        .header-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
        }}
        
        .logo {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        
        .logo h1 {{
            color: #2c3e50;
            font-size: 1.8em;
            font-weight: 700;
        }}
        
        .date-info {{
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: 600;
        }}
        
        .stats-bar {{
            max-width: 1200px;
            margin: 0 auto 40px;
            padding: 0 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}
        
        .stat-card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        
        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #3498db;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            color: #7f8c8d;
            font-size: 0.9em;
            font-weight: 600;
        }}
        
        .strategies-grid {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
        }}
        
        .strategy-card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            opacity: 0;
            transform: translateY(30px);
            animation: fadeInUp 0.6s ease forwards;
        }}
        
        @keyframes fadeInUp {{
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        .strategy-card:hover {{
            transform: translateY(-10px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
        }}
        
        .strategy-header {{
            padding: 25px;
            color: white;
            position: relative;
            overflow: hidden;
        }}
        
        .strategy-header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0));
        }}
        
        .strategy-icon {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }}
        
        .strategy-info h3 {{
            font-size: 1.4em;
            font-weight: 700;
            margin-bottom: 8px;
            text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }}
        
        .strategy-meta {{
            display: flex;
            justify-content: space-between;
            opacity: 0.9;
            font-size: 0.85em;
        }}
        
        .strategy-content {{
            padding: 25px;
        }}
        
        .stocks-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        .stocks-container h4 {{
            color: #2c3e50;
            font-size: 1.1em;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .stocks-container h4::before {{
            content: "📈";
            font-size: 1.2em;
        }}
        
        .industry-summary {{
            font-size: 0.85em;
            color: #7f8c8d;
            background: rgba(255,255,255,0.7);
            padding: 5px 10px;
            border-radius: 12px;
            max-width: 200px;
        }}
        
        .stocks-list {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        
        .stock-item {{
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(52,152,219,0.2);
            border-radius: 12px;
            padding: 12px 15px;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .stock-item:hover {{
            transform: translateX(5px);
            border-color: #3498db;
            box-shadow: 0 3px 15px rgba(52,152,219,0.2);
            background: rgba(52,152,219,0.05);
        }}
        
        .stock-main {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .stock-code {{
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 4px 10px;
            border-radius: 15px;
            font-weight: 600;
            font-size: 0.85em;
            min-width: 60px;
            text-align: center;
        }}
        
        .stock-name {{
            font-weight: 600;
            color: #2c3e50;
            font-size: 0.95em;
        }}
        
        .stock-meta {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 2px;
            text-align: right;
        }}
        
        .stock-industry {{
            font-size: 0.8em;
            color: #7f8c8d;
            background: #ecf0f1;
            padding: 2px 8px;
            border-radius: 10px;
        }}
        
        .stock-market {{
            font-size: 0.75em;
            color: #95a5a6;
        }}
        
        .no-stocks {{
            color: #95a5a6;
            font-style: italic;
            text-align: center;
            padding: 30px 20px;
            background: rgba(255,255,255,0.5);
            border-radius: 10px;
            border: 2px dashed #bdc3c7;
        }}
        
        .no-data {{
            text-align: center;
            color: #7f8c8d;
            font-size: 1.2em;
            margin: 50px 0;
            padding: 40px;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 15px;
            max-width: 600px;
            margin: 50px auto;
        }}
        
        .footer {{
            margin-top: 60px;
            text-align: center;
            padding: 30px;
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.9em;
        }}
        
        @media (max-width: 768px) {{
            .header-content {{
                flex-direction: column;
                gap: 15px;
            }}
            
            .strategies-grid {{
                grid-template-columns: 1fr;
                padding: 0 15px;
            }}
            
            .stats-bar {{
                padding: 0 15px;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            }}
            
            .stocks-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
            }}
            
            .industry-summary {{
                max-width: 100%;
                font-size: 0.8em;
            }}
            
            .stock-item {{
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
            }}
            
            .stock-main {{
                width: 100%;
            }}
            
            .stock-meta {{
                align-items: flex-start;
                text-align: left;
                width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="logo">
                <div style="font-size: 2em;">📊</div>
                <h1>StockTradebyZ</h1>
            </div>
            <div class="date-info">
                📅 {date_str}
            </div>
        </div>
    </div>
    
    <div class="stats-bar">
        <div class="stat-card">
            <div class="stat-number">{stats['total_strategies']}</div>
            <div class="stat-label">总策略数</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{stats['active_strategies']}</div>
            <div class="stat-label">有效策略</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{stats['total_stocks']}</div>
            <div class="stat-label">选中股票</div>
        </div>
    </div>
    
    <div class="strategies-grid">
        {strategies_html}
    </div>
    
    <div class="footer">
        <p>🤖 Generated by GitHub Actions | Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>
    
    <script>
        function searchStock(code) {{
            window.open(`https://xueqiu.com/S/SH${{code}}`, '_blank');
        }}
    </script>
</body>
</html>'''

    # 保存日期报告
    daily_filename = f"report-{date_str}.html"
    daily_filepath = html_dir / daily_filename
    with open(daily_filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"日期报告生成成功: {daily_filepath}")
    return daily_filepath, stats


def generate_index_page(html_dir: Path = None):
    """生成首页，包含日期选择功能"""
    if html_dir is None:
        html_dir = Path("reports")
    
    available_dates = get_available_dates(html_dir)
    
    # 生成日期选项
    date_options = ""
    for date in available_dates:
        date_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%m-%d (%a)')
        date_options += f'<option value="{date}">{formatted_date}</option>'
    
    if not date_options:
        date_options = '<option value="">暂无历史数据</option>'
    
    # 生成首页HTML
    index_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockTradebyZ - 选股报告中心</title>
    <style>
        * {{ 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
        }}
        
        body {{
            font-family: 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .container {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 25px;
            padding: 60px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.1);
            text-align: center;
            max-width: 600px;
            width: 90%;
        }}
        
        .logo {{
            font-size: 4em;
            margin-bottom: 20px;
        }}
        
        h1 {{
            color: #2c3e50;
            font-size: 2.5em;
            margin-bottom: 15px;
            font-weight: 700;
        }}
        
        .subtitle {{
            color: #7f8c8d;
            font-size: 1.1em;
            margin-bottom: 40px;
        }}
        
        .date-selector {{
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 15px;
            padding: 15px 20px;
            font-size: 1.1em;
            width: 100%;
            margin-bottom: 25px;
            outline: none;
            transition: all 0.3s ease;
        }}
        
        .date-selector:focus {{
            border-color: #3498db;
            box-shadow: 0 0 0 3px rgba(52,152,219,0.1);
        }}
        
        .view-button {{
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 25px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            width: 100%;
        }}
        
        .view-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(52,152,219,0.3);
        }}
        
        .view-button:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
        }}
        
        .latest-link {{
            display: inline-block;
            margin-top: 20px;
            color: #3498db;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.3s ease;
        }}
        
        .latest-link:hover {{
            color: #2980b9;
        }}
        
        .footer {{
            margin-top: 40px;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">📊</div>
        <h1>StockTradebyZ</h1>
        <div class="subtitle">智能选股报告中心</div>
        
        <select class="date-selector" id="dateSelector" onchange="updateButton()">
            <option value="">选择查看日期</option>
            {date_options}
        </select>
        
        <button class="view-button" id="viewButton" onclick="viewReport()" disabled>
            查看选股报告
        </button>
        
        {"" if not available_dates else f'<a href="reports/report-{available_dates[0]}.html" class="latest-link">📈 查看最新报告</a>'}
        
        <div class="footer">
            <p>🤖 Powered by GitHub Actions</p>
            <p>每日下午6点自动更新</p>
        </div>
    </div>
    
    <script>
        function updateButton() {{
            const selector = document.getElementById('dateSelector');
            const button = document.getElementById('viewButton');
            button.disabled = !selector.value;
        }}
        
        function viewReport() {{
            const selector = document.getElementById('dateSelector');
            if (selector.value) {{
                window.location.href = `reports/report-${{selector.value}}.html`;
            }}
        }}
    </script>
</body>
</html>'''

    # 保存首页到根目录
    index_path = Path('index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    print(f"首页生成成功: {index_path}")


def generate_html_report(html_dir: str = "reports"):
    """主函数：生成HTML报告"""
    html_path = Path(html_dir)
    
    # 清理旧文件
    cleanup_old_reports(html_path)
    
    # 生成今日报告
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    daily_file, stats = generate_daily_report(today, html_path)
    
    # 生成首页
    generate_index_page(html_path)
    
    print(f"统计信息: {stats['total_strategies']} 个策略, {stats['active_strategies']} 个有效, {stats['total_stocks']} 支股票")
    print(f"所有HTML文件已生成到: {html_path} 目录")


if __name__ == "__main__":
    generate_html_report()