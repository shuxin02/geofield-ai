# app.py - 完整版
import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import os
from collections import Counter

# ==================== 历史记录功能 ====================
HISTORY_FILE = "research_history.json"

def load_history():
    """加载历史记录"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(text):
    """保存历史记录"""
    history = load_history()
    history = [text] + [h for h in history if h != text]
    history = history[:10]
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return history

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
# 历史记录缓存 - 只在页面首次加载时从文件读取
if 'history_display' not in st.session_state:
    st.session_state.history_display = load_history()
# 标记是否允许刷新历史记录
if 'allow_history_refresh' not in st.session_state:
    st.session_state.allow_history_refresh = False

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

# 显示历史记录（使用缓存，除非允许刷新）
if st.session_state.allow_history_refresh:
    st.session_state.history_display = load_history()
    st.session_state.allow_history_refresh = False

history = st.session_state.history_display
if history:
    latest = history[0]
    display_text = latest[:80] + "..." if len(latest) > 80 else latest
    st.caption(f"📜 最近输入：{display_text}")
    if st.button("📝 点击使用", key="use_latest"):
        st.session_state.research_question = latest
        st.session_state.allow_history_refresh = True
        st.rerun()

if st.button("确认研究问题", type="primary"):
    if research_question.strip():
        st.session_state.research_question = research_question.strip()
        current_history = load_history()
        if not current_history or current_history[0] != research_question.strip():
            save_history(research_question.strip())
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

## Memo生成指南
对于每个编码条目，请评估是否需要生成Memo：
- **需要Memo的情况**：该段落揭示了超出字面的深层含义、涉及多重关联、或具有典型分析价值
- **不需要Memo的情况**：内容较为直接明了，无特别的分析线索
- 请适度生成Memo，既不过度（避免为每个条目都生成），也不过于保守

## 输出格式
请以JSON数组格式输出，每个对象包含：
- id: 序号（从1开始）
- quote: 原文引用
- ai_code: 建议编码（简洁的关键词）
- memo_hint: 备注提示（简要概括分析线索，若无则留空）
- memo_reason: 备注原因（说明分析价值，若无则留空）

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
    
    # 自定义CSS：按钮文字颜色
    st.markdown("""
    <style>
    /* 采用按钮 - 绿色 */
    div[data-testid="stButton"] button:has(div:contains("采用")) {
        color: #2E7D32 !important;
        font-weight: 500 !important;
    }
    /* 删除按钮 - 灰色 */
    div[data-testid="stButton"] button:has(div:contains("删除")) {
        color: #757575 !important;
    }
    /* 自定义按钮 - 橘红色 */
    div[data-testid="stButton"] button:has(div:contains("自定义")) {
        color: #E65100 !important;
        font-weight: 500 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
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
                if row.get("AI Memo说明") and str(row["AI Memo说明"]) != "" and str(row["AI Memo说明"]) != "nan":
                    st.caption(f"📝 Memo说明: {row['AI Memo说明']}")
            
            with col_right:
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                
                with btn_col1:
                    if st.button("采用", key=f"adopt_{idx}"):
                        df.at[idx, "研究者编码"] = row["AI建议编码"]
                        st.session_state.row_status[idx] = "已审核"
                        st.session_state.df = df
                        st.rerun()
                
                with btn_col2:
                    if st.button("删除", key=f"delete_{idx}"):
                        st.session_state.row_status[idx] = "已删除"
                        df.at[idx, "研究者编码"] = "（已删除）"
                        st.session_state.df = df
                        st.rerun()
                
                with btn_col3:
                    if st.button("自定义", key=f"custom_{idx}"):
                        st.session_state[f"custom_mode_{idx}"] = not st.session_state.get(f"custom_mode_{idx}", False)
                        st.rerun()
            
            # 自定义输入框（在行下方展开）
            if st.session_state.get(f"custom_mode_{idx}", False):
                new_code = st.text_input(
                    "输入自定义编码",
                    key=f"custom_input_{idx}",
                    placeholder="输入编码后按回车确认",
                    label_visibility="collapsed"
                )
                if new_code:
                    df.at[idx, "研究者编码"] = new_code
                    st.session_state.row_status[idx] = "已审核"
                    st.session_state.df = df
                    st.session_state[f"custom_mode_{idx}"] = False
                    st.rerun()
            
            st.divider()
    
    st.session_state.df = df
    
    # 底部：只保留"生成正式报告"按钮，居左
    st.divider()
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
        
        # 修复CSV乱码：手动添加BOM头
        csv_raw = df_final.to_csv(index=False, encoding='utf-8')
        csv_data = '\ufeff' + csv_raw
        st.download_button(
            label="📥 下载CSV报告（Excel可正常打开）",
            data=csv_data,
            file_name=f"GeoFieldAI_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv; charset=utf-8",
            type="primary"
        )
        
        if st.button("🔄 重新开始"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

st.divider()
st.caption("🌍 GeoField AI v0.3 · 支持TXT文件 · 交互式编码 · 历史记录")
