import os
import requests
import google.generativeai as genai
import sys
from datetime import datetime

# 1. 讀取 GitHub Secrets 中的 API 金鑰
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def send_line_message(message):
    """負責發送 LINE 訊息的函式"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("⚠️ 缺少 LINE 金鑰，跳過 LINE 推播")
        return

    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    payload = {
        'to': LINE_USER_ID,
        'messages': [
            {
                'type': 'text',
                'text': message
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("✅ LINE 訊息推送成功！")
    else:
        print(f"❌ LINE 推送失敗：{response.status_code}, {response.text}")

def fetch_and_summarize():
    # 2. 抓取新聞 (搜尋關鍵字：AI，語言：繁體/簡體中文)
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
            # 整理新聞內容，供 Gemini 參考
            news_raw_data = ""
            for i, a in enumerate(articles):
                source_name = a.get('source', {}).get('name', '未知來源')
                title = a.get('title', '無標題')
                desc = a.get('description', '無摘要內容')
                link = a.get('url', '#')
                news_raw_data += f"\n新聞 {i+1}：{title}\n來源：{source_name}\n連結：{link}\n摘要：{desc}\n"
            
            # 3. 設定 Gemini 
            genai.configure(api_key=GEMINI_API_KEY)
            
            # 獲取帳號目前「真正可用」的模型清單
            print("正在偵測可用 AI 模型...")
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            # 設定嘗試順序：把上次成功且最新的 2.5-flash 放第一位，加快執行速度
            priority_list = [
                'models/gemini-2.5-flash',
                'models/gemini-1.5-flash', 
                'models/gemini-1.5-pro', 
                'models/gemini-2.0-flash' 
            ]
            
            # 整合最終嘗試清單
            final_attempt_list = [p for p in priority_list if p in available_models]
            for m in available_models:
                if m not in final_attempt_list:
                    final_attempt_list.append(m)

            ai_response_text = None
            successful_model = None

            # 🚀 暴力嘗試迴圈：直到有一個模型成功產出內容
            for model_name in final_attempt_list:
                try:
                    print(f"嘗試使用模型：{model_name}...")
                    model = genai.GenerativeModel(model_name)
                    
                    # 這是修改後的 Prompt，特別強化了 Markdown 連結的輸出格式
                    prompt = f"""
                    你是一位資深的科技趨勢分析師。請針對以下新聞內容，製作一份精煉且具深度的《AI 科技每日情報》。
                    
                    格式要求：
                    1. 【核心摘要】：請用兩句話總結今日全球 AI 發展的最重大轉折。
                    2. 【重點新聞追蹤】：精選 3-4 則最具影響力的新聞。
                        - 格式：**[標題]** (來源：[媒體名稱])
                        - 內容簡述：重點說明該事件發生的核心原因與具體內容。
                        - 連結：請使用 Markdown 語法將網址包裝成超連結，例如：[👉 點此閱讀原始新聞](此處填入網址)
                    3. 【深度洞察分析】：
                        - 總結 2-3 個今日最值得關注的趨勢。
                        - 分別從「產業結構影響」與「大眾生活改變」兩個面向深入解析。
                    4. 【今日思考題】：拋出一個關於 AI 發展與人類社會關係的延伸問題。

                    新聞內容：
                    {news_raw_data}
                    
                    請使用繁體中文回答，語氣要專業、精確且易於閱讀。確保不要輸出 Markdown 語法以外的特殊字元，以確保在 LINE 介面上顯示正常。
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
                raise Exception("所有可用模型皆無法執行（可能是配額全滿或 API 版本衝突）。")

            output_content = ai_response_text

        # 4. 寫入 Markdown 檔案與發送 LINE 推播
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 寫入本機檔案 (給 GitHub Actions 備份用)
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 AI 每日新聞洞察\n\n")
            f.write(output_content)
            f.write(f"\n\n--- \n**⚙️ 系統資訊**")
            f.write(f"\n- 執行時間：{current_time} (UTC)")
            f.write(f"\n- 最終選用模型：`{successful_model}`")
            f.write(f"\n- 資料來源：NewsAPI.org")
            
        print("✅ 任務圓滿完成！準備推播至 LINE...")
        
        # 組合 LINE 要傳送的文字內容
        line_msg_text = f"🤖 AI 每日新聞洞察\n\n{output_content}\n\n---\n⚙️ 使用模型：{successful_model}"
        send_line_message(line_msg_text)

    except Exception as e:
        # 強大容錯：即使出錯也寫入檔案，並傳送 LINE 警告通知
        error_msg = f"❌ 執行過程中發生錯誤：{str(e)}"
        
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"# 🤖 機器人執行報告\n\n系統在處理過程中遇到問題：\n`{error_msg}`")
        print(error_msg)
        
        # 傳 LINE 告訴你壞掉了
        alert_msg = f"⚠️ AI 科技日報機器人出錯了！\n\n錯誤訊息：\n{str(e)[:150]}...\n\n請至 GitHub 檢查執行紀錄。"
        send_line_message(alert_msg)

if __name__ == "__main__":
    fetch_and_summarize()
