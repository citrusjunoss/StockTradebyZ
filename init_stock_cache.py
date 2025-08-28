#!/usr/bin/env python3
"""
股票信息缓存初始化脚本
支持使用mootdx离线数据进行批量初始化
"""

import argparse
import logging
from stock_info_cache import StockInfoCache

def main():
    parser = argparse.ArgumentParser(description="初始化股票信息缓存")
    parser.add_argument("--datasource", choices=["mootdx"], default="mootdx", 
                       help="数据源 (目前只支持mootdx离线初始化)")
    parser.add_argument("--force", action="store_true", 
                       help="强制重新初始化（清空现有缓存）")
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="显示详细日志")
    
    args = parser.parse_args()
    
    # 设置日志级别
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    print(f"🚀 开始使用 {args.datasource} 初始化股票信息缓存...")
    
    # 创建缓存实例
    cache = StockInfoCache(datasource=args.datasource)
    
    # 检查是否需要初始化
    if not args.force and not cache.is_cache_empty_or_old():
        print("✅ 缓存数据较新，无需重新初始化")
        print(f"📊 当前缓存: {len(cache.cache)} 只股票")
        return
    
    if args.force:
        print("🗑️ 强制模式：清空现有缓存...")
        cache.cache.clear()
    
    # 执行初始化
    if args.datasource == "mootdx":
        print("📡 使用mootdx离线数据初始化...")
        cache.init_from_mootdx_offline()
    
    # 显示结果
    total_count = len(cache.cache)
    if total_count > 0:
        print(f"✅ 初始化完成！")
        print(f"📊 总计缓存 {total_count} 只股票信息")
        
        # 显示市场分布
        markets = {}
        for info in cache.cache.values():
            market = info.get('market', '未知市场')
            markets[market] = markets.get(market, 0) + 1
        
        print("\n📈 市场分布:")
        for market, count in sorted(markets.items()):
            print(f"  {market}: {count} 只")
        
        # 显示部分样例
        print(f"\n🔍 样例数据（前10只）:")
        count = 0
        for code, info in cache.cache.items():
            if count >= 10:
                break
            print(f"  {code}: {info['name']} ({info['market']})")
            count += 1
        
    else:
        print("❌ 初始化失败，未获取到任何股票信息")

if __name__ == "__main__":
    main()