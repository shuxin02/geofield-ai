# app.py - 最终稳定版
import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import re
from collections import Counter

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
if 'row_status' not in st.session_state:
    st.session_state.row_status = {}

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("⚙️ 配置")
    api_key = st.text_input("DeepSeek API Key", type="password")
    if api_key:
        st.session_state.api_key = api_key
    
    st.divider()
    
    st.subheader("📊 进度")
    steps = [
        ("1. 研究问题", 1),
        ("2. 上传访谈", 2),
        ("3. AI分析", 3),
        ("4. 编码审核", 4),
        ("5. 导出报告", 5)
    ]
    
    current_step = st.session_state.step
    for step_name, step_num in steps:
        if step_num < current_step:
            st.success(f"✅ {step_name}")
        elif step_num == current_step:
            st.info(f"🔄 {step_name}")
        else:
            st.text(f"⏳ {step_name}")
    
    st.divider()
    st.info("📌 支持 TXT 文件")

# ==================== Step 1: 研究问题 ====================
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

# ==================== Step 2: 上传文件 ====================
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
            try:
                content = uploaded_file.read().decode('utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                content = uploaded_file.read().decode('gbk')
            
            st.session_state.interview_text = content
            st.success(f"✅ 文件读取成功：{len(content)} 字")
            
            with st.expander("📄 预览（前300字）"):
                preview = content[:300] + "..." if len(content) > 300 else content
                st.text(preview)
            
            if st.button("开始AI分析", type="primary"):
                if not st.session_state.api_key:
                    st.error("⚠️ 请先在侧边栏输入API Key")
                else:
                    st.session_state.step = 3
                    st.rerun()
                    
        except Exception as e:
            st.error(f"文件读取失败：{str(e)}")

# ==================== Step 3: AI分析 ====================
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
4. **【重要】Memo_hint 和 memo_reason 仅在以下情况填写：**
   - 该段落包含多个层次的含义，需要进一步分析
   - 该段落与其他段落存在潜在关联，值得标记
   - 该段落揭示了超出表面含义的深层逻辑
   - 其他情况，请留空字符串 ""
5. **不要**为每个条目都生成Memo，仅在真正有价值时才填写

## 输出格式
请以JSON数组格式输出，每个对象包含：
- id: 序号（从1开始）
- quote: 原文引用
- ai_code: 建议编码（简洁的关键词）
- memo_hint: 备注提示（仅在真正有价值时填写，否则留空）
- memo_reason: 备注原因（仅在真正有价值时填写，否则留空）

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
                    timeout=180
                )
                
                if response.status_code == 200:
                    result = response.json()
                    analysis = result["choices"][0]["message"]["content"]
                    
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
                    
                    column_order = ["ID", "原文", "AI建议编码", "研究者编码", "AI Memo提示", "AI Memo说明", "研究者Memo"]
                    df = df[column_order]
                    
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

# ==================== Step 4: 编码审核 ====================
if st.session_state.step >= 4 and st.session_state.df is not None:
    st.divider()
    st.header("✏️ Step 4: 编码审核")
    
    df = st.session_state.df.copy()
    
    for idx in df.index:
        if idx not in st.session_state.row_status:
            st.session_state.row_status[idx] = "待审核"
    
    total = len(df)
    coded = df[df["研究者编码"] != ""].shape[0]
    deleted = sum(1 for status in st.session_state.row_status.values() if status == "已删除")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总编码", total)
    col2.metric("已审核", coded)
    col3.metric("待审核", total - coded - deleted)
    col4.metric("已删除", deleted)
    
    st.divider()
    
    for idx, row in df.iterrows():
        status = st.session_state.row_status.get(idx, "待审核")
        
        with st.container():
            if status == "已删除":
                st.markdown(f"~~**[{row['ID']}]** {row['原文'][:150]}...~~")
                st.caption(f"AI建议: {row['AI建议编码']} | 状态: ❌ 已删除")
                st.divider()
                continue
            
            col_left, col_right = st.columns([3, 1])
            
            with col_left:
                st.markdown(f"**[{row['ID']}]** {row['原文'][:150]}...")
                st.caption(f"AI建议编码: {row['AI建议编码']}")
                
                current_code = df.at[idx, "研究者编码"]
                if current_code and str(current_code) != "":
                    st.success(f"研究者编码: {current_code}")
                else:
                    st.info("等待编码...")
                
                if row.get("AI Memo提示") and str(row["AI Memo提示"]) != "" and str(row["AI Memo提示"]) != "nan":
                    st.caption(f"💡 Memo提示: {row['AI Memo提示']}")
            
            with col_right:
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                
                with btn_col1:
                    if st.button(f"✅ 采用", key=f"adopt_{idx}"):
                        df.at[idx, "研究者编码"] = row["AI建议编码"]
                        st.session_state.row_status[idx] = "已审核"
                        st.session_state.df = df
                        st.rerun()
                
                with btn_col2:
                    if st.button(f"🗑️ 删除", key=f"delete_{idx}"):
                        st.session_state.row_status[idx] = "已删除"
                        df.at[idx, "研究者编码"] = "（已删除）"
                        st.session_state.df = df
                        st.rerun()
                
                with btn_col3:
                    if st.button(f"✏️ 自定义", key=f"custom_{idx}"):
                        df.at[idx, "研究者编码"] = ""
                        st.session_state.row_status[idx] = "待审核"
                        st.session_state.df = df
                        st.rerun()
            
            st.divider()
    
    st.session_state.df = df
    
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        df_export = df.copy()
        df_export = df_export[df_export.index.map(lambda x: st.session_state.row_status.get(x, "待审核") != "已删除")]
        if len(df_export) > 0:
            csv_data = df_export.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 导出CSV编码表",
                data=csv_data,
                file_name=f"GeoFieldAI_coding_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("没有可导出的编码")
    
    with col2:
        if st.button("📄 生成正式报告", type="primary"):
            st.session_state.step = 5
            st.rerun()

# ==================== Step 5: 报告 ====================
if st.session_state.step >= 5 and st.session_state.df is not None:
    st.divider()
    st.header("📄 Step 5: 正式报告")
    
    df_final = st.session_state.df.copy()
    df_final = df_final[df_final.index.map(lambda x: st.session_state.row_status.get(x, "待审核") != "已删除")]
    
    if len(df_final) == 0:
        st.warning("没有可生成的报告数据")
        if st.button("返回编码审核"):
            st.session_state.step = 4
            st.rerun()
    else:
        codebook_df = df_final[df_final["研究者编码"] != ""]
        if len(codebook_df) > 0:
            codebook = codebook_df["研究者编码"].value_counts().reset_index()
            codebook.columns = ["编码", "频次"]
            codebook["占比"] = (codebook["频次"] / codebook["频次"].sum() * 100).round(1).astype(str) + "%"
            
            st.subheader("📊 Codebook")
            st.dataframe(codebook, use_container_width=True, hide_index=True)
        else:
            st.info("暂无编码数据")
        
        st.subheader("📋 完整编码记录")
        st.dataframe(df_final, use_container_width=True)
        
        csv_data = df_final.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 下载CSV报告（Excel可正常打开）",
            data=csv_data,
            file_name=f"GeoFieldAI_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            type="primary"
        )
        
        if st.button("🔄 重新开始"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

st.divider()
st.caption("🌍 GeoField AI v0.3 · 支持TXT文件 · 交互式编码")
