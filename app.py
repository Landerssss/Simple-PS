import streamlit as st
from streamlit_drawable_canvas import st_canvas
import easyocr
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io

# 初始化 OCR 读取器 (只加载一次，缓存)
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ch_sim', 'en']) # 支持简体中文和英文

reader = load_ocr()

def get_dominant_color(image_crop):
    """简易提取图片主色调作为文字颜色"""
    # 将图片转为RGB数组
    data = np.reshape(image_crop, (-1, 3))
    data = np.float32(data)
    
    # 简单的K-means聚类找出中心颜色，假设文字颜色和背景色差异大
    # 这里为了简易，直接取图片中心点的颜色，或者用户手动调整
    # 更高级的做法是先二值化把文字扣出来，再取文字像素的平均色
    h, w, _ = image_crop.shape
    center_color = image_crop[h//2, w//2]
    return tuple(map(int, center_color))

def inpaint_text_area(image_np, box):
    """自动擦除指定区域的文字"""
    x, y, w, h = box
    mask = np.zeros(image_np.shape[:2], dtype="uint8")
    # 创建掩膜
    cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
    # 使用OpenCV的修复算法 (Telea算法)
    inpainted = cv2.inpaint(image_np, mask, 3, cv2.INPAINT_TELEA)
    return inpainted

st.title("🎨 AI 简易文字P图工具")
st.markdown("上传图片 -> 框选文字区域 -> 输入新文字 -> 自动替换")

uploaded_file = st.file_uploader("选择一张图片", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    # 1. [...](asc_slot://start-slot-3)读取并显示图片
    image = Image.open(uploaded_file).convert("RGB")
    img_width, img_height = image.size
    
    # 防止图片过大，缩放显示
    canvas_width = 700
    canvas_height = int(img_height * (canvas_width / img_width))
    
    st.write("### 第一步：请在下方框选要修改的文字区域")
    
    # 2. 交互式画板
    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",  # 填充色
        stroke_width=2,
        background_image=image,
        update_streamlit=True,
        height=canvas_height,
        width=canvas_width,
        drawing_mode="rect", # 矩形框选模式
        key="canvas",
    )

    # 3. 处理选区
    if canvas_result.json_data is not None:
        objects = canvas_result.json_data["objects"]
        
        if len(objects) > 0:
            # 获取最后一个框选的坐标（按比例还原到原图尺寸）
            obj = objects[-1]
            scale_x = img_width / canvas_width
            scale_y = img_height / canvas_height
            
            x = int(obj["left"] * scale_x)
            y = int(obj["top"] * scale_y)
            w = int(obj["width"] * scale_x)
            h = int(obj["height"] * scale_y)
            
            # 裁剪出该区域
            roi = np.array(image)[y:y+h, x:x+w]
            
            st.write("---")
            col1, col2 = st.columns(2)
            with col1:
                st.image(roi, caption="选定区域")
            
            # 4. 自动识别：OCR与样式
            with st.spinner('正在分析文字样式...'):
                # 识别文字内容
                ocr_result = reader.readtext(roi)
                detected_text = ocr_result[0][1] if ocr_result else ""
                
                # 估算颜色 (这里简化为取中心点颜色，实际需更复杂算法)
                # 估算字号 (高度的80%作为字号)
                est_font_size = int(h * 0.8)
                est_color = get_dominant_color(roi)
            
            with col2:
                st.info(f"原文字: {detected_text}")
                new_text = st.text_input("输入新文字:", value=detected_text)
                
                # 样式微调面板
                st.markdown("#### 样式微调")
                font_size = st.number_input("字号 (px)", value=est_font_size)
                # 颜色选择器
                color_hex = '#{:02x}{:02x}{:02x}'.format(*est_color)
                picked_color = st.color_picker("文字颜色", value=color_hex)

            
            if st.button("开始替换"):
                # 5. 执行替换
                img_np = np.array(image)
                
                # A. 擦除原文字 (Inpainting)
                # 扩大一点擦除范围以覆盖边缘
                pad = 2
                clean_img_np = inpaint_text_area(img_np, (x-pad, y-pad, w+pad*2, h+pad*2))
                
                # [...](asc_slot://start-slot-5)B. 绘制新文字 (PIL)
                clean_pil = Image.fromarray(clean_img_np)
                draw = ImageDraw.Draw(clean_pil)
                
                # 加载字体 (注意：实际部署需要提供字体文件路径，这里使用默认或系统字体)
                # 为了演示效果，建议你在同目录下放一个 'arial.ttf' 或 'simhei.ttf'
                try:
                    # 尝试加载常用中文字体，Windows/Linux路径不同，这里需根据环境调整
                    # 这是一个简单的 fallback 逻辑
                    font_path = "simhei.ttf" # 请确保目录下有这个字体文件，否则会报错或退回默认
                    font = ImageFont.truetype(font_path, int(font_size))
                except:
                    # 如果找不到字体，使用默认 (不支持中文)
                    font = ImageFont.load_default()
                    st.warning("未找到中文字体文件，使用默认字体（可能无法显示中文）。请将 .ttf 字体文件放入根目录。")

                # 计算文字位置居中
                # text_bbox = draw.textbbox((0, 0), new_text, font=font) # PIL > 8.0.0
                # text_w = text_bbox[2] - text_bbox[0]
                # text_h = text_bbox[3] - text_bbox[1]
                # 简易居中计算
                draw_x = x 
                draw_y = y - (font_size * 0.1) # 微调基线

                # 转换颜色 hex -> rgb
                c_r = int(picked_color[1:3], 16)
                c_g = int(picked_color[3:5], 16)
                c_b = int(picked_color[5:7], 16)
                
                draw.text((draw_x, draw_y), new_text, font=font, fill=(c_r, c_g, c_b))
                
                # 6. 显示结果
                st.image(clean_pil, caption="处理结果", use_column_width=True)

