#!/usr/bin/env python3
"""
股票信息获取器
使用akshare获取股票基本信息并缓存
"""

import time
import logging
from typing import Dict, List, Optional
import akshare as ak
import pandas as pd
from result_cache import ResultCache


class StockInfoFetcher:
    """股票信息获取器"""
    
    def __init__(self, cache: ResultCache):
        self.cache = cache
        self.logger = logging.getLogger("stock_info_fetcher")
        self.request_delay = 0.1  # 请求间隔，避免频繁请求
    
    def fetch_stock_basic_info(self, stock_code: str) -> Optional[Dict]:
        """获取单个股票基本信息"""
        try:
            # 格式化股票代码
            if stock_code.startswith('6'):
                symbol = f"{stock_code}.SH"
            else:
                symbol = f"{stock_code}.SZ"
            
            # 获取股票基本信息
            info = {}
            
            # 尝试获取股票基本面信息
            try:
                # 个股信息
                stock_individual_info = ak.stock_individual_info_em(symbol=stock_code)
                if not stock_individual_info.empty:
                    info_dict = dict(zip(stock_individual_info['item'], stock_individual_info['value']))
                    
                    info.update({
                        'name': info_dict.get('股票简称', ''),
                        'industry': info_dict.get('所处行业', ''),
                        'market_cap': self._safe_float(info_dict.get('总市值')),
                        'pe_ratio': self._safe_float(info_dict.get('市盈率-动态')),
                        'pb_ratio': self._safe_float(info_dict.get('市净率')),
                        'roe': self._safe_float(info_dict.get('净资产收益率'))
                    })
            except Exception as e:
                self.logger.warning(f"获取股票基本信息失败 {stock_code}: {e}")
            
            # 尝试获取财务数据
            try:
                # 资产负债表主要指标
                balance_sheet = ak.stock_balance_sheet_by_report_em(symbol=stock_code)
                if not balance_sheet.empty:
                    latest_data = balance_sheet.iloc[0]
                    info.update({
                        'debt_ratio': self._safe_float(latest_data.get('资产负债率')),
                    })
            except Exception as e:
                self.logger.warning(f"获取财务数据失败 {stock_code}: {e}")
            
            # 尝试获取利润数据
            try:
                profit_data = ak.stock_profit_forecast_ths(symbol=stock_code)
                if not profit_data.empty:
                    latest_profit = profit_data.iloc[0]
                    info.update({
                        'revenue': self._safe_float(latest_profit.get('营业收入')),
                        'profit': self._safe_float(latest_profit.get('净利润'))
                    })
            except Exception as e:
                self.logger.warning(f"获取利润数据失败 {stock_code}: {e}")
            
            # 如果没有获取到名称，尝试从股票列表获取
            if not info.get('name'):
                try:
                    stock_info_sh = ak.stock_info_a_code_name()
                    stock_row = stock_info_sh[stock_info_sh['code'] == stock_code]
                    if not stock_row.empty:
                        info['name'] = stock_row.iloc[0]['name']
                except:
                    pass
            
            # 设置默认值
            if not info.get('name'):
                info['name'] = stock_code
                
            time.sleep(self.request_delay)  # 避免请求过于频繁
            return info
            
        except Exception as e:
            self.logger.error(f"获取股票信息失败 {stock_code}: {e}")
            return {
                'name': stock_code,
                'industry': '',
                'market_cap': None,
                'pe_ratio': None,
                'pb_ratio': None,
                'roe': None,
                'revenue': None,
                'profit': None,
                'debt_ratio': None,
                'dividend_yield': None
            }
    
    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            if value is None or value == '' or value == '-':
                return None
            # 移除可能的单位和格式
            if isinstance(value, str):
                value = value.replace(',', '').replace('%', '').replace('万', '').replace('亿', '')
            return float(value)
        except:
            return None
    
    def fetch_and_cache_stocks_info(self, stock_codes: List[str], force_update: bool = False):
        """批量获取并缓存股票信息"""
        self.logger.info(f"开始批量获取股票信息，共 {len(stock_codes)} 只股票")
        
        success_count = 0
        failed_count = 0
        
        for i, stock_code in enumerate(stock_codes):
            try:
                # 检查是否需要更新
                if not force_update and not self.cache.is_stock_info_stale(stock_code, days=7):
                    self.logger.debug(f"股票信息缓存有效，跳过: {stock_code}")
                    continue
                
                # 获取股票信息
                stock_info = self.fetch_stock_basic_info(stock_code)
                if stock_info:
                    # 保存到缓存
                    self.cache.save_stock_info(stock_code, stock_info)
                    success_count += 1
                    self.logger.debug(f"成功获取并缓存股票信息: {stock_code} - {stock_info.get('name', 'Unknown')}")
                else:
                    failed_count += 1
                    self.logger.warning(f"获取股票信息失败: {stock_code}")
                
                # 进度提示
                if (i + 1) % 10 == 0:
                    self.logger.info(f"进度: {i + 1}/{len(stock_codes)}, 成功: {success_count}, 失败: {failed_count}")
                    
            except Exception as e:
                failed_count += 1
                self.logger.error(f"处理股票 {stock_code} 时出错: {e}")
        
        self.logger.info(f"批量获取股票信息完成，成功: {success_count}, 失败: {failed_count}")
    
    def update_stocks_from_selection_results(self, date: str):
        """从选股结果中更新股票信息"""
        results = self.cache.get_results_by_date(date)
        if not results:
            self.logger.warning(f"未找到 {date} 的选股结果")
            return
            
        # 收集所有股票代码
        all_stock_codes = []
        for result in results:
            all_stock_codes.extend(result['stocks'])
        
        unique_stock_codes = list(set(all_stock_codes))
        self.logger.info(f"从 {date} 选股结果中发现 {len(unique_stock_codes)} 只股票")
        
        # 批量获取并缓存股票信息
        self.fetch_and_cache_stocks_info(unique_stock_codes)


def update_stock_info_task(date: str = None, cache_dir: str = "cache"):
    """更新股票信息的任务函数"""
    cache = ResultCache(cache_dir)
    fetcher = StockInfoFetcher(cache)
    
    if date:
        fetcher.update_stocks_from_selection_results(date)
    else:
        # 获取最近的选股结果日期
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        fetcher.update_stocks_from_selection_results(today)


if __name__ == "__main__":
    # 测试股票信息获取
    import sys
    
    cache = ResultCache()
    fetcher = StockInfoFetcher(cache)
    
    # 测试获取单个股票信息
    test_codes = ["000001", "600000", "300001"]
    
    if len(sys.argv) > 1:
        # 从命令行参数获取日期
        date = sys.argv[1]
        fetcher.update_stocks_from_selection_results(date)
    else:
        # 测试模式
        print("测试模式：获取示例股票信息")
        fetcher.fetch_and_cache_stocks_info(test_codes, force_update=True)
        
        # 显示结果
        for code in test_codes:
            info = cache.get_stock_info(code)
            print(f"{code}: {info}")