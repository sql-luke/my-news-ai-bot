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
                        "backgroundColor": "#000000", # 標題區塊：純黑色
                        "paddingTop": "xl",
                        "paddingBottom": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🤖 AI 科技每日情報",
                                "weight": "bold",
                                "color": "#00FF41", # 駭客綠點綴標題 (若想純白可改為 #FFFFFF)
                                "size": "xl"
                            },
                            {
                                "type": "text",
                                "text": f"分析引擎: {model_name}",
                                "color": "#888888", # 次要資訊用暗灰色
                                "size": "xs",
                                "margin": "sm"
                            }
                        ]
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1A1A1A", # 內文區塊：深灰色，減輕純黑對比的視覺疲勞
                        "paddingTop": "lg",
                        "paddingBottom": "xl",
                        "contents": [
                            {
                                "type": "text",
                                "text": text_content,
                                "wrap": True,
                                "size": "sm",
                                "color": "#F5F5F5", # 內文：柔和的灰白色 (比純白刺眼度低)
                                "lineSpacing": "6px" # 增加行距讓長文更好讀
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
                    
                    # 💡 全新四段式 Prompt 設計
                    prompt = f"""
                    你是一位頂尖的科技趨勢分析師。請仔細閱讀以下最新收集到的 AI 新聞，為我進行深度分析。
                    
                    【⚠️ 排版嚴格限制】
                    1. 絕對不要使用 Markdown 符號（如 `#`, `**`, `*`），通訊軟體無法正常顯示。
                    2. 請嚴格使用以下四個帶有 Emoji 的段落標題進行輸出，段落之間請空一行。
                    3. 絕對不要附上任何網址連結。

                    【報告結構】

                    📰 今日焦點新聞
                    (請列出最重要的 3-4 則新聞。直接列出完整標題與來源，格式例如：標題 (來源：某某媒體))

                    📝 重點摘要說明
                    (針對上述焦點新聞，用幾句話濃縮出今天 AI 圈發生的核心事件與重點)

                    💡 深度洞察發現
                    (根據這些新聞，提出你身為分析師的洞察。這對產業鏈代表什麼？或是我們該注意什麼潛在現象？)

                    🚀 預測與實際應用
                    (將新聞訊息轉化為行動方針。預測未來可能發生的事，或建議一般讀者/企業現在可以採取什麼實際準備)

                    以下是今日的新聞素材：
                    {news_raw_data}
                    
                    請使用繁體中文回答，語氣要專業、精準、直接破題。
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
