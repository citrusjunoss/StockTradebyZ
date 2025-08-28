# 股票选择系统 - 完整功能指南

## 🎉 系统完整功能清单

您的股票选择系统现在支持以下完整功能：

### ✅ 核心功能

1. **自动数据更新**
   - 每次执行选股前自动运行 `fetch_kline.py` 更新股票数据
   - 支持增量更新，提高执行效率
   - 可配置数据源（akshare、tushare、mootdx）

2. **定时任务调度**
   - 支持 cron 表达式精确控制执行时间
   - 自动错误处理和重试机制
   - 完整的执行日志记录

3. **结果缓存系统**
   - SQLite 数据库本地存储
   - 自动清理超过30天的旧数据
   - 支持统计分析和数据导出

4. **Web界面展示**
   - 响应式设计，支持桌面和移动端
   - 实时数据展示和可视化图表
   - 股票搜索和筛选功能

### ✅ 高级功能

5. **PWA（渐进式Web应用）**
   - 支持离线查看缓存数据
   - 可安装到桌面和移动设备
   - 后台同步和推送通知

6. **IndexedDB 前端缓存**
   - 浏览器本地缓存最多30天数据
   - 智能缓存策略，减少服务器请求
   - 自动清理过期数据

7. **Service Worker 离线支持**
   - 静态资源缓存
   - API数据缓存
   - 离线模式提示

## 🚀 快速启动指南

### 1. 使用 Docker Compose（推荐）

```bash
# 启动完整系统（调度器 + Web界面）
docker-compose up -d

# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

系统启动后：
- **Web界面**: http://localhost:8080
- **PWA安装**: 浏览器会提示安装到桌面
- **离线功能**: 断网后仍可查看缓存的数据

### 2. 分别启动服务

```bash
# 只启动数据更新和选股调度器
docker-compose up -d stock-trader-scheduler

# 只启动Web服务
docker-compose up -d stock-trader-web

# 执行一次性测试
docker-compose --profile manual up stock-trader-once
```

### 3. 本地开发运行

```bash
# 安装依赖
pip install -r requirements.txt

# 生成PWA图标
python create_icons.py

# 启动Web服务器
python web_server.py

# 启动定时调度器（另一个终端）
python scheduler.py

# 立即执行一次选股任务
python scheduler.py --run-now
```

## 📱 PWA 功能使用

### 安装应用到设备

1. **桌面端**：
   - 访问 http://localhost:8080
   - 点击地址栏的"安装"按钮
   - 或点击页面右下角的"安装应用"按钮

2. **移动端**：
   - 使用 Chrome 或 Safari 访问
   - 选择"添加到主屏幕"
   - 应用图标将出现在桌面

### 离线功能

- **自动缓存**：访问过的页面和数据会自动缓存
- **离线查看**：断网时可查看最近30天的缓存数据
- **智能更新**：重新联网时自动同步最新数据
- **存储管理**：超过30天的数据自动清理

### 快捷方式

PWA支持以下快捷方式：
- **今日选股**：直接跳转到最新选股结果
- **统计分析**：查看系统统计信息
- **股票搜索**：搜索特定股票

## ⚙️ 配置说明

### 调度器配置 (`scheduler_config.json`)

```json
{
  "scheduler": {
    "timezone": "Asia/Shanghai",
    "max_workers": 1,
    "coalesce": true,
    "max_instances": 1
  },
  "jobs": [
    {
      "id": "daily_stock_selection",
      "name": "每日选股任务",
      "trigger": "cron",
      "enabled": true,
      "hour": 8,                    // 执行时间：早上8点
      "minute": 30,                 // 30分
      "second": 0,
      "args": {
        "data_dir": "./data",
        "config": "./configs.json",
        "tickers": "all",
        "cache_dir": "./cache",
        "datasource": "akshare",    // 数据源
        "workers": 3,               // 并发线程数
        "skip_data_update": false   // 是否跳过数据更新
      },
      "misfire_grace_time": 300
    }
  ]
}
```

### 数据更新配置

- **datasource**: 数据源选择
  - `akshare`: 推荐，免费且稳定
  - `tushare`: 需要token，数据质量高
  - `mootdx`: 通达信数据源
- **workers**: 并发下载线程数（建议2-5）
- **skip_data_update**: 设为`true`可跳过数据更新，仅执行选股

## 📊 数据管理

### 缓存管理工具

```bash
# 查看缓存信息
python cache_manager.py info

# 清理30天前的数据
python cache_manager.py cleanup --days 30

# 分析缓存使用情况
python cache_manager.py analyze --days 7

# 导出结果到CSV
python cache_manager.py export --output results.csv --from 2024-01-01

# 备份数据库
python cache_manager.py backup

# 压缩数据库
python cache_manager.py vacuum
```

### 前端缓存管理

在Web界面中：
1. 点击导航栏"工具"菜单
2. 选择"缓存统计"查看本地缓存状态
3. 选择"刷新数据"强制更新当前页面数据
4. 网络状态会在离线时自动显示

## 🔧 监控和维护

### 查看系统状态

```bash
# Docker服务状态
docker-compose ps

# 实时日志
docker-compose logs -f stock-trader-scheduler
docker-compose logs -f stock-trader-web

# 系统资源使用
docker stats
```

### 日志文件位置

- `logs/scheduler.log` - 调度器日志
- `logs/web_server.log` - Web服务器日志
- `logs/job_execution.log` - 任务执行详细日志
- `select_results.log` - 选股结果日志

### 性能优化

1. **调整并发数**：根据网络状况调整`workers`参数
2. **缓存策略**：合理设置缓存保留天数
3. **定时执行**：避开市场交易繁忙时段
4. **资源监控**：定期检查磁盘空间和内存使用

## 🌐 网络和安全

### 端口配置

- **Web服务**: 8080（可在docker-compose.yml中修改）
- **防火墙**: 如需外网访问，请开放相应端口

### 数据安全

- 所有数据存储在本地
- 支持数据库备份和恢复
- 敏感信息（如API token）请妥善保管

## 📱 移动端优化

### 响应式设计

- 自动适配手机、平板、桌面屏幕
- 触摸友好的界面元素
- 快速加载和流畅滚动

### 离线体验

- 离线时显示缓存数据
- 智能网络状态检测
- 自动同步最新数据

## 🔄 更新升级

### 系统更新

```bash
# 停止服务
docker-compose down

# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 启动服务
docker-compose up -d
```

### 数据迁移

系统更新时，数据会自动保留在：
- `cache/` - 缓存数据库
- `data/` - 股票历史数据
- `logs/` - 日志文件

## 🚨 故障排除

### 常见问题

1. **数据更新失败**
   - 检查网络连接
   - 确认数据源API可用性
   - 查看错误日志定位问题

2. **Web界面无法访问**
   - 确认服务是否正常运行
   - 检查端口是否被占用
   - 查看Web服务器日志

3. **PWA安装失败**
   - 确保使用HTTPS或localhost
   - 检查浏览器是否支持PWA
   - 清除浏览器缓存后重试

4. **离线功能异常**
   - 检查Service Worker注册状态
   - 清除浏览器缓存和数据
   - 确认IndexedDB可用性

### 重置系统

```bash
# 完全重置（清除所有数据）
docker-compose down
rm -rf cache/ logs/
docker-compose up -d
```

---

🎉 **恭喜！您现在拥有了一个功能完整的专业股票选择系统！**

系统特点：
- ✅ 全自动数据更新和选股
- ✅ 美观的Web界面和移动端支持
- ✅ PWA离线功能和桌面安装
- ✅ 智能缓存和性能优化
- ✅ 完整的监控和管理工具

开始使用：访问 http://localhost:8080 体验完整功能！