import os
import requests
import google.generativeai as genai
import sys
from datetime import datetime

# 1. 讀取 GitHub Secrets 中的金鑰
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_and_summarize():
    # 2. 抓取新聞 (搜尋關鍵字：AI，語言：繁體/簡體中文)
    # 你可以修改 q= 後面的關鍵字，例如 q=Nvidia+AI
    url = f"https://newsapi.org/v2/everything?q=AI&language=zh&sortBy=publishedAt&pageSize=8&apiKey={NEWS_API_KEY}"
    
    try:
        print("正在從 News API 獲取資料...")
        response = requests.get(url)
        data = response.json()
        articles = data.get("articles", [])
        
        report_text = ""
        
        if not articles:
            report_text = "⚠️ 今日 News API 沒有回傳任何相關新聞，請檢查關鍵字設定。"
        else:
            # 整理新聞內容，包含來源與 URL 供 Gemini 參考
            news_content = ""
            for i, a in enumerate(articles):
                source_name = a.get('source', {}).get('name', '未知來源')
                title = a.get('title', '無標題')
                desc = a.get('description', '無摘要內容')
                link = a.get('url', '#')
                news_content += f"\n新聞 {i+1}：{title}\n來源：{source_name}\n連結：{link}\n摘要：{desc}\n"
            
            # 3. 設定 Gemini 與自動模型偵測
            genai.configure(api_key=GEMINI_API_KEY)
            
            # 自動找尋當前 API Key 可用的模型
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            # 優先順序：2.0-flash > 1.5-flash > 1.5-pro > gemini-pro
            target_models = [
                'models/gemini-2.0-flash', 
                'models/gemini-1.5-flash', 
                'models/gemini-1.5-pro', 
                'models/gemini-pro'
            ]
            
            chosen_model = None
            for tm in target_models:
                if tm in available_models:
                    chosen_model = tm
                    break
            
            if not chosen_model:
                chosen_model = available_models[0]
            
            print(f"🔄 偵測到可用模型，正在使用: {chosen_model}")
            
            # 4. 專業級 AI 提示詞 (Prompt)
            model = genai.GenerativeModel('gemini-1.5-flash')
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
            {news_content}
            
            請使用繁體中文回答，語氣要專業、精確且易於閱讀。
            """
            
            ai_response = model.generate_content(prompt)
            report_text = ai_response.text

        # 5. 寫入 Markdown 檔案
        # 取得目前台灣時間 (UTC+8)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 AI 每日新聞洞察\n\n")
            f.write(report_text)
            f.write(f"\n\n--- \n**⚙️ 系統資訊**")
            f.write(f"\n- 執行時間：{current_time}")
            f.write(f"\n- 使用模型：`{chosen_model}`")
            f.write(f"\n- 資料來源：NewsAPI.org")
            
        print("✅ 報告已成功生成至 daily_report.md")

    except Exception as e:
        # 強大容錯：即使出錯也寫入檔案，避免 GitHub Actions 報錯斷掉
        error_msg = f"❌ 執行過程中發生錯誤：{str(e)}"
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"# 🤖 機器人執行報告\n\n{error_msg}")
        print(error_msg)

if __name__ == "__main__":
    fetch_and_summarize()
