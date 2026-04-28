import os
import time
import asyncio
import requests
from datetime import datetime, timezone, timedelta
from mutagen.mp3 import MP3

import edge_tts

from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================
# 系統設定與金鑰讀取
# ==========================================
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID")
GDRIVE_CLIENT_ID = os.environ.get("GDRIVE_CLIENT_ID")
GDRIVE_CLIENT_SECRET = os.environ.get("GDRIVE_CLIENT_SECRET")
GDRIVE_REFRESH_TOKEN = os.environ.get("GDRIVE_REFRESH_TOKEN")

# ==========================================
# V4.0 語音設定控制面板
# ==========================================
TTS_VOICE = "zh-TW-YunJheNeural"
TTS_RATE = "+10%" 

# ==========================================

try:
    if GEMINI_API_KEY:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    else:
        print("⚠️ 未偵測到 GEMINI_API_KEY")
        gemini_client = None
except Exception as e:
    print(f"⚠️ Gemini Client 初始化失敗: {e}")
    gemini_client = None

# ==========================================
# 核心功能與工具模組
# ==========================================

def get_kaohsiung_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 22.595,
        "longitude": 120.320,
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_probability_max"],
        "timezone": "Asia/Taipei"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        daily = data.get("daily", {})
        return (f"最高溫: {daily.get('temperature_2m_max', ['N/A'])[0]}°C, "
                f"最低溫: {daily.get('temperature_2m_min', ['N/A'])[0]}°C, "
                f"降雨機率: {daily.get('precipitation_probability_max', ['N/A'])[0]}%")
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return "無法取得天氣資訊"

def get_news(query, language="zh"):
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": language,
        "sortBy": "publishedAt",
        "apiKey": NEWS_API_KEY,
        "pageSize": 5
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        articles = response.json().get("articles", [])
        news_list = [f"標題: {a.get('title')}\n摘要: {a.get('description')}" for a in articles if a.get('title') and a.get('description')]
        return "\n\n".join(news_list)
    except Exception as e:
        print(f"Error fetching news for '{query}': {e}")
        return "無法取得新聞"

def generate_insights(weather_data, global_news, local_news, tech_news):
    if not gemini_client:
        return "抱歉，Gemini 客戶端未正確初始化，請檢查金鑰。"

    prompt = f"""
    你現在是一位專業、具備前瞻視野的 AI 新聞主播。
    請根據以下資訊，整理出一份條理分明、具備深度洞察的晨間新聞播報稿。
    請使用繁體中文，語氣需自信、客觀且具備啟發性。

    【今日高雄氣象】
    {weather_data}

    【全球焦點】
    {global_news}

    【國內時事】
    {local_news}

    【科技 AI 前沿】
    {tech_news}

    【排版要求】
    - 使用 Markdown 格式。
    - 每個段落請使用 `#` 或 `**` 標示大標題或重點。
    - 每則新聞後方，請加入一段「**總結：**」（包含冒號），提供精闢的短評。
    """
    
    models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview"]
    last_error = ""
    for model_name in models:
        for attempt in range(2):
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ 嘗試 {model_name} 失敗 (第 {attempt+1} 次): {error_msg}")
                last_error = error_msg
                if "503" in error_msg or "429" in error_msg:
                    print("⏳ 伺服器忙碌，等待 5 秒後重試...")
                    time.sleep(5)
                    continue
                else:
                    break
    
    return f"抱歉，今日無法產生新聞洞察報告。\n(系統除錯資訊：{last_error})"

async def _async_generate_audio(text, audio_path):
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
    await communicate.save(audio_path)

def generate_audio(full_news_text):
    audio_path = "morning_news.mp3"
    clean_text = full_news_text.replace("**", "").replace("#", "").replace("---", "。")
    try:
        asyncio.run(_async_generate_audio(clean_text, audio_path))
        audio_info = MP3(audio_path)
        duration_ms = int(audio_info.info.length * 1000)
        print(f"✅ 語音檔案已產出 (採用 {TTS_VOICE})，長度為 {duration_ms} 毫秒")
        return audio_path, duration_ms
    except Exception as e:
         print(f"❌ 生成語音失敗: {e}")
         return None, None

def upload_audio_to_drive(file_path):
    if not all([GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN, GDRIVE_FOLDER_ID]):
        print("⚠️ 缺少 Google Drive 必要金鑰，跳過上傳。")
        return None

    try:
        print("⏳ 正在驗證 Google 個人帳號授權...")
        creds = Credentials(
            token=None,
            refresh_token=GDRIVE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GDRIVE_CLIENT_ID,
            client_secret=GDRIVE_CLIENT_SECRET
        )
        service = build('drive', 'v3', credentials=creds)

        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")
        file_metadata = {
            'name': f'AI_News_{date_str}.mp3',
            'parents': [GDRIVE_FOLDER_ID]
        }
        
        media = MediaFileUpload(file_path, mimetype='audio/mpeg')

        print("⏳ 正在上傳音檔至 Google Drive (個人空間)...")
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = file.get('id')
        direct_link = f"https://drive.google.com/uc?export=download&id={file_id}"
        print(f"✅ 上傳成功！直連網址：{direct_link}")
        return direct_link
    except Exception as e:
        print(f"❌ 上傳至 Google Drive 失敗: {e}")
        return None

def send_line_flex_message(insights_text, audio_url=None):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }

    lines = insights_text.split('\n')
    flex_contents = []

    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith("#"):
            flex_contents.append({"type": "text", "text": line.replace("#", "").strip(), "weight": "bold", "size": "xl", "color": "#00FF00"})
        elif "總結：" in line:
            flex_contents.append({"type": "text", "text": line, "weight": "bold", "color": "#FFD700", "wrap": True})
        else:
            flex_contents.append({"type": "text", "text": line, "color": "#F5F5DC", "wrap": True})

    # 建構基礎的氣泡框
    bubble = {
        "type": "bubble",
        "styles": {"body": {"backgroundColor": "#121212"}},
        "body": {"type": "box", "layout": "vertical", "contents": flex_contents}
    }

    # 如果有成功取得音檔網址，就在卡片最下方加入背景播放按鈕
    if audio_url:
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#1DB100",
                    "margin": "md",
                    "action": {
                        "type": "uri",
                        "label": "🎧 啟用背景播放 (可關螢幕)",
                        "uri": audio_url
                    }
                }
            ]
        }
        bubble["styles"]["footer"] = {"backgroundColor": "#121212"}

    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": "您的晨間 AI 情報已送達！",
                "contents": bubble
            }
        ]
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        print("✅ LINE 文字訊息推播成功！")
    except Exception as e:
        print(f"❌ LINE 文字訊息推播失敗: {e}")

def send_line_audio_message(audio_url, duration_ms):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }

    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "audio",
                "originalContentUrl": audio_url,
                "duration": duration_ms
            }
        ]
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        print("✅ LINE 語音訊息推播成功！🎧")
    except Exception as e:
        print(f"❌ LINE 語音訊息推播失敗: {e}")

# ==========================================
# 主程式執行流程 (調整了執行順序)
# ==========================================
def main():
    print(f"啟動晨間新聞播報任務... ({datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')})")
    print("⏳ 正在取得新聞與天氣情報...")
    weather_data = get_kaohsiung_weather()
    global_news = get_news("global economy OR geopolitics")
    local_news = get_news("台灣 OR 台北 OR 台積電")
    tech_news = get_news("generative AI OR semiconductor OR green energy")

    print("⏳ 正在交由 Gemini 分析與整理...")
    insights_text = generate_insights(weather_data, global_news, local_news, tech_news)

    # 先生成音檔並上傳，取得網址
    print("⏳ 正在生成早晨語音播報...")
    audio_path, duration_ms = generate_audio(insights_text)

    audio_url = None
    if audio_path:
        print("⏳ 準備備份音檔至雲端硬碟...")
        audio_url = upload_audio_to_drive(audio_path)
    
    # 將音檔網址一起傳入圖文卡片，生成背景播放按鈕
    print("⏳ 正在推播 LINE 文字訊息 (Flex Message)...")
    send_line_flex_message(insights_text, audio_url)

    # 保留原本的 LINE 原生語音，提供多種播放選擇
    # if audio_url:
    #    print("⏳ 正在推播 LINE 語音訊息...")
    #    send_line_audio_message(audio_url, duration_ms)

    print("🏁 任務完成！")

if __name__ == "__main__":
    main()
