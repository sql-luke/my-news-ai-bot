import os
import requests
import google.generativeai as genai
import sys

# 1. 檢查變數是否存在
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not NEWS_API_KEY or not GEMINI_API_KEY:
    print("❌ 錯誤：找不到 API Key，請檢查 GitHub Secrets 設定。")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

def fetch_and_summarize():
    print("正在抓取新聞...")
    # 這裡將 q 換成更通用的關鍵字，確保有資料
    url = f"https://newsapi.org/v2/top-headlines?country=jp&category=technology&apiKey={NEWS_API_KEY}"
    
    response = requests.get(url)
    data = response.json()

    if response.status_code != 200:
        print(f"❌ News API 錯誤：{data.get('message', '未知錯誤')}")
        sys.exit(1)

    articles = data.get("articles", [])[:5]
    if not articles:
        print("⚠️ 找不到相關新聞，請嘗試更換關鍵字。")
        return

    print(f"成功抓取 {len(articles)} 則新聞，交給 Gemini 分析中...")
    
    news_content = ""
    for i, a in enumerate(articles):
        news_content += f"\n新聞 {i+1}：{a.get('title','')}\n摘要：{a.get('description','')}\n"

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"請將以下新聞整理成繁體中文摘要：\n{news_content}"
        ai_response = model.generate_content(prompt)
        
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 AI 每日新聞洞察\n\n")
            f.write(ai_response.text)
        print("✅ 報告生成成功！")
    except Exception as e:
        print(f"❌ Gemini 分析失敗：{e}")
        sys.exit(1)

if __name__ == "__main__":
    fetch_and_summarize()
