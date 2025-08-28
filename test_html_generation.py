#!/usr/bin/env python3
"""
测试HTML生成功能的脚本
"""

import datetime
from pathlib import Path
from generate_html import generate_html_report, generate_daily_report, generate_index_page
from get_datasource import set_current_datasource


def create_test_data():
    """创建测试数据"""
    test_output = """
2024-08-28 10:15:23 [INFO] select_stock.py:133 

============== 选股结果 [少妇战法] ==============
交易日: 2024-08-28
符合条件股票数: 3
000001, 000002, 600000

2024-08-28 10:15:25 [INFO] select_stock.py:133 

============== 选股结果 [SuperB1战法] ==============
交易日: 2024-08-28
符合条件股票数: 2
600519, 000858

2024-08-28 10:15:27 [INFO] select_stock.py:133 

============== 选股结果 [补票战法] ==============
交易日: 2024-08-28
符合条件股票数: 0


2024-08-28 10:15:29 [INFO] select_stock.py:133 

============== 选股结果 [TePu战法] ==============
交易日: 2024-08-28
符合条件股票数: 1
002415

2024-08-28 10:15:31 [INFO] select_stock.py:133 

============== 选股结果 [填坑战法] ==============
交易日: 2024-08-28
符合条件股票数: 4
600036, 000166, 002304, 000776
"""
    
    # 创建测试用的股票信息缓存
    test_stock_info = {
        "000001": {
            "name": "平安银行",
            "industry": "银行",
            "market": "深交所",
            "last_updated": "2024-08-28"
        },
        "000002": {
            "name": "万科A",
            "industry": "房地产开发",
            "market": "深交所", 
            "last_updated": "2024-08-28"
        },
        "600000": {
            "name": "浦发银行",
            "industry": "银行",
            "market": "上交所",
            "last_updated": "2024-08-28"
        },
        "600519": {
            "name": "贵州茅台",
            "industry": "白酒",
            "market": "上交所",
            "last_updated": "2024-08-28"
        },
        "000858": {
            "name": "五粮液",
            "industry": "白酒",
            "market": "深交所",
            "last_updated": "2024-08-28"
        },
        "002415": {
            "name": "海康威视",
            "industry": "安防设备",
            "market": "深交所",
            "last_updated": "2024-08-28"
        },
        "600036": {
            "name": "招商银行",
            "industry": "银行",
            "market": "上交所",
            "last_updated": "2024-08-28"
        },
        "000166": {
            "name": "申万宏源",
            "industry": "证券",
            "market": "深交所",
            "last_updated": "2024-08-28"
        },
        "002304": {
            "name": "洋河股份",
            "industry": "白酒",
            "market": "深交所",
            "last_updated": "2024-08-28"
        },
        "000776": {
            "name": "广发证券",
            "industry": "证券",
            "market": "深交所",
            "last_updated": "2024-08-28"
        }
    }
    
    # 保存测试股票信息缓存
    import json
    with open('stock_info_cache.json', 'w', encoding='utf-8') as f:
        json.dump(test_stock_info, f, ensure_ascii=False, indent=2)
    
    # 写入测试文件
    with open('stock_results.txt', 'w', encoding='utf-8') as f:
        f.write(test_output)
    
    # 创建日志文件
    with open('select_results.log', 'w', encoding='utf-8') as f:
        f.write("测试选股日志内容\n")
    
    print("✅ 测试数据创建完成")


def test_html_generation(datasource: str = "akshare"):
    """测试HTML生成"""
    print("🧪 开始测试HTML生成功能...")
    
    # 设置测试数据源
    set_current_datasource(datasource)
    print(f"📊 使用数据源: {datasource}")
    
    # 创建测试数据
    create_test_data()
    
    # 生成多个日期的报告用于测试
    test_dates = [
        datetime.datetime.now().strftime('%Y-%m-%d'),
        (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
        (datetime.datetime.now() - datetime.timedelta(days=2)).strftime('%Y-%m-%d'),
    ]
    
    print(f"📅 生成测试日期: {', '.join(test_dates)}")
    
    html_dir = Path("reports")
    
    for date in test_dates:
        print(f"⏳ 生成 {date} 的报告...")
        daily_file, stats = generate_daily_report(date, html_dir)
        print(f"✅ {daily_file} 生成完成 ({stats})")
    
    # 生成首页
    print("⏳ 生成首页...")
    generate_index_page(html_dir)
    
    # 检查生成的文件
    print("\n📄 生成的文件列表:")
    
    # 显示根目录文件
    print("  根目录:")
    for file in sorted(Path('.').glob('index.html')):
        size = file.stat().st_size
        print(f"    {file.name} ({size:,} bytes)")
    
    # 显示reports目录文件
    if html_dir.exists():
        print(f"  {html_dir} 目录:")
        for file in sorted(html_dir.glob('*.html')):
            size = file.stat().st_size
            print(f"    {file.name} ({size:,} bytes)")
    
    print(f"\n🎉 测试完成！可以用浏览器打开 index.html 查看效果")
    print(f"📁 报告文件统一存储在 {html_dir} 目录中")


if __name__ == "__main__":
    import sys
    
    # 支持命令行参数指定数据源
    datasource = sys.argv[1] if len(sys.argv) > 1 else "akshare"
    test_html_generation(datasource)