import os
import requests
import google.generativeai as genai
from datetime import datetime

# 1. API 金鑰與設定
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def get_raw_weather_data():
    """獲取高雄原始氣象數據，交給 AI 扮演主播播報"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=22.6163&longitude=120.3133&daily=temperature_2m_max,temperature_2m_min,weathercode&timezone=Asia%2FTaipei"
    try:
        res = requests.get(url).json()
        daily = res['daily']
        weather_map = {
            0: "晴朗", 1: "晴時多雲", 2: "多雲", 3: "陰天", 
            45: "有霧", 48: "霧淞", 51: "輕微毛毛雨", 
            61: "陣雨", 95: "雷雨"
        }
        today_code = daily['weathercode'][0]
        tomorrow_code = daily['weathercode'][1]
        
        raw_data = f"""
        [高雄氣象原始數據]
        今日：{weather_map.get(today_code, '未知')}，氣溫 {daily['temperature_2m_min'][0]}°C 到 {daily['temperature_2m_max'][0]}°C。
        明日：{weather_map.get(tomorrow_code, '未知')}，氣溫 {daily['temperature_2m_min'][1]}°C 到 {daily['temperature_2m_max'][1]}°C。
        """
        return raw_data
    except Exception as e:
        return "[高雄氣象原始數據] 暫時無法取得，請主播以幽默方式帶過。"

def send_line_flex_message(text_content, model_name):
    """發送深色模式的 LINE Flex Message"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("⚠️ 缺少 LINE 金鑰，跳過 LINE 推播")
        return

    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": "🌍 您的全方位晨間情報已送達！",
                "contents": {
                    "type": "bubble",
                    "size": "mega",
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#000000",
                        "paddingTop": "xl",
                        "paddingBottom": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🌍 全方位晨間情報",
                                "weight": "bold",
                                "color": "#00FF41",
                                "size": "xl"
                            },
                            {
                                "type": "text",
                                "text": f"分析引擎: {model_name}",
                                "color": "#888888",
                                "size": "xs",
                                "margin": "sm"
                            }
                        ]
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1A1A1A",
                        "paddingTop": "lg",
                        "paddingBottom": "xl",
                        "contents": [
                            {
                                "type": "text",
                                "text": text_content,
                                "wrap": True,
                                "size": "sm",
                                "color": "#F5F5F5",
                                "lineSpacing": "6px" 
                            }
                        ]
                    }
                }
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("✅ LINE 綜合情報推送成功！")
    else:
        print(f"❌ LINE 推送失敗：{response.status_code}, {response.text}")

def fetch_and_summarize():
    # 2. 大量抓取素材，確保 AI 有足夠的新聞可以挑選 (pageSize 調高到 15)
    all_news_raw = ""
    
    categories = [
        (f"https://newsapi.org/v2/top-headlines?country=tw&pageSize=15&apiKey={NEWS_API_KEY}", "國內新聞"),
        (f"https://newsapi.org/v2/top-headlines?language=en&pageSize=15&apiKey={NEWS_API_KEY}", "國際新聞"),
        (f"https://newsapi.org/v2/everything?q=AI&pageSize=15&apiKey={NEWS_API_KEY}", "AI科技新聞")
    ]

    for url, label in categories:
        try:
            res = requests.get(url).json()
            all_news_raw += f"\n--- {label} 素材 ---\n"
            for a in res.get("articles", []):
                all_news_raw += f"標題：{a.get('title', '')}\n摘要：{a.get('description', '')}\n\n"
        except:
            pass

    try:
        # 3. 設定 Gemini 
        genai.configure(api_key=GEMINI_API_KEY)
        
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority_list = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        final_attempt_list = [p for p in priority_list if p in available_models] + available_models

        weather_raw = get_raw_weather_data()
        ai_output = None
        successful_model = None
        
        # 💡 全新升級的史詩級 Prompt
        prompt = f"""
        你是一位頂級的「晨間新聞主播」兼「資深分析師」。請根據以下原始數據，產出一份極具深度且專業的晨間情報。

        【⚠️ 絕對嚴格限制】
        1. 語言限制：無論原始新聞是什麼語言，所有輸出內容【必須 100% 翻譯為繁體中文】。絕對不允許出現一整句英文。
        2. 排版限制：不使用 Markdown 符號（如 `#`, `**`），一律使用全形括號【】與條列符號 `•` 來排版。
        3. 內容要求：每一篇新聞都必須包含「詳盡介紹」與「結論洞見」，絕不能含糊帶過。

        請嚴格依照以下四大區塊的格式與標題輸出：

        🌦️ 【氣象播報站：高雄視角】
        (請根據以下提供的氣象數據，化身專業氣象主播進行播報。必須加上溫馨的「穿衣建議」與「是否攜帶雨具」提醒)
        氣象數據：{weather_raw}

        🌍 【國際焦點新聞】
        (請從素材中精選出 5 篇最具影響力的國際新聞，每篇依循以下格式)
        【1】中文標題
        • 詳盡介紹：(詳細說明事件背景與發展)
        👉 結論與洞見：(提出你的專業分析與未來影響)
        (依此類推，列出 5 篇)

        🇹🇼 【國內時事脈動】
        (請從素材中精選出 5 篇最重要的台灣國內新聞，每篇依循以下格式)
        【1】中文標題
        • 詳盡介紹：(詳細說明事件背景與發展)
        👉 結論與洞見：(提出這對台灣社會或經濟的意義)
        (依此類推，列出 5 篇)

        🤖 【AI 科技前沿】
        (請從素材中精選出 5 篇最前沿的 AI 科技新聞，每篇依循以下格式)
        【1】中文標題
        • 詳盡介紹：(詳細說明技術突破或企業動態)
        👉 結論與洞見：(預測這項技術將如何改變未來)
        (依此類推，列出 5 篇)

        以下是今日的新聞素材庫：
        {all_news_raw}
        """

        for model_name in final_attempt_list:
            try:
                print(f"嘗試使用模型：{model_name}...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                ai_output = response.text
                successful_model = model_name
                print(f"✅ {model_name} 成功產出報告！")
                break 
            except Exception as e:
                print(f"❌ {model_name} 失敗 (原因：{str(e)[:50]}...)")
                continue

        if not ai_output:
            raise Exception("所有可用模型皆無法執行。")
        
        # 4. 傳送 LINE
        send_line_flex_message(ai_output, successful_model)
        
        # 5. 更新本地 daily_report.md
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"# 🌍 全方位晨間情報 ({datetime.now().strftime('%Y-%m-%d')})\n\n")
            f.write(ai_output)
            
        print("✅ 全能情報任務圓滿完成！")

    except Exception as e:
        print(f"❌ 執行出錯：{e}")

if __name__ == "__main__":
    fetch_and_summarize()
