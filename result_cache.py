#!/usr/bin/env python3
"""
选股结果缓存系统
支持本地缓存、自动清理和数据管理
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging


class ResultCache:
    """选股结果缓存管理器"""
    
    def __init__(self, cache_dir: str = "cache", max_days: int = 30):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_days = max_days
        self.db_path = self.cache_dir / "results.db"
        self.logger = logging.getLogger("result_cache")
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS selection_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    selector_name TEXT NOT NULL,
                    selector_config TEXT,
                    stocks TEXT NOT NULL,
                    stock_count INTEGER NOT NULL,
                    execution_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, selector_name)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    total_selectors INTEGER,
                    total_stocks INTEGER,
                    execution_time REAL,
                    status TEXT DEFAULT 'success',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 股票基本信息表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_info (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    industry TEXT,
                    market_cap REAL,
                    pe_ratio REAL,
                    pb_ratio REAL,
                    roe REAL,
                    revenue REAL,
                    profit REAL,
                    debt_ratio REAL,
                    dividend_yield REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON selection_results(date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON selection_results(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_industry ON stock_info(industry)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_updated ON stock_info(updated_at)")
    
    def save_result(self, date: str, selector_name: str, stocks: List[str], 
                   execution_time: float = 0.0, selector_config: Dict = None):
        """保存选股结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO selection_results 
                    (date, selector_name, selector_config, stocks, stock_count, execution_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    date,
                    selector_name,
                    json.dumps(selector_config) if selector_config else None,
                    json.dumps(stocks),
                    len(stocks),
                    execution_time
                ))
                
            self.logger.info(f"保存选股结果: {date} - {selector_name} - {len(stocks)}只股票")
            
        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")
    
    def save_execution_log(self, date: str, total_selectors: int, total_stocks: int,
                          execution_time: float, status: str = 'success', 
                          error_message: str = None):
        """保存执行日志"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO execution_logs 
                    (date, total_selectors, total_stocks, execution_time, status, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (date, total_selectors, total_stocks, execution_time, status, error_message))
                
            self.logger.info(f"保存执行日志: {date} - {status}")
            
        except Exception as e:
            self.logger.error(f"保存执行日志失败: {e}")
    
    def get_results_by_date(self, date: str) -> List[Dict]:
        """获取指定日期的选股结果"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM selection_results 
                WHERE date = ? 
                ORDER BY stock_count DESC
            """, (date,))
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                result['stocks'] = json.loads(result['stocks'])
                if result['selector_config']:
                    result['selector_config'] = json.loads(result['selector_config'])
                results.append(result)
            
            return results
    
    def get_recent_dates(self, limit: int = 30) -> List[str]:
        """获取最近的执行日期"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT date FROM selection_results 
                ORDER BY date DESC 
                LIMIT ?
            """, (limit,))
            
            return [row[0] for row in cursor.fetchall()]
    
    def get_execution_summary(self, days: int = 7) -> List[Dict]:
        """获取执行摘要"""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT 
                    date,
                    COUNT(*) as selector_count,
                    SUM(stock_count) as total_stocks,
                    AVG(execution_time) as avg_execution_time
                FROM selection_results 
                WHERE date >= ?
                GROUP BY date 
                ORDER BY date DESC
            """, (cutoff_date,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_selector_performance(self) -> List[Dict]:
        """获取选择器性能统计"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT 
                    selector_name,
                    COUNT(*) as execution_count,
                    AVG(stock_count) as avg_stocks,
                    MAX(stock_count) as max_stocks,
                    AVG(execution_time) as avg_time,
                    MAX(date) as last_execution
                FROM selection_results 
                GROUP BY selector_name 
                ORDER BY avg_stocks DESC
            """, )
            
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_data(self):
        """清理超过最大天数的旧数据"""
        cutoff_date = datetime.now() - timedelta(days=self.max_days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            # 删除旧的选股结果
            cursor = conn.execute("DELETE FROM selection_results WHERE date < ?", (cutoff_str,))
            deleted_results = cursor.rowcount
            
            # 删除旧的执行日志
            cursor = conn.execute("DELETE FROM execution_logs WHERE date < ?", (cutoff_str,))
            deleted_logs = cursor.rowcount
            
            if deleted_results > 0 or deleted_logs > 0:
                self.logger.info(f"清理旧数据: 删除了 {deleted_results} 条结果记录和 {deleted_logs} 条日志记录")
    
    def get_statistics(self) -> Dict:
        """获取缓存统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # 基本统计
            stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(DISTINCT date) as unique_dates,
                    COUNT(DISTINCT selector_name) as unique_selectors,
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date
                FROM selection_results
            """).fetchone()
            
            # 数据库文件大小
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            result = dict(stats) if stats else {}
            result['database_size_mb'] = round(db_size / 1024 / 1024, 2)
            result['cache_dir'] = str(self.cache_dir)
            result['max_retention_days'] = self.max_days
            
            return result
    
    def search_stocks(self, stock_codes: List[str], days: int = 7) -> List[Dict]:
        """搜索特定股票在最近几天的选中情况"""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        results = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for stock_code in stock_codes:
                cursor = conn.execute("""
                    SELECT date, selector_name, stocks, stock_count
                    FROM selection_results 
                    WHERE date >= ? AND stocks LIKE ?
                    ORDER BY date DESC
                """, (cutoff_date, f'%"{stock_code}"%'))
                
                stock_results = []
                for row in cursor.fetchall():
                    stocks = json.loads(row['stocks'])
                    if stock_code in stocks:
                        stock_results.append({
                            'date': row['date'],
                            'selector_name': row['selector_name'],
                            'total_stocks': row['stock_count']
                        })
                
                results.append({
                    'stock_code': stock_code,
                    'selections': stock_results,
                    'selection_count': len(stock_results)
                })
        
        return results
    
    def save_stock_info(self, stock_code: str, stock_info: Dict):
        """保存股票基本信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO stock_info 
                    (code, name, industry, market_cap, pe_ratio, pb_ratio, roe, 
                     revenue, profit, debt_ratio, dividend_yield, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    stock_code,
                    stock_info.get('name', ''),
                    stock_info.get('industry', ''),
                    stock_info.get('market_cap'),
                    stock_info.get('pe_ratio'),
                    stock_info.get('pb_ratio'),
                    stock_info.get('roe'),
                    stock_info.get('revenue'),
                    stock_info.get('profit'),
                    stock_info.get('debt_ratio'),
                    stock_info.get('dividend_yield')
                ))
                self.logger.debug(f"保存股票信息: {stock_code}")
        except Exception as e:
            self.logger.error(f"保存股票信息失败 {stock_code}: {e}")
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("""
                    SELECT code, name, industry, market_cap, pe_ratio, pb_ratio, 
                           roe, revenue, profit, debt_ratio, dividend_yield, updated_at
                    FROM stock_info WHERE code = ?
                """, (stock_code,)).fetchone()
                
                return dict(row) if row else None
        except Exception as e:
            self.logger.error(f"获取股票信息失败 {stock_code}: {e}")
            return None
    
    def get_stocks_info(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """批量获取股票基本信息"""
        results = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                placeholders = ','.join(['?' for _ in stock_codes])
                cursor = conn.execute(f"""
                    SELECT code, name, industry, market_cap, pe_ratio, pb_ratio,
                           roe, revenue, profit, debt_ratio, dividend_yield, updated_at
                    FROM stock_info WHERE code IN ({placeholders})
                """, stock_codes)
                
                for row in cursor.fetchall():
                    results[row['code']] = dict(row)
                    
        except Exception as e:
            self.logger.error(f"批量获取股票信息失败: {e}")
        
        return results
    
    def is_stock_info_stale(self, stock_code: str, days: int = 7) -> bool:
        """检查股票信息是否过期"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("""
                    SELECT updated_at FROM stock_info WHERE code = ?
                """, (stock_code,)).fetchone()
                
                if not row:
                    return True
                    
                updated_at = datetime.fromisoformat(row[0])
                return (datetime.now() - updated_at).days > days
        except:
            return True
    
    def get_results_with_stock_info(self, date: str) -> List[Dict]:
        """获取包含股票详细信息的选股结果"""
        results = self.get_results_by_date(date)
        if not results:
            return []
            
        # 收集所有股票代码
        all_stock_codes = []
        for result in results:
            all_stock_codes.extend(result['stocks'])
        
        # 批量获取股票信息
        stocks_info = self.get_stocks_info(list(set(all_stock_codes)))
        
        # 将股票信息添加到结果中
        for result in results:
            result['stocks_detail'] = []
            for stock_code in result['stocks']:
                stock_detail = {
                    'code': stock_code,
                    'name': '未知',
                    'industry': '',
                    'market_cap': None,
                    'pe_ratio': None
                }
                
                if stock_code in stocks_info:
                    info = stocks_info[stock_code]
                    stock_detail.update({
                        'name': info.get('name', '未知'),
                        'industry': info.get('industry', ''),
                        'market_cap': info.get('market_cap'),
                        'pe_ratio': info.get('pe_ratio'),
                        'pb_ratio': info.get('pb_ratio'),
                        'roe': info.get('roe')
                    })
                
                result['stocks_detail'].append(stock_detail)
        
        return results


def cleanup_cache_task(cache_dir: str = "cache", max_days: int = 30):
    """定时清理缓存的任务函数"""
    cache = ResultCache(cache_dir, max_days)
    cache.cleanup_old_data()


if __name__ == "__main__":
    # 测试缓存功能
    cache = ResultCache()
    
    # 测试保存结果
    test_stocks = ["000001", "000002", "600000"]
    cache.save_result("2024-01-15", "测试选择器", test_stocks, 1.5, {"param1": "value1"})
    
    # 测试获取结果
    results = cache.get_results_by_date("2024-01-15")
    print("测试结果:", results)
    
    # 测试统计信息
    stats = cache.get_statistics()
    print("缓存统计:", stats)