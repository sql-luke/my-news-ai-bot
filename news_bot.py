import os
import requests
import google.generativeai as genai
import sys
from datetime import datetime

# 1. 讀取密鑰
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_and_summarize():
    # 抓取新聞
    url = f"https://newsapi.org/v2/everything?q=AI&language=zh&sortBy=publishedAt&pageSize=8&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        articles = response.json().get("articles", [])
        news_content = ""
        for i, a in enumerate(articles):
            news_content += f"\n新聞 {i+1}：{a.get('title')}\n連結：{a.get('url')}\n"

        # 2. 設定 Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        
        # 獲取所有具備生成功能的模型名字
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 優先順序：我們把最穩定、免費配額最多的 1.5-flash 放在最前面
        # 刻意避開目前 2.0 系列可能的 0 配額陷阱
        priority_list = [
            'models/gemini-1.5-flash', 
            'models/gemini-1.5-pro', 
            'models/gemini-pro',
            'models/gemini-2.0-flash'
        ]
        
        # 整合清單：先按優先順序排，剩下的隨後
        final_attempt_list = [p for p in priority_list if p in available_models]
        for m in available_models:
            if m not in final_attempt_list:
                final_attempt_list.append(m)

        ai_response = None
        successful_model = None

        # 🚀 核心：暴力嘗試迴圈
        for model_name in final_attempt_list:
            try:
                print(f"正在嘗試模型：{model_name}...")
                model = genai.GenerativeModel(model_name)
                prompt = f"請將以下新聞整理成繁體中文摘要，並列出今日科技趨勢：\n{news_content}"
                
                # 試著跑跑看
                response = model.generate_content(prompt)
                
                # 如果跑到這行沒噴錯，代表成功了！
                ai_response = response.text
                successful_model = model_name
                print(f"✅ {model_name} 執行成功！")
                break 
            except Exception as e:
                # 如果是 429 (配額滿) 或 404 (找不到)，就寫 Log 並試下一個
                print(f"❌ {model_name} 失敗：{str(e)[:50]}...")
                continue

        if not ai_response:
            raise Exception("所有可用模型皆無法執行（可能是配額全滿或帳號受限）。")

        # 3. 寫入檔案
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"# 🤖 AI 每日新聞洞察\n\n{ai_response}\n\n")
            f.write(f"--- \n**⚙️ 系統資訊**\n- 執行時間：{current_time}\n- 最終成功模型：`{successful_model}`")

        print("✅ 任務圓滿完成！")

    except Exception as e:
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"# ❌ 系統最終崩潰報告\n\n內容：{str(e)}")
        print(f"💥 最終失敗：{str(e)}")

if __name__ == "__main__":
    fetch_and_summarize()
