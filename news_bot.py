import os
import requests
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
from gtts import gTTS
from mutagen.mp3 import MP3

# ==========================================
# 系統設定與金鑰讀取
# ==========================================
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# 設定 Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# 核心功能與工具模組
# ==========================================

def get_kaohsiung_weather():
    """
    獲取高雄市區 (Cianjhen District) 的天氣預報。
    """
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
    """
    使用 News API 獲取指定關鍵字的新聞。
    """
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
        
        news_list = []
        for article in articles:
            title = article.get("title")
            description = article.get("description")
            if title and description:
                news_list.append(f"標題: {title}\n摘要: {description}")
        return "\n\n".join(news_list)
    except Exception as e:
        print(f"Error fetching news for '{query}': {e}")
        return "無法取得新聞"

def generate_insights(weather_data, global_news, local_news, tech_news):
    """
    使用 Gemini 模型整理新聞並生成具備洞察力的播報稿。
    """
    prompt = f"""
    你現在是一位專業、具備前瞻視野的 AI 新聞主播。
    請根據以下資訊，整理出一份條理分明、具備深度洞察的晨間新聞播報稿。
    請使用繁體中文，語氣需自信、客觀且具備啟發性。

    【今日高雄氣象】
    {weather_data}
    - 請依據氣象數據，提供貼心的穿搭與出門建議（例如是否攜帶雨具）。

    【全球焦點】
    {global_news}
    - 挑選 1-2 則最具影響力的國際事件進行重點解說。

    【國內時事】
    {local_news}
    - 挑選 1-2 則對台灣民生或經濟最具關聯的事件。

    【科技 AI 前沿】
    {tech_news}
    - 挑選 1 則最重要的科技突破或 AI 發展趨勢。

    【排版要求】
    - 使用 Markdown 格式。
    - 每個段落（包含總結）請使用 `#` 或 `**` 標示大標題或重點。
    - 每則新聞後方，請加入一段「**總結：**」（包含冒號），提供精闢的短評或洞察。
    """
    
    # 嘗試使用不同的模型以確保穩定性 (V2.0 容錯機制)
    models = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            print(f"Successfully generated insights using {model_name}")
            return response.text
        except Exception as e:
            print(f"Failed to generate with {model_name}: {e}")
            continue
    
    return "抱歉，今日無法產生新聞洞察報告。"

def generate_audio(full_news_text):
    """
    接收完整的新聞內容文字，生成 MP3 檔案並計算時長。
    """
    audio_path = "morning_news.mp3"
    
    # 為了讓語音聽起來更順暢，我們將文字中的 Markdown 符號（如 ** 或 #）簡單替換掉
    clean_text = full_news_text.replace("**", "").replace("#", "").replace("---", "。")
    
    try:
        # 生成語音 (繁體中文)
        tts = gTTS(text=clean_text, lang='zh-TW', slow=False)
        tts.save(audio_path)
        
        # 計算時長（LINE 語音訊息強制要求填寫毫秒數）
        audio_info = MP3(audio_path)
        duration_ms = int(audio_info.info.length * 1000)
        
        print(f"✅ 語音檔案已產出，長度為 {duration_ms} 毫秒")
        return audio_path, duration_ms
    except Exception as e:
         print(f"Error generating audio: {e}")
         return None, None

def send_line_flex_message(insights_text):
    """
    將生成的洞察報告透過 LINE Messaging API 發送給使用者（包含深色模式 Flex Message）。
    """
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }

    # 將生成的文字稿依照換行符號分割，以便組裝 Flex Message
    lines = insights_text.split('\n')
    flex_contents = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 簡單的解析邏輯：將標題字體放大並設定顏色，將「總結」設為金色
        if line.startswith("#"):
            flex_contents.append({
                "type": "text",
                "text": line.replace("#", "").strip(),
                "weight": "bold",
                "size": "xl",
                "color": "#00FF00" # 駭客綠大標題
            })
        elif "總結：" in line:
            flex_contents.append({
                "type": "text",
                "text": line,
                "weight": "bold",
                "color": "#FFD700", # 金色高亮
                "wrap": True
            })
        else:
            flex_contents.append({
                "type": "text",
                "text": line,
                "color": "#F5F5DC", # 米白色內文
                "wrap": True
            })

    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": "您的晨間 AI 科技與生活情報已送達！",
                "contents": {
                    "type": "bubble",
                    "styles": {
                        "body": {
                            "backgroundColor": "#121212" # 極致黑色底
                        }
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": flex_contents
                    }
                }
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print("✅ LINE 訊息推播成功！")
    except requests.exceptions.RequestException as e:
        print(f"❌ LINE 訊息推播失敗: {e}")
        if e.response is not None:
             print(f"Response Body: {e.response.text}")


# ==========================================
# 主程式執行流程
# ==========================================
def main():
    print(f"啟動晨間新聞播報任務... ({datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')})")

    # 1. 蒐集情報
    print("⏳ 正在取得高雄氣象...")
    weather_data = get_kaohsiung_weather()
    
    print("⏳ 正在取得全球焦點...")
    global_news = get_news("global economy OR geopolitics")
    
    print("⏳ 正在取得國內時事...")
    local_news = get_news("台灣 OR 台北 OR 台積電")
    
    print("⏳ 正在取得科技 AI 前沿...")
    tech_news = get_news("generative AI OR semiconductor OR green energy")

    # 2. 生成洞察報告
    print("⏳ 正在交由 Gemini 分析與整理...")
    insights_text = generate_insights(weather_data, global_news, local_news, tech_news)

    # 3. 產生音檔 (V3.0 新增)
    print("⏳ 正在生成早晨語音播報...")
    audio_path, duration_ms = generate_audio(insights_text)

    # 4. 推播文字訊息
    print("⏳ 正在透過 LINE 推播訊息...")
    send_line_flex_message(insights_text)
    
    # [註] 未來我們會在這裡補上發送 AudioSendMessage 的邏輯，並串接 Google Drive。
    
    print("任務完成！")

if __name__ == "__main__":
    main()
