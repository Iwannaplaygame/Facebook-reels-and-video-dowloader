import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import re
import threading
import time
import queue
from datetime import datetime
import yt_dlp
import subprocess
import sys
from urllib.parse import urlparse

class FacebookVideoDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("Facebook Video & Reels Downloader - Enhanced")
        self.root.geometry("900x700")
        
        # State variables
        self.video_list = []
        self.cookie_path = None
        self.is_downloading = False
        self.download_thread = None
        self.stop_download = False
        
        # Queue for thread communication
        self.status_queue = queue.Queue()
        
        # Statistics
        self.stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0
        }
        
        self.create_widgets()
        self.setup_status_checker()
        self.check_dependencies()

    def check_dependencies(self):
        """Kiểm tra và cập nhật yt-dlp khi khởi động"""
        def update_ytdlp():
            try:
                self.log_message("Đang kiểm tra cập nhật yt-dlp...")
                result = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], 
                                      capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    self.log_message("✓ yt-dlp đã được cập nhật")
                else:
                    self.log_message("⚠ Không thể cập nhật yt-dlp")
            except Exception as e:
                self.log_message(f"⚠ Lỗi cập nhật yt-dlp: {e}")
        
        threading.Thread(target=update_ytdlp, daemon=True).start()

    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="Facebook Video & Reels Downloader", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))

        # File selection frame
        file_frame = ttk.LabelFrame(main_frame, text="File chứa danh sách link", padding=5)
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        file_input_frame = ttk.Frame(file_frame)
        file_input_frame.pack(fill=tk.X)
        
        self.file_entry = ttk.Entry(file_input_frame, width=60)
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(file_input_frame, text="Chọn file", command=self.browse_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_input_frame, text="Phân tích", command=self.analyze_file).pack(side=tk.LEFT, padx=2)

        # Cookie frame
        cookie_frame = ttk.LabelFrame(main_frame, text="Cookie (tùy chọn)", padding=5)
        cookie_frame.pack(fill=tk.X, padx=5, pady=5)
        
        cookie_input_frame = ttk.Frame(cookie_frame)
        cookie_input_frame.pack(fill=tk.X)
        
        self.cookie_entry = ttk.Entry(cookie_input_frame, width=60)
        self.cookie_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(cookie_input_frame, text="Chọn cookie", command=self.load_cookie_file).pack(side=tk.LEFT, padx=2)

        # Quality selection
        quality_frame = ttk.LabelFrame(main_frame, text="Tùy chọn chất lượng", padding=5)
        quality_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.quality_var = tk.StringVar(value="best")
        quality_options = [
            ("Chất lượng cao nhất", "best"),
            ("HD (720p+)", "best[height>=720]"),
            ("SD (480p)", "best[height<=480]"),
            ("Chất lượng thấp nhất", "worst")
        ]
        
        for text, value in quality_options:
            ttk.Radiobutton(quality_frame, text=text, variable=self.quality_var, value=value).pack(anchor=tk.W)

        # Output directory
        path_frame = ttk.LabelFrame(main_frame, text="Thư mục lưu", padding=5)
        path_frame.pack(fill=tk.X, padx=5, pady=5)
        
        path_input_frame = ttk.Frame(path_frame)
        path_input_frame.pack(fill=tk.X)
        
        self.path_entry = ttk.Entry(path_input_frame)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.path_entry.insert(0, os.path.expanduser("~/Downloads/FacebookVideos"))
        
        ttk.Button(path_input_frame, text="Chọn thư mục", command=self.browse_folder).pack(side=tk.LEFT, padx=2)

        # Download options
        options_frame = ttk.LabelFrame(main_frame, text="Tùy chọn tải xuống", padding=5)
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        options_grid = ttk.Frame(options_frame)
        options_grid.pack(fill=tk.X)
        
        self.retry_var = tk.IntVar(value=3)
        ttk.Label(options_grid, text="Số lần thử lại:").grid(row=0, column=0, sticky=tk.W, padx=5)
        retry_spin = ttk.Spinbox(options_grid, from_=1, to=10, width=5, textvariable=self.retry_var)
        retry_spin.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        self.timeout_var = tk.IntVar(value=30)
        ttk.Label(options_grid, text="Timeout (giây):").grid(row=0, column=2, sticky=tk.W, padx=5)
        timeout_spin = ttk.Spinbox(options_grid, from_=10, to=300, width=5, textvariable=self.timeout_var)
        timeout_spin.grid(row=0, column=3, sticky=tk.W, padx=5)

        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        self.download_btn = ttk.Button(control_frame, text="Bắt đầu tải xuống", 
                                      command=self.start_download, state="disabled")
        self.download_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="Dừng", 
                                  command=self.stop_download_process, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_btn = ttk.Button(control_frame, text="Xóa log", command=self.clear_log)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        # Progress section
        progress_frame = ttk.LabelFrame(main_frame, text="Tiến trình", padding=5)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_var = tk.StringVar(value="Sẵn sàng")
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_var)
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Statistics
        stats_frame = ttk.Frame(progress_frame)
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_var = tk.StringVar(value="Tổng: 0 | Thành công: 0 | Thất bại: 0 | Bỏ qua: 0")
        self.stats_label = ttk.Label(stats_frame, textvariable=self.stats_var, font=("Arial", 9))
        self.stats_label.pack()

        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=80)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def setup_status_checker(self):
        """Thiết lập kiểm tra trạng thái từ queue"""
        def check_queue():
            try:
                while not self.status_queue.empty():
                    message_type, data = self.status_queue.get_nowait()
                    
                    if message_type == "log":
                        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {data}\n")
                        self.log_text.see(tk.END)
                    
                    elif message_type == "progress":
                        current, total = data
                        progress = (current / total * 100) if total > 0 else 0
                        self.progress_bar['value'] = progress
                        self.progress_var.set(f"Đang xử lý: {current}/{total} ({progress:.1f}%)")
                    
                    elif message_type == "stats":
                        self.stats_var.set(f"Tổng: {data['total']} | Thành công: {data['completed']} | "
                                         f"Thất bại: {data['failed']} | Bỏ qua: {data['skipped']}")
                    
                    elif message_type == "done":
                        self.download_finished()
                        
            except queue.Empty:
                pass
            
            # Lên lịch kiểm tra lại sau 100ms
            self.root.after(100, check_queue)
        
        check_queue()

    def log_message(self, message):
        """Thread-safe logging"""
        self.status_queue.put(("log", message))

    def update_progress(self, current, total):
        """Thread-safe progress update"""
        self.status_queue.put(("progress", (current, total)))

    def update_stats(self):
        """Thread-safe stats update"""
        self.status_queue.put(("stats", self.stats))

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file chứa danh sách link",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_path)

    def load_cookie_file(self):
        cookie_path = filedialog.askopenfilename(
            title="Chọn file cookie",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if cookie_path:
            self.cookie_path = cookie_path
            self.cookie_entry.delete(0, tk.END)
            self.cookie_entry.insert(0, cookie_path)
            self.log_message(f"Đã tải cookie: {os.path.basename(cookie_path)}")

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục lưu video")
        if folder:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)

    def is_valid_url(self, url):
        """Kiểm tra URL có hợp lệ không"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc]) and 'facebook.com' in result.netloc
        except:
            return False

    def analyze_file(self):
        file_path = self.file_entry.get().strip()
        
        if not file_path:
            messagebox.showerror("Lỗi", "Vui lòng chọn file chứa danh sách link")
            return
            
        if not os.path.exists(file_path):
            messagebox.showerror("Lỗi", "File không tồn tại")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            
            # Lọc các URL hợp lệ
            valid_urls = []
            invalid_count = 0
            
            for line in lines:
                if self.is_valid_url(line):
                    valid_urls.append(line)
                else:
                    invalid_count += 1
            
            self.video_list = valid_urls
            
            if not self.video_list:
                messagebox.showerror("Lỗi", "File không chứa URL Facebook hợp lệ")
                return

            # Reset statistics
            self.stats = {'total': len(self.video_list), 'completed': 0, 'failed': 0, 'skipped': 0}
            self.update_stats()
            
            self.log_message(f"✓ Đã phân tích file: {len(self.video_list)} URL hợp lệ")
            if invalid_count > 0:
                self.log_message(f"⚠ Bỏ qua {invalid_count} dòng không hợp lệ")
            
            self.download_btn.config(state="normal")
            
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể đọc file: {e}")
            self.log_message(f"✗ Lỗi đọc file: {e}")

    def clean_filename(self, title, video_id):
        """Làm sạch tên file một cách kỹ lưỡng"""
        if not title or len(title.strip()) < 3:
            title = f"facebook_video_{video_id}"
        
        # Loại bỏ các pattern thường gặp ở đầu title Facebook
        title = re.sub(r'^\s*\d+(\.\d+)?[MK]?\s+views\s*·\s*\d+(\.\d+)?[MK]?\s+reactions\s*[_-]\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'^\s*\d+(\.\d+)?[MK]?\s+(views?|reactions?)\s*[_-]\s*', '', title, flags=re.IGNORECASE)
        
        # Xóa emoji và ký tự đặc biệt
        title = re.sub(r'[^\w\s\-_\(\)\[\]\.]+', ' ', title)  # Chỉ giữ lại chữ, số, space và một số ký tự an toàn
        
        # Thay thế nhiều space liên tiếp bằng 1 space
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Xóa các ký tự Windows không cho phép
        forbidden_chars = '<>:"/\\|?*'
        for char in forbidden_chars:
            title = title.replace(char, '_')
        
        # Xóa dấu chấm ở cuối (Windows không thích)
        title = title.rstrip('.')
        
        # Giới hạn độ dài (Windows có giới hạn 255 ký tự cho tên file)
        if len(title) > 150:  # Để chừa chỗ cho extension
            title = title[:150].strip()
        
        # Nếu sau khi làm sạch mà rỗng hoặc quá ngắn
        if not title or len(title) < 3:
            title = f"facebook_video_{video_id}"
        
        # Đảm bảo không bắt đầu bằng dấu chấm (hidden file trên Unix)
        if title.startswith('.'):
            title = f"fb_{title[1:]}"
        
        return title

    def create_output_directory(self):
        """Tạo thư mục output nếu chưa tồn tại"""
        output_dir = self.path_entry.get().strip()
        if not output_dir:
            output_dir = os.path.expanduser("~/Downloads/FacebookVideos")
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, output_dir)
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            return output_dir
        except Exception as e:
            self.log_message(f"✗ Không thể tạo thư mục: {e}")
            return None

    def download_single_video(self, url, index):
        """Tải một video với retry mechanism"""
        max_retries = self.retry_var.get()
        timeout = self.timeout_var.get()
        
        for attempt in range(max_retries):
            if self.stop_download:
                return "stopped"
                
            try:
                self.log_message(f"[{index}] Đang tải: {url} (lần thử {attempt + 1}/{max_retries})")
                
                # Bước 1: Lấy thông tin video trước
                info_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'socket_timeout': timeout,
                }
                
                if self.cookie_path and os.path.exists(self.cookie_path):
                    info_opts['cookiefile'] = self.cookie_path
                
                with yt_dlp.YoutubeDL(info_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                
                # Bước 2: Làm sạch title và tạo filename
                title = info.get('title', f'facebook_video_{index}')
                video_id = info.get('id', str(index))
                ext = info.get('ext', 'mp4')
                
                # Làm sạch tên file
                clean_title = self.clean_filename(title, video_id)
                filename = f"{clean_title}.{ext}"
                filepath = os.path.join(self.create_output_directory(), filename)
                
                # Bước 3: Tải video với đường dẫn cố định
                download_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'socket_timeout': timeout,
                    'format': self.quality_var.get(),
                    'outtmpl': filepath,
                }
                
                if self.cookie_path and os.path.exists(self.cookie_path):
                    download_opts['cookiefile'] = self.cookie_path
                
                with yt_dlp.YoutubeDL(download_opts) as ydl:
                    ydl.download([url])
                    
                    self.log_message(f"✓ [{index}] Thành công: {clean_title}")
                    return "success"
                    
            except yt_dlp.DownloadError as e:
                error_msg = str(e)
                if "Private video" in error_msg or "not available" in error_msg:
                    self.log_message(f"⚠ [{index}] Video private hoặc không khả dụng")
                    return "skipped"
                elif attempt < max_retries - 1:
                    self.log_message(f"⚠ [{index}] Lỗi tải (thử lại sau 2s): {error_msg}")
                    time.sleep(2)
                else:
                    self.log_message(f"✗ [{index}] Thất bại sau {max_retries} lần thử: {error_msg}")
                    return "failed"
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    self.log_message(f"⚠ [{index}] Lỗi không xác định (thử lại): {e}")
                    time.sleep(2)
                else:
                    self.log_message(f"✗ [{index}] Lỗi không xác định: {e}")
                    return "failed"
        
        return "failed"

    def download_process(self):
        """Quá trình tải xuống chính"""
        try:
            output_dir = self.create_output_directory()
            if not output_dir:
                return
            
            self.log_message(f"🚀 Bắt đầu tải {len(self.video_list)} video vào: {output_dir}")
            
            total_videos = len(self.video_list)
            
            for i, url in enumerate(self.video_list, 1):
                if self.stop_download:
                    self.log_message("⏹ Quá trình tải đã bị dừng bởi người dùng")
                    break
                
                self.update_progress(i, total_videos)
                
                result = self.download_single_video(url, i)
                
                if result == "success":
                    self.stats['completed'] += 1
                elif result == "failed":
                    self.stats['failed'] += 1
                elif result == "skipped":
                    self.stats['skipped'] += 1
                elif result == "stopped":
                    break
                
                self.update_stats()
            
            # Hoàn thành
            if not self.stop_download:
                self.log_message(f"🎉 Hoàn thành! Thành công: {self.stats['completed']}, "
                               f"Thất bại: {self.stats['failed']}, Bỏ qua: {self.stats['skipped']}")
                messagebox.showinfo("Hoàn thành", f"Đã tải xong!\nThành công: {self.stats['completed']}\n"
                                  f"Thất bại: {self.stats['failed']}\nBỏ qua: {self.stats['skipped']}")
            
        except Exception as e:
            self.log_message(f"✗ Lỗi trong quá trình tải: {e}")
            messagebox.showerror("Lỗi", f"Lỗi trong quá trình tải: {e}")
        
        finally:
            self.status_queue.put(("done", None))

    def start_download(self):
        if not self.video_list:
            messagebox.showerror("Lỗi", "Chưa có danh sách video để tải")
            return
        
        self.is_downloading = True
        self.stop_download = False
        self.download_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        
        # Reset progress
        self.progress_bar['value'] = 0
        self.progress_var.set("Đang chuẩn bị...")
        
        # Bắt đầu thread tải xuống
        self.download_thread = threading.Thread(target=self.download_process, daemon=True)
        self.download_thread.start()

    def stop_download_process(self):
        self.stop_download = True
        self.log_message("⏸ Đang dừng quá trình tải xuống...")
        self.stop_btn.config(state="disabled")

    def download_finished(self):
        """Được gọi khi quá trình tải xuống hoàn thành"""
        self.is_downloading = False
        self.stop_download = False
        self.download_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.progress_var.set("Sẵn sàng")

    def clear_log(self):
        self.log_text.delete('1.0', tk.END)


def main():
    root = tk.Tk()
    app = FacebookVideoDownloader(root)
    root.mainloop()


if __name__ == '__main__':
    main()