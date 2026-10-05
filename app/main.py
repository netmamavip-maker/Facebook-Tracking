import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from threading import Thread
import time

# ================================================================================
# SETUP
# ================================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
FB_EMAIL = os.getenv('FB_EMAIL')
FB_PASSWORD = os.getenv('FB_PASSWORD')
PORT = int(os.getenv('PORT', 10000))

bot = Bot(token=TELEGRAM_BOT_TOKEN)

DATABASE = 'tracker.db'

# ================================================================================
# DATABASE
# ================================================================================

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY,
            fb_id TEXT UNIQUE,
            name TEXT,
            profile_url TEXT,
            user_id INTEGER,
            created_at TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY,
            fb_id TEXT,
            status TEXT,
            last_seen TEXT,
            online_status TEXT,
            timestamp TIMESTAMP,
            session_start TIMESTAMP,
            session_duration INTEGER
        )
    ''')
    conn.commit()
    conn.close()
    logger.info('[DB] Database initialized')

# ================================================================================
# SELENIUM FACEBOOK
# ================================================================================

class FacebookBrowser:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.driver = None
        self.authenticated = False
        self.cookies = None
        self.init_browser()
    
    def init_browser(self):
        """Initialize Selenium browser"""
        try:
            logger.info('[SELENIUM] Initializing Chromium...')
            
            options = Options()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--headless=new')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=options)
            logger.info('[SELENIUM] ✅ Chrome launched')
            
            self.login()
            
        except Exception as e:
            logger.error(f'[SELENIUM] ❌ Browser init failed: {type(e).__name__}: {str(e)}')
            self.authenticated = False
    
    def login(self):
        """Login to Facebook"""
        try:
            logger.info('[FB] Starting login...')
            
            self.driver.get('https://www.facebook.com/login')
            time.sleep(2)
            
            # Enter email
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_field.send_keys(self.email)
            time.sleep(1)
            
            # Enter password
            pass_field = self.driver.find_element(By.ID, "pass")
            pass_field.send_keys(self.password)
            time.sleep(1)
            
            # Click login
            login_btn = self.driver.find_element(By.NAME, "login")
            login_btn.click()
            
            # Wait for redirect
            WebDriverWait(self.driver, 15).until(
                lambda driver: 'login' not in driver.current_url
            )
            
            logger.info(f'[FB] ✅ Login successful')
            self.authenticated = True
            self.cookies = self.driver.get_cookies()
            
        except Exception as e:
            logger.error(f'[FB] ❌ Login failed: {type(e).__name__}: {str(e)}')
            self.authenticated = False
    
    def get_profile_status(self, profile_url):
        """Get real profile status using Selenium"""
        if not self.authenticated or not self.driver:
            logger.warning('[FB] Not authenticated')
            return {
                'name': 'Error',
                'online_status': 'unknown',
                'last_seen': 'unknown',
                'status': 'offline'
            }
        
        try:
            logger.info(f'[FB] Fetching profile: {profile_url}')
            
            self.driver.get(profile_url)
            time.sleep(3)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Get name
            name_elem = soup.find('h1', class_='x1heor9g')
            name = name_elem.text if name_elem else 'Unknown'
            
            # Try to find online indicator
            online_indicator = soup.find('div', {'data-testid': 'online_indicator'})
            online_status = 'now' if online_indicator else 'offline'
            
            # Get last seen (usually in friend list or profile)
            last_seen_text = soup.find('span', string=lambda x: x and ('ago' in str(x) or 'now' in str(x)))
            last_seen = last_seen_text.text if last_seen_text else 'unknown'
            
            logger.info(f'[FB] ✅ Profile: {name} - Status: {online_status}')
            
            return {
                'name': name,
                'online_status': online_status,
                'last_seen': last_seen,
                'status': 'online' if online_status == 'now' else 'offline'
            }
            
        except Exception as e:
            logger.error(f'[FB] ❌ Profile fetch error: {type(e).__name__}: {str(e)}')
            return {
                'name': 'Error',
                'online_status': 'unknown',
                'last_seen': 'unknown',
                'status': 'offline'
            }
    
    def close(self):
        """Close browser"""
        if self.driver:
            self.driver.quit()
            logger.info('[SELENIUM] Browser closed')

fb_browser = None

# ================================================================================
# ACTIVITY TRACKER
# ================================================================================

class ActivityTracker:
    def __init__(self, check_interval=30):
        self.check_interval = check_interval
        self.tracking = {}
        self.sessions = {}
    
    def add_target(self, fb_id, profile_url, user_id):
        """Add profile to track"""
        try:
            # Fetch profile info
            profile_info = fb_browser.get_profile_status(profile_url)
            name = profile_info.get('name', 'Unknown')
            
            # Save to DB
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute(
                'INSERT INTO targets (fb_id, name, profile_url, user_id, created_at) VALUES (?, ?, ?, ?, ?)',
                (fb_id, name, profile_url, user_id, datetime.now().isoformat())
            )
            c.execute(
                'INSERT INTO activity (fb_id, status, last_seen, online_status, timestamp) VALUES (?, ?, ?, ?, ?)',
                (fb_id, profile_info.get('status'), profile_info.get('last_seen'), profile_info.get('online_status'), datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            
            logger.info(f'✅ Tracking started: {name} ({fb_id})')
            self.tracking[fb_id] = {'url': profile_url, 'name': name, 'user_id': user_id}
            return True
        except Exception as e:
            logger.error(f'Error adding target: {type(e).__name__}: {str(e)}')
            return False
    
    def check_all(self):
        """Continuous status checking"""
        while True:
            try:
                for fb_id, data in list(self.tracking.items()):
                    try:
                        profile_info = fb_browser.get_profile_status(data['url'])
                        status = profile_info.get('status')
                        
                        conn = sqlite3.connect(DATABASE)
                        c = conn.cursor()
                        c.execute(
                            'INSERT INTO activity (fb_id, status, last_seen, online_status, timestamp) VALUES (?, ?, ?, ?, ?)',
                            (fb_id, status, profile_info.get('last_seen'), profile_info.get('online_status'), datetime.now().isoformat())
                        )
                        conn.commit()
                        conn.close()
                        
                    except Exception as e:
                        logger.error(f'Check error for {fb_id}: {type(e).__name__}')
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f'Tracking loop error: {type(e).__name__}')
                time.sleep(5)

tracker = ActivityTracker(check_interval=30)

# ================================================================================
# TELEGRAM COMMANDS
# ================================================================================

def handle_telegram():
    """Telegram bot"""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    async def start(update, context):
        msg = '🔍 Facebook Activity Tracker v5.0 - PREMIUM\n\n'
        msg += 'Real-time tracking with advanced analytics\n\n'
        msg += 'Commands:\n'
        msg += '/add URL - Add profile\n'
        msg += '/list - Show profiles\n'
        msg += '/status ID - Check status\n'
        msg += '/analytics ID - View analytics\n\n'
        msg += 'Send Facebook profile URL:\nhttps://facebook.com/username'
        await update.message.reply_text(msg)
    
    async def add_profile(update, context):
        if not context.args:
            await update.message.reply_text('Usage: /add https://facebook.com/username')
            return
        
        url = context.args[0]
        user_id = update.effective_user.id
        fb_id = url.split('/')[-1]
        
        if tracker.add_target(fb_id, url, user_id):
            await update.message.reply_text(f'✅ Added: {fb_id}')
        else:
            await update.message.reply_text(f'❌ Already tracked or error')
    
    async def list_profiles(update, context):
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT fb_id, name FROM targets WHERE user_id = ?', (update.effective_user.id,))
        targets = c.fetchall()
        conn.close()
        
        if not targets:
            await update.message.reply_text('No profiles tracked')
            return
        
        msg = '📱 Your Profiles:\n\n'
        for fb_id, name in targets:
            msg += f'✅ {name}\n/status {fb_id}\n/analytics {fb_id}\n\n'
        await update.message.reply_text(msg)
    
    async def check_status(update, context):
        if not context.args:
            await update.message.reply_text('Usage: /status fb_id')
            return
        
        fb_id = context.args[0]
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT status, last_seen, online_status FROM activity WHERE fb_id = ? ORDER BY timestamp DESC LIMIT 1', (fb_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            status, last_seen, online = row
            icon = '🟢' if status == 'online' else '⚪'
            msg = f'{icon} {fb_id}\n'
            msg += f'Status: {online}\n'
            msg += f'Last seen: {last_seen}'
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text('No data found')
    
    async def get_analytics(update, context):
        if not context.args:
            await update.message.reply_text('Usage: /analytics fb_id')
            return
        
        fb_id = context.args[0]
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Get stats
        c.execute('SELECT COUNT(*) FROM activity WHERE fb_id = ? AND status = "online"', (fb_id,))
        sessions = c.fetchone()[0]
        
        c.execute('SELECT SUM(session_duration) FROM activity WHERE fb_id = ?', (fb_id,))
        duration = c.fetchone()[0]
        total_hours = (duration // 3600) if duration else 0
        
        conn.close()
        
        msg = f'📈 Analytics: {fb_id}\n\n'
        msg += f'Sessions: {sessions}\n'
        msg += f'Online: {total_hours}h\n'
        msg += f'Updated: {datetime.now().strftime("%H:%M:%S")}'
        await update.message.reply_text(msg)
    
    async def handle_message(update, context):
        text = update.message.text
        if text.startswith('http'):
            context.args = [text]
            await add_profile(update, context)
        else:
            await update.message.reply_text('Send Facebook profile URL or use /help')
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('add', add_profile))
    application.add_handler(CommandHandler('list', list_profiles))
    application.add_handler(CommandHandler('status', check_status))
    application.add_handler(CommandHandler('analytics', get_analytics))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info('[TG] Bot polling started')
    application.run_polling()

# ================================================================================
# FLASK API
# ================================================================================

@app.route('/')
def health():
    return jsonify({'status': 'ok', 'version': '5.0', 'service': 'facebook-tracker'})

@app.route('/api/targets/<int:user_id>')
def api_targets(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT fb_id, name, profile_url FROM targets WHERE user_id = ?', (user_id,))
    targets = c.fetchall()
    conn.close()
    return jsonify([{'fb_id': t[0], 'name': t[1], 'url': t[2]} for t in targets])

@app.route('/api/status/<fb_id>')
def api_status(fb_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT status, last_seen, online_status FROM activity WHERE fb_id = ? ORDER BY timestamp DESC LIMIT 1', (fb_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({'fb_id': fb_id, 'status': row[0], 'last_seen': row[1], 'online': row[2]})
    return jsonify({'error': 'Not found'}), 404

# ================================================================================
# MAIN
# ================================================================================

def run_flask():
    logger.info(f'[FLASK] Server on 0.0.0.0:{PORT}')
    logger.info('[API] Ready: /api/targets, /api/status')
    logger.info('=' * 80)
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

if __name__ == '__main__':
    logger.info('=' * 80)
    logger.info('Facebook Activity Tracker v5.0 - PREMIUM')
    logger.info('=' * 80)
    
    init_db()
    
    # Initialize browser
    fb_browser = FacebookBrowser(FB_EMAIL, FB_PASSWORD)
    
    if fb_browser.authenticated:
        logger.info('✅ Facebook authenticated - Full functionality')
    else:
        logger.warning('⚠️ Facebook auth failed - limited functionality')
    
    # Start tracking
    Thread(target=tracker.check_all, daemon=True).start()
    
    # Start Flask
    Thread(target=run_flask, daemon=True).start()
    
    # Start Telegram
    try:
        handle_telegram()
    except KeyboardInterrupt:
        logger.info('Shutting down...')
        if fb_browser:
            fb_browser.close()
