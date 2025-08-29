from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import random
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

import akshare as ak
import baostock as bs
import pandas as pd
import tushare as ts
from mootdx.quotes import Quotes
from tqdm import tqdm
from stock_info_cache import update_stock_info_from_codes
from get_datasource import set_current_datasource

warnings.filterwarnings("ignore")

# 股票信息缓存管理器实例
_stock_cache_manager = None

def get_stock_cache_manager():
    """获取股票信息缓存管理器实例"""
    global _stock_cache_manager
    if _stock_cache_manager is None:
        from data_cache_manager import StockDataCacheManager
        _stock_cache_manager = StockDataCacheManager()
    return _stock_cache_manager

# --------------------------- 全局日志配置 --------------------------- #
LOG_FILE = Path("fetch.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("fetch_mktcap")

# 屏蔽第三方库多余 INFO 日志
for noisy in ("httpx", "urllib3", "_client", "akshare"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# --------------------------- 市值快照 --------------------------- #
# 注：市值数据现在通过 data_cache_manager.py 中的股票信息缓存系统统一管理

# --------------------------- 股票池筛选 --------------------------- #

def get_constituents(
    min_cap: float,
    max_cap: float,
    small_player: bool,
) -> List[str]:
    """根据市值筛选股票池"""
    
    try:
        # 使用新的股票信息缓存系统
        stock_cache = get_stock_cache_manager()
        stocks = stock_cache.get_stocks_by_market_cap(min_cap, max_cap)
        
        codes = []
        for stock in stocks:
            code = stock['code']
            # 如果需要排除小盘股
            if small_player and code.startswith(("300", "301", "688", "8", "4")):
                continue
            codes.append(code)
        
        logger.info(f"从缓存筛选得到 {len(codes)} 只股票")
        
    except Exception as e:
        logger.error(f"使用缓存筛选失败: {e}")
        logger.error("请先运行 'python data_cache_manager.py --update' 更新股票信息缓存")
        codes = []  # 返回空列表而不是使用旧的回退方法

    # 附加股票池 appendix.json
    try:
        with open("appendix.json", "r", encoding="utf-8") as f:
            appendix_codes = json.load(f)["data"]
    except FileNotFoundError:
        appendix_codes = []
    
    # 合并并去重
    all_codes = list(dict.fromkeys(appendix_codes + codes))
    
    logger.info("最终筛选得到 %d 只股票", len(all_codes))
    return all_codes

# --------------------------- 历史 K 线抓取 --------------------------- #
COLUMN_MAP_HIST_AK = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "换手率": "turnover",
}

_FREQ_MAP = {
    0: "5m",
    1: "15m",
    2: "30m",
    3: "1h",
    4: "day",
    5: "week",
    6: "mon",
    7: "1m",
    8: "1m",
    9: "day",
    10: "3mon",
    11: "year",
}

# ---------- Tushare 工具函数 ---------- #

def _to_ts_code(code: str) -> str:
    return f"{code.zfill(6)}.SH" if code.startswith(("60", "68", "9")) else f"{code.zfill(6)}.SZ"


def _get_kline_tushare(code: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    ts_code = _to_ts_code(code)
    adj_flag = None if adjust == "" else adjust
    for attempt in range(1, 4):
        try:
            df = ts.pro_bar(
                ts_code=ts_code,
                adj=adj_flag,
                start_date=start,
                end_date=end,
                freq="D",
            )
            break
        except Exception as e:
            logger.warning("Tushare 拉取 %s 失败(%d/3): %s", code, attempt, e)
            time.sleep(random.uniform(1, 2) * attempt)
    else:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(columns={"trade_date": "date", "vol": "volume"})[
        ["date", "open", "close", "high", "low", "volume"]
    ].copy()
    df["date"] = pd.to_datetime(df["date"])
    df[[c for c in df.columns if c != "date"]] = df[[c for c in df.columns if c != "date"]].apply(
        pd.to_numeric, errors="coerce"
    )    
    return df.sort_values("date").reset_index(drop=True)

# ---------- AKShare 工具函数 ---------- #

def _get_kline_akshare(code: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    for attempt in range(1, 4):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start,
                end_date=end,
                adjust=adjust,
            )
            break
        except Exception as e:
            logger.warning("AKShare 拉取 %s 失败(%d/3): %s", code, attempt, e)
            time.sleep(random.uniform(1, 2) * attempt)
    else:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    df = (
        df[list(COLUMN_MAP_HIST_AK)]
        .rename(columns=COLUMN_MAP_HIST_AK)
        .assign(date=lambda x: pd.to_datetime(x["date"]))
    )
    df[[c for c in df.columns if c != "date"]] = df[[c for c in df.columns if c != "date"]].apply(
        pd.to_numeric, errors="coerce"
    )
    df = df[["date", "open", "close", "high", "low", "volume"]]
    return df.sort_values("date").reset_index(drop=True)

# ---------- Mootdx 工具函数 ---------- #

def _get_kline_mootdx_online(code: str, start: str, end: str, adjust: str, freq_code: int) -> pd.DataFrame:
    """Mootdx在线模式获取K线数据"""
    symbol = code.zfill(6)
    freq = _FREQ_MAP.get(freq_code, "day")
    client = Quotes.factory(market="std")
    try:
        df = client.bars(symbol=symbol, frequency=freq, adjust=adjust or None)
    except Exception as e:
        logger.warning("Mootdx 在线拉取 %s 失败: %s", code, e)
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    
    df = df.rename(
        columns={"datetime": "date", "open": "open", "high": "high", "low": "low", "close": "close", "vol": "volume"}
    )
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    start_ts = pd.to_datetime(start, format="%Y%m%d")
    end_ts = pd.to_datetime(end, format="%Y%m%d")
    df = df[(df["date"].dt.date >= start_ts.date()) & (df["date"].dt.date <= end_ts.date())].copy()    
    df = df.sort_values("date").reset_index(drop=True)    
    return df[["date", "open", "close", "high", "low", "volume"]]

def _get_kline_mootdx_offline(code: str, start: str, end: str, adjust: str, freq_code: int, tdx_dir: str = None) -> pd.DataFrame:
    """Mootdx离线模式获取K线数据"""
    try:
        from mootdx.reader import Reader
    except ImportError:
        try:
            from mootdx import Reader
        except ImportError:
            logger.error("Mootdx Reader 模块导入失败，请确保安装了完整的 mootdx 包")
            return pd.DataFrame()
    
    symbol = code.zfill(6)
    freq = _FREQ_MAP.get(freq_code, "day")
    
    # 检测默认的TDX数据目录
    if not tdx_dir:
        import os
        possible_dirs = [
            r"C:\new_tdx",
            r"C:\tdx", 
            r"D:\new_tdx",
            r"D:\tdx",
            r"C:\Program Files\new_tdx",
            r"C:\Program Files (x86)\new_tdx",
        ]
        for dir_path in possible_dirs:
            if os.path.exists(dir_path):
                tdx_dir = dir_path
                break
        
        if not tdx_dir:
            logger.warning("未找到默认TDX数据目录，请手动指定 --tdx-dir 参数")
            return pd.DataFrame()
    
    try:
        reader = Reader.factory(market='std', tdxdir=tdx_dir)
        
        # 根据频率选择读取方法
        if freq == "day":
            df = reader.daily(symbol=symbol)
        elif freq == "1m":
            df = reader.minute(symbol=symbol)
        elif freq == "5m":
            df = reader.fzline(symbol=symbol)
        else:
            # 对于其他频率，仍然使用日线数据
            df = reader.daily(symbol=symbol)
            
    except Exception as e:
        logger.warning("Mootdx 离线读取 %s 失败: %s", code, e)
        return pd.DataFrame()
    
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 处理日期索引：Mootdx Reader返回的数据通常以日期作为索引
    if df.index.name == 'date' or isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()  # 将日期索引转为列
        if 'index' in df.columns:
            df = df.rename(columns={'index': 'date'})
    
    # 统一列名
    column_mapping = {
        'date': 'date',
        'datetime': 'date', 
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume',
        'vol': 'volume',
        'amount': 'amount'
    }
    
    # 重命名列
    df_columns = df.columns.tolist()
    rename_dict = {}
    for old_col in df_columns:
        if old_col.lower() in column_mapping:
            rename_dict[old_col] = column_mapping[old_col.lower()]
    
    if rename_dict:
        df = df.rename(columns=rename_dict)
    
    # 确保有必要的列
    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.warning("Mootdx 离线数据缺少必要列: %s", missing_cols)
        return pd.DataFrame()
    
    # 处理日期
    if 'date' in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    
    # 筛选日期范围
    start_ts = pd.to_datetime(start, format="%Y%m%d")
    end_ts = pd.to_datetime(end, format="%Y%m%d")
    df = df[(df["date"].dt.date >= start_ts.date()) & (df["date"].dt.date <= end_ts.date())].copy()
    
    # 应用复权调整（如果需要）
    if adjust and adjust.lower() in ['qfq', 'hfq']:
        logger.info(f"注意：Mootdx 离线模式暂不支持 {adjust} 复权调整")
    
    df = df.sort_values("date").reset_index(drop=True)    
    return df[required_cols]

def _get_kline_baostock(code: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    """Baostock获取K线数据"""
    try:
        # 登录baostock系统
        lg = bs.login()
        if lg.error_code != '0':
            raise RuntimeError(f"Baostock登录失败: {lg.error_msg}")
        
        # 转换股票代码格式
        if code.startswith(('60', '68', '9')):
            bs_code = f"sh.{code.zfill(6)}"
        else:
            bs_code = f"sz.{code.zfill(6)}"
        
        # 转换日期格式
        start_date = pd.to_datetime(start, format="%Y%m%d").strftime('%Y-%m-%d')
        end_date = pd.to_datetime(end, format="%Y%m%d").strftime('%Y-%m-%d')
        
        # 设置复权类型
        adjustflag = "3"  # 默认后复权
        if adjust == "":
            adjustflag = "3"  # 后复权
        elif adjust.lower() == "qfq":
            adjustflag = "1"  # 前复权  
        elif adjust.lower() == "hfq":
            adjustflag = "2"  # 后复权
        
        # 获取K线数据
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag=adjustflag
        )
        
        if rs.error_code != '0':
            raise RuntimeError(f"Baostock获取K线数据失败: {rs.error_msg}")
        
        # 转换为DataFrame
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        # 登出系统
        bs.logout()
        
        if not data_list:
            return pd.DataFrame()
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 过滤掉停牌和异常交易状态的数据
        df = df[df['tradestatus'] == '1']  # 1表示正常交易
        
        if df.empty:
            return pd.DataFrame()
        
        # 数据类型转换
        df['date'] = pd.to_datetime(df['date'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 过滤掉无效数据
        df = df.dropna(subset=['open', 'high', 'low', 'close'])
        
        # 选择需要的列
        df = df[['date', 'open', 'close', 'high', 'low', 'volume']].copy()
        
        return df.sort_values("date").reset_index(drop=True)
        
    except Exception as e:
        # 确保登出
        try:
            bs.logout()
        except:
            pass
        raise RuntimeError(f"Baostock获取K线数据失败: {e}")

def _get_kline_mootdx(code: str, start: str, end: str, adjust: str, freq_code: int, offline_mode: bool = False, tdx_dir: str = None) -> pd.DataFrame:
    """Mootdx统一入口：根据模式选择在线或离线获取K线数据"""
    if offline_mode:
        return _get_kline_mootdx_offline(code, start, end, adjust, freq_code, tdx_dir)
    else:
        return _get_kline_mootdx_online(code, start, end, adjust, freq_code)

# ---------- 通用接口 ---------- #

def get_kline(
    code: str,
    start: str,
    end: str,
    adjust: str,
    datasource: str,
    freq_code: int = 4,
    offline_mode: bool = False,
    tdx_dir: str = None,
) -> pd.DataFrame:
    if datasource == "tushare":
        return _get_kline_tushare(code, start, end, adjust)
    elif datasource == "akshare":
        return _get_kline_akshare(code, start, end, adjust)
    elif datasource == "baostock":
        return _get_kline_baostock(code, start, end, adjust)
    elif datasource == "mootdx":        
        return _get_kline_mootdx(code, start, end, adjust, freq_code, offline_mode, tdx_dir)
    else:
        raise ValueError("datasource 仅支持 'tushare', 'akshare', 'baostock' 或 'mootdx'")

# ---------- 数据校验 ---------- #

def validate(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
    if df["date"].isna().any():
        raise ValueError("存在缺失日期！")
    if (df["date"] > pd.Timestamp.today()).any():
        raise ValueError("数据包含未来日期，可能抓取错误！")
    return df

def drop_dup_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.duplicated()]
# ---------- 单只股票抓取 ---------- #
def fetch_one(
    code: str,
    start: str,
    end: str,
    out_dir: Path,
    incremental: bool,
    datasource: str,
    freq_code: int,
    offline_mode: bool = False,
    tdx_dir: str = None,
):    
    csv_path = out_dir / f"{code}.csv"

    # 增量更新：若本地已有数据则从最后一天开始
    if incremental and csv_path.exists():
        try:
            existing = pd.read_csv(csv_path, parse_dates=["date"])
            last_date = existing["date"].max()
            if last_date.date() > pd.to_datetime(end, format="%Y%m%d").date():
                logger.debug("%s 已是最新，无需更新", code)
                return
            start = last_date.strftime("%Y%m%d")
        except Exception:
            logger.exception("读取 %s 失败，将重新下载", csv_path)

    for attempt in range(1, 4):
        try:            
            new_df = get_kline(code, start, end, "qfq", datasource, freq_code, offline_mode, tdx_dir)
            if new_df.empty:
                logger.debug("%s 无新数据", code)
                break
            new_df = validate(new_df)
            if csv_path.exists() and incremental:
                old_df = pd.read_csv(
                    csv_path,
                    parse_dates=["date"],
                    index_col=False
                )
                old_df = drop_dup_columns(old_df)
                new_df = drop_dup_columns(new_df)
                new_df = (
                    pd.concat([old_df, new_df], ignore_index=True)
                    .drop_duplicates(subset="date")
                    .sort_values("date")
                )
            new_df.to_csv(csv_path, index=False)
            break
        except Exception:
            logger.exception("%s 第 %d 次抓取失败", code, attempt)
            time.sleep(random.uniform(1, 3) * attempt)  # 指数退避
    else:
        logger.error("%s 三次抓取均失败，已跳过！", code)


# ---------- 主入口 ---------- #

def main():
    parser = argparse.ArgumentParser(description="按市值筛选 A 股并抓取历史 K 线")
    parser.add_argument("--datasource", choices=["tushare", "akshare", "baostock", "mootdx"], default="baostock", help="历史 K 线数据源")
    parser.add_argument("--frequency", type=int, choices=list(_FREQ_MAP.keys()), default=4, help="K线频率编码，参见说明")
    parser.add_argument("--exclude-gem", default=True, help="True则排除创业板/科创板/北交所")
    parser.add_argument("--min-mktcap", type=float, default=5e9, help="最小总市值（含），单位：元")
    parser.add_argument("--max-mktcap", type=float, default=float("+inf"), help="最大总市值（含），单位：元，默认无限制")
    parser.add_argument("--ignore-mktcap", action="store_true", help="忽略市值筛选，跳过市值数据获取（避免网络问题）")
    parser.add_argument("--start", default="20190101", help="起始日期 YYYYMMDD 或 'today'")
    parser.add_argument("--end", default="today", help="结束日期 YYYYMMDD 或 'today'")
    parser.add_argument("--out", default="./data", help="输出目录")
    parser.add_argument("--workers", type=int, default=3, help="并发线程数")
    
    # Mootdx 离线模式相关参数
    parser.add_argument("--offline", action="store_true", help="启用 Mootdx 离线模式（仅在 datasource=mootdx 时有效）")
    parser.add_argument("--tdx-dir", type=str, help="通达信数据目录路径（离线模式时使用），如: C:\\new_tdx")
    args = parser.parse_args()

    # ---------- 保存数据源配置 ---------- #
    set_current_datasource(args.datasource)
    
    # ---------- Token 处理 ---------- #
    if args.datasource == "tushare":
        ts_token = "86e6ef3f8c09b56db190d5ea64a2ba22708b8f79ba47a2e7a3a78095"  # 在这里补充token
        ts.set_token(ts_token)
        global pro
        pro = ts.pro_api()

    # ---------- 日期解析 ---------- #
    start = dt.date.today().strftime("%Y%m%d") if args.start.lower() == "today" else args.start
    end = dt.date.today().strftime("%Y%m%d") if args.end.lower() == "today" else args.end

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------- 股票池筛选 ---------- #
    if args.ignore_mktcap:
        logger.info("忽略市值筛选，跳过市值数据获取")
        codes_from_filter = []  # 不通过市值筛选获取股票
    else:
        # 使用新的股票信息缓存系统进行筛选
        codes_from_filter = get_constituents(
            args.min_mktcap,
            args.max_mktcap,
            args.exclude_gem,
        )    
    # 加上本地已有的股票，确保旧数据也能更新
    local_codes = [p.stem for p in out_dir.glob("*.csv")]
    
    if args.ignore_mktcap:
        # 忽略市值时，优先使用附加股票池和本地已有股票
        try:
            with open("appendix.json", "r", encoding="utf-8") as f:
                appendix_codes = json.load(f)["data"]
        except FileNotFoundError:
            appendix_codes = []
            
        # 如果没有附加股票池且没有本地股票，提供默认股票列表
        if not appendix_codes and not local_codes:
            default_codes = [
                "000001", "000002", "000858", "600000", "600036", "600519",
                "002415", "002527", "600887", "000166", "002304", "000776"
            ]
            logger.info(f"使用默认股票列表: {len(default_codes)} 只股票")
            codes = sorted(set(default_codes) | set(local_codes))
        else:
            codes = sorted(set(appendix_codes) | set(local_codes))
            logger.info(f"忽略市值筛选，使用附加股票池({len(appendix_codes)})和本地股票({len(local_codes)})")
    else:
        codes = sorted(set(codes_from_filter) | set(local_codes))

    if not codes:
        if args.ignore_mktcap:
            logger.error("忽略市值模式下无股票可处理，请检查附加股票池(appendix.json)或本地CSV文件")
        else:
            logger.error("筛选结果为空，请调整参数！")
        sys.exit(1)

    logger.info(
        "开始抓取 %d 支股票 | 数据源:%s | 频率:%s | 日期:%s → %s",
        len(codes),
        args.datasource,
        _FREQ_MAP[args.frequency],
        start,
        end,
    )

    # ---------- 更新股票信息缓存 ---------- #
    try:
        logger.info(f"使用 {args.datasource} 数据源更新股票信息缓存...")
        update_stock_info_from_codes(codes, args.datasource)
        logger.info("股票信息缓存更新完成")
    except Exception as e:
        logger.warning(f"股票信息缓存更新失败: {e}")

    # ---------- 多线程抓取 ---------- #
    # ---------- 验证离线模式参数 ---------- #
    offline_mode = False
    tdx_dir = None
    if args.datasource == "mootdx" and args.offline:
        offline_mode = True
        tdx_dir = args.tdx_dir
        if not tdx_dir:
            logger.info("未指定 --tdx-dir 参数，将自动检测常见的通达信安装目录")
        else:
            import os
            if not os.path.exists(tdx_dir):
                logger.error("指定的通达信目录不存在: %s", tdx_dir)
                sys.exit(1)
            logger.info("使用指定的通达信数据目录: %s", tdx_dir)
        logger.info("启用 Mootdx 离线模式")

    # ---------- 多线程抓取 ---------- #
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                fetch_one,
                code,
                start,
                end,
                out_dir,
                True,
                args.datasource,
                args.frequency,
                offline_mode,
                tdx_dir,
            )
            for code in codes
        ]
        for _ in tqdm(as_completed(futures), total=len(futures), desc="下载进度"):
            pass

    logger.info("全部任务完成，数据已保存至 %s", out_dir.resolve())


if __name__ == "__main__":
    main()
