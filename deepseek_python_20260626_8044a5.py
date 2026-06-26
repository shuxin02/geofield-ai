# app.py
import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import re
from collections import Counter

# 尝试导入可视化（可选）
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
st.caption("证据导向型田野资料分析工具 | 支持 TXT 文件")

# 初始化session state
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'research_question' not in st.session_state:
    st.session_state.research_question = ""
if 'interview_text' not in st.session_state:
    st.session_state.interview_text = ""
if 'filename' not in st.session_state:
    st.session_state.filename = ""
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
    st.info("📌 当前仅支持 TXT 文件")
    if VIZ_AVAILABLE:
        st.success("✅ 可视化支持已启用")

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
        "上传访谈文本文件 (.txt)",
        type=['txt'],
        help="请上传UTF-8编码的txt文件"
    )
    
    if uploaded_file:
        filename = uploaded_file.name
        st.session_state.filename = filename
        
        try:
            # 尝试UTF-8解码
            try:
                content = uploaded_file.read().decode('utf-8')
            except UnicodeDecodeError:
                # 如果UTF-8失败，尝试GBK
                uploaded_file.seek(0)
                content = uploaded_file.read().decode('gbk')
            
            st.session_state.interview_text = content
            st.success(f"✅ 文件读取成功：{len(content)} 字")
            
            with st.expander("📄 预览（前300字）"):
                preview = content[:300] + "..." if len(content) > 300 else content
                st.text(preview)
            
            # 词云预览
            if VIZ_AVAILABLE and len(content) > 100:
                if st.checkbox("显示词云"):
                    try:
                        words = re.findall(r'[\u4e00-\u9fff]+', content)
                        word_freq = Counter(words)
                        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '来'}
                        word_freq_filtered = {w: f for w, f in word_freq.items() if len(w) > 1 and w not in stopwords}
                        
                        if word_freq_filtered:
                            wordcloud = WordCloud(
                                width=800, height=400,
                                background_color='white',
                                max_words=100,
                                colormap='viridis'
                            ).generate_from_frequencies(word_freq_filtered)
                            
                            fig, ax = plt.subplots(figsize=(10, 5))
                            ax.imshow(wordcloud, interpolation='bilinear')
                            ax.axis('off')
                            st.pyplot(fig)
                    except Exception as e:
                        st.info(f"词云生成失败：{str(e)}")
            
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
        with st.spinner("AI分析中，请稍候..."):
            try:
                prompt = f"""
# GeoField AI：田野资料编码分析

请根据研究问题分析访谈文本，提取关键编码。

## 分析原则
1. 所有分析必须基于访谈原文
2. 不得推测受访者未明确表达的内容
3. 如果资料不足，请明确写出：【资料不足，无法判断】

## 输出格式
请以JSON数组格式输出，每个对象包含：
- id: 序号（从1开始）
- quote: 原文引用
- ai_code: 建议编码
- memo_hint: 备注提示（若无则留空）
- memo_reason: 备注原因（若无则留空）

## 研究问题
{st.session_state.research_question}

## 访谈内容
{st.session_state.interview_text}

请直接输出JSON数组，不要有其他文字。
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
                    
            except json.JSONDecodeError as e:
                st.error(f"JSON解析失败：{str(e)}")
                st.text("原始响应：")
                st.code(analysis if 'analysis' in locals() else "无响应")
            except Exception as e:
                st.error(f"分析失败：{str(e)}")
    
    else:
        st.success("✅ AI分析完成！")
        if st.button("进入编码审核"):
            st.session_state.step = 4
            st.rerun()

# Step 4: 编码审核
if st.session_state.step >= 4 and st.session_state.df is not None:
    st.divider()
    st.header("✏️ Step 4: 编码审核")
    
    st.info("💡 在「研究者编码」和「研究者Memo」列中填写您的内容")
    
    df = st.session_state.df
    
    # 统计
    total = len(df)
    coded = df[df["研究者编码"] != ""].shape[0]
    col1, col2, col3 = st.columns(3)
    col1.metric("总编码", total)
    col2.metric("已审核", coded)
    col3.metric("待审核", total - coded)
    
    st.divider()
    
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
        use_container_width=True
    )
    
    st.session_state.df = edited_df
    
    if st.button("📄 生成报告", type="primary"):
        st.session_state.step = 5
        st.rerun()

# Step 5: 报告
if st.session_state.step >= 5 and st.session_state.df is not None:
    st.divider()
    st.header("📄 Step 5: 正式报告")
    
    df_final = st.session_state.df
    
    # Codebook
    codebook_df = df_final[df_final["研究者编码"] != ""]
    if len(codebook_df) > 0:
        codebook = codebook_df["研究者编码"].value_counts().reset_index()
        codebook.columns = ["编码", "频次"]
        codebook["占比"] = (codebook["频次"] / codebook["频次"].sum() * 100).round(1).astype(str) + "%"
        
        st.subheader("📊 Codebook")
        st.dataframe(codebook, use_container_width=True, hide_index=True)
        
        # 可视化图表
        if VIZ_AVAILABLE:
            try:
                fig, ax = plt.subplots(figsize=(10, 6))
                colors = plt.cm.Set3(range(len(codebook)))
                bars = ax.bar(codebook['编码'], codebook['频次'], color=colors)
                ax.set_title('编码频次分布', fontsize=14, fontweight='bold')
                ax.set_xlabel('编码类别')
                ax.set_ylabel('频次')
                ax.tick_params(axis='x', rotation=45)
                
                for bar, value in zip(bars, codebook['频次']):
                    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                           f'{value}', ha='center', va='bottom')
                
                st.pyplot(fig)
            except Exception as e:
                st.info(f"图表生成失败：{str(e)}")
    
    # 完整表格
    st.subheader("📋 完整编码记录")
    st.dataframe(df_final, use_container_width=True)
    
    # 导出
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

st.divider()
st.caption("🌍 GeoField AI v0.1 · 支持 TXT 文件")
