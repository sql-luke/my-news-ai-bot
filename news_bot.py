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
# 語音設定控制面板
# ==========================================
TTS_VOICE = "zh-TW-YunJheNeural"
TTS_RATE = "+10%" 

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

def generate_insights(weather_data, world_news, finance_news, tech_news, life_news):
    if not gemini_client:
        return "抱歉，Gemini 客戶端未正確初始化，請檢查金鑰。"

    prompt = f"""
    你現在是一位充滿活力、聲音親切的晨間廣播節目主持人。
    請將以下資訊，製作成一份長度適中、富有節奏感的「早晨廣播節目文字稿」。
    
    【節目流程與素材】
    1. 🌤️ 氣象站：{weather_data}
    2. 🌍 國際台：{world_news}
    3. 💰 財經台：{finance_news}
    4. 🔬 科技台：{tech_news}
    5. 🍿 生活台：{life_news}

    【播報要求】
    - 使用 Markdown 格式排版，每個頻道必須以 `# 【頻道名稱】` 作為大標題。
    - 每個頻道開場請設計一句生動的過場口白（例如：「緊接著帶您關心...」、「放鬆一下，來聽聽今天的娛樂焦點...」）。
    - 新聞內容請用「口語化、說故事」的方式呈現，不要死板地條列。
    - 節目最後，請以主持人的身分，送給聽眾一句激勵人心的「今日金句」（中英對照），並做溫暖的道別。
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

    bubble = {
        "type": "bubble",
        "styles": {"body": {"backgroundColor": "#121212"}},
        "body": {"type": "box", "layout": "vertical", "contents": flex_contents}
    }

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
                "altText": "您的晨間 AI 廣播已送達！",
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

def main():
    print(f"啟動晨間廣播播報任務... ({datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')})")
    
    # 擴充為 5 個頻道的情報蒐集
    print("⏳ 正在取得各頻道情報...")
    weather_data = get_kaohsiung_weather()
    world_news = get_news("國際新聞 OR global news")
    finance_news = get_news("股市 OR 經濟 OR finance")
    tech_news = get_news("AI OR 科技 OR apple OR 台積電")
    life_news = get_news("電影 OR 健康 OR 旅遊 OR 娛樂", language="zh")

    print("⏳ 正在交由 Gemini 分析與撰寫節目稿...")
    insights_text = generate_insights(weather_data, world_news, finance_news, tech_news, life_news)

    print("⏳ 正在生成早晨語音播報...")
    audio_path, duration_ms = generate_audio(insights_text)

    audio_url = None
    if audio_path:
        print("⏳ 準備備份音檔至雲端硬碟...")
        audio_url = upload_audio_to_drive(audio_path)
    
    print("⏳ 正在推播 LINE 文字訊息 (Flex Message)...")
    send_line_flex_message(insights_text, audio_url)
    
    # 註：已依要求移除原生語音推播 (紅框處)

    print("🏁 任務完成！")

if __name__ == "__main__":
    main()
