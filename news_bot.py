import os
import json
import requests
from datetime import datetime, timezone, timedelta
from gtts import gTTS
from mutagen.mp3 import MP3

# 新版 Gemini SDK
from google import genai

# Google Drive API 相關套件
from google.oauth2 import service_account
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
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

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
        
        weather_info = (
            f"最高溫: {daily.get('temperature_2m_max', ['N/A'])[0]}°C, "
            f"最低溫: {daily.get('temperature_2m_min', ['N/A'])[0]}°C, "
            f"降雨機率: {daily.get('precipitation_probability_max', ['N/A'])[0]}%"
        )
        return weather_info
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
    
    # 升級為新版 SDK 調用方式
    client = genai.Client(api_key=GEMINI_API_KEY)
    models = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    
    for model_name in models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Failed to generate with {model_name}: {e}")
            continue
            
    return "抱歉，今日無法產生新聞洞察報告。"

def generate_audio(full_news_text):
    audio_path = "morning_news.mp3"
    clean_text = full_news_text.replace("**", "").replace("#", "").replace("---", "。")
    try:
        tts = gTTS(text=clean_text, lang='zh-TW', slow=False)
        tts.save(audio_path)
        audio_info = MP3(audio_path)
        duration_ms = int(audio_info.info.length * 1000)
        print(f"✅ 語音檔案已產出，長度為 {duration_ms} 毫秒")
        return audio_path, duration_ms
    except Exception as e:
         print(f"❌ 生成語音失敗: {e}")
         return None, None

def upload_audio_to_drive(file_path):
    if not GOOGLE_CREDENTIALS_JSON or not GDRIVE_FOLDER_ID:
        print("⚠️ 缺少 Google Drive 金鑰或 Folder ID，跳過上傳。")
        return None

    try:
        print("⏳ 正在驗證 Google Drive 金鑰...")
        creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=creds)

        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")
        file_metadata = {
            'name': f'AI_News_{date_str}.mp3',
            'parents': [GDRIVE_FOLDER_ID]
        }
        
        media = MediaFileUpload(file_path, mimetype='audio/mpeg')

        print("⏳ 正在上傳音檔至 Google Drive...")
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = file.get('id')
        direct_link = f"https://drive.google.com/uc?export=download&id={file_id}"
        print(f"✅ 上傳成功！取得公開直連網址：{direct_link}")
        
        return direct_link
    except Exception as e:
        print(f"❌ 上傳至 Google Drive 失敗: {e}")
        return None

def send_line_flex_message(insights_text):
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

    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": "您的晨間 AI 情報已送達！",
                "contents": {
                    "type": "bubble",
                    "styles": {"body": {"backgroundColor": "#121212"}},
                    "body": {"type": "box", "layout": "vertical", "contents": flex_contents}
                }
            }
        ]
    }
    
    try:
        requests.post(url, headers=headers, json=payload).raise_for_status()
        print("✅ LINE 文字訊息推播成功！")
    except requests.exceptions.RequestException as e:
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
        requests.post(url, headers=headers, json=payload).raise_for_status()
        print("✅ LINE 語音訊息推播成功！使用者現在可以聽新聞了🎧")
    except requests.exceptions.RequestException as e:
        print(f"❌ LINE 語音訊息推播失敗: {e}")
        if e.response is not None:
             print(f"Response Body: {e.response.text}")

# ==========================================
# 主程式執行流程
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

    print("⏳ 正在推播 LINE 文字訊息 (Flex Message)...")
    send_line_flex_message(insights_text)

    print("⏳ 正在生成早晨語音播報...")
    audio_path, duration_ms = generate_audio(insights_text)

    if audio_path:
        print("⏳ 準備備份音檔至雲端硬碟...")
        audio_url = upload_audio_to_drive(audio_path)
        
        if audio_url:
            print("⏳ 正在推播 LINE 語音訊息...")
            send_line_audio_message(audio_url, duration_ms)

    print("任務完成！")

if __name__ == "__main__":
    main()
