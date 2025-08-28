# 股票选择系统 - Web界面使用指南

## 功能概述

现在您的股票选择系统已经完全支持：

✅ **定时任务调度** - 自动执行每日选股  
✅ **结果缓存系统** - 本地存储选股结果，最多保存30天  
✅ **Web界面展示** - 美观的HTML界面查看结果  
✅ **多种部署方式** - Docker容器化部署

## 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   定时调度器     │───▶│   结果缓存       │◀───│   Web服务器      │
│   scheduler.py  │    │ result_cache.py │    │ web_server.py   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ select_stock.py │    │ SQLite数据库    │    │   HTML模板      │
│   选股主程序     │    │   本地存储       │    │   用户界面       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 快速开始

### 1. 使用Docker Compose（推荐）

```bash
# 启动所有服务（调度器 + Web界面）
docker-compose up -d

# 查看Web界面: http://localhost:8080
```

### 2. 分别启动服务

```bash
# 只启动调度器
docker-compose up -d stock-trader-scheduler

# 只启动Web服务
docker-compose up -d stock-trader-web

# 一次性执行测试
docker-compose --profile manual up stock-trader-once
```

### 3. 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 执行一次选股（会自动缓存结果）
python select_stock.py

# 启动Web服务器
python web_server.py

# 启动定时调度器
python scheduler.py
```

## Web界面功能

### 📊 首页 - 选股结果展示
- **URL**: http://localhost:8080
- **功能**:
  - 按日期浏览选股结果
  - 查看每个选择器的股票选择
  - 统计概览（选择器数量、股票总数、执行时间等）
  - 股票选中频率分析

### 📈 统计页面
- **URL**: http://localhost:8080/statistics  
- **功能**:
  - 系统整体统计信息
  - 最近7天执行摘要
  - 选择器性能分析
  - 可视化图表展示

### 🔍 股票搜索
- **URL**: http://localhost:8080/search
- **功能**:
  - 搜索特定股票的选中历史
  - 支持多只股票批量搜索
  - 可配置搜索时间范围

## 缓存管理

### 使用缓存管理工具

```bash
# 查看缓存信息
python cache_manager.py info

# 清理30天前的旧数据
python cache_manager.py cleanup --days 30

# 分析缓存使用情况
python cache_manager.py analyze --days 7

# 备份数据库
python cache_manager.py backup --output backup.db

# 压缩数据库
python cache_manager.py vacuum

# 导出结果到CSV
python cache_manager.py export --output results.csv --from 2024-01-01 --to 2024-01-31
```

### 自动清理配置

缓存系统会自动：
- 保留最多30天的选股结果
- 执行数据库定期压缩
- 提供轮转日志记录

## API接口

系统还提供RESTful API：

```bash
# 获取可用日期列表
curl http://localhost:8080/api/dates

# 获取指定日期的选股结果
curl http://localhost:8080/api/results/2024-01-15

# 获取统计信息
curl http://localhost:8080/api/statistics

# 搜索股票
curl "http://localhost:8080/api/search?stocks=000001,000002&days=7"

# 触发缓存清理
curl http://localhost:8080/api/cleanup
```

## 部署配置

### 环境变量

```bash
# Web服务配置
export WEB_HOST=0.0.0.0
export WEB_PORT=8080

# 缓存配置
export CACHE_DIR=./cache
export CACHE_MAX_DAYS=30

# 时区设置
export TZ=Asia/Shanghai
```

### Docker运行模式

```bash
# 调度器模式
docker run -d stock-trader:latest scheduler

# Web服务模式
docker run -d -p 8080:8080 stock-trader:latest web

# 一次性执行
docker run --rm stock-trader:latest once

# 调试模式
docker run -d -p 8080:8080 stock-trader:latest web-debug
```

## 监控和维护

### 查看日志

```bash
# Docker容器日志
docker-compose logs -f stock-trader-web
docker-compose logs -f stock-trader-scheduler

# 本地日志文件
tail -f logs/web_server.log
tail -f logs/scheduler.log
tail -f logs/job_execution.log
```

### 健康检查

```bash
# 检查Web服务状态
curl http://localhost:8080/api/statistics

# 检查调度器状态
docker-compose ps stock-trader-scheduler

# 查看缓存统计
python cache_manager.py info
```

### 性能优化

1. **定期清理缓存**:
```bash
# 设置cron任务每周清理
0 2 * * 0 cd /path/to/project && python cache_manager.py cleanup --days 30
```

2. **数据库优化**:
```bash
# 定期压缩数据库
python cache_manager.py vacuum
```

3. **日志轮转**:
- 系统已配置自动日志轮转
- 单个文件最大10MB
- 保留最近5个文件

## 故障排除

### 常见问题

1. **Web页面无法访问**
   - 检查容器是否正常运行
   - 确认端口8080未被占用
   - 查看Web服务器日志

2. **没有选股数据显示**
   - 确认调度器正在运行
   - 检查数据目录是否有股票数据
   - 验证选股任务是否成功执行

3. **缓存数据异常**
   - 使用 `cache_manager.py info` 检查缓存状态
   - 必要时备份并重建缓存数据库

### 重置系统

```bash
# 停止所有服务
docker-compose down

# 清除缓存数据（可选）
rm -rf cache/

# 重新启动
docker-compose up -d
```

## 安全考虑

1. **网络访问**: 默认监听所有接口，生产环境建议配置防火墙
2. **数据备份**: 定期备份缓存数据库和配置文件
3. **日志管理**: 注意日志文件可能包含敏感信息

## 扩展功能

系统支持进一步扩展：
- 添加用户认证
- 集成更多数据源
- 增加邮件通知功能
- 支持多种导出格式
- 添加更多可视化图表

---

🎉 现在您可以通过浏览器访问 http://localhost:8080 来查看选股结果了！