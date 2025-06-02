import os
import re
import uuid
import requests
import tempfile
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, unquote

def download_batch(urls, save_dir, max_workers=8, target_subdir="downloaded_images"):
    """
    批量下载图片并重命名临时目录
    
    :param urls: 图片URL列表
    :param save_dir: 最终保存目录
    :param max_workers: 最大线程数
    :param target_subdir: 重命名后的子目录名
    """
    os.makedirs(save_dir, exist_ok=True)  # 确保目录存在
    # 检查目标目录是否存在
    save_dir_existed = True # os.path.exists(save_dir)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"🔄 临时下载目录: {tmpdir}")
        lock = threading.Lock()  # 创建线程锁
        
        with ThreadPoolExecutor(max_workers) as executor:
            futures = [executor.submit(_download, url, tmpdir, lock) 
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
            backup_name = f"{target_subdir}_backup_{uuid.uuid4().hex[:8]}"
            os.rename(target_path, os.path.join(save_dir, backup_name))
        
        os.rename(source_subdir, target_path)
        print(f"♻️ 已将临时目录重命名为: {target_subdir}")

def _download(url, save_dir, lock):
    """
    下载单个文件并保留原始文件名
    
    :param url: 文件URL
    :param save_dir: 保存目录
    :param lock: 线程锁
    """
    try:
        response = requests.get(url, timeout=15, stream=True)
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
        "https://example.com/images/sunset.jpg",
        "https://example.com/gallery/portrait.png"
    ]
    download_batch(
        urls=image_urls,
        save_dir="test/images",
        max_workers=4,
        target_subdir="downloaded_images"
    )