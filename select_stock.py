from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd

# ---------- 日志 ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        # 将日志写入文件
        logging.FileHandler("select_results.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("select")


# ---------- 工具 ----------

def save_picks_to_cache(picks: List[str], alias: str, trade_date: pd.Timestamp, data: Dict[str, pd.DataFrame]) -> None:
    """保存选股结果到cache目录"""
    try:
        cache_dir = Path("cache")
        cache_dir.mkdir(exist_ok=True)
        
        # 创建结构化的选股结果
        result_data = {
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "generated_time": datetime.now().isoformat(),
            "selector_alias": alias,
            "total_stocks": len(picks),
            "selected_stocks": picks,
            "stock_details": {}
        }
        
        # 从股票信息缓存获取详细信息
        try:
            from data_cache_manager import StockDataCacheManager
            stock_cache = StockDataCacheManager()
            
            for code in picks:
                stock_info = stock_cache.get_stock_info(code)
                if stock_info:
                    result_data["stock_details"][code] = {
                        "name": stock_info.get("name", "未知"),
                        "industry": stock_info.get("industry", "未知"),
                        "market": stock_info.get("market", "未知"),
                        "close_price": stock_info.get("close_price"),
                        "market_cap": stock_info.get("market_cap"),
                        "pe_ttm": stock_info.get("pe_ttm"),
                        "pb_mrq": stock_info.get("pb_mrq")
                    }
                
                # 添加K线数据的最新价格（如果可用）
                if code in data:
                    latest_data = data[code].iloc[-1]
                    if code not in result_data["stock_details"]:
                        result_data["stock_details"][code] = {}
                    
                    result_data["stock_details"][code].update({
                        "latest_close": float(latest_data.get("close", 0)),
                        "latest_volume": float(latest_data.get("volume", 0)),
                        "latest_date": latest_data.get("date").strftime("%Y-%m-%d") if pd.notna(latest_data.get("date")) else None
                    })
        
        except Exception as e:
            logger.warning(f"获取股票详细信息失败: {e}")
        
        # 保存到cache目录
        date_str = trade_date.strftime("%Y%m%d")
        cache_file = cache_dir / f"picks_{alias}_{date_str}.json"
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"选股结果已缓存到: {cache_file}")
        
        # 同时更新最新结果的链接文件
        latest_cache_file = cache_dir / f"picks_{alias}_latest.json"
        with open(latest_cache_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"最新选股结果已更新: {latest_cache_file}")
        
    except Exception as e:
        logger.error(f"保存选股结果到缓存失败: {e}")


def load_data(data_dir: Path, codes: Iterable[str]) -> Dict[str, pd.DataFrame]:
    frames: Dict[str, pd.DataFrame] = {}
    for code in codes:
        fp = data_dir / f"{code}.csv"
        if not fp.exists():
            logger.warning("%s 不存在，跳过", fp.name)
            continue
        df = pd.read_csv(fp, parse_dates=["date"]).sort_values("date")
        frames[code] = df
    return frames


def load_config(cfg_path: Path) -> List[Dict[str, Any]]:
    if not cfg_path.exists():
        logger.error("配置文件 %s 不存在", cfg_path)
        sys.exit(1)
    with cfg_path.open(encoding="utf-8") as f:
        cfg_raw = json.load(f)

    # 兼容三种结构：单对象、对象数组、或带 selectors 键
    if isinstance(cfg_raw, list):
        cfgs = cfg_raw
    elif isinstance(cfg_raw, dict) and "selectors" in cfg_raw:
        cfgs = cfg_raw["selectors"]
    else:
        cfgs = [cfg_raw]

    if not cfgs:
        logger.error("configs.json 未定义任何 Selector")
        sys.exit(1)

    return cfgs


def instantiate_selector(cfg: Dict[str, Any]):
    """动态加载 Selector 类并实例化"""
    cls_name: str = cfg.get("class")
    if not cls_name:
        raise ValueError("缺少 class 字段")

    try:
        module = importlib.import_module("Selector")
        cls = getattr(module, cls_name)
    except (ModuleNotFoundError, AttributeError) as e:
        raise ImportError(f"无法加载 Selector.{cls_name}: {e}") from e

    params = cfg.get("params", {})
    return cfg.get("alias", cls_name), cls(**params)


# ---------- 主函数 ----------

def main():
    p = argparse.ArgumentParser(description="Run selectors defined in configs.json")
    p.add_argument("--data-dir", default="./data", help="CSV 行情目录")
    p.add_argument("--config", default="./configs.json", help="Selector 配置文件")
    p.add_argument("--date", help="交易日 YYYY-MM-DD；缺省=数据最新日期")
    p.add_argument("--tickers", default="all", help="'all' 或逗号分隔股票代码列表")
    args = p.parse_args()

    # --- 加载行情 ---
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error("数据目录 %s 不存在", data_dir)
        sys.exit(1)

    codes = (
        [f.stem for f in data_dir.glob("*.csv")]
        if args.tickers.lower() == "all"
        else [c.strip() for c in args.tickers.split(",") if c.strip()]
    )
    if not codes:
        logger.error("股票池为空！")
        sys.exit(1)

    data = load_data(data_dir, codes)
    if not data:
        logger.error("未能加载任何行情数据")
        sys.exit(1)

    trade_date = (
        pd.to_datetime(args.date)
        if args.date
        else max(df["date"].max() for df in data.values())
    )
    if not args.date:
        logger.info("未指定 --date，使用最近日期 %s", trade_date.date())

    # --- 加载 Selector 配置 ---
    selector_cfgs = load_config(Path(args.config))

    # --- 逐个 Selector 运行 ---
    for cfg in selector_cfgs:
        if cfg.get("activate", True) is False:
            continue
        try:
            alias, selector = instantiate_selector(cfg)
        except Exception as e:
            logger.error("跳过配置 %s：%s", cfg, e)
            continue

        picks = selector.select(trade_date, data)
        #
        # 将结果写入日志，同时输出到控制台
        logger.info("")
        logger.info("============== 选股结果 [%s] ==============", alias)
        logger.info("交易日: %s", trade_date.date())
        logger.info("符合条件股票数: %d", len(picks))
        logger.info("%s", ", ".join(picks) if picks else "无符合条件股票")
        
        # 保存选股结果到缓存
        save_picks_to_cache(picks, alias, trade_date, data)


if __name__ == "__main__":
    main()
