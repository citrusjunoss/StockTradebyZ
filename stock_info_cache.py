#!/usr/bin/env python3
"""
股票信息缓存模块
用于获取和缓存股票名称、行业等基本信息
"""

import json
import logging
import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None

try:
    import tushare as ts
except ImportError:
    ts = None

try:
    from mootdx.quotes import Quotes
    from mootdx import consts
except ImportError:
    Quotes = None
    consts = None

logger = logging.getLogger(__name__)

class StockInfoCache:
    """股票信息缓存类"""
    
    def __init__(self, cache_file: str = "stock_info_cache.json", datasource: str = "akshare"):
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.datasource = datasource.lower()
        self.load_cache()
    
    def load_cache(self) -> None:
        """从文件加载缓存"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f) 
                    self.cache = data['stocks']
                    logger.info(f"已加载股票信息缓存，包含 {len(self.cache)} 只股票")
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")
            self.cache = {}
    
    def save_cache(self) -> None:
        """保存缓存到文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存股票信息缓存，包含 {len(self.cache)} 只股票")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
    
    def get_stock_info(self, code: str) -> Dict[str, Any]:
        """获取单只股票信息"""
        code = str(code).zfill(6)  # 确保6位数字
        
        if code in self.cache:
            return self.cache[code]
        
        # 根据数据源获取股票信息
        info = None
        if self.datasource == "akshare" and ak is not None:
            info = self._fetch_from_akshare(code)
        elif self.datasource == "tushare" and ts is not None:
            info = self._fetch_from_tushare(code)
        elif self.datasource == "mootdx" and Quotes is not None:
            info = self._fetch_from_mootdx(code)
        else:
            logger.warning(f"不支持的数据源: {self.datasource} 或相关库未安装")
        
        if info:
            self.cache[code] = info
            return info
        
        # 如果无法获取，返回默认信息
        default_info = {
            'name': f'股票{code}',
            'industry': '未知行业',
            'market': self._get_market_by_code(code),
            'last_updated': time.strftime('%Y-%m-%d')
        }
        self.cache[code] = default_info
        return default_info
    
    def _fetch_from_akshare(self, code: str) -> Optional[Dict[str, Any]]:
        """从akshare获取股票信息"""
        try:
            # 获取股票基本信息
            for attempt in range(3):
                try:
                    # 获取实时行情数据（包含名称）
                    df = ak.stock_zh_a_spot_em()
                    if df is not None and not df.empty:
                        stock_row = df[df['代码'] == code]
                        if not stock_row.empty:
                            name = stock_row.iloc[0]['名称']
                            
                            # 获取行业信息
                            industry = self._get_industry_info(code)
                            
                            info = {
                                'name': name,
                                'industry': industry,
                                'market': self._get_market_by_code(code),
                                'last_updated': time.strftime('%Y-%m-%d')
                            }
                            logger.info(f"获取股票信息: {code} {name} - {industry}")
                            return info
                    
                    time.sleep(random.uniform(0.5, 1.5))
                except Exception as e:
                    logger.warning(f"akshare获取股票 {code} 信息失败 (尝试 {attempt + 1}/3): {e}")
                    time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            logger.error(f"获取股票 {code} 信息失败: {e}")
        
        return None
    
    def _get_industry_info(self, code: str) -> str:
        """获取行业信息"""
        try:
            # 尝试获取行业分类信息
            df = ak.stock_individual_info_em(symbol=code)
            if df is not None and not df.empty:
                # 查找行业信息
                industry_row = df[df['item'] == '行业']
                if not industry_row.empty:
                    return industry_row.iloc[0]['value']
                
                # 备选：所属同花顺行业
                industry_row = df[df['item'] == '所属同花顺行业']
                if not industry_row.empty:
                    return industry_row.iloc[0]['value']
            
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            logger.debug(f"获取股票 {code} 行业信息失败: {e}")
        
        return "未知行业"
    
    def _fetch_from_tushare(self, code: str) -> Optional[Dict[str, Any]]:
        """从tushare获取股票信息"""
        try:
            # 转换为tushare代码格式
            ts_code = self._to_ts_code(code)
            
            # 获取股票基本信息
            for attempt in range(3):
                try:
                    # 获取股票基本信息
                    df = ts.pro_api().stock_basic(ts_code=ts_code, fields='ts_code,name,industry,market')
                    if df is not None and not df.empty:
                        row = df.iloc[0]
                        info = {
                            'name': row.get('name', f'股票{code}'),
                            'industry': row.get('industry', '未知行业'),
                            'market': self._get_market_by_code(code),
                            'last_updated': time.strftime('%Y-%m-%d')
                        }
                        logger.info(f"Tushare获取股票信息: {code} {info['name']} - {info['industry']}")
                        return info
                    
                    time.sleep(random.uniform(0.5, 1.5))
                except Exception as e:
                    logger.warning(f"Tushare获取股票 {code} 信息失败 (尝试 {attempt + 1}/3): {e}")
                    time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            logger.error(f"Tushare获取股票 {code} 信息失败: {e}")
        
        return None
    
    def _to_ts_code(self, code: str) -> str:
        """转换为Tushare代码格式"""
        code = str(code).zfill(6)
        if code.startswith(('60', '68', '90')):
            return f"{code}.SH"
        elif code.startswith(('00', '30', '8')):
            return f"{code}.SZ"
        else:
            return f"{code}.SH"  # 默认上交所
    
    def _fetch_from_mootdx(self, code: str) -> Optional[Dict[str, Any]]:
        """从mootdx获取股票信息"""
        try:
            client = Quotes.factory(market="std")
            
            for attempt in range(3):
                try:
                    # 尝试从股票列表中获取基本信息
                    market = consts.MARKET_SH if code.startswith(('60', '68', '90')) else consts.MARKET_SZ
                    stocks_df = client.stocks(market=market)
                    
                    if stocks_df is not None and not stocks_df.empty:
                        # 查找对应的股票
                        stock_row = stocks_df[stocks_df['code'] == code.zfill(6)]
                        if not stock_row.empty:
                            name = stock_row.iloc[0].get('name', f'股票{code}')
                            
                            info = {
                                'name': name,
                                'industry': '未知行业',  # mootdx不提供行业分类
                                'market': self._get_market_by_code(code),
                                'last_updated': time.strftime('%Y-%m-%d')
                            }
                            logger.info(f"Mootdx获取股票信息: {code} {info['name']}")
                            return info
                    
                    # 备用方案：直接通过quotes接口获取
                    quotes_df = client.quotes(symbol=[code.zfill(6)])
                    if quotes_df is not None and not quotes_df.empty:
                        name = quotes_df.iloc[0].get('name', f'股票{code}')
                        
                        info = {
                            'name': name,
                            'industry': '未知行业',
                            'market': self._get_market_by_code(code),
                            'last_updated': time.strftime('%Y-%m-%d')
                        }
                        logger.info(f"Mootdx(quotes)获取股票信息: {code} {info['name']}")
                        return info
                    
                    time.sleep(random.uniform(0.5, 1.5))
                except Exception as e:
                    logger.warning(f"Mootdx获取股票 {code} 信息失败 (尝试 {attempt + 1}/3): {e}")
                    time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            logger.error(f"Mootdx获取股票 {code} 信息失败: {e}")
        
        return None
    
    def _get_market_by_code(self, code: str) -> str:
        """根据股票代码判断市场"""
        if code.startswith(('60', '68', '90')):
            return "上交所"
        elif code.startswith(('00', '30')):
            return "深交所"
        elif code.startswith('8'):
            return "北交所"
        else:
            return "未知市场"
    
    def batch_update(self, codes: List[str], max_new: int = 50) -> None:
        """批量更新股票信息"""
        codes = [str(code).zfill(6) for code in codes]
        new_codes = [code for code in codes if code not in self.cache]
        
        if not new_codes:
            logger.info("所有股票信息都已缓存，无需更新")
            return
        
        # 限制每次更新的数量，避免请求过多
        if len(new_codes) > max_new:
            new_codes = new_codes[:max_new]
            logger.info(f"限制更新数量为 {max_new} 只股票")
        
        logger.info(f"开始批量更新 {len(new_codes)} 只股票信息...")
        
        updated = 0
        for i, code in enumerate(new_codes):
            try:
                self.get_stock_info(code)
                updated += 1
                
                # 控制请求频率
                if i < len(new_codes) - 1:
                    time.sleep(random.uniform(0.8, 1.5))
                
                # 每更新10个保存一次
                if (i + 1) % 10 == 0:
                    self.save_cache()
                    logger.info(f"已更新 {i + 1}/{len(new_codes)} 只股票")
                    
            except Exception as e:
                logger.error(f"更新股票 {code} 信息失败: {e}")
        
        self.save_cache()
        logger.info(f"批量更新完成，成功更新 {updated} 只股票")
    
    def get_stocks_info(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """获取多只股票信息"""
        result = {}
        for code in codes:
            result[code] = self.get_stock_info(code)
        return result
    
    def search_by_name(self, keyword: str) -> List[Dict[str, Any]]:
        """根据股票名称搜索"""
        results = []
        for code, info in self.cache.items():
            if keyword in info.get('name', ''):
                results.append({'code': code, **info})
        return results
    
    def get_industry_stats(self) -> Dict[str, int]:
        """获取行业统计"""
        industry_count = {}
        for info in self.cache.values():
            industry = info.get('industry', '未知行业')
            industry_count[industry] = industry_count.get(industry, 0) + 1
        return dict(sorted(industry_count.items(), key=lambda x: x[1], reverse=True))
    
    def cleanup_cache(self, days: int = 30) -> None:
        """清理过期缓存"""
        import datetime
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        expired_codes = []
        for code, info in self.cache.items():
            if info.get('last_updated', '2000-01-01') < cutoff_str:
                expired_codes.append(code)
        
        for code in expired_codes:
            del self.cache[code]
        
        if expired_codes:
            self.save_cache()
            logger.info(f"已清理 {len(expired_codes)} 条过期缓存")
    
    def init_from_mootdx_offline(self) -> None:
        """使用mootdx离线数据批量初始化股票信息缓存"""
        if not Quotes or not consts:
            logger.error("mootdx库未安装，无法进行离线初始化")
            return
        
        try:
            client = Quotes.factory(market="std")
            logger.info("开始使用mootdx离线数据初始化股票信息缓存...")
            
            # 获取上交所股票列表
            logger.info("获取上交所股票列表...")
            sh_stocks = client.stocks(market=consts.MARKET_SH)
            if sh_stocks is not None and not sh_stocks.empty:
                for _, row in sh_stocks.iterrows():
                    code = str(row.get('code', '')).zfill(6)
                    name = str(row.get('name', f'股票{code}'))
                    
                    if code and code not in self.cache:
                        self.cache[code] = {
                            'name': name,
                            'industry': '未知行业',
                            'market': '上交所',
                            'last_updated': time.strftime('%Y-%m-%d')
                        }
                
                logger.info(f"已添加 {len(sh_stocks)} 只上交所股票信息")
            
            # 获取深交所股票列表
            logger.info("获取深交所股票列表...")
            sz_stocks = client.stocks(market=consts.MARKET_SZ)
            if sz_stocks is not None and not sz_stocks.empty:
                for _, row in sz_stocks.iterrows():
                    code = str(row.get('code', '')).zfill(6)
                    name = str(row.get('name', f'股票{code}'))
                    
                    if code and code not in self.cache:
                        self.cache[code] = {
                            'name': name,
                            'industry': '未知行业', 
                            'market': '深交所',
                            'last_updated': time.strftime('%Y-%m-%d')
                        }
                
                logger.info(f"已添加 {len(sz_stocks)} 只深交所股票信息")
            
            # 保存缓存
            self.save_cache()
            total_stocks = len(self.cache)
            logger.info(f"mootdx离线初始化完成，总计缓存 {total_stocks} 只股票信息")
            
        except Exception as e:
            logger.error(f"mootdx离线初始化失败: {e}")
    
    def is_cache_empty_or_old(self, days: int = 7) -> bool:
        """检查缓存是否为空或过期"""
        if not self.cache:
            return True
        
        # 检查最新更新时间
        import datetime
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        # 如果大部分数据都过期了，认为需要重新初始化
        old_count = 0
        for info in self.cache.values():
            if info.get('last_updated', '2000-01-01') < cutoff_str:
                old_count += 1
        
        return old_count > len(self.cache) * 0.8  # 80%以上过期


def update_stock_info_from_codes(codes: List[str], datasource: str = "akshare") -> None:
    """从股票代码列表更新缓存（供外部调用）"""
    cache = StockInfoCache(datasource=datasource)
    
    # 如果使用mootdx且缓存为空或过期，进行离线初始化
    if datasource.lower() == "mootdx" and cache.is_cache_empty_or_old():
        logger.info("检测到mootdx数据源且缓存过期，开始离线初始化...")
        cache.init_from_mootdx_offline()
    
    cache.batch_update(codes)


def get_stock_display_info(code: str, datasource: str = "akshare") -> Dict[str, str]:
    """获取用于显示的股票信息（供HTML生成使用）"""
    cache = StockInfoCache(datasource=datasource)
    info = cache.get_stock_info(code)
    return {
        'code': str(code).zfill(6),
        'name': info.get('name', f'股票{code}'),
        'industry': info.get('industry', '未知行业'),
        'market': info.get('market', '未知市场')
    }


if __name__ == "__main__":
    # 测试代码
    import sys
    logging.basicConfig(level=logging.INFO)
    
    # 支持命令行参数指定数据源和操作
    if len(sys.argv) > 1:
        if sys.argv[1] == "init_mootdx":
            # 测试mootdx离线初始化
            print("🧪 测试mootdx离线初始化功能...")
            cache = StockInfoCache(datasource="mootdx")
            cache.init_from_mootdx_offline()
            
            print(f"\n📊 初始化完成，缓存了 {len(cache.cache)} 只股票")
            
            # 显示一些样例
            print("\n🔍 样例数据（前10只）:")
            count = 0
            for code, info in cache.cache.items():
                if count >= 10:
                    break
                print(f"  {code}: {info['name']} ({info['market']})")
                count += 1
            sys.exit(0)
    
    # 常规测试
    datasource = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "init_mootdx" else "akshare"
    print(f"使用数据源: {datasource}")
    
    cache = StockInfoCache(datasource=datasource)
    
    # 测试获取一些股票信息
    test_codes = ['000001', '600000', '000002', '600519', '000858']
    
    print("测试获取股票信息:")
    for code in test_codes:
        info = cache.get_stock_info(code)
        print(f"{code}: {info['name']} - {info['industry']} ({info['market']})")
    
    print(f"\n当前缓存中有 {len(cache.cache)} 只股票")
    
    # 显示行业统计
    industry_stats = cache.get_industry_stats()
    print(f"\n行业分布（前5）:")
    for industry, count in list(industry_stats.items())[:5]:
        print(f"{industry}: {count} 只股票")