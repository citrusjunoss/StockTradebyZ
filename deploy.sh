#!/bin/bash

# 阿里云镜像仓库配置
REGISTRY_URL="registry.cn-hangzhou.aliyuncs.com"
NAMESPACE="<您的命名空间>"
IMAGE_NAME="stock-trader"
TAG="latest"

echo "开始构建Docker镜像..."
docker build -t ${IMAGE_NAME}:${TAG} .

if [ $? -eq 0 ]; then
    echo "镜像构建成功!"
    
    echo "正在标记镜像..."
    docker tag ${IMAGE_NAME}:${TAG} ${REGISTRY_URL}/${NAMESPACE}/${IMAGE_NAME}:${TAG}
    
    echo "正在推送镜像到阿里云私有仓库..."
    docker push ${REGISTRY_URL}/${NAMESPACE}/${IMAGE_NAME}:${TAG}
    
    if [ $? -eq 0 ]; then
        echo "镜像推送成功!"
        echo "镜像地址: ${REGISTRY_URL}/${NAMESPACE}/${IMAGE_NAME}:${TAG}"
    else
        echo "镜像推送失败!"
        exit 1
    fi
else
    echo "镜像构建失败!"
    exit 1
fi