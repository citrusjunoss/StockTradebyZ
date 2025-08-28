#!/usr/bin/env python3
"""
生成PWA图标
创建不同尺寸的应用图标
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, output_path):
    """创建指定尺寸的图标"""
    
    # 创建图像
    img = Image.new('RGB', (size, size), color='#007bff')
    draw = ImageDraw.Draw(img)
    
    # 绘制边框
    border_width = max(2, size // 64)
    draw.rectangle([0, 0, size-1, size-1], outline='white', width=border_width)
    
    # 绘制图标内容 - 简单的图表符号
    margin = size // 6
    
    # 绘制柱状图
    bar_width = size // 10
    bar_spacing = size // 12
    max_height = size - 2 * margin
    
    bars = [0.3, 0.7, 0.5, 0.9, 0.4, 0.8]
    start_x = margin
    
    for i, height_ratio in enumerate(bars):
        x = start_x + i * (bar_width + bar_spacing)
        if x + bar_width > size - margin:
            break
            
        bar_height = int(max_height * height_ratio)
        y = size - margin - bar_height
        
        # 绘制柱子
        draw.rectangle([x, y, x + bar_width, size - margin], fill='white')
        draw.rectangle([x, y, x + bar_width, size - margin], outline='#0056b3', width=1)
    
    # 绘制标题文字（仅对较大尺寸）
    if size >= 128:
        try:
            font_size = max(12, size // 20)
            # 使用默认字体
            font = ImageFont.load_default()
            
            # 绘制标题
            text = "股选"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (size - text_width) // 2
            y = margin // 2
            
            draw.text((x, y), text, fill='white', font=font)
            
        except:
            # 如果字体加载失败，跳过文字
            pass
    
    # 保存图像
    img.save(output_path, 'PNG')
    print(f'创建图标: {output_path} ({size}x{size})')

def main():
    """主函数"""
    
    # 图标尺寸列表
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    # 创建图标目录
    icons_dir = 'static/icons'
    os.makedirs(icons_dir, exist_ok=True)
    
    # 生成各种尺寸的图标
    for size in sizes:
        output_path = os.path.join(icons_dir, f'icon-{size}x{size}.png')
        create_icon(size, output_path)
    
    # 创建快捷方式图标（简化版）
    shortcuts = [
        ('shortcut-today.png', '今'),
        ('shortcut-stats.png', '统'),
        ('shortcut-search.png', '搜')
    ]
    
    for filename, text in shortcuts:
        img = Image.new('RGB', (96, 96), color='#28a745')
        draw = ImageDraw.Draw(img)
        
        # 绘制边框
        draw.rectangle([0, 0, 95, 95], outline='white', width=2)
        
        # 绘制文字
        try:
            font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (96 - text_width) // 2
            y = (96 - text_height) // 2
            
            draw.text((x, y), text, fill='white', font=font)
        except:
            pass
        
        output_path = os.path.join(icons_dir, filename)
        img.save(output_path, 'PNG')
        print(f'创建快捷方式图标: {output_path}')
    
    print('所有图标创建完成!')

if __name__ == '__main__':
    main()