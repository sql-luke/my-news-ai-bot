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
# LINE_USER_ID 現在可以支援多個，請在 Secrets 用逗號分隔，例如: U123...,U456...
LINE_USER_IDS = os.getenv("LINE_USER_ID", "").split(",") 
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
GDRIVE_CLIENT_ID = os.getenv("GDRIVE_CLIENT_ID")
GDRIVE_CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
GDRIVE_REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")

if not GEMINI_API_KEY:
    print("❌ 嚴重錯誤：找不到 GEMINI_API_KEY")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

# 【自定義人聲清單】你可以隨時更換這裡的字串
VOICES = {
    "HostA": "zh-CN-XiaoxiaoNeural", # 大陸曉曉(女聲)
    "HostB": "zh-CN-YunxiNeural"      # 大陸雲希(男聲)
}

# ==========================================
# 2. 核心功能：雙人劇本生成 (NotebookLM 優化版)
# ==========================================
def generate_podcast_script(news_summary):
    # 這裡的 Prompt 是讓對話變順的關鍵
    prompt = f"""
    你現在是專業的 AI Podcast 製作人，風格模仿 NotebookLM。
    請根據以下新聞內容，寫一段 HostA (女) 與 HostB (男) 的深度聊天劇本。
    
    製作要求：
    1. 非常口語化：多使用「嗯...」、「對啊」、「其實」、「你知道嗎？」、「我跟你說喔」。
    2. 反應式對話：當 HostA 講完一個新聞點，HostB 不要直接講下一個，要先給予短回應（如：真的假的小心點、這影響很大耶）。
    3. 節奏感：每句話不要太長，像真實聊天一樣有來有往。
    4. 禁止唸稿感：不要說「以下是今天的財經新聞」，要說「喔對了，說到錢，你有看今天的股市嗎？」。
    
    輸出格式：純 JSON 陣列，不要有任何 Markdown 標記。
    範例：[
      {{"speaker": "HostA", "text": "欸，你有看到明天的天氣嗎？會變超冷的。"}},
      {{"speaker": "HostB", "text": "喔？真的嗎？我才正打算明天去海邊耶。"}},
      {{"speaker": "HostA", "text": "那我看你還是待在家喝咖啡好了，北部會下探12度喔。"}},
      {{"speaker": "HostB", "text": "哇...那真的差很多耶，看來毛衣要拿出來了。"}},
    ]
    
    內容：{news_summary}
    """
    
    print("🔍 查詢可用模型...")
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name.replace('models/', ''))
    except Exception as e:
        print(f"查詢失敗: {e}")

    preferred = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    selected = next((m for m in preferred if m in available_models), available_models[0])
    print(f"🚀 使用模型: {selected}")
    
    try:
        model = genai.GenerativeModel(selected)
        response = model.generate_content(prompt)
        
        # 清理 JSON
        content = response.text.strip()
        triple_backticks = chr(96) * 3 
        content = content.replace(triple_backticks + "json", "").replace(triple_backticks, "").strip()
            
        return json.loads(content)
    except Exception as e:
        raise Exception(f"生成劇本失敗: {e}")

# ==========================================
# 3. 核心功能：語音生成與拼接 (增加動態停頓)
# ==========================================
async def generate_audio(script, output_file):
    print("🎙️ 正在生成語音並進行 NotebookLM 風格拼接...")
    final_audio = AudioSegment.empty()
    
    for i, line in enumerate(script):
        text = line.get('text', '')
        speaker = line.get('speaker', 'HostA')
        voice = VOICES.get(speaker, VOICES["HostA"])
        temp_name = f"segment_{i}.mp3"
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_name)
        
        segment = AudioSegment.from_mp3(temp_name)
        
        # 動態調整停頓：如果是 HostB 在回應，停頓縮短一點會更自然
        pause_duration = 300 if speaker == "HostB" else 500
        pause = AudioSegment.silent(duration=pause_duration)
        
        final_audio += segment + pause
        os.remove(temp_name)
    
    final_audio.export(output_file, format="mp3", bitrate="128k")
    return output_file

# ==========================================
# 4. API 實作：Google Drive 上傳
# ==========================================
def upload_to_gdrive(file_path):
    print("📡 正在上傳至 Google Drive...")
    token_url = "https://oauth2.googleapis.com/token"
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
    upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.post(upload_url, headers=headers, files=files)
    res.raise_for_status()
    file_id = res.json().get("id")

    perm_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions"
    requests.post(perm_url, headers=headers, json={"role": "reader", "type": "anyone"})
    
    return f"https://docs.google.com/uc?export=download&id={file_id}"

# ==========================================
# 5. API 實作：LINE Flex Message (支援多人發送)
# ==========================================
def send_line_podcast(audio_url):
    print(f"💬 正在向 {len(LINE_USER_IDS)} 位使用者發送 LINE 訊息...")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    
    for user_id in LINE_USER_IDS:
        user_id = user_id.strip()
        if not user_id: continue
        
        payload = {
            "to": user_id,
            "messages": [{
                "type": "flex",
                "altText": "雙聲道 Podcast 已經準備好囉！",
                "contents": {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {"type": "text", "text": "🎙️ AI 雙人晨間新聞", "weight": "bold", "size": "xl"},
                            {"type": "text", "text": "更自然的口語對話版本", "size": "xs", "color": "#aaaaaa", "margin": "sm"},
                            {
                                "type": "button",
                                "action": {
                                    "type": "uri",
                                    "label": "▶️ 播放今日對話",
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
        try:
            line_url = "https://api.line.me/v2/bot/message/push"
            res = requests.post(line_url, headers=headers, json=payload)
            res.raise_for_status()
            print(f"✅ 已成功傳送給: {user_id[:8]}...")
        except Exception as e:
            print(f"❌ 傳送給 {user_id} 失敗: {e}")

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
        print("🚀 開始執行升級版 AI Podcast 任務...")
        script = generate_podcast_script(news_content)
        
        output_file = "daily_news_podcast.mp3"
        asyncio.run(generate_audio(script, output_file))
        
        audio_link = upload_to_gdrive(output_file)
        send_line_podcast(audio_link)
        
        print("🎉 全部優化任務已完成！")
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")

if __name__ == "__main__":
    main()
