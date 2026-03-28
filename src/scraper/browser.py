import os
import sys
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

def init_driver():
    service = Service(settings.DRIVER_PATH)
    options = Options()
    
    # Ẩn log rác & Tối ưu WebRTC
    options.add_argument("--log-level=3")
    options.add_argument("--disable-webrtc")
    options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")

    # Xóa cờ Bot
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Profile lưu Cookie
    profile_path = os.path.join(os.getcwd(), "edge_profile")
    options.add_argument(f"user-data-dir={profile_path}")

    return webdriver.Edge(service=service, options=options)