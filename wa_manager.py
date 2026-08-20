import os
import re
import sys
import json
import asyncio
import requests
from telethon import TelegramClient
from telethon.tl.types import UserStatusOnline
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.errors import (
    SessionPasswordNeededError,
    FloodWaitError,
    PeerFloodError,
    UserPrivacyRestrictedError,
    UserNotMutualContactError,
    UserChannelsTooMuchError,
    UserAlreadyParticipantError,
    ChatAdminRequiredError,
    UserBannedInChannelError,
    UserKickedError
)

# ================= COLOR CODES =================
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

# ================= STORAGE FILES =================
CONFIG_FILE = "config.json"
SESSION_FILE = "termux_session"
SCRAPED_FILE = "scraped_users.txt"

client = None

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def banner():
    clear_screen()
    print(f"{CYAN}{BOLD}")
    print("==================================================")
    print("      🚀 TELEGRAM SCRAPER & ADDER (CLI)          ")
    print("==================================================")
    print(f"{RESET}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ================= AUTO API_ID / HASH EXTRACTOR =================
def extract_telegram_api(phone):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36",
        "Referer": "https://my.telegram.org/auth",
        "Origin": "https://my.telegram.org"
    })

    print(f"\n{CYAN}[*] my.telegram.org se Web OTP request bhej rahe hain...{RESET}")
    res = session.post("https://my.telegram.org/auth/send_password", data={"phone": phone})
    
    try:
        data = res.json()
        random_hash = data.get("random_hash")
    except Exception:
        print(f"{RED}[!] OTP Request failed. Number check karein ya thori dair baad try karein.{RESET}")
        return None, None

    if not random_hash:
        print(f"{RED}[!] Server Error: {res.text}{RESET}")
        return None, None

    print(f"{GREEN}[✓] Web Login Code Telegram official chat par bhej diya gaya hai!{RESET}")
    web_code = input(f"{BOLD}Enter Web Login Code: {RESET}").strip()

    print(f"\n{CYAN}[*] Web portal par login ho raha hai...{RESET}")
    login_res = session.post("https://my.telegram.org/auth/login", data={
        "phone": phone,
        "random_hash": random_hash,
        "password": web_code
    })

    if login_res.text != "true":
        print(f"{RED}[!] Invalid Web Code ya Login Error!{RESET}")
        return None, None

    apps_page = session.get("https://my.telegram.org/apps")
    
    api_id_match = re.search(r'<strong>App api_id:</strong>.*?<span[^>]*>(\d+)</span>', apps_page.text, re.S)
    api_hash_match = re.search(r'<strong>App api_hash:</strong>.*?<span[^>]*>([a-f0-9]{32})</span>', apps_page.text, re.S)

    if api_id_match and api_hash_match:
        return int(api_id_match.group(1)), api_hash_match.group(1)

    print(f"{YELLOW}[*] New App create ki ja rahi hai...{RESET}")
    app_hash_match = re.search(r'name="hash"\s+value="([a-zA-Z0-9_-]+)"', apps_page.text)
    
    if not app_hash_match:
        print(f"{RED}[!] App creation token nahi mila.{RESET}")
        return None, None

    create_data = {
        "hash": app_hash_match.group(1),
        "app_title": "Termux Tool",
        "app_shortname": "termuxapp",
        "app_url": "",
        "app_platform": "android",
        "app_desc": "Telegram CLI Automation"
    }

    session.post("https://my.telegram.org/apps/create", data=create_data)
    apps_page_after = session.get("https://my.telegram.org/apps")

    api_id_match = re.search(r'<strong>App api_id:</strong>.*?<span[^>]*>(\d+)</span>', apps_page_after.text, re.S)
    api_hash_match = re.search(r'<strong>App api_hash:</strong>.*?<span[^>]*>([a-f0-9]{32})</span>', apps_page_after.text, re.S)

    if api_id_match and api_hash_match:
        return int(api_id_match.group(1)), api_hash_match.group(1)
    
    return None, None

# ================= LOGIN FLOW =================
async def connect_and_login():
    global client
    banner()
    config = load_config()

    api_id = config.get("api_id")
    api_hash = config.get("api_hash")

    if not api_id or not api_hash:
        print(f"{YELLOW}{BOLD}📲 TELEGRAM ACCOUNT SETUP{RESET}\n")
        print(f"{BOLD}1.{RESET} Auto Fetch API ID & Hash via Phone Number")
        print(f"{BOLD}2.{RESET} Enter API ID & Hash Manually\n")
        
        setup_choice = input(f"{CYAN}Option choose karein (1/2): {RESET}").strip()

        if setup_choice == "1":
            phone = input(f"\n{BOLD}Enter Telegram Phone Number (e.g. +923001234567): {RESET}").strip()
            api_id, api_hash = extract_telegram_api(phone)
            
            if not api_id or not api_hash:
                print(f"{RED}[!] API ID & Hash extract nahi ho sake. Dobara try karein.{RESET}")
                sys.exit(1)

            print(f"\n{GREEN}[✓] API ID: {api_id}{RESET}")
            print(f"{GREEN}[✓] API HASH: {api_hash}{RESET}")
        else:
            while True:
                try:
                    api_id = int(input(f"{BOLD}Enter App API ID: {RESET}").strip())
                    break
                except ValueError:
                    print(f"{RED}[!] Numeric value enter karein!{RESET}")
            api_hash = input(f"{BOLD}Enter App API HASH: {RESET}").strip()

    client = TelegramClient(SESSION_FILE, api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"\n{YELLOW}[*] Telethon Login Verification...{RESET}")
        phone = input(f"{BOLD}Enter Phone Number (e.g. +923001234567): {RESET}").strip()
        
        try:
            await client.send_code_request(phone)
            code = input(f"{BOLD}Enter OTP Code received on Telegram: {RESET}").strip()
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input(f"{BOLD}Enter 2-Step Verification Password: {RESET}").strip()
            await client.sign_in(password=password)
        except Exception as e:
            print(f"\n{RED}[!] Login Failed: {str(e)}{RESET}")
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            sys.exit(1)

    save_config({
        "api_id": api_id,
        "api_hash": api_hash
    })

    me = await client.get_me()
    print(f"\n{GREEN}[✓] Connected Successfully as: {me.first_name} (@{me.username}){RESET}")
    input(f"\n{CYAN}Press Enter to continue to Main Menu...{RESET}")

# 1. SCRAPE ALL MEMBERS
async def scrape_all_members():
    banner()
    print(f"{YELLOW}--- 1. SCRAPE ALL GROUP USERNAMES ---{RESET}\n")
    group_link = input(f"{BOLD}Enter Source Group Link/Username (e.g. @group_name): {RESET}").strip()
    
    try:
        print(f"\n{CYAN}[*] Fetching group details...{RESET}")
        entity = await client.get_entity(group_link)
        
        usernames = []
        total_scanned = 0
        
        print(f"{CYAN}[*] Scraping participants, please wait...{RESET}")
        async for user in client.iter_participants(entity):
            total_scanned += 1
            if user.bot or (user.username and user.username.lower().endswith("bot")):
                continue
            if user.username:
                usernames.append(f"@{user.username}")
                
        with open(SCRAPED_FILE, "w", encoding="utf-8") as f:
            for un in usernames:
                f.write(un + "\n")
                
        print(f"\n{GREEN}[✓] SCRAPING COMPLETED!{RESET}")
        print(f"Total Scanned: {total_scanned}")
        print(f"Total Usernames Saved: {len(usernames)} -> {SCRAPED_FILE}")
        
    except Exception as e:
        print(f"\n{RED}[!] Scrape Error: {str(e)}{RESET}")
        
    input(f"\n{CYAN}Press Enter to return...{RESET}")

# 2. SCRAPE ONLY ONLINE MEMBERS
async def scrape_online_members():
    banner()
    print(f"{YELLOW}--- 2. SCRAPE ONLINE MEMBERS ONLY (LIVE ACTIVE) ---{RESET}\n")
    group_link = input(f"{BOLD}Enter Source Group Link/Username (e.g. @group_name): {RESET}").strip()
    
    try:
        print(f"\n{CYAN}[*] Fetching group details...{RESET}")
        entity = await client.get_entity(group_link)
        
        online_usernames = []
        total_scanned = 0
        
        print(f"{CYAN}[*] Scanning active and online members...{RESET}")
        async for user in client.iter_participants(entity):
            total_scanned += 1
            if user.bot or (user.username and user.username.lower().endswith("bot")):
                continue
            
            # Check if user status is strictly Online
            if isinstance(user.status, UserStatusOnline):
                if user.username:
                    online_usernames.append(f"@{user.username}")
                
        with open(SCRAPED_FILE, "w", encoding="utf-8") as f:
            for un in online_usernames:
                f.write(un + "\n")
                
        print(f"\n{GREEN}[✓] ONLINE MEMBERS SCRAPED SUCCESSFULLY!{RESET}")
        print(f"Total Members Scanned: {total_scanned}")
        print(f"{GREEN}Live Online Users Saved: {len(online_usernames)} -> {SCRAPED_FILE}{RESET}")
        
    except Exception as e:
        print(f"\n{RED}[!] Scrape Error: {str(e)}{RESET}")
        
    input(f"\n{CYAN}Press Enter to return...{RESET}")

# 3. AUTO ADD MEMBERS
async def add_members():
    banner()
    print(f"{YELLOW}--- 3. AUTO ADD MEMBERS ---{RESET}\n")
    
    if not os.path.exists(SCRAPED_FILE):
        print(f"{RED}[!] '{SCRAPED_FILE}' nahi mili. Pehle scrape karein.{RESET}")
        input(f"\n{CYAN}Press Enter to return...{RESET}")
        return

    with open(SCRAPED_FILE, "r", encoding="utf-8") as f:
        usernames = [line.strip() for line in f if line.strip()]

    if not usernames:
        print(f"{RED}[!] '{SCRAPED_FILE}' khali hai.{RESET}")
        input(f"\n{CYAN}Press Enter to return...{RESET}")
        return

    target_group = input(f"{BOLD}Enter Target Group Link/Username (e.g. @target_group): {RESET}").strip()
    
    try:
        target_entity = await client.get_entity(target_group)
    except Exception as e:
        print(f"{RED}[!] Group Entity Error: {str(e)}{RESET}")
        input(f"\n{CYAN}Press Enter to return...{RESET}")
        return

    added = 0
    skipped = 0
    failed = 0

    print(f"\n{CYAN}[*] Adding process started...{RESET}\n")

    for user_str in usernames:
        try:
            user_entity = await client.get_input_entity(user_str)
            await client(InviteToChannelRequest(target_entity, [user_entity]))
            added += 1
            print(f"{GREEN}[+] Added: {user_str} | Total: {added}{RESET}")
            await asyncio.sleep(5)

        except UserPrivacyRestrictedError:
            skipped += 1
            print(f"{YELLOW}[-] Privacy Restricted: {user_str}{RESET}")
        except UserAlreadyParticipantError:
            skipped += 1
            print(f"{YELLOW}[-] Already in group: {user_str}{RESET}")
        except PeerFloodError:
            print(f"{RED}[!] PeerFloodError: Account rate-limited. Process stopped.{RESET}")
            break
        except FloodWaitError as e:
            print(f"{YELLOW}[!] FloodWait: Waiting for {e.seconds} seconds...{RESET}")
            await asyncio.sleep(e.seconds)
        except (UserNotMutualContactError, UserChannelsTooMuchError, ChatAdminRequiredError, UserBannedInChannelError, UserKickedError):
            skipped += 1
        except Exception as e:
            failed += 1
            print(f"{RED}[!] Failed ({user_str}): {str(e)}{RESET}")

    print(f"\n{GREEN}===================================={RESET}")
    print(f"{BOLD}Summary: Added: {added} | Skipped: {skipped} | Failed: {failed}{RESET}")
    print(f"{GREEN}===================================={RESET}")
    input(f"\n{CYAN}Press Enter to return...{RESET}")

# 4. REMOVE ALREADY ADDED MEMBERS FROM SAVED LIST
async def remove_existing_from_file():
    banner()
    print(f"{YELLOW}--- 4. REMOVE ALREADY ADDED USERS FROM LIST ---{RESET}\n")
    
    if not os.path.exists(SCRAPED_FILE):
        print(f"{RED}[!] '{SCRAPED_FILE}' nahi mili. Pehle scrape karein.{RESET}")
        input(f"\n{CYAN}Press Enter to return...{RESET}")
        return

    with open(SCRAPED_FILE, "r", encoding="utf-8") as f:
        scraped_users = [line.strip() for line in f if line.strip()]

    if not scraped_users:
        print(f"{RED}[!] '{SCRAPED_FILE}' file khali hai.{RESET}")
        input(f"\n{CYAN}Press Enter to return...{RESET}")
        return

    print(f"Total Usernames in File: {BOLD}{len(scraped_users)}{RESET}")
    target_group = input(f"\n{BOLD}Enter Target Group to Check (e.g. @target_group): {RESET}").strip()

    try:
        print(f"\n{CYAN}[*] Target Group ke existing members scan ho rahe hain...{RESET}")
        target_entity = await client.get_entity(target_group)
        
        target_members = set()
        async for user in client.iter_participants(target_entity):
            if user.username:
                target_members.add(user.username.lower())

        print(f"{CYAN}[*] Saved list se already added members remove ho rahe hain...{RESET}")
        
        fresh_users = []
        removed_count = 0

        for user_str in scraped_users:
            clean_username = user_str.lstrip('@').lower()
            if clean_username in target_members:
                removed_count += 1
            else:
                fresh_users.append(user_str)

        with open(SCRAPED_FILE, "w", encoding="utf-8") as f:
            for un in fresh_users:
                f.write(un + "\n")

        print(f"\n{GREEN}[✓] LIST CLEANED SUCCESSFULLY!{RESET}")
        print(f"Pehle Total Users: {len(scraped_users)}")
        print(f"{RED}Already Added (File se Delete huwe): {removed_count}{RESET}")
        print(f"{GREEN}File me Baqi Fresh Users: {len(fresh_users)}{RESET}")
        print(f"Updated File: {SCRAPED_FILE}")

    except Exception as e:
        print(f"\n{RED}[!] Clean Error: {str(e)}{RESET}")

    input(f"\n{CYAN}Press Enter to return...{RESET}")

# 5. RESET / SWITCH ACCOUNT
async def reset_account():
    banner()
    print(f"{YELLOW}--- 5. RESET / SWITCH ACCOUNT ---{RESET}\n")
    confirm = input(f"{RED}Kya aap saved account details delete karna chahte hain? (y/n): {RESET}").lower()
    
    if confirm == 'y':
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        if os.path.exists(f"{SESSION_FILE}.session"):
            os.remove(f"{SESSION_FILE}.session")
        print(f"\n{GREEN}[✓] Session aur Config delete ho gaye!{RESET}")
        input(f"\n{CYAN}Press Enter to Exit...{RESET}")
        sys.exit(0)
    else:
        print(f"\n{YELLOW}[*] Cancelled.{RESET}")
        input(f"\n{CYAN}Press Enter to return...{RESET}")

# ================= MAIN MENU =================
async def main():
    await connect_and_login()
    
    while True:
        banner()
        print(f"{BOLD}1.{RESET} Scrape All Group Usernames")
        print(f"{BOLD}2.{RESET} Scrape Online Members Only (Live Active)")
        print(f"{BOLD}3.{RESET} Auto Add Members to Target Group")
        print(f"{BOLD}4.{RESET} Remove Already Added Members From Saved List")
        print(f"{BOLD}5.{RESET} Switch / Reset Telegram Account")
        print(f"{BOLD}6.{RESET} Exit")
        print("--------------------------------------------------")
        
        choice = input(f"{CYAN}Select an option (1-6): {RESET}").strip()
        
        if choice == "1":
            await scrape_all_members()
        elif choice == "2":
            await scrape_online_members()
        elif choice == "3":
            await add_members()
        elif choice == "4":
            await remove_existing_from_file()
        elif choice == "5":
            await reset_account()
        elif choice == "6":
            print(f"\n{YELLOW}[*] Disconnecting and Exiting...{RESET}")
            if client and client.is_connected():
                await client.disconnect()
            sys.exit(0)
        else:
            print(f"{RED}[!] Invalid Choice!{RESET}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{RED}[!] Program closed manually.{RESET}")
        