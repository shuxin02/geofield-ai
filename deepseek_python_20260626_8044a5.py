# app.py
import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import io
import re
from collections import Counter

# 导入docx处理 - 修复了导入方式
try:
    import docx
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    Document = None
    docx = None

# 导入可视化
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
    from wordcloud import WordCloud
    import numpy as np
    VIZ_AVAILABLE = True
except ImportError:
    VIZ_AVAILABLE = False
    plt = None
    WordCloud = None
    np = None

# 页面配置
st.set_page_config(
    page_title="GeoField AI - 田野访谈编码助手",
    page_icon="🌍",
    layout="wide"
)

# 标题
st.title("🌍 GeoField AI · 田野访谈编码助手")
st.caption("证据导向型田野资料分析工具 | 支持 TXT / DOCX")

# 检查依赖
if not DOCX_AVAILABLE:
    st.sidebar.error("⚠️ python-docx 未安装，无法读取DOCX文件")
else:
    st.sidebar.success("✅ python-docx 已加载")

# 初始化session state
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'research_question' not in st.session_state:
    st.session_state.research_question = ""
if 'interview_text' not in st.session_state:
    st.session_state.interview_text = ""
if 'filename' not in st.session_state:
    st.session_state.filename = ""
if 'analysis_data' not in st.session_state:
    st.session_state.analysis_data = None
if 'df' not in st.session_state:
    st.session_state.df = None
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""
if 'has_images' not in st.session_state:
    st.session_state.has_images = False

# 侧边栏 - API配置
with st.sidebar:
    st.header("⚙️ 配置")
    
    api_key = st.text_input(
        "DeepSeek API Key",
        type="password",
        help="请输入您的DeepSeek API Key",
        value=st.session_state.api_key
    )
    if api_key:
        st.session_state.api_key = api_key
    
    st.divider()
    
    st.subheader("📊 进度")
    steps = ["1. 研究问题", "2. 上传访谈", "3. AI分析", "4. 编码审核", "5. 导出报告"]
    current_step = st.session_state.step
    for i, step in enumerate(steps, 1):
        if i < current_step:
            st.success(f"✅ {step}")
        elif i == current_step:
            st.info(f"🔄 {step}")
        else:
            st.text(f"⏳ {step}")

# ==================== 文本提取函数 ====================
def extract_text_from_txt(file):
    """从TXT文件提取文本"""
    try:
        # 重置文件指针到开始
        file.seek(0)
        content = file.read().decode('utf-8')
        return content, False
    except UnicodeDecodeError:
        try:
            file.seek(0)
            content = file.read().decode('gbk')
            return content, False
        except:
            raise ValueError("无法解码文件，请确保文件是UTF-8或GBK编码")

def extract_text_from_docx(file):
    """从DOCX文件提取文本（忽略图片）"""
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx库未安装，请检查requirements.txt")
    
    try:
        # 重置文件指针到开始
        file.seek(0)
        # 读取文件内容
        doc = Document(io.BytesIO(file.read()))
        
        # 提取所有段落文本
        full_text = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                full_text.append(text)
        
        # 提取表格中的文本
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    text = cell.text.strip()
                    if text:
                        row_text.append(text)
                if row_text:
                    full_text.append(' | '.join(row_text))
        
        # 检查是否有图片
        has_images = False
        try:
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    has_images = True
                    break
        except:
            pass
        
        text = '\n'.join(full_text)
        
        if not text.strip():
            raise ValueError("文档中没有提取到文本内容")
        
        return text, has_images
        
    except Exception as e:
        raise ValueError(f"读取DOCX文件失败: {str(e)}")

def extract_text(file, filename):
    """根据文件类型提取文本"""
    try:
        if filename.lower().endswith('.txt'):
            return extract_text_from_txt(file)
        elif filename.lower().endswith('.docx'):
            return extract_text_from_docx(file)
        else:
            raise ValueError(f"不支持的文件格式: {filename}")
    except Exception as e:
        raise

# ==================== 可视化函数 ====================
def create_code_chart(codebook_df):
    """创建编码分类统计图表"""
    if not VIZ_AVAILABLE or plt is None:
        return None
    
    try:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        colors = plt.cm.Set3(range(len(codebook_df)))
        bars = ax1.bar(codebook_df['编码'], codebook_df['频次'], color=colors)
        ax1.set_title('编码频次分布', fontsize=14, fontweight='bold')
        ax1.set_xlabel('编码类别', fontsize=12)
        ax1.set_ylabel('频次', fontsize=12)
        ax1.tick_params(axis='x', rotation=45)
        
        for bar, value in zip(bars, codebook_df['频次']):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{value}', ha='center', va='bottom', fontsize=10)
        
        if len(codebook_df) <= 10:
            ax2.pie(
                codebook_df['频次'], 
                labels=codebook_df['编码'],
                autopct='%1.1f%%',
                colors=colors
            )
            ax2.set_title('编码占比分布', fontsize=14, fontweight='bold')
        else:
            ax2.text(0.5, 0.5, f'编码类别较多\n({len(codebook_df)}类)',
                    ha='center', va='center', fontsize=12)
            ax2.set_title('编码占比分布', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        return fig
    except Exception as e:
        return None

def create_wordcloud(text):
    """创建词云图"""
    if not VIZ_AVAILABLE or WordCloud is None:
        return None
    
    if not text or len(text) < 10:
        return None
    
    try:
        words = re.findall(r'[\u4e00-\u9fff]+', text)
        word_freq = Counter(words)
        
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '来'}
        
        word_freq_filtered = {w: f for w, f in word_freq.items() if len(w) > 1 and w not in stopwords}
        
        if not word_freq_filtered:
            return None
        
        wordcloud = WordCloud(
            font_path=None,
            width=800,
            height=400,
            background_color='white',
            max_words=100,
            relative_scaling=0.5,
            colormap='viridis'
        ).generate_from_frequencies(word_freq_filtered)
        
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.axis('off')
        ax.set_title('访谈文本词云', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        return fig
    except Exception as e:
        return None

# ==================== UI 主流程 ====================

# Step 1: 研究问题
st.header("📌 Step 1: 输入研究问题")

research_question = st.text_area(
    "请输入研究问题",
    value=st.session_state.research_question,
    placeholder="例如：本地居民如何感知乡村旅游发展带来的社区变化？",
    height=100
)

if st.button("确认研究问题", type="primary"):
    if research_question.strip():
        st.session_state.research_question = research_question.strip()
        st.session_state.step = 2
        st.rerun()
    else:
        st.warning("请输入研究问题")

# Step 2: 上传访谈文件
if st.session_state.step >= 2:
    st.divider()
    st.header("📂 Step 2: 上传访谈文件")
    
    uploaded_file = st.file_uploader(
        "上传访谈文本文件 (.txt 或 .docx)",
        type=['txt', 'docx'],
        help="支持UTF-8编码的txt文件或docx文件。注意：docx中的图片将被忽略。"
    )
    
    if uploaded_file:
        try:
            filename = uploaded_file.name
            st.session_state.filename = filename
            
            # 显示文件信息
            file_size = uploaded_file.size / 1024  # KB
            st.info(f"📄 文件: {filename} ({file_size:.1f} KB)")
            
            # 提取文本
            with st.spinner("正在读取文件..."):
                text, has_images = extract_text(uploaded_file, filename)
            
            st.session_state.interview_text = text
            st.session_state.has_images = has_images
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.success(f"✔ 文件读取成功")
            with col2:
                st.info(f"📏 字数：{len(text)}")
            with col3:
                if has_images:
                    st.warning("🖼️ 检测到图片，已忽略")
            
            with st.expander("📄 数据预览（前300字）"):
                preview = text[:300] + "..." if len(text) > 300 else text
                st.text(preview)
            
            # 词云预览
            if VIZ_AVAILABLE and len(text) > 100:
                if st.checkbox("显示访谈文本词云"):
                    wordcloud_fig = create_wordcloud(text)
                    if wordcloud_fig:
                        st.pyplot(wordcloud_fig)
                    else:
                        st.info("词云生成失败，文本内容可能不足")
            
            if st.button("开始AI分析", type="primary"):
                if not st.session_state.api_key:
                    st.error("⚠️ 请先在侧边栏输入DeepSeek API Key")
                else:
                    st.session_state.step = 3
                    st.rerun()
                    
        except Exception as e:
            st.error(f"文件读取失败：{str(e)}")
            st.info("💡 提示：如果是DOCX文件，请确保文件格式正确且未被损坏")

# Step 3: AI分析
if st.session_state.step >= 3:
    st.divider()
    st.header("🧠 Step 3: AI分析")
    
    if not st.session_state.analysis_complete:
        with st.spinner("AI分析中，请稍候..."):
            try:
                # 构建Prompt（这里省略了完整prompt，你需要补全）
                prompt = f"""
# GeoField AI V2：证据导向型田野资料分析 Prompt

你是一名具有人文地理学、民族志研究和定性研究经验的研究助手。

请根据研究问题分析访谈资料。

分析时必须严格遵守以下原则：

1. 所有分析必须基于访谈原文
2. 不得推测受访者未明确表达的内容
3. 不得根据常识补充受访者的动机、情感、价值观和社会背景
4. 不得为了丰富分析而强行引入理论概念
5. 如果资料不足，请明确写出：【资料不足，无法判断】
6. 优先保证分析的真实性，而非丰富性

请严格按照JSON格式输出，不要输出Markdown，不要输出解释，不要输出```json。

输出必须是一个JSON数组，数组中的每一个对象代表一条事实编码。

每个对象必须包含以下字段：id, quote, ai_code, memo_hint, memo_reason

研究问题：
{st.session_state.research_question}

访谈内容：
{st.session_state.interview_text}
"""

                # 调用API
                headers = {
                    "Authorization": f"Bearer {st.session_state.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
                
                response = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120
                )
                
                if response.status_code == 200:
                    result = response.json()
                    analysis = result["choices"][0]["message"]["content"]
                    
                    # 解析JSON
                    data = json.loads(analysis)
                    st.session_state.analysis_data = data
                    
                    # 创建DataFrame
                    df = pd.DataFrame(data)
                    df = df.rename(columns={
                        "id": "ID",
                        "quote": "原文",
                        "ai_code": "AI建议编码",
                        "memo_hint": "AI Memo提示",
                        "memo_reason": "AI Memo说明",
                    })
                    
                    df.insert(df.columns.get_loc("AI建议编码") + 1, "研究者编码", "")
                    df["研究者Memo"] = ""
                    
                    st.session_state.df = df
                    st.session_state.analysis_complete = True
                    st.session_state.step = 4
                    st.rerun()
                    
                else:
                    st.error(f"API调用失败 (HTTP {response.status_code})：{response.text}")
                    
            except json.JSONDecodeError as e:
                st.error(f"JSON解析失败：{e}")
            except Exception as e:
                st.error(f"分析失败：{e}")
    
    else:
        st.success("✅ AI分析已完成！")
        if st.button("进入编码审核"):
            st.session_state.step = 4
            st.rerun()

# Step 4: 编码审核（省略详细代码，同之前）
if st.session_state.step >= 4 and st.session_state.df is not None:
    st.divider()
    st.header("✏️ Step 4: 编码审核")
    st.info("编辑下方表格中的「研究者编码」和「研究者Memo」")
    
    df = st.session_state.df.copy()
    
    edited_df = st.data_editor(
        df,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "原文": st.column_config.TextColumn("原文", width="large"),
            "AI建议编码": st.column_config.TextColumn("AI建议编码", width="medium"),
            "研究者编码": st.column_config.TextColumn("研究者编码 ✏️", width="medium"),
            "研究者Memo": st.column_config.TextColumn("研究者Memo ✏️", width="large"),
            "AI Memo提示": st.column_config.TextColumn("AI Memo提示", width="medium"),
            "AI Memo说明": st.column_config.TextColumn("AI Memo说明", width="medium"),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic"
    )
    
    st.session_state.df = edited_df
    
    if st.button("📄 生成正式报告", type="primary"):
        st.session_state.step = 5
        st.rerun()

# Step 5: 生成报告
if st.session_state.step >= 5 and st.session_state.df is not None:
    st.divider()
    st.header("📄 Step 5: 正式报告")
    
    df_final = st.session_state.df.copy()
    st.success("✅ 报告生成完成！")
    
    # 显示报告预览
    st.dataframe(df_final, use_container_width=True)
    
    # 下载按钮
    csv = df_final.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 下载CSV报告",
        data=csv,
        file_name=f"GeoFieldAI_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        type="primary"
    )
    
    if st.button("🔄 重新开始"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# 页脚
st.divider()
st.caption("🌍 GeoField AI v0.2 · 支持 TXT/DOCX · 词云与可视化")
