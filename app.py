import streamlit as st
from streamlit_drawable_canvas import st_canvas
import easyocr
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import glob
import os

# 设置页面配置，解决一些显示问题
st.set_page_config(page_title="AI 简易P图工具", layout="centered")

# 初始化 OCR 读取器 (只加载一次)
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ch_sim', 'en'])

reader = load_ocr()

def get_dominant_color(image_crop):
    """简易提取图片主色调"""
    if image_crop.size == 0: return (0, 0, 0)
    # 取中心点颜色作为文字颜色
    h, w, _ = image_crop.shape
    center_color = image_crop[h//2, w//2]
    return tuple(map(int, center_color))

def inpaint_text_area(image_np, box):
    """自动擦除指定区域"""
    x, y, w, h = box
    mask = np.zeros(image_np.shape[:2], dtype="uint8")
    cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
    # 使用 Telea 算法修复
    inpainted = cv2.inpaint(image_np, mask, 3, cv2.INPAINT_TELEA)
    return inpainted

st.title("🎨 AI 简易文字P图工具 (修复版)")
st.markdown("上传图片 -> 框选文字 -> 输入新内容 -> 自动替换")

uploaded_file = st.file_uploader("选择一张图片", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    # 1. 读取并显示图片
    image = Image.open(uploaded_file).convert("RGB")
    img_width, img_height = image.size
    
    # 防止图片过大，缩放显示
    canvas_width = 700
    canvas_height = int(img_height * (canvas_width / img_width))
    
    st.info("👇 请在下方直接框选你要修改的文字区域：")
    
    # 2. 交互式画板
    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",
        stroke_width=2,
        background_image=image,
        update_streamlit=True,
        height=canvas_height,
        width=canvas_width,
        drawing_mode="rect",
        key="canvas",
    )

    # 3. 处理选区
    if canvas_result.json_data is not None:
        objects = canvas_result.json_data["objects"]
        
        if len(objects) > 0:
            # 获取最后一个框选的坐标
            obj = objects[-1]
            scale_x = img_width / canvas_width
            scale_y = img_height / canvas_height
            
            x = int(obj["left"] * scale_x)
            y = int(obj["top"] * scale_y)
            w = int(obj["width"] * scale_x)
            h = int(obj["height"] * scale_y)
            
            # 裁剪出该区域
            roi = np.array(image)[y:y+h, x:x+w]
            
            if roi.size > 0:
                st.write("---")
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.image(roi, caption="选定区域")
                
                # 4. 自动识别：OCR与样式
                with st.spinner('正在分析文字...'):
                    # 识别文字
                    ocr_result = reader.readtext(roi)
                    detected_text = ocr_result[0][1] if ocr_result else ""
                    
                    # 估算样式
                    est_font_size = int(h * 0.8) # 默认字号为框高度的80%
                    est_color = get_dominant_color(roi)
                
                with col2:
                    st.success(f"识别到文字: {detected_text}")
                    new_text = st.text_input("输入新文字:", value=detected_text)
                    
                    st.markdown("#### 🎨 样式微调")
                    c1, c2 = st.columns(2)
                    with c1:
                        font_size = st.number_input("字号 (px)", value=est_font_size)
                    with c2:
                        color_hex = '#{:02x}{:02x}{:02x}'.format(*est_color)
                        picked_color = st.color_picker("文字颜色", value=color_hex)
                
                # 5. 执行替换按钮
                if st.button("✨ 立即替换", type="primary"):
                    img_np = np.array(image)
                    
                    # A. 擦除原文字
                    pad = 2 #稍微多擦一点边缘
                    clean_img_np = inpaint_text_area(img_np, (x-pad, y-pad, w+pad*2, h+pad*2))
                    
                    # B. 绘制新文字
                    clean_pil = Image.fromarray(clean_img_np)
                    draw = ImageDraw.Draw(clean_pil)
                    
                    # --- 自动寻找字体文件 (关键修复) ---
                    # 查找当前目录下所有的 .ttf 或 .otf 文件
                    font_files = glob.glob("*.ttf") + glob.glob("*.otf") + glob.glob("*.ttc")
                    
                    selected_font = None
                    if font_files:
                        try:
                            # 优先使用第一个找到的字体
                            font_path = font_files[0]
                            selected_font = ImageFont.truetype(font_path, int(font_size))
                            st.toast(f"✅ 已加载字体: {font_path}") # 提示用户用的是哪个字体
                        except Exception as e:
                            st.error(f"字体加载失败: {e}")
                    
                    if selected_font is None:
                        st.error("⚠️ 未找到任何中文字体文件！文字将无法显示或显示乱码。请确保目录下有 .ttf 文件。")
                        selected_font = ImageFont.load_default()
                    
                    # 计算颜色
                    c_r = int(picked_color[1:3], 16)
                    c_g = int(picked_color[3:5], 16)
                    c_b = int(picked_color[5:7], 16)
                    
                    # 绘制
                    draw_y = y - (font_size * 0.15) # 稍微向上修正基线
                    draw.text((x, draw_y), new_text, font=selected_font, fill=(c_r, c_g, c_b))
                    
                    # 6. 显示最终大图
                    st.write("### 🎉 处理结果")
                    # 修复 use_column_width 警告，改用 use_container_width
                    st.image(clean_pil, caption="右键可另存为图片", use_container_width=True)

