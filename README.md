# 🔍 Facebook Activity Tracker v3.0 - Production Ready

Real-time profile monitoring, last seen tracking, and activity logging for Facebook profiles.

## Features

✅ Real-time profile status monitoring  
✅ Last seen tracking (online/offline/recently active)  
✅ Activity history logging (SQLite database)  
✅ Telegram bot integration  
✅ REST API endpoints  
✅ Session persistence  
✅ Multiple profile tracking  
✅ Automatic status change detection  

---

## 📋 Prerequisites

- Python 3.9+
- Git
- GitHub account
- Render account (free)
- Telegram bot token
- Facebook credentials

---

## 🚀 QUICK START (LOCAL TESTING)

### Step 1: Clone and Setup

```bash
# Create project directory
mkdir facebook-tracker-bot
cd facebook-tracker-bot

# Clone or download all files from this repo
# Or copy the files provided
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Setup Environment Variables

```bash
# Copy example to .env
cp .env.example .env

# Edit .env with your credentials
# Windows: notepad .env
# Mac/Linux: nano .env
```

**Fill in these values:**

```
TELEGRAM_BOT_TOKEN=your_token_from_botfather
FB_EMAIL=your_facebook_email@gmail.com
FB_PASSWORD=your_facebook_password
PORT=10000
```

### Step 5: Run Locally

```bash
python app/main.py
```

Expected output:
```
2024-01-15 10:30:45 [INFO] ================================================================================
2024-01-15 10:30:45 [INFO] 🔍 Facebook Activity Tracker v3.0 - STARTING
2024-01-15 10:30:45 [INFO] ================================================================================
2024-01-15 10:30:46 [INFO] ✅ Facebook session authenticated
2024-01-15 10:30:47 [INFO] 🚀 Telegram bot polling started
2024-01-15 10:30:47 [INFO] 🚀 Flask server on 0.0.0.0:10000
```

---

## 📱 Telegram Bot Usage

### Get Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send command `/newbot`
3. Name your bot: "Facebook Tracker Bot"
4. Username: "facebook_tracker_bot_123" (must be unique)
5. **Copy the token** → paste in `.env`

### Telegram Commands

| Command | Usage | Example |
|---------|-------|---------|
| `/start` | Main menu | `/start` |
| `/add URL` | Add profile | `/add https://facebook.com/username` |
| `/list` | Show all profiles | `/list` |
| `/status ID` | Check live status | `/status username` |
| `/stop ID` | Stop tracking | `/stop username` |
| `/history ID` | View activity log | `/history username` |
| `/help` | Show help | `/help` |

---

## 🌐 REST API Endpoints

### Health Check
```
GET http://localhost:10000/
```

### Get All Targets for User
```
GET http://localhost:10000/api/targets/{user_id}
```

### Get Profile Status
```
GET http://localhost:10000/api/status/{fb_id}
```

### Get Activity History
```
GET http://localhost:10000/api/history/{fb_id}?limit=20
```

### Get Service Stats
```
GET http://localhost:10000/api/stats
```

---

## 📤 DEPLOYMENT TO RENDER (STEP-BY-STEP)

### Step 1: Push Code to GitHub

```bash
# Initialize git repository
git init

# Add all files
git add .

# Commit
git commit -m "Facebook tracker bot - v3.0"

# Rename branch to main
git branch -M main

# Add remote (replace YOUR_USERNAME and REPO_NAME)
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# Push to GitHub
git push -u origin main
```

### Step 2: Create Render Account

1. Go to https://render.com
2. Sign up with GitHub account
3. Authorize Render to access your GitHub

### Step 3: Create New Web Service on Render

1. Go to https://dashboard.render.com
2. Click **New +** → **Web Service**
3. Select your GitHub repository (facebook-tracker-bot)
4. Fill in the form:
   - **Name:** `facebook-tracker-bot`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `cd app && python main.py`
   - **Instance Type:** Free (or Starter if needed)

### Step 4: Add Environment Variables

1. In Render dashboard, go to your service → **Environment**
2. Click **Add Environment Variable** for each:

```
TELEGRAM_BOT_TOKEN = your_bot_token_here
FB_EMAIL = your_facebook_email@gmail.com
FB_PASSWORD = your_facebook_password
PORT = 10000
```

3. Click **Save Changes**

### Step 5: Deploy

1. Click **Create Web Service**
2. Wait for build to complete (2-3 minutes)
3. Check logs for "🚀 Flask server on 0.0.0.0:10000"

---

## ✅ VERIFICATION CHECKLIST

### Local Testing
- [ ] Virtual environment created
- [ ] Requirements installed
- [ ] `.env` file with credentials
- [ ] Flask server runs on port 10000
- [ ] Telegram bot receives `/start` command
- [ ] Can add a Facebook profile
- [ ] Status endpoint works

### GitHub Setup
- [ ] Repository created on GitHub
- [ ] All files committed and pushed
- [ ] `.env` is in `.gitignore` (not committed)
- [ ] No sensitive data in public files

### Render Deployment
- [ ] Service created successfully
- [ ] Environment variables set
- [ ] Build completes without errors
- [ ] Logs show "✅ Facebook session authenticated"
- [ ] Service URL is live (e.g., `https://facebook-tracker-bot.onrender.com/`)

### Post-Deployment Testing
```bash
# Test health endpoint
curl https://facebook-tracker-bot.onrender.com/

# Test API
curl https://facebook-tracker-bot.onrender.com/api/stats

# Test Telegram (send /start to your bot)
```

---

## 🔧 TROUBLESHOOTING

### Issue: "ModuleNotFoundError: No module named 'flask'"
**Solution:** Ensure `requirements.txt` is in project root, not in `/app` folder.

### Issue: Facebook Login Fails
**Solution:**
- Verify email/password are correct
- Check if 2FA is enabled (may need to disable temporarily)
- Try accessing Facebook in browser to confirm account works
- Check Render logs for specific error message

### Issue: Telegram Bot Not Responding
**Solution:**
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Send `/start` command again
- Check Render logs: `Telegram bot polling started`

### Issue: Service Crashes After Deploy
**Solution:**
- Check Render logs for error details
- Verify all environment variables are set
- Ensure Python version is 3.9+
- Check database file isn't corrupted

### Issue: Database Errors
**Solution:**
- Render free plan resets data on redeploy
- For persistence, upgrade to paid plan
- Or manually backup database before updates

### How to Check Render Logs

1. Go to Render dashboard
2. Click on your service
3. Go to **Logs** tab
4. Watch real-time output
5. Search for errors (usually in red)

---

## 📊 Database Schema

### targets table
```sql
fb_id TEXT (Primary identifier)
name TEXT (Display name)
profile_url TEXT (Facebook URL)
user_id INTEGER (Telegram user ID)
created_at TIMESTAMP (When added)
```

### activity table
```sql
fb_id TEXT (Profile being tracked)
status TEXT (online/offline/seen_recently)
last_seen TEXT (Time ago or "now")
online_status TEXT (online/offline/unknown)
timestamp TIMESTAMP (When checked)
```

---

## 🔐 Security Notes

⚠️ **DO NOT COMMIT `.env` FILE**
- Contains sensitive credentials
- Already in `.gitignore`
- Add env vars only in Render dashboard

⚠️ **Facebook Login Security**
- Use a test/secondary Facebook account if possible
- Credentials stored only in `.env` (not committed)
- Consider using app password if available

⚠️ **API Access**
- APIs are public (add authentication if needed)
- Rate limit Telegram requests (built-in)
- Database queries are local

---

## 📈 Performance Notes

- **Check Interval:** 5 minutes (configurable in code)
- **Max Concurrent Tracking:** 1000+ profiles
- **Memory Usage:** ~50-100MB
- **Database Size:** ~1MB per 1000 activity logs

### To Change Check Interval

Edit `main.py` line:
```python
self.check_interval = 300  # Change 300 to desired seconds
```

---

## 🛠️ Customization

### Change Telegram Bot Polling Rate
```python
# In TelegramBot.run()
time.sleep(0.1)  # Change to desired interval
```

### Change Activity Check Interval
```python
# In ActivityTracker.__init__()
self.check_interval = 300  # 5 minutes, change as needed
```

### Add Custom Database Fields
Edit `TrackerDB.init()` to add new columns and migrations

---

## 📝 File Structure

```
facebook-tracker-bot/
├── app/
│   └── main.py              (Main application)
├── .env.example             (Template for env vars)
├── .env                     (Your credentials - DON'T COMMIT)
├── .gitignore              (Git ignore rules)
├── Procfile                (Render configuration)
├── requirements.txt        (Python dependencies)
└── README.md              (This file)
```

---

## 🚨 Common Mistakes

❌ **Committing .env file** → Use `.env.example` only  
❌ **Wrong folder structure** → Keep `main.py` in `/app` folder  
❌ **Missing Procfile** → Render needs it to start service  
❌ **Not setting env vars on Render** → They must be added in dashboard  
❌ **Using old Selenium approach** → This version uses lightweight requests  

---

## 💾 Backup & Restore

### Backup Database
```bash
cp facebook_tracker.db facebook_tracker.backup.db
```

### Export Data
```bash
sqlite3 facebook_tracker.db ".dump" > backup.sql
```

---

## 📞 Support

**Issues:**
- Check logs in Render dashboard
- Verify all environment variables
- Ensure `.env` format is correct
- Test locally before deploying

**Rendering Logs Location:**
`Render Dashboard → Your Service → Logs Tab`

---

## 📜 License

Free to use. No warranty provided.

---

**Last Updated:** 2024  
**Version:** 3.0 Production Ready

