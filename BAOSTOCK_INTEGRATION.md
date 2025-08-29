# Baostock 数据源集成方案

## 概述

本方案成功集成了baostock作为新的股票数据源，实现了市值数据的获取、本地缓存和定期更新，有效避免了因频繁请求导致的IP封禁问题。

## 核心特性

### 1. 多数据源支持
- **Baostock**: 作为主要数据源，稳定性好，不易被封IP
- **AKShare**: 备选数据源
- **TuShare**: 备选数据源  
- **Mootdx**: 备选数据源

### 2. 智能缓存系统
- **缓存有效期**: 7天
- **本地存储**: JSON格式，包含市值数据和元数据
- **自动fallback**: 数据源失败时自动切换到其他源
- **版本控制**: 缓存文件纳入Git管理

### 3. GitHub Actions自动化
- **定期更新**: 每周一自动更新数据
- **条件检查**: 每日检查缓存是否过期
- **手动触发**: 支持手动执行和参数配置
- **自动提交**: 数据更新后自动提交到仓库

## 文件结构

```
├── .github/
│   ├── workflows/
│   │   ├── update-market-data.yml    # 自动更新工作流
│   │   └── manual-update.yml         # 手动更新工作流
│   └── README.md                     # GitHub Actions说明
├── cache/                            # 缓存目录
│   ├── mktcap_cache.json            # 市值数据缓存
│   └── cache_metadata.json          # 缓存元数据
├── data_cache_manager.py             # 缓存管理器
├── fetch_kline.py                    # 主数据获取模块 (已更新)
├── get_datasource.py                 # 数据源配置 (已更新)
└── requirements.txt                  # 依赖包 (已更新)
```

## 使用方法

### 本地使用

```bash
# 检查缓存状态
python data_cache_manager.py --status

# 强制更新缓存
python data_cache_manager.py --update

# 条件更新(仅在缓存过期时更新)
python data_cache_manager.py --check-update

# 使用baostock数据源获取K线
python fetch_kline.py --datasource baostock --start 20240101 --end 20240131
```

### GitHub Actions使用

1. **自动更新**: 无需操作，系统会自动运行
2. **手动更新**: GitHub仓库 → Actions → Manual Market Data Update → Run workflow

## 技术实现

### Baostock集成

```python
def _get_mktcap_baostock() -> pd.DataFrame:
    """获取市值数据的简化实现"""
    # 登录baostock
    bs.login()
    
    # 获取股票基本信息
    rs = bs.query_stock_basic()
    
    # 处理A股数据并估算市值
    # 返回DataFrame: ['code', 'mktcap']
```

### 缓存管理

```python
class DataCacheManager:
    def update_mktcap_cache(self, force_update=False):
        """更新市值缓存，支持强制更新"""
        
    def get_mktcap_data(self):
        """智能获取市值数据，优先使用缓存"""
        
    def is_cache_valid(self, cache_type):
        """检查缓存是否在有效期内"""
```

### GitHub Actions工作流

```yaml
# 每周自动更新 + 每日条件检查
on:
  schedule:
    - cron: '0 6 * * 1'  # 每周一
    - cron: '0 2 * * *'  # 每日检查
  workflow_dispatch:     # 手动触发
```

## 优势总结

1. **避免IP封禁**: 通过GitHub Actions的云端IP执行请求
2. **数据稳定性**: baostock相对稳定，不易被限制
3. **自动化程度高**: 无需人工干预，自动维护数据新鲜度
4. **容错能力强**: 多数据源fallback，提高成功率
5. **成本低**: 利用GitHub的免费额度，无需额外服务器
6. **易于维护**: 集成到现有项目，最小化代码改动

## 注意事项

1. **GitHub Actions限制**: 免费账户每月2000分钟额度
2. **网络依赖**: 依赖GitHub Actions的网络环境
3. **数据准确性**: baostock的市值数据基于估算，可能与实时数据有差异
4. **仓库大小**: 缓存文件会增加仓库体积

## 后续扩展

1. 可以添加更多数据源(如Wind、同花顺等)
2. 支持更多数据类型(PE ratio、PB ratio等)
3. 添加数据质量检查和异常告警
4. 支持增量更新，减少数据传输量

## 测试验证

项目已通过以下测试：
- ✅ Baostock数据源连接和数据获取
- ✅ 缓存系统的读写和有效性检查
- ✅ GitHub Actions工作流配置
- ✅ 多数据源fallback机制
- ✅ K线数据获取集成测试

该解决方案成功实现了稳定的股票数据获取和缓存管理，有效解决了IP封禁问题。