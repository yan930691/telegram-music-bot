# Telegram Music Bot — Backup Info

မှတ်တမ်းရက်: 2026-11-11 (commit `7013b4e`)

## Bot ရဲ့ လုပ်ဆောင်ချက်များ (အကုန်အားလုံး)

1. **Music Library အဓိကစနစ်** — album / artist စာရင်း လှန်ကြည့်၊ သီချင်းတွဲ၊ pagination
2. **Search** — `/search` command၊ "ရှာဖွေ" button၊ တိုက်ရိုက် အဆိုတော်နာမည် ရိုက်လိုက်ရင်လည်း private chat မှာ အလိုအလျောက် ရှာပေး (Myanmar unicode normalize ပါ)
3. **Link Downloader** (private chat သာ) — YouTube / TikTok / Facebook စတာ link ပို့ရင် yt-dlp နဲ့ ဒေါင်ပြီး audio (mp3) ဒါမှမဟုတ် video ပြန်ပို့
4. **သီချင်းဖော်ထုတ်ခြင်း (Shazam-style)** — voice / audio / video / video note ပို့ရင် audd.io API နဲ့ သီချင်းနာမည် ဖော်ထုတ်ပေး
5. **Channel Import** — `/importchannel` နဲ့ ချန်နယ်ထဲက သီချင်းအိုတွေ catalog ထဲ သွင်း (Pyrogram + forward_message + fast mode)
6. **Admin Panel** — သီချင်း upload၊ album/category စီမံခန့်ခွဲမှု
7. **Health server** (port 10000) + long polling

## အရေးကြီး file တွေ

| File | လုပ်ဆောင်ချက် |
|---|---|
| `bot.py` | Entry point။ Router အစဉ်: start → downloader → shazam → search → music → admin → channel |
| `handlers/extras/downloader.py` | Link downloader (URL ပါမှသာ အလုပ်လုပ်) |
| `handlers/extras/shazam.py` | audd.io သီချင်းဖော်ထုတ်ခြင်း |
| `handlers/search.py` | Search + plain-text search fallback |
| `handlers/admin.py` | Admin panel၊ `/importchannel` flow |
| `handlers/channel.py` | Channel အသစ်တင်တာ ဖမ်းယူခြင်း |
| `database.py` | MongoDB catalog |
| `config.py` | Env config |
| `requirements.txt` | aiogram, motor, pyrogram, yt-dlp, imageio-ffmpeg, mutagen စသဖြင့် |

## Environment Variables (Render မှာ သတ်မှတ်ရမည်)

- `BOT_TOKEN` — BotFather ကနေရတဲ့ token
- `MONGODB_URI` — MongoDB connection string
- `DB_NAME` — (default: `music_bot`)
- `ADMIN_IDS` — comma ခံထားတဲ့ admin ID တွေ
- `CHANNEL_ID` — release ကြေညာချန်နယ်
- `TG_API_ID`, `TG_API_HASH` — my.telegram.org ကနေရတဲ့ (channel import အတွက်)
- `AUDD_API_KEY` — audd.io API key (သီချင်းဖော်ထုတ်ခြင်းအတွက်)
- `BUILD_VERSION` — (optional)

## ပြန်ထူးနည်း (Restore)

1. ဒီ backup ကို unzip လုပ် (ဒါမှမဟုတ် `git clone https://github.com/yan930691/telegram-music-bot.git`)
2. `pip install -r requirements.txt`
3. အထက်ပါ env variables တွေ သတ်မှတ်ပေး (`.env` ဖိုင် ဒါမှမဟုတ် Render Environment)
4. `python bot.py`

## Render မှာ Deploy နည်း

- Repo: `https://github.com/yan930691/telegram-music-bot` (branch: `main`)
- Start command: `python bot.py`
- Render → Environment မှာ env vars သတ်မှတ် → **Manual Deploy > Deploy latest commit**

## သတိထားရန်

- ကုဒ် push တိုင်း Render မှာ **Manual Deploy** လုပ်ပေးရမည် (auto မဟုတ်)
- GitHub token တွေ chat/log ထဲ ထွက်သွားပြီဆိုရင် **rotate (အသစ်ပြောင်း)** လုပ်ပါ
