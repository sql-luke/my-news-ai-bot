import os
import json
import asyncio
import requests
import edge_tts
from pydub import AudioSegment
import google.generativeai as genai

# ==========================================
# 1. 讀取 GitHub Secrets 環境變數
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
GDRIVE_CLIENT_ID = os.getenv("GDRIVE_CLIENT_ID")
GDRIVE_CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
GDRIVE_REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")

# 設定 Gemini
genai.configure(api_key=GEMINI_API_KEY)

# 語音角色設定 (Edge TTS 台灣口音)
VOICES = {
    "HostA": "zh-TW-HsiaoChenNeural", # 女聲 (主 Key)
    "HostB": "zh-TW-YunJheNeural"     # 男聲 (搭檔)
}

# ==========================================
# 2. 核心功能：雙人劇本生成 (具備自動備援機制)
# ==========================================
def generate_podcast_script(news_summary):
    prompt = f"""
    你現在是專業 Podcast 製作人。請根據以下新聞內容，寫一段兩人對話的 Podcast 劇本。
    - HostA (女)：主持人，節奏輕快、負責開場與主要播報。
    - HostB (男)：搭檔，負責提問、補充有趣點、或表達驚訝。
    請確保對話生動，像是在聊天而不是唸稿。
    
    輸出格式：純 JSON 陣列，不要有任何 Markdown 標記或說明文字。
    範例：[
      {{"speaker": "HostA", "text": "各位聽眾朋友大家好，我是 HostA！"}},
      {{"speaker": "HostB", "text": "大家好，我是 HostB！今天的新聞很有趣喔！"}}
    ]
    
    今日新聞內容：
    {news_summary}
    """
    
    # 依序嘗試目前最穩定與最新的模型名稱，防止 API 404 錯誤
    models_to_try = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    
    for model_name in models_to_try:
        try:
            print(f"🔄 正在嘗試使用模型: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            
            # 清理格式以確保 JSON 能夠被正確解析
            content = response.text.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            return json.loads(content.strip())
            
        except Exception as e:
            print(f"⚠️ 模型 {model_name} 發生錯誤: {e}")
            continue # 失敗則嘗試下一個模型
            
    # 如果迴圈跑完還是失敗，拋出最終錯誤
    raise Exception("❌ 所有設定的 Gemini 模型均無法呼叫，請確認 API 狀態或金鑰是否正確。")

# ==========================================
# 3. 核心功能：語音生成與拼接
# ==========================================
async def generate_audio(script, output_file):
    print("🎙️ 正在逐句生成語音並進行無縫拼接...")
    final_audio = AudioSegment.empty()
    pause = AudioSegment.silent(duration=400) # 對話間隔 0.4 秒的呼吸停頓
    
    for i, line in enumerate(script):
        text = line.get('text', '')
        speaker = line.get('speaker', 'HostA')
        voice = VOICES.get(speaker, VOICES["HostA"])
        temp_name = f"segment_{i}.mp3"
        
        # 產生單句語音
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_name)
        
        # 使用 pydub 拼接
        segment = AudioSegment.from_mp3(temp_name)
        final_audio += segment + pause
        os.remove(temp_name) # 用完即刪除暫存檔
    
    # 匯出最終檔案
    final_audio.export(output_file, format="mp3", bitrate="128k")
    return output_file

# ==========================================
# 4. API 實作：Google Drive 上傳
# ==========================================
def upload_to_gdrive(file_path):
    print("📡 正在上傳至 Google Drive...")
    # A. 透過 Refresh Token 換取臨時 Access Token
    token_url = "[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)"
    token_data = {
        "client_id": GDRIVE_CLIENT_ID,
        "client_secret": GDRIVE_CLIENT_SECRET,
        "refresh_token": GDRIVE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    r = requests.post(token_url, data=token_data)
    r.raise_for_status() # 確保請求成功
    access_token = r.json().get("access_token")

    # B. 上傳檔案
    metadata = {
        "name": os.path.basename(file_path),
        "parents": [GDRIVE_FOLDER_ID]
    }
    files = {
        'data': ('metadata', json.dumps(metadata), 'application/json'),
        'file': open(file_path, 'rb')
    }
    upload_url = "[https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart](https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart)"
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.post(upload_url, headers=headers, files=files)
    res.raise_for_status()
    file_id = res.json().get("id")

    # C. 設定權限為公開讀取並取得連結 (LINE 必須能公開讀取才能播放)
    perm_url = f"[https://www.googleapis.com/drive/v3/files/](https://www.googleapis.com/drive/v3/files/){file_id}/permissions"
    requests.post(perm_url, headers=headers, json={"role": "reader", "type": "anyone"})
    
    # 回傳直接下載連結格式
    return f"[https://docs.google.com/uc?export=download&id=](https://docs.google.com/uc?export=download&id=){file_id}"

# ==========================================
# 5. API 實作：LINE Flex Message 推播
# ==========================================
def send_line_podcast(audio_url):
    print("💬 正在發送 LINE 訊息...")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{
            "type": "flex",
            "altText": "您的雙聲道新聞 Podcast 已送到！",
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "🎙️ 今日雙人 Podcast 新聞", "weight": "bold", "size": "xl", "wrap": True},
                        {"type": "text", "text": "Gemini & Edge TTS 聯合製作", "size": "xs", "color": "#aaaaaa", "margin": "sm"},
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "▶️ 立即點擊播放",
                                "uri": audio_url
                            },
                            "style": "primary",
                            "color": "#1DB446",
                            "margin": "xl"
                        }
                    ]
                }
            }
        }]
    }
    res = requests.post("[https://api.line.me/v2/bot/message/push](https://api.line.me/v2/bot/message/push)", headers=headers, json=payload)
    res.raise_for_status()

# ==========================================
# 主程式
# ==========================================
def main():
    # 這裡放你原本抓取新聞的邏輯 (這是一組測試資料，確認流程跑通後可換成你的爬蟲/API)
    news_content = """
    氣象：明天全台降溫，北部低溫下探 15 度。
    國際：美國聯準會宣布利率維持不變。
    財經：台股今日開高走低，終場小跌 50 點。
    科技：AI 發展迅速，多家科技巨頭宣布加碼投資。
    生活：最新研究指出，每天喝三杯黑咖啡有助於提升代謝。
    """
    
    try:
        print("🚀 開始執行 AI Podcast 任務...")
        
        print("\n--- 步驟 1：生成雙人對話劇本 ---")
        script = generate_podcast_script(news_content)
        print("✅ 劇本生成完畢！")
        
        print("\n--- 步驟 2：製作音檔 ---")
        output_file = "daily_news_podcast.mp3"
        asyncio.run(generate_audio(script, output_file))
        print("✅ 音檔製作完畢！")
        
        print("\n--- 步驟 3：上傳雲端 ---")
        audio_link = upload_to_gdrive(output_file)
        print(f"✅ 上傳成功，音檔連結：{audio_link}")
        
        print("\n--- 步驟 4：發送 LINE 訊息 ---")
        send_line_podcast(audio_link)
        print("✅ LINE 推播發送成功！")
        
        print("\n🎉 任務全數順利完成！")
        
    except Exception as e:
        print(f"\n❌ 程式執行過程中發生錯誤: {e}")

if __name__ == "__main__":
    main()
