# 股票选择定时任务系统

这个系统为股票交易策略应用添加了定时任务功能，支持配置化的每日选股任务执行。

## 功能特性

- ✅ 支持配置化的定时任务执行
- ✅ 多种执行时间配置（按小时、分钟、秒）
- ✅ 完善的日志记录和轮转
- ✅ Docker容器化部署
- ✅ 任务执行监控和错误处理
- ✅ 支持立即执行测试功能

## 文件结构

```
├── scheduler.py              # 定时任务调度器
├── scheduler_config.json     # 调度器配置文件
├── logger_config.py          # 日志配置模块
├── docker-compose.yml        # Docker Compose配置
├── docker-compose.override.yml # 开发环境配置
├── Dockerfile               # 更新的Docker镜像定义
└── SCHEDULER_README.md      # 本说明文件
```

## 配置说明

### 1. 调度器配置 (`scheduler_config.json`)

```json
{
  "scheduler": {
    "timezone": "Asia/Shanghai",  // 时区设置
    "max_workers": 1,            // 最大工作线程数
    "coalesce": true,            // 是否合并延迟的任务
    "max_instances": 1           // 同一任务最大并发实例数
  },
  "jobs": [
    {
      "id": "daily_stock_selection",      // 任务唯一ID
      "name": "每日选股任务",              // 任务名称
      "trigger": "cron",                  // 触发器类型
      "enabled": true,                    // 是否启用
      "hour": 8,                          // 执行小时
      "minute": 30,                       // 执行分钟
      "second": 0,                        // 执行秒数
      "args": {                           // 任务参数
        "data_dir": "./data",
        "config": "./configs.json",
        "tickers": "all"
      },
      "misfire_grace_time": 300           // 错过执行的宽限时间(秒)
    }
  ]
}
```

### 2. 时间配置选项

- `hour`: 0-23，执行小时
- `minute`: 0-59，执行分钟
- `second`: 0-59，执行秒数
- `day_of_week`: 0-6，星期几执行（可选）

## 使用方法

### 本地运行

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **运行调度器**
```bash
python scheduler.py
```

3. **立即测试执行**
```bash
python scheduler.py --run-now
```

4. **使用自定义配置**
```bash
python scheduler.py --config custom_scheduler_config.json
```

### Docker运行

1. **构建镜像**
```bash
docker build -t stock-trader:latest .
```

2. **运行调度器**
```bash
docker run -d --name stock-scheduler \
  -v $(pwd)/data:/app/data:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/configs.json:/app/configs.json:ro \
  -v $(pwd)/scheduler_config.json:/app/scheduler_config.json:ro \
  stock-trader:latest scheduler
```

3. **一次性执行**
```bash
docker run --rm \
  -v $(pwd)/data:/app/data:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/configs.json:/app/configs.json:ro \
  stock-trader:latest once
```

### Docker Compose运行

1. **启动调度器服务**
```bash
docker-compose up -d
```

2. **一次性执行测试**
```bash
docker-compose --profile manual up stock-trader-once
```

3. **查看日志**
```bash
docker-compose logs -f stock-trader
```

4. **停止服务**
```bash
docker-compose down
```

## 日志管理

### 日志文件位置
- `logs/scheduler.log` - 调度器日志
- `logs/scheduler_error.log` - 调度器错误日志
- `logs/job_execution.log` - 任务执行日志
- `select_results.log` - 选股结果日志

### 日志轮转
- 单个日志文件最大10MB
- 保留最近5个历史文件
- 支持自动清理超过30天的旧日志

## 监控和维护

### 查看运行状态
```bash
# 查看Docker容器状态
docker-compose ps

# 查看实时日志
docker-compose logs -f stock-trader

# 查看最近的日志
tail -f logs/scheduler.log
```

### 重启服务
```bash
# 重启调度器服务
docker-compose restart stock-trader

# 重新加载配置（需要重启）
docker-compose down && docker-compose up -d
```

### 修改任务时间
1. 编辑 `scheduler_config.json` 文件
2. 重启Docker容器使配置生效

## 常见问题

### 1. 任务没有按时执行
- 检查时区设置是否正确
- 确认容器时间与系统时间同步
- 查看错误日志排查问题

### 2. 任务执行失败
- 检查数据目录是否存在股票数据
- 确认配置文件格式正确
- 查看详细错误日志

### 3. 内存或磁盘使用过高
- 检查日志文件大小，清理旧日志
- 调整日志轮转配置
- 监控Docker容器资源使用

## 示例配置

### 每个工作日早上8:30执行
```json
{
  "id": "workday_morning",
  "name": "工作日晨选",
  "trigger": "cron",
  "enabled": true,
  "hour": 8,
  "minute": 30,
  "day_of_week": "0-4",  // 周一到周五
  "args": {
    "data_dir": "./data",
    "config": "./configs.json",
    "tickers": "all"
  }
}
```

### 每周日晚上执行
```json
{
  "id": "weekly_analysis",
  "name": "周末分析",
  "trigger": "cron", 
  "enabled": true,
  "hour": 20,
  "minute": 0,
  "day_of_week": "6",  // 周日
  "args": {
    "data_dir": "./data",
    "config": "./configs.json",
    "tickers": "all"
  }
}
```

## 部署到生产环境

1. 使用生产环境配置覆盖开发配置
2. 设置适当的资源限制
3. 配置监控和告警
4. 定期备份配置文件和日志