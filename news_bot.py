import os
import requests
import google.generativeai as genai
import sys
from datetime import datetime

# 1. 讀取 GitHub Secrets 中的 API 金鑰
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_and_summarize():
    # 2. 抓取新聞 (搜尋關鍵字：AI，語言：繁體/簡體中文)
    # 你可以修改 q= 後面的關鍵字，例如 q=Nvidia+AI 或 q=半導體
    url = f"https://newsapi.org/v2/everything?q=AI&language=zh&sortBy=publishedAt&pageSize=8&apiKey={NEWS_API_KEY}"
    
    try:
        print("正在從 News API 獲取資料...")
        response = requests.get(url)
        data = response.json()
        articles = data.get("articles", [])
        
        if not articles:
            output_content = "⚠️ 今日 News API 沒有回傳任何相關新聞，請檢查關鍵字設定或 API 額度。"
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
            
            # 設定嘗試順序：1.5-flash 最穩定且配額多，放在第一位
            priority_list = [
                'models/gemini-1.5-flash', 
                'models/gemini-1.5-pro', 
                'models/gemini-pro',
                'models/gemini-2.0-flash' # 2.0 目前免費版配額較嚴格，放後面
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
                    
                    prompt = f"""
                    你是一位資深的科技趨勢分析師。請針對以下新聞內容，製作一份精煉且具深度的《AI 科技每日情報》。
                    
                    格式要求：
                    1. 【核心摘要】：請用兩句話總結今日全球 AI 發展的最重大轉折。
                    2. 【重點新聞追蹤】：精選 3-4 則最具影響力的新聞。
                       - 格式：**[標題]** (來源：[媒體名稱])
                       - 內容簡述：重點說明該事件發生的核心原因與具體內容。
                       - 連結：請務必保留原始新聞連結。
                    3. 【深度洞察分析】：
                       - 總結 2-3 個今日最值得關注的趨勢。
                       - 分別從「產業結構影響」與「大眾生活改變」兩個面向深入解析。
                    4. 【今日思考題】：拋出一個關於 AI 發展與人類社會關係的延伸問題。

                    新聞內容：
                    {news_raw_data}
                    
                    請使用繁體中文回答，語氣要專業、精確且易於閱讀。
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

        # 4. 寫入 Markdown 檔案
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 AI 每日新聞洞察\n\n")
            f.write(output_content)
            f.write(f"\n\n--- \n**⚙️ 系統資訊**")
            f.write(f"\n- 執行時間：{current_time} (UTC)")
            f.write(f"\n- 最終選用模型：`{successful_model}`")
            f.write(f"\n- 資料來源：NewsAPI.org")
            
        print("✅ 任務圓滿完成！請查看 daily_report.md")

    except Exception as e:
        # 強大容錯：即使出錯也寫入檔案，避免 GitHub Actions 報錯斷掉
        error_msg = f"❌ 執行過程中發生錯誤：{str(e)}"
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"# 🤖 機器人執行報告\n\n系統在處理過程中遇到問題：\n`{error_msg}`")
        print(error_msg)

if __name__ == "__main__":
    fetch_and_summarize()
