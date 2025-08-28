#!/usr/bin/env python3
"""
定时任务调度器
支持配置化的定时任务执行select_stock.py
"""

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from select_stock import main as select_stock_main
from stock_info_fetcher import StockInfoFetcher
from result_cache import ResultCache


class StockScheduler:
    def __init__(self, config_path: str = "scheduler_config.json"):
        self.config_path = Path(config_path)
        self.scheduler = None
        self.config = None
        self.setup_logging()
        self.load_config()
    
    def setup_logging(self):
        """设置日志记录"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s][%(levelname)s] %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("scheduler.log", encoding="utf-8"),
            ],
        )
        self.logger = logging.getLogger("scheduler")
    
    def load_config(self):
        """加载调度器配置"""
        if not self.config_path.exists():
            self.logger.error("配置文件 %s 不存在", self.config_path)
            sys.exit(1)
        
        try:
            with self.config_path.open(encoding="utf-8") as f:
                self.config = json.load(f)
            self.logger.info("成功加载配置文件: %s", self.config_path)
        except Exception as e:
            self.logger.error("加载配置文件失败: %s", e)
            sys.exit(1)
    
    def setup_scheduler(self):
        """初始化调度器"""
        scheduler_config = self.config.get("scheduler", {})
        timezone_str = scheduler_config.get("timezone", "Asia/Shanghai")
        timezone = pytz.timezone(timezone_str)
        
        self.scheduler = BlockingScheduler(
            timezone=timezone,
            job_defaults={
                'coalesce': scheduler_config.get("coalesce", True),
                'max_instances': scheduler_config.get("max_instances", 1),
                'misfire_grace_time': 300
            }
        )
        
        self.logger.info("调度器初始化完成，时区: %s", timezone_str)
    
    def run_data_update(self, **kwargs):
        """执行数据更新任务"""
        self.logger.info("开始执行数据更新...")
        start_time = time.time()
        
        try:
            # 构造fetch_kline.py的参数
            cmd = ["python", "fetch_kline.py"]
            
            # 从配置中获取数据更新参数
            datasource = kwargs.get("datasource", "akshare")
            workers = kwargs.get("workers", 3)
            data_dir = kwargs.get("data_dir", "./data")
            
            cmd.extend(["--datasource", datasource])
            cmd.extend(["--workers", str(workers)])
            cmd.extend(["--out", data_dir])
            cmd.extend(["--start", "today"])  # 增量更新，从今天开始
            cmd.extend(["--end", "today"])
            
            # 执行数据更新
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=3600,  # 1小时超时
                encoding='utf-8'
            )
            
            elapsed = time.time() - start_time
            
            if result.returncode == 0:
                self.logger.info("数据更新完成，耗时: %.2f秒", elapsed)
                return True
            else:
                self.logger.error("数据更新失败，耗时: %.2f秒，错误: %s", elapsed, result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            self.logger.error("数据更新超时，耗时: %.2f秒", elapsed)
            return False
        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error("数据更新异常，耗时: %.2f秒，错误: %s", elapsed, e)
            return False

    def run_stock_selection(self, job_id: str, **kwargs):
        """执行选股任务（包含数据更新）"""
        self.logger.info("开始执行任务: %s", job_id)
        total_start_time = time.time()
        
        try:
            # 步骤1：先执行数据更新
            update_success = kwargs.get("skip_data_update", False)
            
            if not update_success:
                self.logger.info("步骤1: 执行数据更新...")
                update_success = self.run_data_update(**kwargs)
                
                if not update_success:
                    # 数据更新失败，记录错误但不阻止选股（使用现有数据）
                    self.logger.warning("数据更新失败，将使用现有数据执行选股")
            
            # 步骤2：执行选股
            self.logger.info("步骤2: 执行选股任务...")
            selection_start_time = time.time()
            
            # 备份原始sys.argv
            original_argv = sys.argv.copy()
            
            # 构造参数
            sys.argv = ["select_stock.py"]
            
            data_dir = kwargs.get("data_dir", "./data")
            config = kwargs.get("config", "./configs.json")
            tickers = kwargs.get("tickers", "all")
            date = kwargs.get("date")  # 如果不指定，使用最新日期
            cache_dir = kwargs.get("cache_dir", "./cache")
            
            sys.argv.extend(["--data-dir", data_dir])
            sys.argv.extend(["--config", config])
            sys.argv.extend(["--tickers", tickers])
            sys.argv.extend(["--cache-dir", cache_dir])
            
            if date:
                sys.argv.extend(["--date", date])
            
            # 执行选股
            select_stock_main()
            
            # 恢复原始sys.argv
            sys.argv = original_argv
            
            selection_elapsed = time.time() - selection_start_time
            
            # 步骤3：获取并缓存股票基本信息
            self.logger.info("步骤3: 获取股票基本信息...")
            info_start_time = time.time()
            
            try:
                cache = ResultCache(cache_dir)
                fetcher = StockInfoFetcher(cache)
                
                # 获取当天日期
                target_date = date if date else datetime.now().strftime('%Y-%m-%d')
                
                # 更新股票信息
                fetcher.update_stocks_from_selection_results(target_date)
                
                info_elapsed = time.time() - info_start_time
                self.logger.info("股票信息获取完成，耗时: %.2f秒", info_elapsed)
                
            except Exception as e:
                info_elapsed = time.time() - info_start_time
                self.logger.error("股票信息获取失败，耗时: %.2f秒，错误: %s", info_elapsed, e)
            
            total_elapsed = time.time() - total_start_time
            
            self.logger.info("选股任务完成，耗时: %.2f秒", selection_elapsed)
            self.logger.info("任务 %s 总耗时: %.2f秒", job_id, total_elapsed)
            
        except Exception as e:
            total_elapsed = time.time() - total_start_time
            self.logger.error("任务 %s 执行失败，总耗时: %.2f秒，错误: %s", job_id, total_elapsed, e)
            # 恢复原始sys.argv
            if 'original_argv' in locals():
                sys.argv = original_argv
    
    def add_jobs(self):
        """添加任务到调度器"""
        jobs_config = self.config.get("jobs", [])
        
        for job_config in jobs_config:
            if not job_config.get("enabled", True):
                self.logger.info("跳过已禁用的任务: %s", job_config.get("name", "未命名"))
                continue
            
            job_id = job_config["id"]
            job_name = job_config.get("name", job_id)
            trigger_type = job_config.get("trigger", "cron")
            
            if trigger_type == "cron":
                # 创建cron触发器
                trigger = CronTrigger(
                    hour=job_config.get("hour", 0),
                    minute=job_config.get("minute", 0),
                    second=job_config.get("second", 0),
                    day_of_week=job_config.get("day_of_week"),
                    timezone=self.scheduler.timezone
                )
                
                # 添加任务
                self.scheduler.add_job(
                    func=self.run_stock_selection,
                    trigger=trigger,
                    id=job_id,
                    name=job_name,
                    kwargs={"job_id": job_id, **job_config.get("args", {})},
                    misfire_grace_time=job_config.get("misfire_grace_time", 300)
                )
                self.logger.info("添加任务: %s", job_name)
            else:
                self.logger.warning("不支持的触发器类型: %s，跳过任务: %s", trigger_type, job_name)
    
    def start(self):
        """启动调度器"""
        try:
            self.setup_scheduler()
            self.add_jobs()
            
            if not self.scheduler.get_jobs():
                self.logger.warning("没有启用的任务，调度器将退出")
                return
            
            self.logger.info("调度器启动，等待任务执行...")
            
            
            
            self.scheduler.start()
            
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在停止调度器...")
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown()
        except Exception as e:
            self.logger.error("调度器运行异常: %s", e)
            sys.exit(1)
    
    def stop(self):
        """停止调度器"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            self.logger.info("调度器已停止")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="股票选择定时任务调度器")
    parser.add_argument("--config", default="scheduler_config.json", help="调度器配置文件路径")
    parser.add_argument("--run-now", action="store_true", help="立即执行一次选股任务（用于测试）")
    
    args = parser.parse_args()
    
    scheduler = StockScheduler(args.config)
    
    if args.run_now:
        # 立即执行一次任务
        scheduler.logger.info("执行测试任务...")
        scheduler.run_stock_selection(
            job_id="test",
            data_dir="./data",
            config="./configs.json",
            tickers="all"
        )
    else:
        # 启动调度器
        scheduler.start()


if __name__ == "__main__":
    main()