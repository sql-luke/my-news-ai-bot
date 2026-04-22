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
    """使用 LINE Flex Message 發送具有大標題排版的精美卡片"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("⚠️ 缺少 LINE 金鑰，跳過 LINE 推播")
        return

    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    
    # Flex Message 的 JSON 排版結構
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
                        "backgroundColor": "#2c3e50", # 專業的深藍灰色背景
                        "contents": [
                            {
                                "type": "text",
                                "text": "🤖 AI 科技每日情報",
                                "weight": "bold",
                                "color": "#ffffff",
                                "size": "xl" # 放大標題字體
                            },
                            {
                                "type": "text",
                                "text": f"分析引擎: {model_name}",
                                "color": "#aab7c4",
                                "size": "xs",
                                "margin": "sm"
                            }
                        ]
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": text_content,
                                "wrap": True,
                                "size": "sm",
                                "color": "#333333"
                            }
                        ]
                    }
                }
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("✅ LINE Flex 訊息推送成功！")
    else:
        print(f"❌ LINE 推送失敗：{response.status_code}, {response.text}")

def fetch_and_summarize():
    # 2. 抓取新聞 (搜尋關鍵字：AI)
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
            # 整理新聞內容 (移除連結，只保留標題、來源與摘要給 Gemini 分析)
            news_raw_data = ""
            for i, a in enumerate(articles):
                source_name = a.get('source', {}).get('name', '未知來源')
                title = a.get('title', '無標題')
                desc = a.get('description', '無摘要內容')
                news_raw_data += f"\n[新聞 {i+1}] {title}\n來源：{source_name}\n摘要：{desc}\n"
            
            # 3. 設定 Gemini 
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
                    
                    # 全新升級的 Prompt 提示詞：著重分析與排版
                    prompt = f"""
                    你是一位頂尖的科技趨勢分析師。請仔細閱讀以下最新收集到的 AI 新聞，為我進行深度分析，並撰寫一份專業報告。
                    
                    【⚠️ 排版嚴格限制】
                    1. 絕對不要使用 Markdown 符號（如 `#`, `**`, `*`），因為通訊軟體無法顯示。
                    2. 請使用空白行來分段。
                    3. 不要附上任何網址連結。

                    【報告結構要求】
                    請依序包含以下四個區塊，並直接使用我提供的 Emoji 作為段落標題：

                    📊 數據總結與結論
                    (請綜合這批新聞，用一段話寫出今日 AI 發展的核心結論與走向)

                    📰 焦點新聞追蹤
                    (挑選 3 則最重要的新聞，列出標題與來源，並用一句話解釋為何重要)

                    💡 深度洞察與發現
                    (根據新聞內容，分析出 2 個值得注意的產業洞察、隱憂或市場發現)

                    🔮 未來趨勢預測
                    (根據上述資料，大膽預測未來 3 到 6 個月內可能發生的科技演變或社會影響)

                    以下是今日的新聞素材：
                    {news_raw_data}
                    
                    請使用繁體中文回答，語氣要專業、精準。
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

        # 4. 寫入 Markdown 檔案與發送 LINE 推播
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 AI 每日新聞洞察\n\n")
            f.write(output_content)
            f.write(f"\n\n--- \n**⚙️ 系統資訊**")
            f.write(f"\n- 執行時間：{current_time} (UTC)")
            f.write(f"\n- 最終選用模型：`{successful_model}`")
            
        print("✅ 任務圓滿完成！準備推播至 LINE...")
        
        # 呼叫新的 Flex Message 函式
        send_line_flex_message(output_content, successful_model)

    except Exception as e:
        error_msg = f"❌ 執行過程中發生錯誤：{str(e)}"
        print(error_msg)
        # 若發生錯誤，發送簡單的純文字警告
        if LINE_ACCESS_TOKEN and LINE_USER_ID:
            url = 'https://api.line.me/v2/bot/message/push'
            requests.post(url, headers={'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'}, json={
                'to': LINE_USER_ID,
                'messages': [{'type': 'text', 'text': f"⚠️ 機器人出錯：\n{str(e)[:150]}"}]
            })

if __name__ == "__main__":
    fetch_and_summarize()
