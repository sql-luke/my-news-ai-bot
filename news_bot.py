import os
import requests
import google.generativeai as genai
from datetime import datetime

# 1. API 金鑰與設定
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def get_kaohsiung_weather():
    """獲取高雄今明兩日氣象預報 (使用 Open-Meteo 免費 API)"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=22.6163&longitude=120.3133&daily=temperature_2m_max,temperature_2m_min,weathercode&timezone=Asia%2FTaipei"
    try:
        res = requests.get(url).json()
        daily = res['daily']
        weather_map = {
            0: "☀️ 晴朗", 1: "🌤️ 晴時多雲", 2: "⛅ 多雲", 3: "☁️ 陰天", 
            45: "🌫️ 有霧", 48: "🌫️ 霧淞", 51: "🌧️ 輕微毛毛雨", 
            61: "🌧️ 陣雨", 95: "⚡ 雷雨"
        }
        
        today_code = daily['weathercode'][0]
        tomorrow_code = daily['weathercode'][1]
        
        weather_msg = f"🌡️ 【高雄氣象快報】\n"
        weather_msg += f"• 今日：{weather_map.get(today_code, '天氣穩定')} ({daily['temperature_2m_min'][0]}°C ~ {daily['temperature_2m_max'][0]}°C)\n"
        weather_msg += f"• 明日：{weather_map.get(tomorrow_code, '天氣穩定')} ({daily['temperature_2m_min'][1]}°C ~ {daily['temperature_2m_max'][1]}°C)"
        return weather_msg
    except Exception as e:
        print(f"獲取天氣失敗: {e}")
        return "🌡️ 【高雄氣象快報】暫時無法取得預報資料"

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
                "altText": "🌍 全球情報與氣象已更新！",
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
                                "text": "🌍 全球與國內科技情報",
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
    # 2. 準備素材庫
    all_news_raw = ""
    
    try:
        tw_url = f"https://newsapi.org/v2/top-headlines?country=tw&pageSize=5&apiKey={NEWS_API_KEY}"
        tw_res = requests.get(tw_url).json()
        for a in tw_res.get("articles", []):
            all_news_raw += f"[國內] {a['title']}\n摘要：{a.get('description', '')}\n"
    except: pass

    try:
        gl_url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize=5&apiKey={NEWS_API_KEY}"
        gl_res = requests.get(gl_url).json()
        for a in gl_res.get("articles", []):
            all_news_raw += f"[國際] {a['title']}\n摘要：{a.get('description', '')}\n"
    except: pass

    try:
        ai_url = f"https://newsapi.org/v2/everything?q=AI&pageSize=5&apiKey={NEWS_API_KEY}"
        ai_res = requests.get(ai_url).json()
        for a in ai_res.get("articles", []):
            all_news_raw += f"[科技] {a['title']}\n摘要：{a.get('description', '')}\n"
    except: pass
    
    try:
        # 3. 設定 Gemini 與動態模型切換容錯機制
        genai.configure(api_key=GEMINI_API_KEY)
        
        print("正在偵測可用 AI 模型...")
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 把上次成功運作的 2.5-flash 放第一位
        priority_list = [
            'models/gemini-2.5-flash',
            'models/gemini-1.5-flash',
            'models/gemini-1.5-pro'
        ]
        
        final_attempt_list = [p for p in priority_list if p in available_models]
        for m in available_models:
            if m not in final_attempt_list:
                final_attempt_list.append(m)

        weather_text = get_kaohsiung_weather()
        ai_output = None
        successful_model = None
        
        prompt = f"""
        你是一位全能的資訊策展人。請閱讀以下新聞素材，為我產出今日情報。
        
        【⚠️ 排版與內容嚴格限制】
        1. 絕對不使用 Markdown 符號（如 `#`, `**`, `*`）。
        2. 絕對不附上連結。
        3. 標題欄位嚴禁標註來源媒體（例如：不要寫 Yahoo、中時等）。
        4. 全程使用「條列式」，每句盡量不超過 30 字，並善用全形括號【】。

        【報告結構】請直接複製以下標題：

        📰 【今日焦點】全球與國內
        (請從素材中挑選 4 則最重要的新聞。直接列出完整標題。)
        👉 重點解讀：(用白話解釋為什麼這件事重要)

        📝 【重點摘要】快速瀏覽
        (用 3 條短句總結今天整體的資訊氛圍)
        • 
        • 
        • 

        💡 【深度洞察】我的發現
        (從全球局勢或產業變動的角度，提出 2 個獨特的觀察或發現)
        • 
        • 

        以下是今日的新聞素材：
        {all_news_raw}
        
        請使用繁體中文回答，語氣專業且俐落。
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
                print(f"❌ {model_name} 失敗 (原因：{str(e)[:50]}...)，嘗試下一個...")
                continue

        if not ai_output:
            raise Exception("所有可用模型皆無法執行。")
        
        # 結合氣象與新聞內容
        final_display_content = f"{weather_text}\n\n{ai_output}"
        
        # 4. 傳送 LINE
        send_line_flex_message(final_display_content, successful_model)
        
        # 5. 更新本地 daily_report.md
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"# 🌍 全球與國內科技情報 ({datetime.now().strftime('%Y-%m-%d')})\n\n")
            f.write(final_display_content)
            
        print("✅ 全能情報任務圓滿完成！")

    except Exception as e:
        print(f"❌ 執行出錯：{e}")

if __name__ == "__main__":
    fetch_and_summarize()
