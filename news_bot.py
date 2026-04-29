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

# API 金鑰檢查
if not GEMINI_API_KEY:
    print("❌ 嚴重錯誤：找不到 GEMINI_API_KEY！請確認 GitHub Secrets 已設定且名稱拼寫正確。")
    exit(1)

# 設定 Gemini
genai.configure(api_key=GEMINI_API_KEY)

# 語音角色設定 (Edge TTS 台灣口音)
VOICES = {
    "HostA": "zh-TW-HsiaoChenNeural", # 女聲 (主 Key)
    "HostB": "zh-TW-YunJheNeural"     # 男聲 (搭檔)
}

# ==========================================
# 2. 核心功能：雙人劇本生成 (動態模型偵測版)
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
    
    print("🔍 正在向伺服器查詢您的 API Key 支援哪些模型...")
    available_models = []
    try:
        # 動態抓取支援 generateContent 的模型清單
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                clean_name = m.name.replace('models/', '')
                available_models.append(clean_name)
        
        print(f"✅ 您的金鑰可用的模型清單有: {available_models}")
        
    except Exception as e:
        raise Exception(f"❌ 查詢模型清單失敗，可能是 API Key 無效或網路問題: {e}")

    if not available_models:
        raise Exception("❌ 您的 API Key 沒有任何支援生成文字的模型。")

    # 偏好順序：越前面的越聰明/速度越快
    preferred_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro', 'gemini-1.0-pro']
    
    # 從您可用的模型中，挑出順位最高的一個
    selected_model = next((model for model in preferred_models if model in available_models), None)
    
    if not selected_model:
        selected_model = available_models[0]

    print(f"🚀 最終決定使用模型: {selected_model}")
    
    try:
        model = genai.GenerativeModel(selected_model)
        response = model.generate_content(prompt)
        
        content = response.text.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        return json.loads(content.strip())
        
    except Exception as e:
        raise Exception(f"使用模型 {selected_model} 執行失敗: {e}")

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
        os.remove(temp_name) 
    
    # 匯出最終檔案
    final_audio.export(output_file, format="mp3", bitrate="128k")
    return output_file

# ==========================================
# 4. API 實作：Google Drive 上傳
# ==========================================
def upload_to_gdrive(file_path):
    print("📡 正在上傳至 Google Drive...")
    
    # 這裡的網址已確保是純字串，沒有任何超連結干擾
    token_url = "[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)"
    token_data = {
        "client_id": GDRIVE_CLIENT_ID,
        "client_secret": GDRIVE_CLIENT_SECRET,
        "refresh_token": GDRIVE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    r = requests.post(token_url, data=token_data)
    r.raise_for_status()
    access_token = r.json().get("access_token")

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

    perm_url = f"[https://www.googleapis.com/drive/v3/files/](https://www.googleapis.com/drive/v3/files/){file_id}/permissions"
    requests.post(perm_url, headers=headers, json={"role": "reader", "type": "anyone"})
    
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
    
    line_url = "[https://api.line.me/v2/bot/message/push](https://api.line.me/v2/bot/message/push)"
    res = requests.post(line_url, headers=headers, json=payload)
    res.raise_for_status()

# ==========================================
# 主程式
# ==========================================
def main():
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
