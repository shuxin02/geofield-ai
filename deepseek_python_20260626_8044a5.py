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

# 尝试导入依赖
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    Document = None

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

st.title("🌍 GeoField AI · 田野访谈编码助手")
st.caption("证据导向型田野资料分析工具 | 支持 TXT / DOCX")

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

# 侧边栏
with st.sidebar:
    st.header("⚙️ 配置")
    api_key = st.text_input("DeepSeek API Key", type="password")
    if api_key:
        st.session_state.api_key = api_key
    
    st.divider()
    if DOCX_AVAILABLE:
        st.success("✅ DOCX支持已启用")
    else:
        st.error("❌ DOCX支持未启用")
        st.info("请确保 requirements.txt 包含 python-docx")

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

# Step 2: 上传文件
if st.session_state.step >= 2:
    st.divider()
    st.header("📂 Step 2: 上传访谈文件")
    
    uploaded_file = st.file_uploader(
        "上传访谈文本文件 (.txt 或 .docx)",
        type=['txt', 'docx']
    )
    
    if uploaded_file:
        filename = uploaded_file.name
        st.session_state.filename = filename
        
        try:
            if filename.endswith('.txt'):
                content = uploaded_file.read().decode('utf-8')
                st.session_state.interview_text = content
                st.success(f"✅ TXT文件读取成功：{len(content)} 字")
                
            elif filename.endswith('.docx'):
                if not DOCX_AVAILABLE:
                    st.error("❌ python-docx未安装，无法读取DOCX文件")
                    st.info("请检查 requirements.txt 是否包含 python-docx")
                else:
                    doc = Document(io.BytesIO(uploaded_file.read()))
                    full_text = []
                    for para in doc.paragraphs:
                        if para.text.strip():
                            full_text.append(para.text.strip())
                    content = '\n'.join(full_text)
                    st.session_state.interview_text = content
                    st.success(f"✅ DOCX文件读取成功：{len(content)} 字")
            
            with st.expander("预览（前300字）"):
                st.text(content[:300] + "..." if len(content) > 300 else content)
            
            if st.button("开始AI分析", type="primary"):
                if not st.session_state.api_key:
                    st.error("⚠️ 请先在侧边栏输入API Key")
                else:
                    st.session_state.step = 3
                    st.rerun()
                    
        except Exception as e:
            st.error(f"文件读取失败：{str(e)}")

# Step 3: AI分析
if st.session_state.step >= 3:
    st.divider()
    st.header("🧠 Step 3: AI分析")
    
    if not st.session_state.analysis_complete:
        with st.spinner("AI分析中..."):
            try:
                prompt = f"""
请分析以下访谈文本，提取关键编码。

研究问题：{st.session_state.research_question}

访谈内容：
{st.session_state.interview_text}

请以JSON数组格式输出，每个对象包含：
- id: 序号
- quote: 原文引用
- ai_code: 建议编码
- memo_hint: 备注提示
- memo_reason: 备注原因
"""

                headers = {
                    "Authorization": f"Bearer {st.session_state.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
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
                    
                    # 清理并解析JSON
                    analysis = analysis.replace('```json', '').replace('```', '').strip()
                    data = json.loads(analysis)
                    
                    df = pd.DataFrame(data)
                    df = df.rename(columns={
                        "id": "ID",
                        "quote": "原文",
                        "ai_code": "AI建议编码",
                        "memo_hint": "AI Memo提示",
                        "memo_reason": "AI Memo说明",
                    })
                    df["研究者编码"] = ""
                    df["研究者Memo"] = ""
                    
                    st.session_state.df = df
                    st.session_state.analysis_complete = True
                    st.session_state.step = 4
                    st.rerun()
                else:
                    st.error(f"API调用失败：{response.text}")
                    
            except Exception as e:
                st.error(f"分析失败：{str(e)}")
    
    else:
        st.success("✅ AI分析完成")
        if st.button("进入编码审核"):
            st.session_state.step = 4
            st.rerun()

# Step 4: 编码审核
if st.session_state.step >= 4 and st.session_state.df is not None:
    st.divider()
    st.header("✏️ Step 4: 编码审核")
    
    edited_df = st.data_editor(
        st.session_state.df,
        column_config={
            "ID": "ID",
            "原文": "原文",
            "AI建议编码": "AI建议编码",
            "研究者编码": st.column_config.TextColumn("研究者编码 ✏️"),
            "研究者Memo": st.column_config.TextColumn("研究者Memo ✏️"),
            "AI Memo提示": "AI Memo提示",
            "AI Memo说明": "AI Memo说明",
        },
        hide_index=True,
        use_container_width=True
    )
    
    st.session_state.df = edited_df
    
    if st.button("📄 生成报告", type="primary"):
        st.session_state.step = 5
        st.rerun()

# Step 5: 报告
if st.session_state.step >= 5 and st.session_state.df is not None:
    st.divider()
    st.header("📄 Step 5: 报告")
    
    df_final = st.session_state.df
    
    # 统计编码
    codebook = df_final[df_final["研究者编码"] != ""]["研究者编码"].value_counts().reset_index()
    if len(codebook) > 0:
        codebook.columns = ["编码", "频次"]
        st.subheader("📊 Codebook")
        st.dataframe(codebook, use_container_width=True)
    
    st.subheader("📋 完整编码表")
    st.dataframe(df_final, use_container_width=True)
    
    # 导出CSV
    csv = df_final.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 下载CSV",
        data=csv,
        file_name=f"GeoFieldAI_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        type="primary"
    )
    
    if st.button("🔄 重新开始"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

st.divider()
st.caption("🌍 GeoField AI")
