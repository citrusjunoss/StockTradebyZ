#!/usr/bin/env python3
"""
股票数据缓存管理器 - 管理股票基本信息、市值、PE等数据的缓存和定期更新
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any

import pandas as pd
import baostock as bs

logger = logging.getLogger(__name__)

class StockDataCacheManager:
    """股票数据缓存管理器 - 管理完整的股票基本信息"""
    
    def __init__(self, cache_file: str = "stock_info_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        # 缓存有效期 (天)
        self.cache_validity_days = 15  # 15天更新一次
        
        # 加载现有缓存
        self.load_cache()
    
    def load_cache(self) -> None:
        """从文件加载缓存"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.cache = cache_data.get('stocks', {})
                logger.info(f"已加载股票信息缓存，包含 {len(self.cache)} 只股票")
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")
            self.cache = {}
    
    def save_cache(self) -> None:
        """保存缓存到文件"""
        try:
            cache_data = {
                'last_update': datetime.now().isoformat(),
                'data_source': 'baostock',
                'total_count': len(self.cache),
                'stocks': self.cache
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存股票信息缓存，包含 {len(self.cache)} 只股票")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
    
    def is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        try:
            if not self.cache_file.exists():
                return False
                
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            if 'last_update' not in cache_data:
                return False
                
            last_update = datetime.fromisoformat(cache_data['last_update'])
            return (datetime.now() - last_update).days < self.cache_validity_days
        except Exception as e:
            logger.warning(f"检查缓存有效性失败: {e}")
            return False
    
    def update_stock_financial_data_only(self, code: str) -> Optional[Dict[str, Any]]:
        """15天周期增量更新：更新K线接口的所有数据(价格、成交量、PE等)，基本信息(名称、行业)仅在缺失时更新"""
        try:
            # 转换代码格式
            if code.startswith(('60', '68', '9')):
                bs_code = f"sh.{code.zfill(6)}"
            else:
                bs_code = f"sz.{code.zfill(6)}"
            
            # 获取缓存中的现有数据
            existing_data = self.cache.get(code, {})
            
            # 只有在基本信息缺失时才获取
            need_basic_info = not existing_data.get('name') or existing_data.get('industry') == '待更新'
            
            if need_basic_info:
                # 获取股票基本信息
                rs = bs.query_stock_basic(code=bs_code)
                if rs.error_code != '0':
                    logger.error(f"❌ 获取股票基本信息失败 {bs_code}: 错误代码={rs.error_code}, 错误信息={rs.error_msg}")
                    return None
                
                basic_data = []
                while (rs.error_code == '0') & rs.next():
                    basic_data.append(rs.get_row_data())
                
                if not basic_data:
                    logger.error(f"❌ 股票基本信息为空 {bs_code}: 查询返回空结果")
                    return None
                
                stock_info = dict(zip(rs.fields, basic_data[0]))
                
                # 获取行业信息
                industry_info = existing_data.get('industry', '未知行业')
                if industry_info in ['待更新', '未知行业', '']:
                    try:
                        rs_industry = bs.query_stock_industry(code=bs_code)
                        if rs_industry.error_code == '0':
                            industry_data = []
                            while (rs_industry.error_code == '0') & rs_industry.next():
                                industry_data.append(rs_industry.get_row_data())
                            
                            if industry_data:
                                industry_dict = dict(zip(rs_industry.fields, industry_data[0]))
                                industry_info = industry_dict.get('industry', '未知行业')
                            else:
                                logger.warning(f"⚠️  行业信息为空 {bs_code}: 查询返回空结果")
                        else:
                            logger.warning(f"⚠️  获取行业信息失败 {bs_code}: 错误代码={rs_industry.error_code}, 错误信息={rs_industry.error_msg}")
                    except Exception as e:
                        logger.warning(f"⚠️  获取行业信息异常 {bs_code}: {type(e).__name__}: {str(e)}")
            else:
                # 使用现有的基本信息
                stock_info = {
                    'code_name': existing_data.get('name', f'股票{code}'),
                    'ipoDate': existing_data.get('list_date', ''),
                    'outDate': ''
                }
                industry_info = existing_data.get('industry', '未知行业')
            
            # 总是获取最新的K线数据（价格、成交量、估值指标等，都来自同一个API接口）
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            rs_kdata = bs.query_history_k_data_plus(
                bs_code,
                "date,code,open,high,low,close,preclose,volume,amount,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"
            )
            
            kdata_info = {}
            if rs_kdata.error_code == '0':
                kdata_list = []
                while (rs_kdata.error_code == '0') & rs_kdata.next():
                    kdata_list.append(rs_kdata.get_row_data())
                
                if kdata_list:
                    kdata_info = dict(zip(rs_kdata.fields, kdata_list[-1]))  # 取最新数据
                else:
                    logger.warning(f"⚠️  K线数据为空 {bs_code}: 最近7天无交易数据")
            else:
                logger.warning(f"⚠️  获取K线数据失败 {bs_code}: 错误代码={rs_kdata.error_code}, 错误信息={rs_kdata.error_msg}")
            
            # 整合信息 - 保留现有信息，只更新财务数据
            result = {
                'code': code,
                'name': stock_info.get('code_name', existing_data.get('name', f'股票{code}')),
                'industry': industry_info,
                'market': existing_data.get('market', self._get_market_by_code(code)),
                'list_date': stock_info.get('ipoDate', existing_data.get('list_date', '')),
                'list_status': stock_info.get('outDate', '') == '' and '1' or '0',
                'last_updated': datetime.now().isoformat(),
                'detailed_info_updated': True,
                'last_detailed_update': datetime.now().isoformat()
            }
            
            # 更新同一API接口的所有数据（价格、成交、估值指标都来自K线数据接口）
            if kdata_info:
                result.update({
                    # 价格数据（同一接口）
                    'close_price': float(kdata_info.get('close', 0)) if kdata_info.get('close') else 0,
                    'open_price': float(kdata_info.get('open', 0)) if kdata_info.get('open') else 0,
                    'high_price': float(kdata_info.get('high', 0)) if kdata_info.get('high') else 0,
                    'low_price': float(kdata_info.get('low', 0)) if kdata_info.get('low') else 0,
                    # 成交数据（同一接口）
                    'volume': float(kdata_info.get('volume', 0)) if kdata_info.get('volume') else 0,
                    'amount': float(kdata_info.get('amount', 0)) if kdata_info.get('amount') else 0,
                    'pct_chg': float(kdata_info.get('pctChg', 0)) if kdata_info.get('pctChg') else 0,
                    # 估值指标（同一接口）
                    'pe_ttm': float(kdata_info.get('peTTM', 0)) if kdata_info.get('peTTM') else None,
                    'pb_mrq': float(kdata_info.get('pbMRQ', 0)) if kdata_info.get('pbMRQ') else None,
                    'ps_ttm': float(kdata_info.get('psTTM', 0)) if kdata_info.get('psTTM') else None,
                    'pcf_ttm': float(kdata_info.get('pcfNcfTTM', 0)) if kdata_info.get('pcfNcfTTM') else None,
                })
                
                # 估算市值（每次都更新）
                close_price = result.get('close_price', 0)
                if close_price > 0:
                    if code.startswith(('000', '001', '002')):
                        estimated_shares = 8e8
                    elif code.startswith(('300', '301')):
                        estimated_shares = 4e8
                    elif code.startswith(('600', '601', '603', '605')):
                        estimated_shares = 15e8
                    elif code.startswith('688'):
                        estimated_shares = 6e8
                    else:
                        estimated_shares = 10e8
                    
                    result['market_cap'] = close_price * estimated_shares
                else:
                    result['market_cap'] = None
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 增量更新股票{code}信息发生异常: {type(e).__name__}: {str(e)}")
            logger.debug(f"详细错误信息: {e}", exc_info=True)
            return None

    def get_stock_basic_info_from_baostock(self, code: str) -> Optional[Dict[str, Any]]:
        """从baostock获取单只股票的基本信息"""
        try:
            # 转换代码格式
            if code.startswith(('60', '68', '9')):
                bs_code = f"sh.{code.zfill(6)}"
            else:
                bs_code = f"sz.{code.zfill(6)}"
            
            # 获取股票基本信息
            rs = bs.query_stock_basic(code=bs_code)
            if rs.error_code != '0':
                logger.error(f"❌ 获取股票基本信息失败 {bs_code}: 错误代码={rs.error_code}, 错误信息={rs.error_msg}")
                return None
            
            basic_data = []
            while (rs.error_code == '0') & rs.next():
                basic_data.append(rs.get_row_data())
            
            if not basic_data:
                logger.error(f"❌ 股票基本信息为空 {bs_code}: 查询返回空结果")
                return None
            
            # 取第一条记录
            stock_info = dict(zip(rs.fields, basic_data[0]))
            
            # 获取行业信息
            industry_info = "未知行业"
            try:
                rs_industry = bs.query_stock_industry(code=bs_code)
                if rs_industry.error_code == '0':
                    industry_data = []
                    while (rs_industry.error_code == '0') & rs_industry.next():
                        industry_data.append(rs_industry.get_row_data())
                    
                    if industry_data:
                        industry_dict = dict(zip(rs_industry.fields, industry_data[0]))
                        industry_info = industry_dict.get('industry', '未知行业')
                    else:
                        logger.warning(f"⚠️  行业信息为空 {bs_code}: 查询返回空结果")
                else:
                    logger.warning(f"⚠️  获取行业信息失败 {bs_code}: 错误代码={rs_industry.error_code}, 错误信息={rs_industry.error_msg}")
            except Exception as e:
                logger.warning(f"⚠️  获取行业信息异常 {bs_code}: {type(e).__name__}: {str(e)}")
            
            # 获取最新交易数据(包含价格、市值等) - 尝试最近几天的数据
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            rs_kdata = bs.query_history_k_data_plus(
                bs_code,
                "date,code,open,high,low,close,preclose,volume,amount,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"
            )
            
            kdata_info = {}
            if rs_kdata.error_code == '0':
                kdata_list = []
                while (rs_kdata.error_code == '0') & rs_kdata.next():
                    kdata_list.append(rs_kdata.get_row_data())
                
                if kdata_list:
                    kdata_info = dict(zip(rs_kdata.fields, kdata_list[-1]))  # 取最新数据
                else:
                    logger.warning(f"⚠️  K线数据为空 {bs_code}: 最近7天无交易数据")
            else:
                logger.warning(f"⚠️  获取K线数据失败 {bs_code}: 错误代码={rs_kdata.error_code}, 错误信息={rs_kdata.error_msg}")
            
            # 整合信息
            result = {
                'code': code,
                'name': stock_info.get('code_name', f'股票{code}'),
                'industry': industry_info,
                'market': self._get_market_by_code(code),
                'list_date': stock_info.get('ipoDate', ''),
                'list_status': stock_info.get('outDate', '') == '' and '1' or '0',  # 是否正常上市
                'last_updated': datetime.now().isoformat()
            }
            
            # 添加价格和估值数据
            if kdata_info:
                result.update({
                    'close_price': float(kdata_info.get('close', 0)) if kdata_info.get('close') else 0,
                    'open_price': float(kdata_info.get('open', 0)) if kdata_info.get('open') else 0,
                    'high_price': float(kdata_info.get('high', 0)) if kdata_info.get('high') else 0,
                    'low_price': float(kdata_info.get('low', 0)) if kdata_info.get('low') else 0,
                    'volume': float(kdata_info.get('volume', 0)) if kdata_info.get('volume') else 0,
                    'amount': float(kdata_info.get('amount', 0)) if kdata_info.get('amount') else 0,
                    'pct_chg': float(kdata_info.get('pctChg', 0)) if kdata_info.get('pctChg') else 0,
                    'pe_ttm': float(kdata_info.get('peTTM', 0)) if kdata_info.get('peTTM') else None,
                    'pb_mrq': float(kdata_info.get('pbMRQ', 0)) if kdata_info.get('pbMRQ') else None,
                    'ps_ttm': float(kdata_info.get('psTTM', 0)) if kdata_info.get('psTTM') else None,
                    'pcf_ttm': float(kdata_info.get('pcfNcfTTM', 0)) if kdata_info.get('pcfNcfTTM') else None,
                })
                
                # 估算市值
                close_price = result.get('close_price', 0)
                if close_price > 0:
                    # 使用经验公式估算总股本
                    if code.startswith(('000', '001', '002')):
                        estimated_shares = 8e8  # 8亿股
                    elif code.startswith(('300', '301')):
                        estimated_shares = 4e8  # 4亿股
                    elif code.startswith(('600', '601', '603', '605')):
                        estimated_shares = 15e8  # 15亿股
                    elif code.startswith('688'):
                        estimated_shares = 6e8  # 6亿股
                    else:
                        estimated_shares = 10e8  # 默认10亿股
                    
                    result['market_cap'] = close_price * estimated_shares
                else:
                    result['market_cap'] = None
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 获取股票{code}信息发生异常: {type(e).__name__}: {str(e)}")
            logger.debug(f"详细错误信息: {e}", exc_info=True)
            return None
    
    def _get_market_by_code(self, code: str) -> str:
        """根据股票代码判断市场"""
        code = str(code).zfill(6)
        if code.startswith(('60', '68', '9')):
            return '上海'
        elif code.startswith(('00', '30')):
            return '深圳'
        elif code.startswith('8'):
            return '北交所'
        else:
            return '未知'
    
    def initialize_stock_list(self) -> bool:
        """初始化A股代码列表到缓存中（不包含详细信息）"""
        try:
            logger.info("开始初始化A股代码列表...")
            
            # 登录baostock系统
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(f"Baostock登录失败: {lg.error_msg}")
            
            # 获取股票列表
            rs = bs.query_stock_basic()
            if rs.error_code != '0':
                bs.logout()
                raise RuntimeError(f"获取股票列表失败: {rs.error_msg}")
            
            stock_list = []
            while (rs.error_code == '0') & rs.next():
                stock_list.append(rs.get_row_data())
            
            bs.logout()
            
            if not stock_list:
                raise RuntimeError("未获取到股票列表")
            
            # 过滤A股并初始化基本结构
            df_basic = pd.DataFrame(stock_list, columns=rs.fields)
            df_basic = df_basic[df_basic['code'].str.contains(r'^(sz|sh)\.(000|001|002|300|301|600|601|603|605|688)')]
            
            logger.info(f"找到{len(df_basic)}只A股，开始初始化代码列表")
            
            # 初始化所有股票的基本结构
            for _, row in df_basic.iterrows():
                try:
                    code_with_market = row['code']
                    code = code_with_market.split('.')[1]
                    
                    # 如果缓存中已有完整信息，跳过
                    if code in self.cache and 'close_price' in self.cache[code]:
                        continue
                    
                    # 初始化基本信息结构
                    self.cache[code] = {
                        'code': code,
                        'name': row.get('code_name', f'股票{code}'),
                        'industry': '待更新',
                        'market': self._get_market_by_code(code),
                        'list_date': row.get('ipoDate', ''),
                        'list_status': row.get('outDate', '') == '' and '1' or '0',
                        'last_updated': datetime.now().isoformat(),
                        'detailed_info_updated': False  # 标记是否已更新详细信息
                    }
                    
                except Exception as e:
                    logger.warning(f"初始化股票{row.get('code', 'unknown')}失败: {e}")
                    continue
            
            # 保存缓存
            self.save_cache()
            logger.info(f"A股代码列表初始化完成，共{len(self.cache)}只股票")
            return True
            
        except Exception as e:
            logger.error(f"初始化A股代码列表失败: {e}")
            return False
    
    def update_stock_cache_financial_only_with_retry(self, delay_seconds: int = 10, max_consecutive_failures: int = 3) -> bool:
        """增量渐进式更新股票财务数据，15天频率，支持智能退避重试"""
        # 退避时间序列：20s, 60s, 120s, 300s
        backoff_delays = [20, 60, 120, 300]
        consecutive_failures = 0
        
        # 统计信息
        stats = {
            'total_stocks': 0,
            'success_count': 0,
            'failure_count': 0,
            'skipped_count': 0,
            'start_time': datetime.now(),
            'end_time': None
        }
        
        try:
            # 检查所有股票
            all_codes = list(self.cache.keys())
            stats['total_stocks'] = len(all_codes)
            
            if not all_codes:
                logger.info("缓存为空，无股票需要更新")
                return True
            
            logger.info(f"开始15天周期财务数据更新，总股票数：{len(all_codes)}")
            
            # 登录baostock系统
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(f"❌ Baostock初始登录失败: 错误代码={lg.error_code}, 错误信息={lg.error_msg}")
            
            for i, code in enumerate(all_codes):
                try:
                    logger.info(f"正在更新股票 {code} ({i+1}/{len(all_codes)}) [成功:{stats['success_count']}, 失败:{consecutive_failures}]")
                    
                    # 使用增量更新方法
                    stock_info = self.update_stock_financial_data_only(code)
                    if stock_info:
                        self.cache[code] = stock_info
                        stats['success_count'] += 1
                        consecutive_failures = 0  # 重置失败计数
                        
                        logger.info(f"✅ 成功更新 {code}: {stock_info.get('name', '未知')} (PE:{stock_info.get('pe_ttm', 'N/A')}, 市值:{stock_info.get('market_cap', 0)/1e8:.1f}亿)")
                        
                        # 每100只股票保存一次缓存
                        if stats['success_count'] % 100 == 0:
                            self.save_cache()
                            logger.info(f"📊 进度更新 - 已成功更新{stats['success_count']}只股票，已保存缓存")
                    else:
                        consecutive_failures += 1
                        stats['failure_count'] += 1
                        logger.warning(f"❌ 获取股票{code}财务数据失败 (失败计数: {consecutive_failures}) - 可能原因: 网络问题、API限制或数据不存在")
                    
                    # 检查是否需要触发退避机制
                    if consecutive_failures >= max_consecutive_failures:
                        backoff_delay = backoff_delays[min(consecutive_failures - max_consecutive_failures, len(backoff_delays) - 1)]
                        logger.warning(f"🔄 连续失败{consecutive_failures}次，触发退避机制，暂停{backoff_delay}秒后继续...")
                        time.sleep(backoff_delay)
                        consecutive_failures = 0  # 重置计数，给系统一次机会
                        
                        # 重新登录，防止会话超时
                        try:
                            bs.logout()
                            lg = bs.login()
                            if lg.error_code != '0':
                                logger.error(f"❌ 重新登录失败: 错误代码={lg.error_code}, 错误信息={lg.error_msg}")
                                break
                            logger.info("🔄 重新登录成功，继续更新...")
                        except Exception as e:
                            logger.error(f"❌ 重新登录发生异常: {type(e).__name__}: {str(e)}")
                            break
                    else:
                        # 正常延迟等待
                        if i < len(all_codes) - 1:  # 最后一只股票不需要等待
                            logger.debug(f"等待{delay_seconds}秒后处理下一只股票...")
                            time.sleep(delay_seconds)
                        
                except Exception as e:
                    consecutive_failures += 1
                    stats['failure_count'] += 1
                    logger.error(f"❌ 更新股票{code}财务数据发生异常: {type(e).__name__}: {str(e)} (失败计数: {consecutive_failures})")
                    logger.debug(f"详细异常信息: {e}", exc_info=True)
                    continue
            
            bs.logout()
            
            # 最终保存缓存
            self.save_cache()
            stats['end_time'] = datetime.now()
            
            # 输出统计信息
            duration = stats['end_time'] - stats['start_time']
            success_rate = (stats['success_count'] / stats['total_stocks'] * 100) if stats['total_stocks'] > 0 else 0
            
            logger.info("=" * 60)
            logger.info("🎉 15天周期财务数据更新完成")
            logger.info(f"📊 执行统计:")
            logger.info(f"   总股票数: {stats['total_stocks']}")
            logger.info(f"   成功更新: {stats['success_count']} ({success_rate:.1f}%)")
            logger.info(f"   更新失败: {stats['failure_count']}")
            logger.info(f"   执行时长: {duration}")
            logger.info(f"   平均用时: {duration.total_seconds()/stats['total_stocks']:.2f}秒/股票")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            stats['end_time'] = datetime.now()
            duration = stats['end_time'] - stats['start_time']
            
            logger.error("=" * 60)
            logger.error(f"❌ 15天周期财务数据更新发生严重异常: {type(e).__name__}: {str(e)}")
            logger.error(f"📊 中断前统计:")
            logger.error(f"   已处理股票: {stats['success_count'] + stats['failure_count']}/{stats['total_stocks']}")
            logger.error(f"   成功更新: {stats['success_count']}")
            logger.error(f"   更新失败: {stats['failure_count']}")
            logger.error(f"   执行时长: {duration}")
            logger.error("=" * 60)
            logger.debug(f"详细异常信息: {e}", exc_info=True)
            
            try:
                bs.logout()
            except:
                pass
            return False

    def update_stock_cache_gradual_with_retry(self, delay_seconds: int = 10, max_consecutive_failures: int = 3) -> bool:
        """渐进式更新股票详细信息，支持智能退避重试机制"""
        # 退避时间序列：20s, 60s, 120s, 300s
        backoff_delays = [10, 15, 20, 30]
        consecutive_failures = 0
        
        try:
            # 找到需要更新详细信息的股票
            pending_codes = []
            for code, info in self.cache.items():
                if not info.get('detailed_info_updated', False):
                    pending_codes.append(code)
            
            if not pending_codes:
                logger.info("所有股票详细信息已更新完成")
                return True
            
            logger.info(f"开始渐进式更新，待更新股票数：{len(pending_codes)}")
            
            # 登录baostock系统
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(f"❌ Baostock初始登录失败: 错误代码={lg.error_code}, 错误信息={lg.error_msg}")
            
            updated_count = 0
            for i, code in enumerate(pending_codes):
                try:
                    logger.info(f"正在更新股票 {code} ({i+1}/{len(pending_codes)}) [连续失败: {consecutive_failures}]")
                    
                    # 获取详细信息
                    stock_info = self.get_stock_basic_info_from_baostock(code)
                    if stock_info:
                        # 保留原有的基本信息，更新详细信息
                        original_info = self.cache[code].copy()
                        stock_info.update({
                            'detailed_info_updated': True,
                            'last_detailed_update': datetime.now().isoformat()
                        })
                        self.cache[code] = stock_info
                        updated_count += 1
                        consecutive_failures = 0  # 重置失败计数
                        
                        logger.info(f"✅ 成功更新 {code}: {stock_info.get('name', '未知')}")
                        
                        # 每10只股票保存一次缓存
                        if updated_count % 10 == 0:
                            self.save_cache()
                            logger.info(f"已更新{updated_count}只股票信息，已保存缓存")
                    else:
                        consecutive_failures += 1
                        logger.warning(f"❌ 获取股票{code}详细信息失败 (失败计数: {consecutive_failures}) - 可能原因: 网络问题、API限制或数据不存在")
                    
                    # 检查是否需要触发退避机制
                    if consecutive_failures >= max_consecutive_failures:
                        backoff_delay = backoff_delays[min(consecutive_failures - max_consecutive_failures, len(backoff_delays) - 1)]
                        logger.warning(f"🔄 连续失败{consecutive_failures}次，触发退避机制，暂停{backoff_delay}秒后继续...")
                        time.sleep(backoff_delay)
                        consecutive_failures = 0  # 重置计数，给系统一次机会
                        
                        # 重新登录，防止会话超时
                        try:
                            bs.logout()
                            lg = bs.login()
                            if lg.error_code != '0':
                                logger.error(f"❌ 重新登录失败: 错误代码={lg.error_code}, 错误信息={lg.error_msg}")
                                break
                            logger.info("🔄 重新登录成功，继续更新...")
                        except Exception as e:
                            logger.error(f"❌ 重新登录发生异常: {type(e).__name__}: {str(e)}")
                            break
                    else:
                        # 正常延迟等待
                        if i < len(pending_codes) - 1:  # 最后一只股票不需要等待
                            logger.debug(f"等待{delay_seconds}秒后处理下一只股票...")
                            time.sleep(delay_seconds)
                        
                except Exception as e:
                    consecutive_failures += 1
                    logger.error(f"❌ 更新股票{code}详细信息发生异常: {type(e).__name__}: {str(e)} (失败计数: {consecutive_failures})")
                    logger.debug(f"详细异常信息: {e}", exc_info=True)
                    continue
            
            bs.logout()
            
            # 最终保存缓存
            self.save_cache()
            logger.info(f"🎉 渐进式更新完成，成功更新{updated_count}只股票的详细信息")
            return True
            
        except Exception as e:
            logger.error(f"❌ 智能重试渐进式更新发生严重异常: {type(e).__name__}: {str(e)}")
            logger.debug(f"详细异常信息: {e}", exc_info=True)
            try:
                bs.logout()
            except:
                pass
            return False

    def update_stock_cache_gradual(self, delay_seconds: int = 1) -> bool:
        """渐进式更新股票详细信息，每次更新一只股票"""
        try:
            # 找到需要更新详细信息的股票
            pending_codes = []
            for code, info in self.cache.items():
                if not info.get('detailed_info_updated', False):
                    pending_codes.append(code)
            
            if not pending_codes:
                logger.info("所有股票详细信息已更新完成")
                return True
            
            logger.info(f"开始渐进式更新，待更新股票数：{len(pending_codes)}")
            
            # 登录baostock系统
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(f"Baostock登录失败: {lg.error_msg}")
            
            updated_count = 0
            for i, code in enumerate(pending_codes):
                try:
                    logger.info(f"正在更新股票 {code} ({i+1}/{len(pending_codes)})")
                    
                    # 获取详细信息
                    stock_info = self.get_stock_basic_info_from_baostock(code)
                    if stock_info:
                        # 保留原有的基本信息，更新详细信息
                        original_info = self.cache[code].copy()
                        stock_info.update({
                            'detailed_info_updated': True,
                            'last_detailed_update': datetime.now().isoformat()
                        })
                        self.cache[code] = stock_info
                        updated_count += 1
                        
                        # 每10只股票保存一次缓存
                        if updated_count % 10 == 0:
                            self.save_cache()
                            logger.info(f"已更新{updated_count}只股票信息，已保存缓存")
                    else:
                        logger.warning(f"获取股票{code}详细信息失败")
                    
                    # 延迟等待
                    if i < len(pending_codes) - 1:  # 最后一只股票不需要等待
                        logger.debug(f"等待{delay_seconds}秒后处理下一只股票...")
                        time.sleep(delay_seconds)
                        
                except Exception as e:
                    logger.error(f"更新股票{code}详细信息失败: {e}")
                    continue
            
            bs.logout()
            
            # 最终保存缓存
            self.save_cache()
            logger.info(f"渐进式更新完成，成功更新{updated_count}只股票的详细信息")
            return True
            
        except Exception as e:
            logger.error(f"渐进式更新失败: {e}")
            try:
                bs.logout()
            except:
                pass
            return False
    
    def update_stock_cache(self, force_update: bool = False, max_stocks: int = 500, gradual: bool = False, delay_seconds: int = 10, use_retry: bool = False, max_consecutive_failures: int = 3) -> bool:
        """更新股票基本信息缓存"""
        if not force_update and self.is_cache_valid():
            logger.info("股票信息缓存仍然有效，跳过更新")
            return True
        
        # 如果启用渐进更新模式
        if gradual:
            # 首先确保已初始化股票代码列表
            if not self.cache:
                logger.info("缓存为空，先初始化A股代码列表")
                if not self.initialize_stock_list():
                    return False
            
            # 然后进行渐进式详细信息更新
            if use_retry:
                return self.update_stock_cache_gradual_with_retry(delay_seconds, max_consecutive_failures)
            else:
                return self.update_stock_cache_gradual(delay_seconds)
        
        try:
            logger.info("开始更新股票信息缓存...")
            
            # 登录baostock系统
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(f"Baostock登录失败: {lg.error_msg}")
            
            # 获取股票列表
            rs = bs.query_stock_basic()
            if rs.error_code != '0':
                bs.logout()
                raise RuntimeError(f"获取股票列表失败: {rs.error_msg}")
            
            stock_list = []
            while (rs.error_code == '0') & rs.next():
                stock_list.append(rs.get_row_data())
            
            if not stock_list:
                bs.logout()
                raise RuntimeError("未获取到股票列表")
            
            # 过滤A股并处理
            updated_count = 0
            df_basic = pd.DataFrame(stock_list, columns=rs.fields)
            df_basic = df_basic[df_basic['code'].str.contains(r'^(sz|sh)\.(000|001|002|300|301|600|601|603|605|688)')]
            
            # 限制处理数量
            df_basic = df_basic.head(max_stocks)
            logger.info(f"准备更新{len(df_basic)}只股票的基本信息")
            
            for idx, row in df_basic.iterrows():
                try:
                    code_with_market = row['code']
                    code = code_with_market.split('.')[1]
                    
                    # 获取详细信息
                    stock_info = self.get_stock_basic_info_from_baostock(code)
                    if stock_info:
                        self.cache[code] = stock_info
                        updated_count += 1
                        
                        if updated_count % 50 == 0:
                            logger.info(f"已更新{updated_count}只股票信息")
                            # 中间保存，避免数据丢失
                            self.save_cache()
                    
                    # 添加延时避免频繁请求
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.debug(f"更新股票{row['code']}失败: {e}")
                    continue
            
            # 登出系统
            bs.logout()
            
            # 保存缓存
            self.save_cache()
            
            logger.info(f"股票信息缓存更新完成，成功更新{updated_count}只股票")
            return True
            
        except Exception as e:
            # 确保登出
            try:
                bs.logout()
            except:
                pass
            logger.error(f"更新股票信息缓存失败: {e}")
            return False
    
    def get_stock_info(self, code: str) -> Optional[Dict[str, Any]]:
        """获取单只股票信息（优先从缓存）"""
        code = str(code).zfill(6)
        
        # 先从缓存获取
        if code in self.cache:
            return self.cache[code]
        
        # 缓存中没有，尝试从baostock获取
        try:
            lg = bs.login()
            if lg.error_code == '0':
                stock_info = self.get_stock_basic_info_from_baostock(code)
                bs.logout()
                
                if stock_info:
                    self.cache[code] = stock_info
                    return stock_info
        except Exception as e:
            logger.debug(f"从baostock获取股票{code}信息失败: {e}")
            try:
                bs.logout()
            except:
                pass
        
        return None
    
    def get_stocks_by_market_cap(self, min_cap: float = None, max_cap: float = None) -> List[Dict[str, Any]]:
        """根据市值筛选股票"""
        result = []
        
        for code, info in self.cache.items():
            market_cap = info.get('market_cap')
            if market_cap is None:
                continue
                
            # 应用市值筛选
            if min_cap is not None and market_cap < min_cap:
                continue
            if max_cap is not None and market_cap > max_cap:
                continue
                
            result.append(info)
        
        # 按市值排序
        result.sort(key=lambda x: x.get('market_cap', 0), reverse=True)
        return result
    
    def get_cache_status(self) -> Dict:
        """获取缓存状态信息"""
        try:
            if not self.cache_file.exists():
                return {
                    'last_update': None,
                    'age_days': None,
                    'is_valid': False,
                    'data_source': None,
                    'total_count': 0
                }
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            last_update_str = cache_data.get('last_update')
            if last_update_str:
                last_update = datetime.fromisoformat(last_update_str)
                age_days = (datetime.now() - last_update).days
            else:
                last_update_str = None
                age_days = None
            
            return {
                'last_update': last_update_str,
                'age_days': age_days,
                'is_valid': age_days < self.cache_validity_days if age_days is not None else False,
                'data_source': cache_data.get('data_source', 'unknown'),
                'total_count': cache_data.get('total_count', len(self.cache))
            }
            
        except Exception as e:
            logger.error(f"获取缓存状态失败: {e}")
            return {
                'last_update': None,
                'age_days': None,
                'is_valid': False,
                'data_source': None,
                'total_count': 0
            }
    
    def check_and_update_if_needed(self) -> bool:
        """检查并在需要时更新"""
        if not self.is_cache_valid():
            logger.info("检测到缓存过期，开始更新...")
            return self.update_stock_cache(force_update=True)
        else:
            logger.info("缓存仍然有效，无需更新")
            return True


def main():
    """主函数 - 命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description="股票数据缓存管理工具")
    parser.add_argument("--update", action="store_true", help="强制更新股票信息缓存")
    parser.add_argument("--status", action="store_true", help="显示缓存状态")
    parser.add_argument("--check-update", action="store_true", help="检查并在需要时更新缓存")
    parser.add_argument("--cache-file", default="stock_info_cache.json", help="缓存文件路径")
    parser.add_argument("--max-stocks", type=int, default=500, help="最大更新股票数量")
    parser.add_argument("--query-stock", type=str, help="查询指定股票信息")
    parser.add_argument("--filter-mktcap", nargs=2, type=float, metavar=('MIN', 'MAX'), 
                        help="按市值筛选股票 (最小值 最大值)")
    parser.add_argument("--init", action="store_true", help="初始化A股代码列表")
    parser.add_argument("--gradual", action="store_true", help="渐进式更新股票详细信息")
    parser.add_argument("--gradual-retry", action="store_true", help="渐进式更新股票详细信息(支持智能重试)")
    parser.add_argument("--financial-update", action="store_true", help="15天周期K线数据更新(更新价格、成交量、PE等同一接口数据，基本信息仅在缺失时更新)")
    parser.add_argument("--delay", type=int, default=10, help="渐进更新时每只股票间的延迟秒数 (默认10秒)")
    parser.add_argument("--max-failures", type=int, default=3, help="触发退避重试的最大连续失败次数 (默认3次)")
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    manager = StockDataCacheManager(cache_file=args.cache_file)
    
    if args.status:
        status = manager.get_cache_status()
        print("\n=== 股票信息缓存状态 ===")
        if status['last_update']:
            print(f"最后更新: {status['last_update']}")
            print(f"数据源: {status['data_source']}")
            print(f"股票总数: {status['total_count']}")
            print(f"缓存年龄: {status['age_days']}天")
            print(f"是否有效: {'是' if status['is_valid'] else '否'}")
        else:
            print("无缓存数据")
    
    elif args.init:
        print("开始初始化A股代码列表...")
        success = manager.initialize_stock_list()
        print("初始化完成" if success else "初始化失败")
    
    elif args.gradual:
        print(f"开始渐进式更新股票详细信息（延迟{args.delay}秒）...")
        success = manager.update_stock_cache_gradual(delay_seconds=args.delay)
        print("渐进式更新完成" if success else "渐进式更新失败")
    
    elif args.gradual_retry:
        print(f"开始智能重试渐进式更新股票详细信息（延迟{args.delay}秒，最大连续失败{args.max_failures}次）...")
        success = manager.update_stock_cache_gradual_with_retry(
            delay_seconds=args.delay, 
            max_consecutive_failures=args.max_failures
        )
        print("智能重试渐进式更新完成" if success else "智能重试渐进式更新失败")
    
    elif args.financial_update:
        print(f"开始15天周期财务数据更新（延迟{args.delay}秒，最大连续失败{args.max_failures}次）...")
        success = manager.update_stock_cache_financial_only_with_retry(
            delay_seconds=args.delay, 
            max_consecutive_failures=args.max_failures
        )
        print("15天周期财务数据更新完成" if success else "15天周期财务数据更新失败")
    
    elif args.update:
        if args.gradual or args.gradual_retry:
            retry_text = "（支持智能重试）" if args.gradual_retry else ""
            print(f"开始渐进式强制更新股票信息缓存（延迟{args.delay}秒）{retry_text}...")
            success = manager.update_stock_cache(
                force_update=True, 
                max_stocks=args.max_stocks, 
                gradual=True, 
                delay_seconds=args.delay,
                use_retry=args.gradual_retry,
                max_consecutive_failures=args.max_failures
            )
        else:
            print("开始强制更新股票信息缓存...")
            success = manager.update_stock_cache(force_update=True, max_stocks=args.max_stocks)
        print("更新完成" if success else "更新失败")
    
    elif args.check_update:
        print("检查缓存状态并在需要时更新...")
        success = manager.check_and_update_if_needed()
        print("检查更新完成" if success else "检查更新失败")
    
    elif args.query_stock:
        print(f"查询股票 {args.query_stock} 的信息...")
        stock_info = manager.get_stock_info(args.query_stock)
        if stock_info:
            print(f"股票代码: {stock_info.get('code', 'N/A')}")
            print(f"股票名称: {stock_info.get('name', 'N/A')}")
            print(f"所属市场: {stock_info.get('market', 'N/A')}")
            print(f"所属行业: {stock_info.get('industry', 'N/A')}")
            print(f"最新价格: {stock_info.get('close_price', 'N/A')}")
            print(f"市值: {stock_info.get('market_cap', 'N/A')}")
            print(f"市盈率: {stock_info.get('pe_ttm', 'N/A')}")
            print(f"市净率: {stock_info.get('pb_mrq', 'N/A')}")
        else:
            print("未找到股票信息")
    
    elif args.filter_mktcap:
        min_cap, max_cap = args.filter_mktcap
        print(f"筛选市值在 {min_cap:.0f} - {max_cap:.0f} 之间的股票...")
        stocks = manager.get_stocks_by_market_cap(min_cap, max_cap)
        print(f"找到 {len(stocks)} 只符合条件的股票:")
        for i, stock in enumerate(stocks[:20], 1):  # 显示前20只
            print(f"{i:2d}. {stock['code']} {stock['name']} "
                  f"市值: {stock.get('market_cap', 0):.0f} "
                  f"PE: {stock.get('pe_ttm', 'N/A')}")
        if len(stocks) > 20:
            print(f"... 还有 {len(stocks) - 20} 只股票未显示")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()