#Phai chuan reeltab https://www.facebook.com/profile.php?id=UID&sk=reels_tab or sk=videos
import time
import pickle
import os
import re
import json
import logging
from datetime import datetime
from threading import Thread
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

class FacebookScraper:
    def __init__(self):
        self.driver = None
        self.is_running = False
        self.is_paused = False
        self.setup_logging()
        
    def setup_logging(self):
        """Thiết lập logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('scraper.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def validate_facebook_url(self, url):
        """Validate URL Facebook"""
        fb_patterns = [
            r'https?://(?:www\.)?facebook\.com/[^/]+/?$',
            r'https?://(?:www\.)?facebook\.com/[^/]+/videos/?$',
            r'https?://(?:www\.)?facebook\.com/groups/[^/]+/?$',
        ]
        return any(re.match(pattern, url) for pattern in fb_patterns)

    def create_chrome_driver(self):
        """Tạo Chrome driver với các tùy chọn tối ưu"""
        options = Options()
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            driver = webdriver.Chrome(options=options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e:
            self.logger.error(f"Không thể tạo Chrome driver: {e}")
            raise

    def load_cookies(self, cookie_path):
        """Load cookies với xử lý lỗi tốt hơn"""
        if not os.path.exists(cookie_path) or os.path.getsize(cookie_path) == 0:
            self.logger.warning("File cookie không tồn tại hoặc rỗng")
            return False
            
        try:
            with open(cookie_path, "rb") as f:
                cookies = pickle.load(f)
            
            self.driver.get("https://www.facebook.com/")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            valid_cookies = 0
            for cookie in cookies:
                # Loại bỏ các thuộc tính có thể gây lỗi
                cookie.pop("sameSite", None)
                cookie.pop("expiry", None)
                cookie.pop("httpOnly", None)
                
                try:
                    self.driver.add_cookie(cookie)
                    valid_cookies += 1
                except Exception as e:
                    self.logger.debug(f"Không thể thêm cookie: {e}")
                    continue
            
            self.driver.refresh()
            time.sleep(3)
            
            # Kiểm tra đăng nhập thành công
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='nav-logo']"))
                )
                self.logger.info(f"Đăng nhập thành công với {valid_cookies} cookies")
                return True
            except TimeoutException:
                self.logger.warning("Có thể chưa đăng nhập thành công")
                return False
                
        except Exception as e:
            self.logger.error(f"Lỗi khi load cookies: {e}")
            return False

    def smart_scroll(self, callback=None):
        """Scroll thông minh với điều kiện dừng - tối ưu cho Reels"""
        links = set()
        scroll_count = 0
        no_new_content_count = 0
        max_no_new_content = 8  # Tăng lên để chờ load content
        
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while (self.is_running and 
               no_new_content_count < max_no_new_content and 
               scroll_count < 200):  # Tăng giới hạn scroll
            
            if self.is_paused:
                time.sleep(1)
                continue
                
            # Scroll xuống từ từ để trigger lazy loading
            current_position = self.driver.execute_script("return window.pageYOffset")
            new_position = current_position + 800  # Scroll nhỏ hơn để load tốt hơn
            self.driver.execute_script(f"window.scrollTo(0, {new_position});")
            
            time.sleep(1.5)  # Chờ content load
            
            # Scroll thêm một chút
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Thời gian chờ để Facebook load thêm content
            wait_time = 3 if scroll_count < 10 else 2  # Chờ lâu hơn ở đầu
            time.sleep(wait_time)
            
            # Thu thập links với nhiều selector khác nhau
            old_count = len(links)
            
            # 1. Tìm tất cả <a> tags
            all_links = self.driver.find_elements(By.TAG_NAME, "a")
            
            # 2. Tìm các element có data attributes của reels
            reel_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-pagelet*='reel'], [data-testid*='reel']")
            
            # 3. Tìm video containers
            video_containers = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button'][tabindex='0']")
            
            all_elements = all_links + reel_elements + video_containers
            
            for element in all_elements:
                try:
                    # Lấy href trực tiếp
                    href = element.get_attribute("href")
                    if href and self.is_video_link(href):
                        clean_link = self.clean_facebook_url(href)
                        if clean_link:
                            links.add(clean_link)
                            continue
                    
                    # Tìm href trong parent/child elements
                    parent = element.find_element(By.XPATH, "..")
                    parent_href = parent.get_attribute("href")
                    if parent_href and self.is_video_link(parent_href):
                        clean_link = self.clean_facebook_url(parent_href)
                        if clean_link:
                            links.add(clean_link)
                            continue
                    
                    # Tìm trong child elements
                    child_links = element.find_elements(By.TAG_NAME, "a")
                    for child in child_links:
                        child_href = child.get_attribute("href")
                        if child_href and self.is_video_link(child_href):
                            clean_link = self.clean_facebook_url(child_href)
                            if clean_link:
                                links.add(clean_link)
                                break
                    
                    # Tìm data-href attribute
                    data_href = element.get_attribute("data-href")
                    if data_href and self.is_video_link(data_href):
                        clean_link = self.clean_facebook_url(data_href)
                        if clean_link:
                            links.add(clean_link)
                            
                except Exception as e:
                    continue
            
            new_count = len(links)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Kiểm tra có content mới không (cả chiều cao và số lượng link)
            if new_height == last_height and new_count == old_count:
                no_new_content_count += 1
            else:
                no_new_content_count = 0
                
            last_height = new_height
            scroll_count += 1
            
            # Callback để cập nhật UI
            if callback:
                callback(scroll_count, len(links), no_new_content_count)
                
            self.logger.info(f"Scroll {scroll_count}: {len(links)} links, no new: {no_new_content_count}")
            
            # Trigger thêm interaction để load content
            if scroll_count % 5 == 0:  # Mỗi 5 lần scroll
                try:
                    self.driver.execute_script("window.dispatchEvent(new Event('scroll'));")
                    time.sleep(1)
                except:
                    pass
        
        return links

    def is_video_link(self, url):
        """Kiểm tra xem có phải link video/reel không - mở rộng patterns"""
        if not url:
            return False
            
        video_patterns = [
            "/reel/",
            "/reels/", 
            "/videos/",
            "/watch/",
            "facebook.com/watch",
            "/video.php",
            "fb.watch/",
            "/story.php",
            "story_fbid=",
            "/permalink.php",
        ]
        
        # Kiểm tra pattern cơ bản
        for pattern in video_patterns:
            if pattern in url.lower():
                return True
        
        # Kiểm tra Reels ID pattern (số dài sau facebook.com/)
        import re
        reel_id_pattern = r'facebook\.com/[^/]+/?\?.*story_fbid=\d+'
        if re.search(reel_id_pattern, url):
            return True
            
        # Pattern cho reel ID trực tiếp
        direct_reel_pattern = r'facebook\.com/\d{10,}'
        if re.search(direct_reel_pattern, url):
            return True
            
        return False

    def clean_facebook_url(self, url):
        """Làm sạch URL Facebook và chuẩn hóa"""
        if not url or "facebook.com" not in url:
            return None
            
        try:
            # Loại bỏ các parameter không cần thiết nhưng giữ lại ID quan trọng
            important_params = ['story_fbid', 'id', 'v', 'fbid']
            
            if '?' in url:
                base_url, params = url.split('?', 1)
                if any(param in params for param in important_params):
                    # Giữ lại URL với params quan trọng
                    return url.split('#')[0]  # Chỉ bỏ fragment
                else:
                    # Bỏ tất cả params
                    return base_url
            
            return url.split('#')[0]  # Bỏ fragment
            
        except Exception:
            return url.split('?')[0] if '?' in url else url

    def save_results(self, links, filepath, format_type="txt"):
        """Lưu kết quả với nhiều format"""
        try:
            if format_type == "txt":
                with open(filepath, "w", encoding="utf-8") as f:
                    for link in sorted(links):
                        f.write(link + "\n")
            elif format_type == "json":
                data = {
                    "timestamp": datetime.now().isoformat(),
                    "total_links": len(links),
                    "links": sorted(list(links))
                }
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    
            self.logger.info(f"Đã lưu {len(links)} links vào {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi lưu file: {e}")
            return False

    def scrape_facebook_videos(self, url, save_path, cookie_path=None, 
                             progress_callback=None, status_callback=None):
        """Hàm chính để scrape videos - tối ưu cho Reels"""
        try:
            self.is_running = True
            
            if status_callback:
                status_callback("🚀 Khởi tạo Chrome driver...")
            
            self.driver = self.create_chrome_driver()
            
            # Load cookies nếu có
            if cookie_path:
                if status_callback:
                    status_callback("🔐 Đang đăng nhập bằng cookie...")
                self.load_cookies(cookie_path)
            
            # Mở trang Facebook
            if status_callback:
                status_callback("🌐 Đang mở trang Facebook...")
            
            self.driver.get(url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Chờ thêm để page load hoàn toàn
            time.sleep(5)
            
            # Kiểm tra xem có phải trang reels không và chuyển hướng nếu cần
            current_url = self.driver.current_url
            if "/reels" not in current_url and "reel" not in url.lower():
                # Thử navigate đến tab reels nếu có
                try:
                    reels_tab = self.driver.find_element(By.XPATH, "//a[contains(@href, '/reels') or contains(text(), 'Reels')]")
                    reels_tab.click()
                    time.sleep(3)
                    if status_callback:
                        status_callback("📱 Đã chuyển đến tab Reels...")
                except:
                    pass
            
            # Bắt đầu scroll và thu thập links
            if status_callback:
                status_callback("📜 Bắt đầu thu thập Reels links...")
                
            def scroll_callback(scroll_count, link_count, no_new_count):
                if progress_callback:
                    progress_callback(scroll_count, link_count)
                if status_callback:
                    status_callback(f"🔄 Scroll {scroll_count} - {link_count} reels - No new: {no_new_count}")
            
            links = self.smart_scroll(scroll_callback)
            
            # Lọc và validate links một lần nữa
            valid_links = set()
            for link in links:
                if self.is_video_link(link) and "facebook.com" in link:
                    valid_links.add(link)
            
            # Lưu kết quả
            if status_callback:
                status_callback("💾 Đang lưu kết quả...")
                
            success = self.save_results(valid_links, save_path)
            
            if success:
                if status_callback:
                    status_callback(f"✅ Hoàn thành! Đã lưu {len(valid_links)} reels")
                return len(valid_links)
            else:
                if status_callback:
                    status_callback("❌ Lỗi khi lưu file")
                return 0
                
        except Exception as e:
            error_msg = f"❌ Lỗi: {str(e)}"
            self.logger.error(error_msg)
            if status_callback:
                status_callback(error_msg)
            return 0
        finally:
            self.is_running = False
            if self.driver:
                self.driver.quit()
                self.driver = None

    def pause_scraping(self):
        """Tạm dừng scraping"""
        self.is_paused = True

    def resume_scraping(self):
        """Tiếp tục scraping"""
        self.is_paused = False

    def stop_scraping(self):
        """Dừng scraping"""
        self.is_running = False


class FacebookScraperGUI:
    def __init__(self):
        self.scraper = FacebookScraper()
        self.scraper_thread = None
        self.setup_gui()
        
    def setup_gui(self):
        """Thiết lập giao diện"""
        self.root = tk.Tk()
        self.root.title("📥 Facebook Reels/Video Scraper - Advanced")
        self.root.geometry("900x500")
        self.root.resizable(True, True)
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # URL input
        ttk.Label(main_frame, text="🔗 Facebook URL:").grid(row=0, column=0, sticky="w", pady=5)
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=80)
        url_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        
        # Output file
        ttk.Label(main_frame, text="💾 Output file:").grid(row=1, column=0, sticky="w", pady=5)
        self.output_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.output_var, width=60).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(main_frame, text="Browse", command=self.choose_output_file).grid(row=1, column=2, padx=5)
        
        # Cookie file
        ttk.Label(main_frame, text="🍪 Cookie file (optional):").grid(row=2, column=0, sticky="w", pady=5)
        self.cookie_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.cookie_var, width=60).grid(row=2, column=1, sticky="ew", padx=5)
        ttk.Button(main_frame, text="Browse", command=self.choose_cookie_file).grid(row=2, column=2, padx=5)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        self.start_btn = ttk.Button(button_frame, text="▶ Start", command=self.start_scraping)
        self.start_btn.pack(side="left", padx=5)
        
        self.pause_btn = ttk.Button(button_frame, text="⏸ Pause", command=self.pause_scraping, state="disabled")
        self.pause_btn.pack(side="left", padx=5)
        
        self.stop_btn = ttk.Button(button_frame, text="⏹ Stop", command=self.stop_scraping, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        # Progress bar
        ttk.Label(main_frame, text="Progress:").grid(row=4, column=0, sticky="w", pady=5)
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        
        # Status
        self.status_var = tk.StringVar(value="🕓 Ready...")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.grid(row=5, column=0, columnspan=3, pady=10)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics", padding="10")
        stats_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=10)
        
        self.stats_text = tk.Text(stats_frame, height=8, width=80)
        scrollbar = ttk.Scrollbar(stats_frame, orient="vertical", command=self.stats_text.yview)
        self.stats_text.configure(yscrollcommand=scrollbar.set)
        
        self.stats_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
    def choose_output_file(self):
        """Chọn file output"""
        path = filedialog.asksaveasfilename(
            title="Choose output file",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json")]
        )
        if path:
            self.output_var.set(path)
            
    def choose_cookie_file(self):
        """Chọn file cookie"""
        path = filedialog.askopenfilename(
            title="Choose cookie file",
            filetypes=[("Pickle files", "*.pkl")]
        )
        if path:
            self.cookie_var.set(path)
    
    def update_status(self, message):
        """Cập nhật status"""
        self.status_var.set(message)
        self.root.update()
        
    def update_progress(self, scroll_count, link_count):
        """Cập nhật progress"""
        stats_msg = f"Scroll: {scroll_count} | Links found: {link_count}\n"
        self.stats_text.insert(tk.END, stats_msg)
        self.stats_text.see(tk.END)
        self.root.update()
        
    def start_scraping(self):
        """Bắt đầu scraping"""
        url = self.url_var.get().strip()
        output_path = self.output_var.get().strip()
        cookie_path = self.cookie_var.get().strip()
        
        # Validation
        if not url:
            messagebox.showerror("Error", "Please enter Facebook URL")
            return
            
        if not self.scraper.validate_facebook_url(url):
            messagebox.showerror("Error", "Invalid Facebook URL format")
            return
            
        if not output_path:
            messagebox.showerror("Error", "Please choose output file")
            return
        
        # Update UI
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        self.progress.start()
        self.stats_text.delete(1.0, tk.END)
        
        # Start scraping in thread
        self.scraper_thread = Thread(
            target=self._scrape_worker,
            args=(url, output_path, cookie_path),
            daemon=True
        )
        self.scraper_thread.start()
        
    def _scrape_worker(self, url, output_path, cookie_path):
        """Worker function cho scraping"""
        try:
            result = self.scraper.scrape_facebook_videos(
                url=url,
                save_path=output_path,
                cookie_path=cookie_path if cookie_path else None,
                progress_callback=self.update_progress,
                status_callback=self.update_status
            )
            
            if result > 0:
                messagebox.showinfo("Success", f"Successfully scraped {result} video links!")
            else:
                messagebox.showerror("Error", "Scraping failed or no links found")
                
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        finally:
            # Reset UI
            self.root.after(0, self._reset_ui)
    
    def _reset_ui(self):
        """Reset UI sau khi scraping xong"""
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.progress.stop()
        
    def pause_scraping(self):
        """Tạm dừng scraping"""
        if self.scraper.is_running:
            if self.scraper.is_paused:
                self.scraper.resume_scraping()
                self.pause_btn.config(text="⏸ Pause")
                self.update_status("▶ Resumed scraping...")
            else:
                self.scraper.pause_scraping()
                self.pause_btn.config(text="▶ Resume")
                self.update_status("⏸ Paused scraping...")
                
    def stop_scraping(self):
        """Dừng scraping"""
        self.scraper.stop_scraping()
        self.update_status("⏹ Stopping scraping...")
        
    def run(self):
        """Chạy ứng dụng"""
        self.root.mainloop()


if __name__ == "__main__":
    app = FacebookScraperGUI()
    app.run()