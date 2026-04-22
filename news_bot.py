import os
import requests
import google.generativeai as genai
from datetime import datetime

# 1. 讀取 GitHub Secrets 中的 API 金鑰
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def send_line_flex_message(text_content, model_name):
    """發送深色模式 (Dark Mode) 的 LINE Flex Message"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("⚠️ 缺少 LINE 金鑰，跳過 LINE 推播")
        return

    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    
    # 🖤 深色模式 Flex Message 排版
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": "🤖 您的 AI 科技每日情報已送達！",
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
                                "text": "🤖 AI 科技每日情報",
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
        print("✅ LINE 深色 Flex 訊息推送成功！")
    else:
        print(f"❌ LINE 推送失敗：{response.status_code}, {response.text}")

def fetch_and_summarize():
    url = f"https://newsapi.org/v2/everything?q=AI&language=zh&sortBy=publishedAt&pageSize=8&apiKey={NEWS_API_KEY}"
    
    try:
        print("正在從 News API 獲取資料...")
        response = requests.get(url)
        data = response.json()
        articles = data.get("articles", [])
        
        if not articles:
            output_content = "⚠️ 今日 News API 沒有回傳任何相關新聞，請檢查關鍵字設定或 API 額度。"
            successful_model = "無"
        else:
            news_raw_data = ""
            for i, a in enumerate(articles):
                source_name = a.get('source', {}).get('name', '未知來源')
                title = a.get('title', '無標題')
                desc = a.get('description', '無摘要內容')
                news_raw_data += f"\n[新聞 {i+1}] {title}\n來源：{source_name}\n摘要：{desc}\n"
            
            genai.configure(api_key=GEMINI_API_KEY)
            print("正在偵測可用 AI 模型...")
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            priority_list = [
                'models/gemini-2.5-flash',
                'models/gemini-1.5-flash', 
                'models/gemini-1.5-pro'
            ]
            
            final_attempt_list = [p for p in priority_list if p in available_models]
            for m in available_models:
                if m not in final_attempt_list:
                    final_attempt_list.append(m)

            ai_response_text = None
            successful_model = None

            for model_name in final_attempt_list:
                try:
                    print(f"嘗試使用模型：{model_name}...")
                    model = genai.GenerativeModel(model_name)
                    
                    # 💡 易讀性大升級的 Prompt 設計
                    prompt = f"""
                    你是一位「善於將複雜科技白話文化」的 AI 科技專欄作家。
                    你的目標是讓讀者在早上通勤的 1 分鐘內，輕鬆、無痛地吸收今天最重要的 AI 資訊。
                    請閱讀以下新聞，並嚴格依照格式輸出。

                    【⚠️ 排版與語氣嚴格限制】
                    1. 絕對不使用 Markdown 符號（如 `#`, `**`, `*`）。
                    2. 絕對不附上任何網址連結。
                    3. 語氣要像朋友分享新知一樣輕鬆、口語，避免生硬的學術名詞。
                    4. 全程使用「條列式」，句子越短越好，每句盡量不超過 30 字。
                    5. 善用全形括號【】來標示專有名詞或重點，取代粗體效果。

                    【報告結構】請直接複製以下帶有 Emoji 的段落標題：

                    📰 【今日焦點】一秒看懂
                    (請挑選最重要的 3 則新聞，格式如下)
                    • 標題 (媒體名稱)
                    👉 發生什麼事：(用一句最白話的話解釋)

                    📝 【重點摘要】總結
                    (綜合以上新聞，用 2 條短句總結今天的 AI 發展主軸)
                    • 
                    • 

                    💡 【深度洞察】這代表什麼？
                    (從產業或大眾生活的角度，提煉 2 個有趣的觀察)
                    • 
                    • 

                    🚀 【未來預測】我們可以怎麼做？
                    (給讀者 1 到 2 個具體的未來預測，或是可以直接應用的建議)
                    • 
                    • 

                    以下是今日的新聞素材：
                    {news_raw_data}
                    
                    請使用繁體中文回答，確保排版乾淨俐落、充滿呼吸空間。
                    """
                    
                    response = model.generate_content(prompt)
                    ai_response_text = response.text
                    successful_model = model_name
                    print(f"✅ {model_name} 成功產出報告！")
                    break 
                except Exception as e:
                    print(f"❌ {model_name} 失敗 (原因：{str(e)[:50]}...)，嘗試下一個...")
                    continue

            if not ai_response_text:
                raise Exception("所有可用模型皆無法執行。")

            output_content = ai_response_text

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 AI 每日新聞洞察\n\n")
            f.write(output_content)
            f.write(f"\n\n--- \n**⚙️ 系統資訊**")
            f.write(f"\n- 執行時間：{current_time} (UTC)")
            f.write(f"\n- 最終選用模型：`{successful_model}`")
            
        print("✅ 任務圓滿完成！準備推播至 LINE...")
        send_line_flex_message(output_content, successful_model)

    except Exception as e:
        error_msg = f"❌ 執行過程中發生錯誤：{str(e)}"
        print(error_msg)
        if LINE_ACCESS_TOKEN and LINE_USER_ID:
            url = 'https://api.line.me/v2/bot/message/push'
            requests.post(url, headers={'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'}, json={
                'to': LINE_USER_ID,
                'messages': [{'type': 'text', 'text': f"⚠️ 機器人出錯：\n{str(e)[:150]}"}]
            })

if __name__ == "__main__":
    fetch_and_summarize()
