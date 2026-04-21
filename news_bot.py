import os
import requests
import google.generativeai as genai
import sys

# 讀取金鑰
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_and_summarize():
    # 1. 抓取新聞
    url = f"https://newsapi.org/v2/everything?q=AI&language=zh&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        articles = data.get("articles", [])
        
        report_text = ""
        
        if not articles:
            report_text = "⚠️ 今日 News API 沒有回傳任何相關新聞。"
        else:
            news_content = ""
            for i, a in enumerate(articles):
                news_content += f"\n新聞 {i+1}：{a.get('title','')}\n摘要：{a.get('description','')}\n"
            
            # 2. 設定 Gemini
            genai.configure(api_key=GEMINI_API_KEY)
            
            # 🚀 這裡換成最穩定的模型名稱
            # 如果 1.5-flash 還是不行，可以改成 'gemini-1.5-pro'
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"請將以下新聞整理成繁體中文摘要，並列出三個今日最值得關注的科技趨勢：\n{news_content}"
            
            ai_response = model.generate_content(prompt)
            report_text = ai_response.text

        # 3. 寫入檔案
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 AI 每日新聞洞察\n\n")
            f.write(report_text)
            f.write(f"\n\n--- \n*最後更新時間：{os.popen('date').read()}*")
            
        print("✅ 報告生成成功！")

    except Exception as e:
        # 如果模型報錯，這裡會寫入具體的錯誤訊息
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"❌ 發生錯誤，請檢查模型設定：{e}")
        print(f"❌ 錯誤：{e}")

if __name__ == "__main__":
    fetch_and_summarize()
