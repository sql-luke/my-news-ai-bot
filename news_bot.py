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
    """獲取高雄詳細氣象數據"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=22.6163&longitude=120.3133&hourly=temperature_2m,precipitation_probability&daily=weathercode&timezone=Asia%2FTaipei&forecast_days=2"
    try:
        res = requests.get(url).json()
        hourly = res['hourly']
        
        t_8 = hourly['temperature_2m'][8]
        t_14 = hourly['temperature_2m'][14]
        t_20 = hourly['temperature_2m'][20]
        
        today_rain_probs = hourly['precipitation_probability'][0:24]
        max_rain_prob = max(today_rain_probs)
        max_rain_hour = today_rain_probs.index(max_rain_prob)
        
        weather_raw = f"""
        [高雄詳細氣象數據]
        今日氣溫分布：早上8點 {t_8}°C、下午2點 {t_14}°C、晚上8點 {t_20}°C。
        今日降雨資訊：最高降雨機率為 {max_rain_prob}%，最可能降雨時間點在 {max_rain_hour}:00 左右。
        """
        return weather_raw
    except Exception as e:
        print(f"氣象擷取錯誤: {e}")
        return "[高雄氣象數據] 目前系統連線異常，請提醒注意天氣變換。"

def create_section(title, content):
    """建立 Flex Message 區塊，並針對「新聞標題」與「總結」做特殊排版"""
    blocks = [
        {
            "type": "text",
            "text": title,
            "weight": "bold",
            "color": "#00FF41", # 大分類標題：駭客綠
            "size": "lg",       # 尺寸加大到 lg
            "margin": "xl"      # 增加上方間距
        }
    ]
    
    for line in content.split('\n'):
        line = line.replace("**", "").strip()
        if not line: continue
        
        # 特殊排版 1：偵測到「總結：」，賦予專屬金色與粗體
        if line.startswith("總結："):
            blocks.append({
                "type": "text", "text": line, "weight": "bold", 
                "color": "#FFD700", "size": "sm", "wrap": True, "margin": "md"
            })
        # 特殊排版 2：偵測到新聞標題 (帶有【】符號)，放大字體、加粗、純白色
        elif line.startswith("【") and "】" in line:
            blocks.append({
                "type": "text", "text": line, "weight": "bold", 
                "color": "#FFFFFF", "size": "md", "wrap": True, "margin": "lg"
            })
        # 一般內文：維持舒適的淺灰小字
        else:
            blocks.append({
                "type": "text", "text": line, 
                "color": "#E0E0E0", "size": "sm", "wrap": True, "margin": "sm"
            })
            
    return blocks

def send_line_flex_message(weather_text, intl_text, tw_text, ai_text, model_name):
    """發送單一結構化 Flex Message 卡片"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID: return

    url = 'https://api.line.me/v2/bot/message/push'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'}
    
    body_contents = []
    if weather_text: body_contents.extend(create_section("🌦️ 氣象主播特報", weather_text))
    if intl_text: body_contents.extend(create_section("🌍 全球焦點新聞", intl_text))
    if tw_text: body_contents.extend(create_section("🇹🇼 國內時事脈動", tw_text))
    if ai_text: body_contents.extend(create_section("🤖 科技與 AI 前沿", ai_text))

    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": "🌍 您的全方位晨間情報已送達！",
                "contents": {
                    "type": "bubble", "size": "mega",
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
            }
        ]
    }
    requests.post(url, headers=headers, json=payload)

def fetch_and_summarize():
    all_news_raw = ""
    categories = [
        (f"https://newsapi.org/v2/everything?q=台灣 OR 台北 OR 台積電&language=zh&sortBy=publishedAt&pageSize=20&apiKey={NEWS_API_KEY}", "國內"),
        (f"https://newsapi.org/v2/top-headlines?language=en&pageSize=40&apiKey={NEWS_API_KEY}", "國際"),
        (f"https://newsapi.org/v2/everything?q=AI OR 人工智慧 OR 核能 OR 科技突破&language=zh&sortBy=publishedAt&pageSize=20&apiKey={NEWS_API_KEY}", "科技")
    ]
    
    for url, label in categories:
        try:
            res = requests.get(url).json()
            all_news_raw += f"\n--- {label} 素材 ---\n"
            for a in res.get("articles", []):
                all_news_raw += f"標題：{a.get('title', '')}\n摘要：{a.get('description', '')}\n\n"
        except: pass

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("正在偵測可用 AI 模型...")
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        priority_list = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        final_attempt_list = [p for p in priority_list if p in available_models]
        for m in available_models:
            if m not in final_attempt_list: final_attempt_list.append(m)

        weather_raw = get_detailed_weather()
        ai_output = None
        successful_model = None
        
        prompt = f"""
        你是一位頂級的「新聞主播」。請根據素材產出情報。
        
        【⚠️ 絕對嚴格限制】
        1. 語言：100% 繁體中文，禁止夾雜英文句子。
        2. 格式：禁止使用 Markdown 粗體（**）。
        
        【輸出結構】請嚴格依照下方格式：

        [WEATHER]
        (請化身「專業氣象主播」，用溫暖且專業的口吻播報以下數據。必須包含早中晚溫差變化、精準降雨時段預測，並給予具體的「穿搭建議」與「雨具提醒」。)
        氣象數據：{weather_raw}

        [INTL]
        (精選 5 篇影響全人類或國際局勢的新聞，以沉穩專業的主播口吻詳述)
        【1】新聞標題
        (新聞細節...)
        總結：(一句話精華)
        (依此類推)

        [TW]
        (精選 5 篇與台灣社會、經濟最相關的重大新聞，以主播口吻詳述)
        【1】新聞標題
        (新聞細節...)
        總結：(一句話精華)
        (依此類推)

        [AI]
        (精選 5 篇聚焦於 AI、核能或科技突破，以主播口吻詳述)
        【1】新聞標題
        (新聞細節...)
        總結：(一句話精華)
        (依此類推)

        新聞素材：
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
        
        # 解析 AI 輸出的內容
        sections = {"WEATHER": "", "INTL": "", "TW": "", "AI": ""}
        current_sec = ""
        plain_text_builder = f"🤖 AI 晨間情報 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
        
        for line in ai_output.split('\n'):
            clean_line = line.replace("**", "").strip()
            if "[WEATHER]" in clean_line: 
                current_sec = "WEATHER"
            elif "[INTL]" in clean_line: 
                current_sec = "INTL"
            elif "[TW]" in clean_line: 
                current_sec = "TW"
            elif "[AI]" in clean_line: 
                current_sec = "AI"
            elif current_sec: 
                sections[current_sec] += clean_line + "\n"
                plain_text_builder += clean_line + "\n"

        # 發送精美卡片
        send_line_flex_message(
            sections["WEATHER"].strip(), 
            sections["INTL"].strip(), 
            sections["TW"].strip(), 
            sections["AI"].strip(), 
            successful_model
        )
        
        # 保留 GitHub 本地的文字檔備份
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(plain_text_builder)
            
        print("✅ 任務圓滿完成！")

    except Exception as e:
        print(f"❌ 執行出錯：{e}")

if __name__ == "__main__":
    fetch_and_summarize()
