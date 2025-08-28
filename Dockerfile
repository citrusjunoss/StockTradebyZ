FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装系统依赖 (移除gcc g++, 仅保留必要依赖)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 复制应用代码
COPY . .

# 生成PWA图标
RUN python create_icons.py

# 创建必要目录
RUN mkdir -p /app/data /app/logs /app/cache

# 复制启动脚本
COPY entrypoint.sh /app/entrypoint.sh

# 设置权限
RUN chmod +x /app/*.py /app/entrypoint.sh

# 暴露Web服务端口
EXPOSE 8080

# 设置入口点
ENTRYPOINT ["/app/entrypoint.sh"]

# 默认运行调度器
CMD ["scheduler"]