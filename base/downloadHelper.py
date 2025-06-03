import os
import re
import uuid
import requests
import tempfile
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, unquote
from datetime import datetime

import time  # 修复 RateLimiter 中的 time.time()
from requests.adapters import HTTPAdapter  # 修复 HTTPAdapter
from urllib3.util.retry import Retry  # 修复 Retry

# 全局添加令牌桶限流器
class RateLimiter:
    def __init__(self, rate):
        self.rate = rate  # 每秒请求数
        self.tokens = 0
        self.last = time.time()
    
    def acquire(self):
        now = time.time()
        elapsed = now - self.last
        self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
        self.last = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
    
def download_batch(urls, save_dir, max_workers=8, target_subdir="downloaded", del_dir_existed=False):
    """
    批量下载图片并重命名临时目录
    
    :param urls: 图片URL列表
    :param save_dir: 最终保存目录
    :param max_workers: 最大线程数
    :param target_subdir: 重命名后的子目录名
    :param del_dir_existed: 是否删除已存在的目标目录（默认为False）downloaded
    """
    os.makedirs(save_dir, exist_ok=True)  # 确保目录存在
    # 检查目标目录是否存在
    save_dir_existed = True # os.path.exists(save_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    limiter = RateLimiter(rate=15)  # 根据服务器承受能力调整
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"🔄 临时下载目录: {tmpdir}")
        lock = threading.Lock()  # 创建线程锁
        
        with ThreadPoolExecutor(max_workers) as executor:
            futures = [executor.submit(_download, url, tmpdir, lock, limiter) 
                      for url in urls]
            for future in futures:
                future.result()  # 等待所有任务完成
        
        # 移动整个临时目录到目标位置
        shutil.move(tmpdir, save_dir)
        print(f"📦 文件已移动到: {save_dir}")

    # 重命名子目录（仅在目标目录已存在时执行）
    if save_dir_existed:
        tmpdir_name = os.path.basename(tmpdir)
        source_subdir = os.path.join(save_dir, tmpdir_name)
        target_path = os.path.join(save_dir, target_subdir)
        
        # 安全重命名（避免覆盖已有目录）
        if os.path.exists(target_path):
            if del_dir_existed:
                # 删除现有目录
                shutil.rmtree(target_path)
                print(f"🗑️ 已删除现有目录: {target_path}")
            else:
                # backup_name = f"{target_subdir}_backup_{uuid.uuid4().hex[:8]}"
                backup_name = f"{target_subdir}_backup_{timestamp}"
                os.rename(target_path, os.path.join(save_dir, backup_name))
        
        os.rename(source_subdir, target_path)
        print(f"♻️ 已将临时目录重命名为: {target_subdir}")

def _download(url, save_dir, lock, limiter):
    """
    下载单个文件并保留原始文件名
    
    :param url: 文件URL
    :param save_dir: 保存目录
    :param lock: 线程锁
    :param limiter: 令牌桶限流器
    """
    if not limiter.acquire():
        time.sleep(0.1)  # 等待令牌

    # 创建带连接池的session
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=100,    # 连接池数量
        pool_maxsize=200,        # 最大连接数
        max_retries=Retry(       # 重试策略
            total=3,             # 总重试次数
            backoff_factor=0.5,  # 重试等待时间因子
            status_forcelist=[500, 502, 503, 504]
        )
    )
    session.mount('https://', adapter)
    
    try:
        response = session.get(url, timeout=(3.05, 30), stream=True)  # 分连接/读取超时
        response.raise_for_status()
        
        # 提取原始文件名
        filename = _extract_filename(url, response.headers)
        temp_file = os.path.join(save_dir, f"temp_{uuid.uuid4().hex}.tmp")
        
        # 流式下载到临时文件
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # 过滤keep-alive的chunk
                    f.write(chunk)
        
        # 使用锁确保线程安全的重命名
        with lock:
            final_path = _get_unique_filename(save_dir, filename)
            os.rename(temp_file, final_path)
        
        print(f"✅ 下载成功: {os.path.basename(final_path)}")
        return True
    except Exception as e:
        print(f"❌ 下载失败 [{url}]: {str(e)}")
        return False

def _extract_filename(url, headers):
    """三级策略提取原始文件名"""
    # 1. 从Content-Disposition头获取[1](@ref)
    if 'Content-Disposition' in headers:
        match = re.search(r'filename\*?=["\']?(?:UTF-\d[\'"]*)?([^;\'\"]+)["\']?', 
                          headers['Content-Disposition'], re.IGNORECASE)
        if match:
            return unquote(match.group(1).strip())
    
    # 2. 从URL路径提取[3](@ref)
    parsed = urlparse(url)
    if parsed.path:
        filename = unquote(parsed.path.rsplit('/', 1)[-1])
        if '.' in filename and len(filename) > 4:  # 基本验证
            return filename
    
    # 3. 使用内容类型生成[4](@ref)
    content_type = headers.get('Content-Type', '').partition(';')[0].strip()
    ext_map = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'application/pdf': '.pdf'
    }
    ext = ext_map.get(content_type, '.bin')
    return f"file_{uuid.uuid4().hex}{ext}"

def _get_unique_filename(save_dir, filename):
    """生成唯一的文件名（避免冲突）[6](@ref)"""
    base, ext = os.path.splitext(filename)
    counter = 1
    new_name = filename
    
    while os.path.exists(os.path.join(save_dir, new_name)):
        new_name = f"{base}_{counter}{ext}"
        counter += 1
    
    return os.path.join(save_dir, new_name)

# 使用示例
if __name__ == "__main__":
    image_urls = [
        "https://img.dyn123.com/images/slot-images/PS/25cookieshitthebonus.png",        # ps_25_cookies
        "https://img.dyn123.com/images/slot-images/PS/wolflandholdandwin.png",          # wolf_land
        "https://img.dyn123.com/images/slot-images/PS/sherwoodcoinsholdandwin.png",     # sherwood_coins
        "https://img.dyn123.com/images/slot-images/PS/merrygiftmasholdandwin.png",      # merry_giftmas
        "https://img.dyn123.com/images/slot-images/PS/mammothpeakholdandwin.png",       # mammoth_peak
    ]
    download_batch(
        urls=image_urls,
        save_dir="test/images",
        max_workers=8,
        target_subdir="downloaded",
        del_dir_existed=True
    )