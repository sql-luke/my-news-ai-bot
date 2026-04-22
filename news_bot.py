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
                "altText": "🌍 全球科技趨勢情報已送達！",
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
                                "text": "🌍 全球科技趨勢情報",
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
    # 2. 擴大搜索範圍：包含 AI, 科技, 半導體, 創新, 數位轉型
    # 增加 pageSize 到 15，提供更多原始素材給 AI 篩選分析
    search_query = "(AI OR 科技 OR 半導體 OR 數位轉型 OR 創新)"
    url = f"https://newsapi.org/v2/everything?q={search_query}&language=zh&sortBy=publishedAt&pageSize=15&apiKey={NEWS_API_KEY}"
    
    try:
        print("正在獲取全球科技資料...")
        response = requests.get(url)
        data = response.json()
        articles = data.get("articles", [])
        
        if not articles:
            output_content = "⚠️ 今日未能獲取相關科技新聞，請檢查 API 額度。"
            successful_model = "無"
        else:
            # 整理新聞內容：精簡化，不傳送來源媒體資訊給 AI，專注於標題與內容
            news_raw_data = ""
            for i, a in enumerate(articles):
                title = a.get('title', '無標題')
                desc = a.get('description', '無摘要內容')
                news_raw_data += f"\n[資料 {i+1}] {title}\n摘要：{desc}\n"
            
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
                    
                    # 💡 針對擴大範圍與精簡來源設計的新 Prompt
                    prompt = f"""
                    你是一位「具備全球視野」的科技趨勢專欄作家。
                    請閱讀以下來自全球的科技、AI 與半導體相關資訊，為我進行精煉的分析。
                    
                    【⚠️ 排版限制】
                    1. 絕對不使用 Markdown 符號（如 `#`, `**`, `*`）。
                    2. 絕對不附上連結。
                    3. 全程使用「條列式」，每句盡量不超過 30 字。
                    4. 使用全形括號【】標示重點。

                    【報告結構】請直接複製以下標題：

                    📰 【今日焦點】全球動態
                    (挑選 4 則最重磅的全球科技新聞。格式如下，嚴禁標註新聞來源媒體)
                    • 完整標題文字
                    👉 重點解讀：(用一句話解釋這對全球科技界的影響)

                    📝 【核心摘要】重點濃縮
                    (用 2 到 3 條短句，總結今天全球科技環境的整體氣氛與關鍵變動)
                    • 
                    • 

                    💡 【深度洞察】世界趨勢
                    (從全球競爭、產業鏈轉移或社會變革的角度，提出 2 個獨特的發現)
                    • 
                    • 

                    🚀 【未來預測】應用與行動
                    (預測接下來的技術演變，並建議讀者在職場或生活中可以注意的機會)
                    • 
                    • 

                    素材內容：
                    {news_raw_data}
                    
                    請使用繁體中文，確保內容具備專業深度但文字白話易讀。
                    """
                    
                    response = model.generate_content(prompt)
                    ai_response_text = response.text
                    successful_model = model_name
                    print(f"✅ {model_name} 成功產出分析報告！")
                    break 
                except Exception as e:
                    print(f"❌ {model_name} 失敗 (原因：{str(e)[:50]}...)")
                    continue

            if not ai_response_text:
                raise Exception("所有可用模型皆無法執行。")

            output_content = ai_response_text

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 全球科技趨勢情報\n\n")
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
                'messages': [{'type': 'text', 'text': f"⚠️ 機器人報錯：\n{str(e)[:150]}"}]
            })

if __name__ == "__main__":
    fetch_and_summarize()
