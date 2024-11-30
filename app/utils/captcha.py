import colorsys

from PIL import Image, ImageDraw, ImageFont
import random
import string
import os
import io

def generate_captcha():
    # 调整图片尺寸和字体大小
    width = 130  # 增加宽度
    height = 45  # 增加高度
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # 生成随机字符
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    # 使用更大的字体
    font_size = 35  # 增加字体大小
    font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'default.otf')
    font = ImageFont.truetype(font_path, font_size)
    
    # 添加背景干扰
    for i in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill=(220, 220, 220))
    
    # 绘制文字
    for i, char in enumerate(chars):
        x = 20 + i * 30  # 调整字符间距
        y = random.randint(5, 10)  # 调整垂直位置范围
        # 随机颜色，将RGB值转换为0-255的整数范围
        r, g, b = colorsys.hsv_to_rgb(random.randint(190, 220) / 360.0, random.randint(30, 60) / 100.0, random.randint(70, 90) / 100.0)
        color = (int(r * 255), int(g * 255), int(b * 255))
        draw.text((x, y), char, font=font, fill=color)
    
    # 转换为字节流
    byte_io = io.BytesIO()
    image.save(byte_io, 'PNG')
    byte_io.seek(0)
    
    return byte_io, chars 