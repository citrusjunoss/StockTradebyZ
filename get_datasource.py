#!/usr/bin/env python3
"""
获取当前数据源配置的工具模块
"""

import os
import json
from pathlib import Path

DEFAULT_DATASOURCE = "akshare"
CONFIG_FILE = "datasource_config.json"

def get_current_datasource() -> str:
    """获取当前配置的数据源"""
    # 1. 优先从环境变量读取
    datasource = os.getenv('STOCK_DATASOURCE')
    if datasource:
        return datasource.lower()
    
    # 2. 从配置文件读取
    config_path = Path(CONFIG_FILE)
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('datasource', DEFAULT_DATASOURCE).lower()
        except Exception:
            pass
    
    # 3. 返回默认值
    return DEFAULT_DATASOURCE

def set_current_datasource(datasource: str) -> None:
    """设置当前数据源并保存到配置文件"""
    config = {'datasource': datasource.lower()}
    config_path = Path(CONFIG_FILE)
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"已设置数据源为: {datasource}")
    except Exception as e:
        print(f"保存数据源配置失败: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 设置数据源
        new_datasource = sys.argv[1]
        if new_datasource.lower() in ['akshare', 'tushare', 'mootdx']:
            set_current_datasource(new_datasource)
        else:
            print(f"不支持的数据源: {new_datasource}")
            print("支持的数据源: akshare, tushare, mootdx")
    else:
        # 显示当前数据源
        current = get_current_datasource()
        print(f"当前数据源: {current}")