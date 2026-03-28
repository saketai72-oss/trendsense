import time
import random
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

def solve_rotate_captcha(driver):
    try:
        time.sleep(3) # Đợi form Captcha load hẳn

        # BƯỚC 1: Lấy mã Base64
        captcha_imgs = driver.find_elements(By.CSS_SELECTOR, "img[alt='Captcha']")
        if len(captcha_imgs) < 2:
            print("  [!] Không tìm thấy ảnh Captcha. Bỏ qua video.")
            driver.refresh()
            return False 

        outer_src = captcha_imgs[0].get_attribute("src")
        outer_b64 = outer_src.split(",")[1] if "," in outer_src else outer_src
        inner_src = captcha_imgs[1].get_attribute("src")
        inner_b64 = inner_src.split(",")[1] if "," in inner_src else inner_src

        # BƯỚC 2: Gọi API
        api_url = "https://captchaapi.hacodev.io.vn/tiktok/rotate" 
        payload = {"Bade64anhNgoai": outer_b64, "Base64anhTrong": inner_b64, "type": "v2"}
        print("  [*] Đang gửi 2 ảnh lên API...")
        response = requests.post(api_url, json=payload, timeout=10).json()

        if response.get("success"):
            angle = float(response["angle"])
            slider_width = 284 
            distance = (angle / 360) * slider_width
            
            print(f"  [*] Góc xoay: {angle} độ => Kéo: {distance:.1f} px")

            # BƯỚC 3: MÔ PHỎNG KÉO CHUỘT
            slider_btn = driver.find_element(By.ID, "captcha_slide_button")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", slider_btn)
            time.sleep(1)

            actions = ActionChains(driver)
            actions.move_to_element(slider_btn).click_and_hold()
            actions.pause(random.uniform(0.3, 0.7)) 
            
            print("  [*] Đang kéo...")
            track = []
            current_int_pos = 0
            steps = random.randint(30, 45) 

            for step in range(1, steps + 1):
                t = step / steps
                ideal_pos = distance * (1 - (1 - t)**2)
                target_int_pos = round(ideal_pos)
                move_x = target_int_pos - current_int_pos
                if move_x > 0:
                    track.append(move_x)
                    current_int_pos = target_int_pos
            
            overshoot = random.randint(3, 7) 
            track.append(overshoot)
            track.append(-overshoot)

            for move in track:
                actions.move_by_offset(move, random.randint(-2, 2))
                actions.pause(random.uniform(0.01, 0.03)) 
            
            actions.pause(random.uniform(0.4, 0.8))
            actions.release()
            actions.perform()
            
            print("  [*] Kéo xong! Chờ kết quả...")
            time.sleep(5)
            return True
        else:
            print(f"  [!] API lỗi: {response}")
            return False

    except Exception as e:
        print(f"  [!] Lỗi thao tác Captcha: {e}")
        time.sleep(2)
        driver.refresh()
        time.sleep(5)
        return False