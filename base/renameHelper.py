import os
import shutil
from datetime import datetime

def batch_rename_with_duplicate(src_dir, name_map, del_dir_existed=False):
    """
    批量重命名文件并复制到新目录（支持单文件生成多个重命名副本）
    
    参数:
        src_dir: 源目录路径
        name_map: 映射字典 {旧文件名: [新文件名1, 新文件名2...]}
        del_dir_existed: 是否删除已存在的目标目录（默认为False）rename_**
    """
    # 创建新目录（格式：rename_原目录名）
    base_name = os.path.basename(src_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = os.path.join(os.path.dirname(src_dir), f"rename_{base_name}")

    # 安全重命名（避免覆盖已有目录）
    if os.path.exists(dest_dir):
        if del_dir_existed:
            # 删除现有目录
            shutil.rmtree(dest_dir)
            print(f"🗑️ 已删除现有目录: {dest_dir}")
        else:
            # 备份现有目录（格式：rename_原目录名_backup_时间戳）
            backup_name = f"{dest_dir}_backup_{timestamp}"
            os.rename(dest_dir, backup_name)
    
    # 复制目录结构
    shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
    
    # 遍历所有文件
    for root, _, files in os.walk(dest_dir):
        for file in files:
            src_file = os.path.join(root, file)
            
            # 检查是否在重命名映射中
            if file in name_map:
                # 获取新文件名列表
                new_names = name_map[file]
                
                # 为每个新文件名创建副本
                for new_name in new_names:
                    dest_file = os.path.join(root, new_name)
                    shutil.copy2(src_file, dest_file)
                    print(f"✅ 创建副本: {file} → {new_name}")
                
                # 删除原始文件（保留重命名后的副本）
                os.remove(src_file)
                print(f"🗑️ 移除原始文件: {file}")
    
    print(f"\n🎉 操作完成！新目录已创建在: {dest_dir}")

# 示例用法
if __name__ == "__main__":
    # 配置参数
    source_directory = "test/images/downloaded"  # 替换为实际目录
    
    # 重命名映射配置 {旧文件名: [新文件名1, 新文件名2...]}
    rename_mapping = {
        "25cookieshitthebonus.png": ["ps_25_cookies.png"],
        "mammothpeakholdandwin.png": ["wolf_land_1.png", "wolf_land_2.png"]
    }
    
    # 执行重命名
    batch_rename_with_duplicate(source_directory, rename_mapping, True)