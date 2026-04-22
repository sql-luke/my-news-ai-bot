import os
import requests
import google.generativeai as genai
from datetime import datetime

# 1. API 金鑰與設定
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def get_detailed_weather():
    """獲取高雄詳細氣象數據 (含降雨機率與早中晚溫差)"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=22.6163&longitude=120.3133&hourly=temperature_2m,precipitation_probability&daily=weathercode&timezone=Asia%2FTaipei&forecast_days=2"
    try:
        res = requests.get(url).json()
        hourly = res['hourly']
        
        # 提取今日關鍵時段數據 (早上8點, 下午2點, 晚上8點)
        t_8 = hourly['temperature_2m'][8]
        t_14 = hourly['temperature_2m'][14]
        t_20 = hourly['temperature_2m'][20]
        
        # 找出今日最高降雨機率及其時段
        today_rain_probs = hourly['precipitation_probability'][0:24]
        max_rain_prob = max(today_rain_probs)
        max_rain_hour = today_rain_probs.index(max_rain_prob)
        
        weather_raw = f"""
        [高雄詳細氣象數據]
        今日氣溫分布：早上8點 {t_8}°C、下午2點 {t_14}°C、晚上8點 {t_20}°C。
        今日降雨資訊：最高降雨機率為 {max_rain_prob}%，預計最可能降雨的時間點在 {max_rain_hour}:00 左右。
        """
        return weather_raw
    except Exception as e:
        print(f"氣象擷取錯誤: {e}")
        return "[高雄氣象數據] 目前系統連線異常，請主播以專業口吻提醒注意天氣變換。"

def create_section(title, content):
    """建立 Flex Message 的區塊結構，確保大標題與小內文層次分明"""
    # 強制清除可能殘留的 Markdown 粗體符號
    clean_content = content.replace("**", "").strip()
    return [
        {
            "type": "text",
            "text": title,
            "weight": "bold",
            "color": "#00FF41",
            "size": "md", 
            "margin": "lg"
        },
        {
            "type": "text",
            "text": clean_content,
            "wrap": True,
            "size": "sm",
            "color": "#F5F5F5",
            "lineSpacing": "6px",
            "margin": "md"
        }
    ]

def send_line_structured_flex(weather_text, intl_text, tw_text, ai_text, model_name):
    """發送結構化的深色模式 Flex Message"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID: return

    url = 'https://api.line.me/v2/bot/message/push'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'}
    
    body_contents = []
    if weather_text: body_contents.extend(create_section("🌦️ 氣象主播特報", weather_text))
    if intl_text: body_contents.extend(create_section("🌍 國際焦點新聞", intl_text))
    if tw_text: body_contents.extend(create_section("🇹🇼 國內時事脈動", tw_text))
    if ai_text: body_contents.extend(create_section("🤖 AI 科技前沿", ai_text))

    payload = {
        "to": LINE_USER_ID,
        "messages": [{
            "type": "flex",
            "altText": "🌍 您的全方位晨間情報已送達！",
            "contents": {
                "type": "bubble",
                "size": "mega",
                "header": {
                    "type": "box", "layout": "vertical", "backgroundColor": "#000000",
                    "contents": [
                        {"type": "text", "text": "🌍 全方位晨間情報", "weight": "bold", "color": "#FFFFFF", "size": "xl"},
                        {"type": "text", "text": f"分析引擎: {model_name}", "color": "#888888", "size": "xs", "margin": "sm"}
                    ]
                },
                "body": {
                    "type": "box", "layout": "vertical", "backgroundColor": "#1A1A1A",
                    "contents": body_contents
                }
            }
        }]
    }
    requests.post(url, headers=headers, json=payload)

def fetch_and_summarize():
    all_news_raw = ""
    categories = [
        (f"https://newsapi.org/v2/top-headlines?country=tw&pageSize=20&apiKey={NEWS_API_KEY}", "國內"),
        (f"https://newsapi.org/v2/top-headlines?language=en&pageSize=20&apiKey={NEWS_API_KEY}", "國際"),
        (f"https://newsapi.org/v2/everything?q=AI&pageSize=20&apiKey={NEWS_API_KEY}", "AI科技")
    ]
    for url, label in categories:
        try:
            res = requests.get(url).json()
            all_news_raw += f"\n--- {label} 素材 ---\n"
            for a in res.get("articles", []):
                all_news_raw += f"標題：{a.get('title', '')}\n摘要：{a.get('description', '')}\n\n"
        except: pass

    try:
        # 🌟 找回最強的 AI 模型偵測與自動切換機制
        genai.configure(api_key=GEMINI_API_KEY)
        print("正在偵測可用 AI 模型...")
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        priority_list = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        final_attempt_list = [p for p in priority_list if p in available_models]
        for m in available_models:
            if m not in final_attempt_list:
                final_attempt_list.append(m)

        weather_raw = get_detailed_weather()
        ai_output = None
        successful_model = None
        
        prompt = f"""
        你是一位頂級「新聞主播」兼「領域首席專家」。請根據素材產出情報。
        
        【要求】
        1. 語言：100% 繁體中文。
        2. 格式：絕對禁止使用 Markdown 粗體符號（**）。請直接輸出純文字。
        3. 語氣：直接破題，不要出現「好的」、「以下是」等冗餘開頭。
        4. 內容：每個主題精選 5 篇新聞。
        5. 氣象：扮演專業氣象主播，分析溫差變化、準確預測降雨時段，並給予具體的衣著/雨具建議。
        6. 新聞結構：
           【新聞序號】標題文字
           (直接說明新聞內容，不使用標籤文字，單純敘述事件)
           進一步思考：(由專家給出深度、犀利的看法)

        請務必將四個部分用 [WEATHER], [INTL], [TW], [AI] 標籤隔開輸出，方便系統解析。
        
        素材：
        氣象：{weather_raw}
        新聞：{all_news_raw}
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
        
        # 解析 AI 輸出的內容
        sections = {"WEATHER": "", "INTL": "", "TW": "", "AI": ""}
        current_sec = ""
        for line in ai_output.split('\n'):
            if "[WEATHER]" in line: current_sec = "WEATHER"
            elif "[INTL]" in line: current_sec = "INTL"
            elif "[TW]" in line: current_sec = "TW"
            elif "[AI]" in line: current_sec = "AI"
            elif current_sec: sections[current_sec] += line + "\n"

        # 發送結構化訊息
        send_line_structured_flex(
            sections["WEATHER"].strip(), 
            sections["INTL"].strip(), 
            sections["TW"].strip(), 
            sections["AI"].strip(), 
            successful_model
        )
        
        print("✅ 任務圓滿完成！")

    except Exception as e:
        print(f"❌ 執行出錯：{e}")

if __name__ == "__main__":
    fetch_and_summarize()
