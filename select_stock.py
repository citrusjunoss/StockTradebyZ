from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd
from result_cache import ResultCache

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
    p.add_argument("--cache-dir", default="./cache", help="结果缓存目录")
    p.add_argument("--no-cache", action="store_true", help="不使用缓存")
    args = p.parse_args()
    
    # 初始化缓存
    cache = None if args.no_cache else ResultCache(args.cache_dir)

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

    # 记录执行开始时间
    execution_start_time = time.time()
    date_str = trade_date.strftime('%Y-%m-%d')
    successful_selectors = 0
    total_selected_stocks = 0

    # --- 逐个 Selector 运行 ---
    for cfg in selector_cfgs:
        if cfg.get("activate", True) is False:
            continue
        
        try:
            alias, selector = instantiate_selector(cfg)
        except Exception as e:
            logger.error("跳过配置 %s：%s", cfg, e)
            continue

        # 记录单个选择器执行时间
        selector_start_time = time.time()
        
        try:
            picks = selector.select(trade_date, data)
            selector_execution_time = time.time() - selector_start_time
            
            successful_selectors += 1
            total_selected_stocks += len(picks)

            # 将结果写入日志，同时输出到控制台
            logger.info("")
            logger.info("============== 选股结果 [%s] ==============", alias)
            logger.info("交易日: %s", trade_date.date())
            logger.info("符合条件股票数: %d", len(picks))
            logger.info("执行时间: %.3f秒", selector_execution_time)
            logger.info("%s", ", ".join(picks) if picks else "无符合条件股票")
            
            # 保存结果到缓存
            if cache:
                try:
                    cache.save_result(
                        date=date_str,
                        selector_name=alias,
                        stocks=picks,
                        execution_time=selector_execution_time,
                        selector_config=cfg.get('params', {})
                    )
                except Exception as cache_error:
                    logger.warning("缓存结果失败: %s", cache_error)
                    
        except Exception as e:
            selector_execution_time = time.time() - selector_start_time
            logger.error("选择器 [%s] 执行失败，耗时 %.3f秒：%s", alias, selector_execution_time, e)
    
    # 记录总体执行日志
    total_execution_time = time.time() - execution_start_time
    logger.info("")
    logger.info("=============== 执行完成 ===============")
    logger.info("执行日期: %s", date_str)
    logger.info("成功执行选择器: %d", successful_selectors)
    logger.info("选中股票总数: %d", total_selected_stocks)
    logger.info("总执行时间: %.3f秒", total_execution_time)
    
    # 保存执行日志到缓存
    if cache:
        try:
            cache.save_execution_log(
                date=date_str,
                total_selectors=successful_selectors,
                total_stocks=total_selected_stocks,
                execution_time=total_execution_time,
                status='success'
            )
        except Exception as cache_error:
            logger.warning("缓存执行日志失败: %s", cache_error)


if __name__ == "__main__":
    main()
