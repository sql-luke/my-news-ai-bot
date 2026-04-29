import os
import json
import asyncio
import edge_tts
from pydub import AudioSegment
import google.generativeai as genai
# import requests  # 保留用於你的 GDrive / LINE 上傳邏輯

# ==========================================
# 1. 基本設定與環境變數
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# 語音角色設定 (Edge TTS)
VOICES = {
    "HostA": "zh-TW-HsiaoChenNeural", # 女聲 (主導播報)
    "HostB": "zh-TW-YunJheNeural"     # 男聲 (補充、吐槽、提問)
}

# ==========================================
# 2. Gemini 雙人劇本生成邏輯
# ==========================================
def generate_podcast_script(news_data):
    """
    將新聞資料餵給 Gemini，並強制要求輸出 JSON 格式的雙人對話劇本。
    """
    prompt = f"""
    你現在是一個專業的 Podcast 製作人。請將以下 5 大類新聞（氣象、國際、財經、科技、生活）
    改寫成一段生動、口語化的雙人 Podcast 節目劇本。
    
    主持人設定：
    - HostA (女)：節目主 Key，熱情、專業，負責帶出主要新聞。
    - HostB (男)：搭檔，幽默、敏銳，負責補充細節、吐槽或提問。
    
    請務必以「純 JSON 陣列」格式輸出，不要包含任何 Markdown 標記 (如 ```json) 或其他說明文字。
    JSON 格式範例如下：
    [
      {{"speaker": "HostA", "text": "各位聽眾朋友大家好！歡迎收聽今天的每日新聞 Podcast，我是 HostA！"}},
      {{"speaker": "HostB", "text": "大家好，我是 HostB！今天的新聞真的非常精彩，尤其是科技圈又有大動作了。"}},
      ...
    ]
    
    今日新聞資料：
    {news_data}
    """
    
    model = genai.GenerativeModel('gemini-1.5-pro-latest') # 建議使用 1.5 pro 以獲得最佳邏輯
    response = model.generate_content(prompt)
    
    # 清理回應，確保是純 JSON
    raw_text = response.text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
        
    return json.loads(raw_text.strip())

# ==========================================
# 3. 異步生成單句語音音檔
# ==========================================
async def generate_audio_segment(text, voice, filename):
    """使用 Edge TTS 生成單句音檔"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

async def process_all_audio_segments(script_json):
    """根據劇本批次生成所有暫存音檔"""
    temp_files = []
    for i, line in enumerate(script_json):
        speaker = line.get("speaker", "HostA")
        text = line.get("text", "")
        voice = VOICES.get(speaker, VOICES["HostA"]) # 預設使用女聲
        
        filename = f"temp_{i}.mp3"
        await generate_audio_segment(text, voice, filename)
        temp_files.append(filename)
        print(f"✅ 已生成片段 {i}: {speaker}")
        
    return temp_files

# ==========================================
# 4. 音檔拼接與後製
# ==========================================
def merge_audio_files(temp_files, output_filename="final_podcast.mp3"):
    """使用 pydub 拼接音檔，並加入適當的停頓"""
    final_audio = AudioSegment.empty()
    pause = AudioSegment.silent(duration=350)  # 350毫秒的換氣/換人停頓
    
    for file in temp_files:
        segment = AudioSegment.from_mp3(file)
        final_audio += segment + pause
        os.remove(file) # 合併後刪除暫存檔，保持乾淨
        
    # 匯出最終音檔
    final_audio.export(output_filename, format="mp3", bitrate="128k")
    print(f"🎉 最終 Podcast 音檔已匯出：{output_filename}")
    return output_filename

# ==========================================
# 5. 上傳與推播 (保留你原有的邏輯)
# ==========================================
def upload_to_gdrive(file_path):
    # 你的 Google Drive 上傳程式碼放這裡
    print("上傳至 Google Drive...")
    return "gdrive_share_link"

def send_line_flex_message(audio_url):
    # 你的 LINE 推播程式碼放這裡
    print("發送 LINE Flex Message...")

# ==========================================
# 主程式執行入口
# ==========================================
def main():
    # 1. 取得或爬取你的新聞資料 (此處為模擬資料)
    news_data = """
    氣象：明天全台降溫，北部低溫下探 15 度。
    國際：美國聯準會宣布利率維持不變。
    財經：台股今日開高走低，終場小跌 50 點。
    科技：蘋果傳出將於下個月發表新款 iPad Pro。
    生活：最新研究指出，每天喝三杯黑咖啡有助於提升代謝。
    """
    
    try:
        # 2. 生成對話劇本
        print("正在呼叫 Gemini 生成雙人劇本...")
        script = generate_podcast_script(news_data)
        
        # 3. 異步生成語音片段
        print("正在使用 Edge TTS 生成分段語音...")
        temp_files = asyncio.run(process_all_audio_segments(script))
        
        # 4. 拼接音檔
        print("正在將對話拼接成完整 Podcast...")
        final_mp3 = merge_audio_files(temp_files, "daily_news_podcast.mp3")
        
        # 5. 上傳與推播
        file_link = upload_to_gdrive(final_mp3)
        send_line_flex_message(file_link)
        
        print("任務全數完成！")
        
    except Exception as e:
        print(f"發生錯誤：{e}")

if __name__ == "__main__":
    main()
