#!/usr/bin/env python3
"""
股票选择系统Web服务器
提供HTML界面展示选股结果
"""

import os
from datetime import datetime
from typing import Dict, List, Optional
from collections import Counter

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
from flask_cors import CORS

from result_cache import ResultCache
from logger_config import setup_logger


class StockWebServer:
    """股票选择系统Web服务器"""
    
    def __init__(self, cache_dir: str = "cache", host: str = "0.0.0.0", port: int = 8080):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'stock-selector-secret-key')
        
        # 启用CORS支持
        CORS(self.app)
        
        self.cache = ResultCache(cache_dir)
        self.logger = setup_logger("web_server")
        self.host = host
        self.port = port
        
        self._setup_routes()
        self._setup_error_handlers()
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.app.route('/')
        def index():
            """首页 - 选股结果展示"""
            try:
                # 获取请求参数
                selected_date = request.args.get('date')
                recent_dates = self.cache.get_recent_dates(30)
                
                if selected_date:
                    # 显示指定日期的结果（包含股票详细信息）
                    results = self.cache.get_results_with_stock_info(selected_date)
                    
                    # 计算统计信息
                    total_stocks = sum(len(r['stocks']) for r in results)
                    all_stocks = []
                    for r in results:
                        all_stocks.extend(r['stocks'])
                    unique_stocks = len(set(all_stocks))
                    avg_execution_time = sum(r['execution_time'] for r in results) / len(results) if results else 0
                    
                    # 股票选中频率统计
                    stock_frequency = dict(Counter(all_stocks).most_common(20))
                    
                    return render_template(
                        'index.html',
                        current_date=selected_date,
                        results=results,
                        recent_dates=recent_dates,
                        total_stocks=total_stocks,
                        unique_stocks=unique_stocks,
                        avg_execution_time=avg_execution_time,
                        stock_frequency=stock_frequency,
                        current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    )
                else:
                    # 显示首页，让用户选择日期
                    return render_template(
                        'index.html',
                        recent_dates=recent_dates,
                        current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    )
                    
            except Exception as e:
                self.logger.error(f"首页加载失败: {e}")
                return render_template(
                    'index.html',
                    error=f"加载数据失败: {str(e)}",
                    current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        @self.app.route('/statistics')
        def statistics():
            """统计页面"""
            try:
                # 获取系统统计信息
                system_stats = self.cache.get_statistics()
                
                # 获取最近执行摘要
                execution_summary = self.cache.get_execution_summary(7)
                
                # 获取选择器性能统计
                selector_performance = self.cache.get_selector_performance()
                
                return render_template(
                    'statistics.html',
                    system_stats=system_stats,
                    execution_summary=execution_summary,
                    selector_performance=selector_performance,
                    current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
                
            except Exception as e:
                self.logger.error(f"统计页面加载失败: {e}")
                return render_template(
                    'statistics.html',
                    error=f"加载统计数据失败: {str(e)}",
                    current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        @self.app.route('/search')
        def search():
            """股票搜索页面"""
            try:
                stocks_param = request.args.get('stocks', '').strip()
                days = int(request.args.get('days', 7))
                
                search_results = []
                if stocks_param:
                    # 解析股票代码
                    stock_codes = [code.strip() for code in stocks_param.split(',') if code.strip()]
                    stock_codes = [code for code in stock_codes if len(code) == 6 and code.isdigit()]
                    
                    if stock_codes:
                        search_results = self.cache.search_stocks(stock_codes, days)
                
                return render_template(
                    'search.html',
                    search_results=search_results,
                    request_stocks=stocks_param,
                    days=days,
                    current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
                
            except Exception as e:
                self.logger.error(f"搜索页面加载失败: {e}")
                return render_template(
                    'search.html',
                    error=f"搜索失败: {str(e)}",
                    current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        # API路由
        @self.app.route('/api/dates')
        def api_dates():
            """API: 获取可用日期列表"""
            try:
                dates = self.cache.get_recent_dates(100)
                return jsonify({
                    'status': 'success',
                    'data': dates
                })
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                }), 500
        
        @self.app.route('/api/results/<date>')
        def api_results(date):
            """API: 获取指定日期的选股结果（包含股票详细信息）"""
            try:
                results = self.cache.get_results_with_stock_info(date)
                return jsonify({
                    'status': 'success',
                    'data': results
                })
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                }), 500
        
        @self.app.route('/api/statistics')
        def api_statistics():
            """API: 获取统计信息"""
            try:
                stats = {
                    'system': self.cache.get_statistics(),
                    'execution_summary': self.cache.get_execution_summary(30),
                    'selector_performance': self.cache.get_selector_performance()
                }
                return jsonify({
                    'status': 'success',
                    'data': stats
                })
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                }), 500
        
        @self.app.route('/api/search')
        def api_search():
            """API: 股票搜索"""
            try:
                stocks_param = request.args.get('stocks', '').strip()
                days = int(request.args.get('days', 7))
                
                if not stocks_param:
                    return jsonify({
                        'status': 'error',
                        'message': '请提供股票代码'
                    }), 400
                
                stock_codes = [code.strip() for code in stocks_param.split(',') if code.strip()]
                stock_codes = [code for code in stock_codes if len(code) == 6 and code.isdigit()]
                
                if not stock_codes:
                    return jsonify({
                        'status': 'error',
                        'message': '请提供有效的6位股票代码'
                    }), 400
                
                results = self.cache.search_stocks(stock_codes, days)
                return jsonify({
                    'status': 'success',
                    'data': results
                })
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                }), 500
        
        @self.app.route('/api/cleanup')
        def api_cleanup():
            """API: 清理旧数据"""
            try:
                self.cache.cleanup_old_data()
                return jsonify({
                    'status': 'success',
                    'message': '清理完成'
                })
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                }), 500
        
        # 静态文件路由
        @self.app.route('/static/<path:filename>')
        def static_files(filename):
            """提供静态文件"""
            return send_from_directory('static', filename)
        
        @self.app.route('/manifest.json')
        def manifest():
            """PWA清单文件"""
            return send_from_directory('static', 'manifest.json')
        
        @self.app.route('/sw.js')
        def service_worker():
            """服务工作者"""
            return send_from_directory('static', 'sw.js')
    
    def _setup_error_handlers(self):
        """设置错误处理"""
        
        @self.app.errorhandler(404)
        def not_found(error):
            return render_template(
                'index.html',
                error="页面未找到",
                current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            return render_template(
                'index.html',
                error="服务器内部错误",
                current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ), 500
    
    def run(self, debug: bool = False):
        """启动Web服务器"""
        self.logger.info(f"启动Web服务器: http://{self.host}:{self.port}")
        
        try:
            self.app.run(
                host=self.host,
                port=self.port,
                debug=debug,
                threaded=True
            )
        except Exception as e:
            self.logger.error(f"Web服务器启动失败: {e}")
            raise


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="股票选择系统Web服务器")
    parser.add_argument("--host", default="0.0.0.0", help="服务器地址")
    parser.add_argument("--port", type=int, default=8080, help="服务器端口")
    parser.add_argument("--cache-dir", default="cache", help="缓存目录")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    
    args = parser.parse_args()
    
    # 创建并启动Web服务器
    server = StockWebServer(
        cache_dir=args.cache_dir,
        host=args.host,
        port=args.port
    )
    
    server.run(debug=args.debug)


if __name__ == "__main__":
    main()