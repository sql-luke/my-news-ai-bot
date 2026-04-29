import os
import json
import asyncio
import requests
import edge_tts
from pydub import AudioSegment
import google.generativeai as genai

# ==========================================
# 1. 讀取 GitHub Secrets 環境變數
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
GDRIVE_CLIENT_ID = os.getenv("GDRIVE_CLIENT_ID")
GDRIVE_CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
GDRIVE_REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")

# API 金鑰檢查
if not GEMINI_API_KEY:
    print("❌ 嚴重錯誤：找不到 GEMINI_API_KEY！請確認 GitHub Secrets 已設定且名稱拼寫正確。")
    exit(1)

# 設定 Gemini
genai.configure(api_key=GEMINI_API_KEY)

# 語音角色設定 (Edge TTS 台灣口音)
VOICES = {
    "HostA": "zh-TW-HsiaoChenNeural", # 女聲 (主 Key)
    "HostB": "zh-TW-YunJheNeural"     # 男聲 (搭檔)
}

# ==========================================
# 2. 核心功能：雙人劇本生成 (動態模型偵測版)
# ==========================================
def generate_podcast_script(news_summary):
    prompt = f"""
    你現在是專業 Podcast 製作人。請根據以下新聞內容，寫一段兩人對話的 Podcast 劇本。
    - HostA (女)：主持人，節奏輕快、負責開場與主要播報。
    - HostB (男)：搭檔，負責提問、補充有趣點、或表達驚訝。
    請確保對話生動，像是在聊天而不是唸稿。
    
    輸出格式：純 JSON 陣列，不要有任何 Markdown 標記或說明文字。
    範例：[
      {{"speaker": "HostA", "text": "各位聽眾朋友大家好，我是 HostA！"}},
      {{"speaker": "HostB", "text": "大家好，我是 HostB！今天的新聞很有趣喔！"}}
    ]
    
    今日新聞內容：
    {news_summary}
    """
    
    print("🔍 正在向伺服器查詢您的 API Key 支援哪些模型...")
    available_models = []
    try:
        # 動態抓取支援 generateContent 的模型清單
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                clean_name = m.name.replace('models/', '')
                available_models.append(clean_name)
    except Exception as e:
        raise Exception(f"❌ 查詢模型清單失敗，可能是 API Key 無效或網路問題: {e}")

    if not available_models:
        raise Exception("❌ 您的 API Key 沒有任何支援生成文字的模型。")

    # 偏好順序：越前面的越聰明/速度越快
    preferred_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro', 'gemini-1.0-pro']
    
    # 從您可用的模型中，挑出順位最高的一個
    selected_model = next((model for model in preferred_models if model in available_models), None)
    
    if not selected_model:
        selected_model = available_models[0]

    print(f"🚀 最終決定使用模型: {selected_model}")
    
    try:
        model = genai.GenerativeModel(selected_model)
        response = model.generate_content(prompt)
        
        # 清理格式以確保 JSON 能夠被正確解析
        content = response.text.strip()
        if content.startswith("
