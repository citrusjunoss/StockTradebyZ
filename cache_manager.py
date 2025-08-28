#!/usr/bin/env python3
"""
缓存管理工具
提供缓存清理、维护和监控功能
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from result_cache import ResultCache
from logger_config import setup_logger


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache = ResultCache(cache_dir)
        self.logger = setup_logger("cache_manager")
    
    def cleanup_old_data(self, days: int = 30):
        """清理超过指定天数的旧数据"""
        try:
            self.logger.info(f"开始清理超过 {days} 天的旧数据...")
            
            # 获取清理前的统计信息
            before_stats = self.cache.get_statistics()
            
            # 执行清理
            self.cache.cleanup_old_data()
            
            # 获取清理后的统计信息
            after_stats = self.cache.get_statistics()
            
            # 计算清理效果
            records_cleaned = before_stats.get('total_records', 0) - after_stats.get('total_records', 0)
            size_freed = before_stats.get('database_size_mb', 0) - after_stats.get('database_size_mb', 0)
            
            self.logger.info(f"清理完成: 删除了 {records_cleaned} 条记录，释放了 {size_freed:.2f}MB 空间")
            
            return {
                'records_cleaned': records_cleaned,
                'size_freed_mb': size_freed,
                'before_stats': before_stats,
                'after_stats': after_stats
            }
            
        except Exception as e:
            self.logger.error(f"清理数据失败: {e}")
            raise
    
    def get_cache_info(self):
        """获取缓存详细信息"""
        try:
            stats = self.cache.get_statistics()
            recent_dates = self.cache.get_recent_dates(10)
            performance = self.cache.get_selector_performance()
            
            info = {
                'cache_directory': str(self.cache_dir),
                'database_path': str(self.cache.db_path),
                'statistics': stats,
                'recent_execution_dates': recent_dates,
                'top_selectors': performance[:5] if performance else []
            }
            
            return info
            
        except Exception as e:
            self.logger.error(f"获取缓存信息失败: {e}")
            raise
    
    def vacuum_database(self):
        """压缩数据库，回收空间"""
        try:
            self.logger.info("开始压缩数据库...")
            
            import sqlite3
            with sqlite3.connect(self.cache.db_path) as conn:
                conn.execute("VACUUM")
            
            self.logger.info("数据库压缩完成")
            
        except Exception as e:
            self.logger.error(f"数据库压缩失败: {e}")
            raise
    
    def backup_database(self, backup_path: str = None):
        """备份数据库"""
        try:
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.cache_dir / f"backup_results_{timestamp}.db"
            else:
                backup_path = Path(backup_path)
            
            self.logger.info(f"开始备份数据库到: {backup_path}")
            
            import shutil
            shutil.copy2(self.cache.db_path, backup_path)
            
            self.logger.info("数据库备份完成")
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"数据库备份失败: {e}")
            raise
    
    def analyze_cache_usage(self, days: int = 30):
        """分析缓存使用情况"""
        try:
            self.logger.info(f"分析最近 {days} 天的缓存使用情况...")
            
            # 获取执行摘要
            summary = self.cache.get_execution_summary(days)
            
            # 获取选择器性能
            performance = self.cache.get_selector_performance()
            
            # 计算统计信息
            total_executions = len(summary)
            total_stocks_selected = sum(s['total_stocks'] for s in summary)
            avg_stocks_per_day = total_stocks_selected / total_executions if total_executions > 0 else 0
            
            # 最活跃的选择器
            most_active_selector = max(performance, key=lambda x: x['execution_count']) if performance else None
            
            # 最高效的选择器（平均选股最多）
            most_effective_selector = max(performance, key=lambda x: x['avg_stocks']) if performance else None
            
            analysis = {
                'analysis_period_days': days,
                'total_execution_days': total_executions,
                'total_stocks_selected': total_stocks_selected,
                'average_stocks_per_day': avg_stocks_per_day,
                'most_active_selector': most_active_selector,
                'most_effective_selector': most_effective_selector,
                'daily_summary': summary,
                'selector_performance': performance
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"分析缓存使用失败: {e}")
            raise
    
    def export_results(self, output_file: str, date_from: str = None, date_to: str = None):
        """导出选股结果到CSV文件"""
        try:
            import pandas as pd
            
            self.logger.info(f"开始导出结果到: {output_file}")
            
            # 获取数据
            import sqlite3
            with sqlite3.connect(self.cache.db_path) as conn:
                query = """
                    SELECT date, selector_name, stocks, stock_count, execution_time, created_at
                    FROM selection_results
                """
                params = []
                
                if date_from or date_to:
                    conditions = []
                    if date_from:
                        conditions.append("date >= ?")
                        params.append(date_from)
                    if date_to:
                        conditions.append("date <= ?")
                        params.append(date_to)
                    
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY date DESC, selector_name"
                
                df = pd.read_sql_query(query, conn, params=params)
            
            # 处理股票列表
            import json
            df['stock_list'] = df['stocks'].apply(lambda x: ', '.join(json.loads(x)))
            df = df.drop('stocks', axis=1)
            
            # 导出到CSV
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            
            self.logger.info(f"导出完成: {len(df)} 条记录")
            return len(df)
            
        except Exception as e:
            self.logger.error(f"导出结果失败: {e}")
            raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="缓存管理工具")
    parser.add_argument("--cache-dir", default="cache", help="缓存目录")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 清理命令
    cleanup_parser = subparsers.add_parser("cleanup", help="清理旧数据")
    cleanup_parser.add_argument("--days", type=int, default=30, help="保留天数")
    
    # 信息命令
    subparsers.add_parser("info", help="显示缓存信息")
    
    # 压缩命令
    subparsers.add_parser("vacuum", help="压缩数据库")
    
    # 备份命令
    backup_parser = subparsers.add_parser("backup", help="备份数据库")
    backup_parser.add_argument("--output", help="备份文件路径")
    
    # 分析命令
    analyze_parser = subparsers.add_parser("analyze", help="分析缓存使用情况")
    analyze_parser.add_argument("--days", type=int, default=30, help="分析天数")
    
    # 导出命令
    export_parser = subparsers.add_parser("export", help="导出结果到CSV")
    export_parser.add_argument("--output", required=True, help="输出文件路径")
    export_parser.add_argument("--from", dest="date_from", help="开始日期 (YYYY-MM-DD)")
    export_parser.add_argument("--to", dest="date_to", help="结束日期 (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = CacheManager(args.cache_dir)
    
    try:
        if args.command == "cleanup":
            result = manager.cleanup_old_data(args.days)
            print(f"清理完成: 删除 {result['records_cleaned']} 条记录，释放 {result['size_freed_mb']:.2f}MB")
        
        elif args.command == "info":
            info = manager.get_cache_info()
            print("缓存信息:")
            print(f"  缓存目录: {info['cache_directory']}")
            print(f"  数据库: {info['database_path']}")
            print(f"  总记录数: {info['statistics'].get('total_records', 0)}")
            print(f"  执行天数: {info['statistics'].get('unique_dates', 0)}")
            print(f"  选择器数量: {info['statistics'].get('unique_selectors', 0)}")
            print(f"  数据库大小: {info['statistics'].get('database_size_mb', 0):.2f}MB")
            print(f"  最早日期: {info['statistics'].get('earliest_date', 'N/A')}")
            print(f"  最新日期: {info['statistics'].get('latest_date', 'N/A')}")
        
        elif args.command == "vacuum":
            manager.vacuum_database()
            print("数据库压缩完成")
        
        elif args.command == "backup":
            backup_path = manager.backup_database(args.output)
            print(f"备份完成: {backup_path}")
        
        elif args.command == "analyze":
            analysis = manager.analyze_cache_usage(args.days)
            print(f"缓存使用分析 (最近{analysis['analysis_period_days']}天):")
            print(f"  执行天数: {analysis['total_execution_days']}")
            print(f"  总选股数: {analysis['total_stocks_selected']}")
            print(f"  日均选股: {analysis['average_stocks_per_day']:.1f}")
            
            if analysis['most_active_selector']:
                selector = analysis['most_active_selector']
                print(f"  最活跃选择器: {selector['selector_name']} ({selector['execution_count']}次)")
            
            if analysis['most_effective_selector']:
                selector = analysis['most_effective_selector']
                print(f"  最高效选择器: {selector['selector_name']} (平均{selector['avg_stocks']:.1f}只)")
        
        elif args.command == "export":
            count = manager.export_results(args.output, args.date_from, args.date_to)
            print(f"导出完成: {count} 条记录 -> {args.output}")
    
    except Exception as e:
        print(f"执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()