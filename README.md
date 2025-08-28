# Z哥战法的Python实现

> **更新时间：2025-08-28** – 增加 GitHub Actions 自动化部署，每日自动选股并发布到 GitHub Pages。

---

## 目录

* [项目简介](#项目简介)
* [GitHub Actions 自动化](#github-actions-自动化)
* [快速上手](#快速上手)

  * [安装依赖](#安装依赖)
  * [Tushare Token（可选）](#tushare-token可选)
  * [Mootdx 运行前置步骤](#mootdx-运行前置步骤)
  * [下载历史行情](#下载历史行情)
  * [运行选股](#运行选股)
* [参数说明](#参数说明)

  * [`fetch_kline.py`](#fetch_klinepy)

    * [K 线频率编码](#k-线频率编码)
  * [`select_stock.py`](#select_stockpy)
  * [内置策略参数](#内置策略参数)

    * [1. BBIKDJSelector（少妇战法）](#1-bbikdjselector少妇战法)
    * [2. PeakKDJSelector（填坑战法）](#2-peakkdjselector填坑战法)
    * [3. BBIShortLongSelector（补票战法）](#3-bbishortlongselector补票战法)
    * [4. BreakoutVolumeKDJSelector（TePu 战法）](#4-breakoutvolumekdjselectortepu-战法)
* [项目结构](#项目结构)
* [免责声明](#免责声明)

---

## 项目简介

| 名称                    | 功能简介                                                                                                             |
| --------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **`fetch_kline.py`**  | *按市值筛选* A 股股票，并抓取其**历史 K 线**保存为 CSV。支持 **AkShare / Tushare / Mootdx** 三大数据源，自动增量更新、多线程下载。*本版本不再保存市值快照*，每次运行实时拉取。 |
| **`select_stock.py`** | 读取本地 CSV 行情，依据 `configs.json` 中的 **Selector** 定义批量选股，结果输出到 `select_results.log` 与控制台。                            |

内置策略（见 `Selector.py`）：

* **BBIKDJSelector**（少妇战法）
* **PeakKDJSelector**（填坑战法）
* **BBIShortLongSelector**（补票战法）
* **BreakoutVolumeKDJSelector**（TePu 战法）

---

## GitHub Actions 自动化

本项目已配置 GitHub Actions 工作流，可实现每日自动选股并发布结果到 GitHub Pages。

### ✨ 功能特性

- 🕕 **每日定时执行**：北京时间下午6点自动运行
- 📊 **自动数据获取**：执行 `fetch_kline.py` 获取最新股价数据
- 🎯 **智能选股**：运行 `select_stock.py` 基于配置的策略自动选股
- 📈 **精美报告**：生成现代化设计的 HTML 可视化报告
  - 🎨 **战法卡片**：每个战法独立展示，不同颜色和图标
  - 📱 **响应式设计**：支持手机、平板、电脑完美显示
  - 🔍 **股票详情**：显示股票代码、名称、行业、市场信息
  - 🏢 **行业分布**：自动统计和显示各战法的行业分布情况
  - 📊 **统计面板**：一目了然的策略和股票统计
  - 🔗 **便捷链接**：点击股票卡片直接跳转雪球查看
- 📅 **历史记录**：保留最近一周的选股记录，可切换查看
- 🌐 **自动发布**：将结果自动发布到 GitHub Pages
- 🤖 **手动触发**：支持在 GitHub Actions 页面手动运行

### 🚀 快速启用

1. **启用 GitHub Pages**
   - 进入仓库 Settings → Pages
   - Source 选择 "GitHub Actions"
   - 保存设置

2. **配置权限**
   - 进入 Settings → Actions → General
   - 确保 "Workflow permissions" 设置为 "Read and write permissions"

3. **手动测试**（可选）
   - 进入 Actions → "Daily Stock Analysis"
   - 点击 "Run workflow" 手动触发一次测试

4. **访问结果**
   - 访问 `https://你的用户名.github.io/StockTradebyZ` 查看选股结果

### 📋 工作流说明

工作流文件位置：`.github/workflows/daily-stock-analysis.yml`

**执行步骤**：
1. 设置 Python 环境并安装依赖
2. **Mootdx IP 检测**：`python -m mootdx bestip -vv`（提升连接稳定性）
3. 执行 `fetch_kline.py --datasource akshare` 获取股价数据
4. **多数据源股票信息缓存**：根据指定数据源获取股票名称、行业等
5. 运行 `select_stock.py` 执行所有策略的选股
6. 生成今日选股报告（`reports/report-YYYY-MM-DD.html`）
7. 更新首页和历史记录索引（`index.html`）
8. 自动清理 `reports/` 目录中超过一周的旧报告
9. 发布到 GitHub Pages

**自动触发条件**：
- 每日北京时间18:00（UTC 10:00）
- 也可在 Actions 页面手动触发

---

## 快速上手

### 安装依赖

```bash
# 创建并激活 Python 3.12 虚拟环境（推荐）
conda create -n stock python=3.12
conda activate stock

# 进入项目目录（将以下路径替换为你的实际路径）
cd "你的路径"

# 安装依赖
pip install -r requirements.txt

# 若遇到 cffi 安装报错，可先升级后重试
pip install --upgrade cffi  
```

> 主要依赖：`akshare`、`tushare`、`mootdx`、`pandas`、`tqdm` 等。

### Tushare Token（可选）

若选择 **Tushare** 作为数据源，请按以下步骤操作：

1. **注册账号**
   点击专属注册链接 [https://tushare.pro/register?reg=820660](https://tushare.pro/register?reg=820660) 完成注册。*通过该链接注册，我将获得 50 积分 – 感谢支持！*
2. **开通基础权限**
   登录后进入「**平台介绍 → 社区捐助**」，按提示捐赠 **200 元/年** 可解锁 Tushare 基础接口。
3. **获取 Token**
   打开个人主页，点击 **「接口 Token」**，复制生成的 Token。
4. **填入代码**
   在 `fetch_kline.py` 约 **第 307 行**（以实际行为准）：

   ```python
   ts_token = "***"  # ← 替换为你的 Token
   ```

### 数据源选择建议

**推荐优先级**：TuShare > AkShare > Mootdx

1. **TuShare**（推荐）
   - ✅ 数据质量高，更新及时
   - ✅ 完整的股票名称和行业分类
   - ✅ 专业金融数据服务
   - ⚠️ 需要注册并获取token

2. **AkShare**（备选）
   - ✅ 功能丰富，免费使用
   - ✅ 股票名称和行业信息完整
   - ⚠️ 请求频率限制较严格

3. **Mootdx**（应急）
   - ✅ 完全免费，无需注册
   - ✅ 支持离线数据批量初始化股票信息
   - ⚠️ 数据是未复权数据，影响选股精度
   - ⚠️ 行业信息缺失（仅提供股票名称）

### Mootdx 运行前置步骤

使用 **Mootdx** 数据源前，需先探测最快行情服务器：

```bash
python -m mootdx bestip -vv
```

脚本将保存最佳 IP，提升后续抓取稳定性。GitHub Actions 会自动执行此步骤。

**Mootdx 离线数据初始化**（推荐）：

```bash
# 使用mootdx离线数据批量初始化股票信息缓存
python init_stock_cache.py --datasource mootdx

# 强制重新初始化（清空现有缓存）
python init_stock_cache.py --datasource mootdx --force

# 测试mootdx离线初始化功能
python stock_info_cache.py init_mootdx
```

**离线初始化优势**：
- 🚀 **快速批量**：一次性获取全市场股票基本信息
- 📡 **离线获取**：无需逐个请求，大大提升效率
- 🏢 **完整覆盖**：包含上交所、深交所所有股票
- 💾 **自动缓存**：初始化后长期有效，减少网络请求

### 下载历史行情

```bash
python fetch_kline.py \
  --datasource mootdx      # mootdx / akshare / tushare
  --frequency 4            # K 线频率编码（4 = 日线）
  --exclude-gem ture       # 排除创业板 / 科创板 / 北交所
  --min-mktcap 5e9         # 最小总市值（元）
  --max-mktcap +inf        # 最大总市值（元）
  --start 20200101         # 起始日期（YYYYMMDD 或 today）
  --end today              # 结束日期
  --out ./data             # 输出目录
  --workers 10             # 并发线程数
```

*首跑* 下载完整历史；之后脚本会 **增量更新**。

### 运行选股

```bash
python select_stock.py \
  --data-dir ./data        # CSV 行情目录
  --config ./configs.json  # Selector 配置
  --date 2025-07-02        # 交易日（缺省 = 最新）
```

示例输出：

```
============== 选股结果 [填坑战法] ===============
交易日: 2025-07-02
符合条件股票数: 2
600690, 000333
```

### 生成HTML报告

运行选股后，可以生成精美的HTML报告：

```bash
# 生成HTML报告
python generate_html.py

# 或本地测试（使用模拟数据）
python test_html_generation.py

# 测试不同数据源
python test_html_generation.py tushare
python test_html_generation.py mootdx
```

生成的文件：
- `index.html` - 首页，可选择查看不同日期的报告
- `reports/report-YYYY-MM-DD.html` - 每日选股报告，包含各战法的卡片展示

### 股票信息缓存

项目支持多数据源获取股票基本信息（名称、行业、市场），自动缓存避免重复获取：

```bash
# 使用不同数据源更新缓存
python -c "from stock_info_cache import StockInfoCache; cache = StockInfoCache(datasource='akshare'); cache.batch_update(['000001', '600000'])"
python -c "from stock_info_cache import StockInfoCache; cache = StockInfoCache(datasource='tushare'); cache.batch_update(['000001', '600000'])"

# 查看缓存统计
python -c "from stock_info_cache import StockInfoCache; cache = StockInfoCache(); print('缓存股票数量:', len(cache.cache)); print('行业分布:', cache.get_industry_stats())"

# 设置默认数据源
python get_datasource.py akshare  # 设置为akshare
python get_datasource.py         # 查看当前数据源
```

**多数据源支持**：
- 🔸 **AkShare**：功能最全，支持股票名称和详细行业分类
- 🔹 **TuShare**：专业金融数据，需要token，提供规范的行业分类  
- 🔶 **Mootdx**：开源免费，支持离线批量初始化，仅提供股票名称

**缓存特性**：
- 📂 **本地存储**：缓存保存在 `stock_info_cache.json` 文件
- 🔄 **增量更新**：只获取新股票的信息，已缓存的直接使用
- ⏰ **自动过期**：30天后自动清理过期数据
- 🛡️ **错误处理**：获取失败时使用默认信息，不影响主流程
- 🔀 **多源兼容**：自动根据运行时数据源获取信息

### HTML文件管理

为了便于管理和清理，所有HTML报告文件都统一存储在 `reports/` 目录中：

```bash
# 查看所有生成的报告
ls -la reports/

# 手动清理旧报告（保留最近7天）
python -c "from generate_html import cleanup_old_reports; cleanup_old_reports()"

# 完全清理所有HTML文件
rm -rf reports/
```

**目录结构优势**：
- 🗂️ **统一管理**：所有历史报告集中在一个目录
- 🧹 **便于清理**：可以一次性删除整个reports目录
- 📁 **结构清晰**：根目录只有首页，报告文件分离存储
- 🚀 **自动维护**：超过一周的旧报告自动清理

---

## 参数说明

### `fetch_kline.py`

| 参数                  | 默认值      | 说明                                   |
| ------------------- | -------- | ------------------------------------ |
| `--datasource`      | `mootdx` | 数据源：`tushare` / `akshare` / `mootdx` |
| `--frequency`       | `4`      | K 线频率编码（下表）                          |
| `--exclude-gem`     | flag     | 排除创业板/科创板/北交所                        |
| `--min-mktcap`      | `5e9`    | 最小总市值（元）                             |
| `--max-mktcap`      | `+inf`   | 最大总市值（元）                             |
| `--start` / `--end` | `today`  | 日期范围，`YYYYMMDD` 或 `today`            |
| `--out`             | `./data` | 输出目录                                 |
| `--workers`         | `10`     | 并发线程数                                |

#### K 线频率编码

|  编码 |  周期  | Mootdx 关键字 | 用途   |
| :-: | :--: | :--------: | ---- |
|  0  |  5 分 |    `5m`    | 高频   |
|  1  | 15 分 |    `15m`   | 高频   |
|  2  | 30 分 |    `30m`   | 高频   |
|  3  | 60 分 |    `1h`    | 波段   |
|  4  |  日线  |    `day`   | ★ 常用 |
|  5  |  周线  |   `week`   | 中长线  |
|  6  |  月线  |    `mon`   | 中长线  |
|  7  |  1 分 |    `1m`    | Tick |
|  8  |  1 分 |    `1m`    | Tick |
|  9  |  日线  |    `day`   | 备用   |
|  10 |  季线  |   `3mon`   | 长周期  |
|  11 |  年线  |   `year`   | 长周期  |

### `select_stock.py`

| 参数           | 默认值              | 说明            |
| ------------ | ---------------- | ------------- |
| `--data-dir` | `./data`         | CSV 行情目录      |
| `--config`   | `./configs.json` | Selector 配置文件 |
| `--date`     | 最新交易日            | 选股日期          |
| `--tickers`  | `all`            | 股票池（逗号分隔列表）   |

执行 `python select_stock.py --help` 获取更多高级参数与解释。

### 内置策略参数

以下参数均来自 **`configs.json`**，可根据个人喜好自由调整。

#### 1. BBIKDJSelector（少妇战法）

| 参数                | 预设值    | 说明                                                  |
| ----------------- | ------ | --------------------------------------------------- |
| `j_threshold`     | `1`    | 当日 **J** 值必须 *小于* 该阈值                               |
| `bbi_min_window`  | `20`   | 检测 BBI 上升的最短窗口（交易日）                                 |
| `max_window`      | `60`   | 参与检测的最大窗口（交易日）                                      |
| `price_range_pct` | `0.5`  | 最近 *max\_window* 根 K 线内，收盘价最大波动（`high/low−1`）不得超过此值 |
| `bbi_q_threshold` | `0.1`  | 允许 BBI 一阶差分为负的分位阈值（回撤容忍度）                           |
| `j_q_threshold`   | `0.10` | 当日 **J** 值需 *不高于* 最近窗口内该分位数                         |

#### 2. PeakKDJSelector（填坑战法）

| 参数               | 预设值    | 说明                                                          |
| ---------------- | ------ | ----------------------------------------------------------- |
| `j_threshold`    | `10`   | 当日 **J** 值必须 *小于* 该阈值                                       |
| `max_window`     | `100`  | 参与检测的最大窗口（交易日）                                              |
| `fluc_threshold` | `0.03` | 当日收盘价与坑口的最大允许波动率                                            |
| `gap_threshold`  | `0.2`  | 要求坑口高于区间最低收盘价的幅度（`oc_prev > min_close × (1+gap_threshold)`） |
| `j_q_threshold`  | `0.10` | 当日 **J** 值需 *不高于* 最近窗口内该分位数                                 |

#### 3. BBIShortLongSelector（补票战法）

| 参数                | 预设值   | 说明                      |
| ----------------- | ----- | ----------------------- |
| `n_short`         | `3`   | 计算短周期 **RSV** 的窗口（交易日）  |
| `n_long`          | `21`  | 计算长周期 **RSV** 的窗口（交易日）  |
| `m`               | `3`   | 最近 *m* 天满足短 RSV 条件的判别窗口 |
| `bbi_min_window`  | `2`   | 检测 BBI 上升的最短窗口（交易日）     |
| `max_window`      | `60`  | 参与检测的最大窗口（交易日）          |
| `bbi_q_threshold` | `0.2` | 允许 BBI 一阶差分为负的分位阈值      |

#### 4. BreakoutVolumeKDJSelector（TePu 战法）

| 参数                 | 预设值      | 说明                                                  |
| ------------------ | -------- | --------------------------------------------------- |
| `j_threshold`      | `1`      | 当日 **J** 值必须 *小于* 该阈值                               |
| `j_q_threshold`    | `0.10`   | 当日 **J** 值需 *不高于* 最近窗口内该分位数                         |
| `up_threshold`     | `3.0`    | 单日涨幅不低于该百分比，视为“突破”                                  |
| `volume_threshold` | `0.6667` | 放量日成交量需 **≥ 1/(1−volume\_threshold)** 倍于窗口内其他任意日    |
| `offset`           | `15`     | 向前回溯的突破判定窗口（交易日）                                    |
| `max_window`       | `60`     | 参与检测的最大窗口（交易日）                                      |
| `price_range_pct`  | `0.5`    | 最近 *max\_window* 根 K 线内，收盘价最大波动不得超过此值（`high/low−1`） |

---

## 项目结构

```
.
├── .github/
│   └── workflows/
│       └── daily-stock-analysis.yml  # GitHub Actions 工作流
├── appendix.json                     # 附加股票池
├── configs.json                      # Selector 配置
├── fetch_kline.py                    # 行情抓取脚本
├── select_stock.py                   # 批量选股脚本
├── Selector.py                       # 策略实现
├── generate_html.py                  # HTML 报告生成脚本
├── stock_info_cache.py               # 股票信息缓存模块
├── get_datasource.py                 # 数据源配置管理工具
├── init_stock_cache.py               # 股票信息缓存初始化脚本
├── test_html_generation.py           # HTML 生成测试脚本
├── data/                             # CSV 数据输出目录
├── reports/                          # HTML 报告输出目录
│   └── report-YYYY-MM-DD.html       # 每日选股报告
├── index.html                        # 首页（日期选择器）
├── stock_info_cache.json            # 股票信息缓存文件
├── datasource_config.json           # 数据源配置文件
├── fetch.log                         # 抓取日志
└── select_results.log                # 选股日志
```

---

## 免责声明

* 本仓库仅供学习与技术研究之用，**不构成任何投资建议**。股市有风险，入市需审慎。
* 致谢 **@Zettaranc** 在 Bilibili 的无私分享：[https://b23.tv/JxIOaNE](https://b23.tv/JxIOaNE)
