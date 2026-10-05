import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
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
        self.last_check = {}
        self.init_browser()
    
    def init_browser(self):
        """Initialize Selenium browser with Chrome"""
        try:
            logger.info('[SELENIUM] Initializing Chrome...')
            
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
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            logger.info('[SELENIUM] ✅ Chrome launched successfully')
            
            self.login()
            
        except Exception as e:
            logger.error(f'[SELENIUM] ❌ Browser init failed: {type(e).__name__}: {str(e)}')
            self.authenticated = False
    
    def login(self):
        """Login to Facebook using Selenium"""
        try:
            logger.info('[FB] Starting login process...')
            
            self.driver.get('https://www.facebook.com/login')
            time.sleep(3)
            
            # Enter email
            try:
                email_field = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.ID, "email"))
                )
                email_field.clear()
                email_field.send_keys(self.email)
                logger.info('[FB] Email entered')
                time.sleep(1)
            except Exception as e:
                logger.error(f'[FB] Email field error: {type(e).__name__}')
                return False
            
            # Enter password
            try:
                pass_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "pass"))
                )
                pass_field.clear()
                pass_field.send_keys(self.password)
                logger.info('[FB] Password entered')
                time.sleep(1)
            except Exception as e:
                logger.error(f'[FB] Password field error: {type(e).__name__}')
                return False
            
            # Click login button
            try:
                login_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.NAME, "login"))
                )
                login_btn.click()
                logger.info('[FB] Login button clicked')
            except Exception as e:
                logger.error(f'[FB] Login button error: {type(e).__name__}')
                return False
            
            # Wait for redirect to home page
            try:
                WebDriverWait(self.driver, 20).until(
                    lambda driver: 'login' not in driver.current_url and driver.current_url.startswith('https://www.facebook.com')
                )
                logger.info(f'[FB] ✅ Login successful - URL: {self.driver.current_url[:50]}...')
                self.authenticated = True
                self.cookies = self.driver.get_cookies()
                return True
            except Exception as e:
                logger.error(f'[FB] Redirect timeout: {type(e).__name__}')
                self.authenticated = False
                return False
            
        except Exception as e:
            logger.error(f'[FB] ❌ Login failed: {type(e).__name__}: {str(e)}')
            self.authenticated = False
            return False
    
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
            logger.info(f'[FB] Fetching: {profile_url}')
            
            self.driver.get(profile_url)
            time.sleep(4)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Get profile name
            name_elem = soup.find('h1')
            if name_elem:
                name = name_elem.text.strip()
            else:
                name_elem_alt = soup.find('span', {'data-testid': 'ProfileNameTopSection'})
                name = name_elem_alt.text if name_elem_alt else 'Unknown'
            
            # Check for online status indicator
            online_indicator = soup.find('div', {'data-testid': 'online_indicator'})
            is_online = online_indicator is not None
            
            # Get last seen info
            last_seen_text = 'unknown'
            time_span = soup.find('span', string=lambda x: x and any(word in str(x).lower() for word in ['ago', 'now', 'minute', 'hour', 'day']))
            if time_span:
                last_seen_text = time_span.text.strip()
            
            online_status = 'now' if is_online else 'offline'
            status = 'online' if is_online else 'offline'
            
            logger.info(f'[FB] ✅ Fetched: {name} - Status: {online_status}')
            
            return {
                'name': name,
                'online_status': online_status,
                'last_seen': last_seen_text,
                'status': status
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
            try:
                self.driver.quit()
                logger.info('[SELENIUM] Browser closed')
            except:
                pass

fb_browser = None

# ================================================================================
# ACTIVITY TRACKER
# ================================================================================

class ActivityTracker:
    def __init__(self, check_interval=30):
        self.check_interval = check_interval
        self.tracking = {}
        self.running = False
    
    def add_target(self, fb_id, profile_url, user_id):
        """Add profile to track"""
        try:
            if not fb_browser or not fb_browser.authenticated:
                logger.warning('[TRACKER] Browser not authenticated')
                return False
            
            profile_info = fb_browser.get_profile_status(profile_url)
            name = profile_info.get('name', 'Unknown')
            
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            
            try:
                c.execute(
                    'INSERT INTO targets (fb_id, name, profile_url, user_id, created_at) VALUES (?, ?, ?, ?, ?)',
                    (fb_id, name, profile_url, user_id, datetime.now().isoformat())
                )
            except sqlite3.IntegrityError:
                logger.warning(f'[TRACKER] Profile {fb_id} already tracked')
                conn.close()
                return False
            
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
            logger.error(f'[TRACKER] Error adding target: {type(e).__name__}: {str(e)}')
            return False
    
    def check_all(self):
        """Continuous status checking loop"""
        self.running = True
        logger.info('[TRACKER] Status checking started (30s interval)')
        
        while self.running:
            try:
                if not fb_browser or not fb_browser.authenticated:
                    time.sleep(10)
                    continue
                
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
                        logger.error(f'[TRACKER] Check error for {fb_id}: {type(e).__name__}')
                        time.sleep(1)
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f'[TRACKER] Loop error: {type(e).__name__}')
                time.sleep(5)
    
    def stop(self):
        """Stop tracking"""
        self.running = False
        logger.info('[TRACKER] Tracking stopped')

tracker = ActivityTracker(check_interval=30)

# ================================================================================
# TELEGRAM BOT
# ================================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = '🔍 Facebook Activity Tracker v5.0 - PREMIUM\n\n'
    msg += 'Real-time tracking with Selenium browser\n\n'
    msg += '📱 Commands:\n'
    msg += '/add URL - Add profile\n'
    msg += '/list - Show profiles\n'
    msg += '/status ID - Check status\n'
    msg += '/analytics ID - View analytics\n\n'
    msg += 'Example:\n'
    msg += '/add https://facebook.com/username'
    await update.message.reply_text(msg)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Usage: /add https://facebook.com/username')
        return
    
    url = context.args[0]
    user_id = update.effective_user.id
    fb_id = url.rstrip('/').split('/')[-1]
    
    if tracker.add_target(fb_id, url, user_id):
        await update.message.reply_text(f'✅ Added: {fb_id}')
    else:
        await update.message.reply_text(f'❌ Already tracked or error')

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        msg += f'✅ {name}\n'
        msg += f'   /status {fb_id}\n'
        msg += f'   /analytics {fb_id}\n\n'
    await update.message.reply_text(msg)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Usage: /analytics fb_id')
        return
    
    fb_id = context.args[0]
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM activity WHERE fb_id = ? AND status = "online"', (fb_id,))
    sessions = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM activity WHERE fb_id = ?', (fb_id,))
    total_checks = c.fetchone()[0]
    
    conn.close()
    
    msg = f'📈 Analytics: {fb_id}\n\n'
    msg += f'Sessions: {sessions}\n'
    msg += f'Total checks: {total_checks}\n'
    msg += f'Last check: {datetime.now().strftime("%H:%M:%S")}'
    await update.message.reply_text(msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith('http'):
        context.args = [text]
        await add_command(update, context)
    else:
        await update.message.reply_text('Send Facebook profile URL or use /help')

def start_telegram():
    """Start Telegram bot polling"""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('add', add_command))
    application.add_handler(CommandHandler('list', list_command))
    application.add_handler(CommandHandler('status', status_command))
    application.add_handler(CommandHandler('analytics', analytics_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info('[TG] Telegram bot polling started')
    application.run_polling()

# ================================================================================
# FLASK API
# ================================================================================

@app.route('/')
def health():
    return jsonify({'status': 'ok', 'version': '5.0', 'service': 'facebook-tracker', 'authenticated': fb_browser.authenticated if fb_browser else False})

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

@app.route('/api/history/<fb_id>')
def api_history(fb_id):
    limit = request.args.get('limit', 20, type=int)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT status, last_seen, timestamp FROM activity WHERE fb_id = ? ORDER BY timestamp DESC LIMIT ?', (fb_id, limit))
    rows = c.fetchall()
    conn.close()
    return jsonify([{'status': r[0], 'last_seen': r[1], 'time': r[2]} for r in rows])

# ================================================================================
# MAIN
# ================================================================================

def run_flask():
    logger.info(f'[FLASK] Server on 0.0.0.0:{PORT}')
    logger.info('[API] Ready: /api/targets, /api/status, /api/history')
    logger.info('=' * 80)
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False, threaded=True)

if __name__ == '__main__':
    logger.info('=' * 80)
    logger.info('Facebook Activity Tracker v5.0 - PREMIUM - STARTING')
    logger.info('=' * 80)
    
    init_db()
    
    # Initialize browser
    fb_browser = FacebookBrowser(FB_EMAIL, FB_PASSWORD)
    
    if fb_browser and fb_browser.authenticated:
        logger.info('✅ Facebook authenticated - Full functionality enabled')
    else:
        logger.warning('⚠ Facebook auth failed - limited functionality')
    
    # Start tracking thread
    tracking_thread = Thread(target=tracker.check_all, daemon=True)
    tracking_thread.start()
    logger.info('[TRACKER] Tracking thread started')
    
    # Start Flask thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info('[FLASK] Flask thread started')
    
    # Start Telegram polling
    try:
        start_telegram()
    except KeyboardInterrupt:
        logger.info('Shutting down...')
        tracker.stop()
        if fb_browser:
            fb_browser.close()
