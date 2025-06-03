from PIL import Image
import os
import concurrent.futures

def batch_process_images(input_dir, output_dir, new_size=None, target_format=None, quality=85, keep_aspect_ratio=True, max_workers=8):
    """
    多线程批量处理图片（尺寸调整 + 格式转换）
    :param input_dir: 输入目录
    :param output_dir: 输出目录
    :param new_size: 目标尺寸 (宽度, 高度) 或 None
    :param target_format: 目标格式 ('JPEG', 'PNG'等) 或 None
    :param quality: 保存质量 (1-100)
    :param max_workers: 最大线程数（根据CPU核心数设置）[4,7](@ref)
    """
    os.makedirs(output_dir, exist_ok=True)
    img_formats = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')
    
    # 获取所有图片文件
    img_files = []
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(img_formats):
            img_files.append(filename)
    
    # 定义单张图片处理函数
    def process_single_image(filename):
        input_path = os.path.join(input_dir, filename)
        
        # 确定输出文件名
        base_name = os.path.splitext(filename)[0]
        ext = target_format.lower() if target_format else os.path.splitext(filename)[1][1:]
        output_filename = f"{base_name}.{ext}"
        output_path = os.path.join(output_dir, output_filename)
        
        try:
            with Image.open(input_path) as img:
                print(f"处理: {filename}")
                
                # 1. 调整尺寸
                if new_size:
                    if keep_aspect_ratio:
                        print(f"  保持比例调整: {img.size} → {new_size}")
                        img.thumbnail(new_size, Image.LANCZOS)
                    else:
                        print(f"  尺寸调整: {img.size} → {new_size}")
                        img = img.resize(new_size, Image.LANCZOS)
                
                # 2. 格式转换处理
                if target_format:
                    if target_format.upper() == 'JPEG' and img.mode in ['RGBA', 'LA']:
                        img = img.convert('RGB')
                
                # 保存参数
                save_params = {}
                if target_format:
                    save_params['format'] = target_format
                if target_format and target_format.upper() == 'JPEG':
                    save_params['quality'] = quality
                
                img.save(output_path, **save_params)
                print(f"✓ 保存为: {output_filename}")
                return True, filename
        except Exception as e:
            print(f"❌ 处理失败 {filename}: {str(e)}")
            return False, filename
    
    # 使用线程池处理[1,4,6](@ref)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_single_image, filename) for filename in img_files]
        
        # 收集结果
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    
    # 生成处理报告
    success_count = sum(1 for success, _ in results if success)
    print("\n📊 处理报告:")
    print("-" * 65)
    print(f"✅ 成功: {success_count}/{len(img_files)}")
    print(f"❌ 失败: {len(img_files)-success_count}")
    print("-" * 65)
    
    # 打印失败文件列表
    if len(img_files) > success_count:
        print("失败文件列表:")
        for success, filename in results:
            if not success:
                print(f"  - {filename}")


def smart_compress(input_path, output_path, quality=85, optimize=True):
    """
    智能压缩单张图片（不改变尺寸和格式）
    :param input_path: 输入图片路径
    :param output_path: 输出图片路径
    :param quality: 压缩质量 (1-95)
    :param optimize: 是否启用优化算法
    """
    try:
        with Image.open(input_path) as img:
            # 保留原始格式和模式
            orig_format = img.format
            orig_mode = img.mode
            
            # 特殊格式处理
            save_params = {
                'format': orig_format,
                'optimize': optimize
            }
            
            # JPEG特有参数
            if orig_format == 'JPEG':
                save_params['quality'] = quality
                save_params['subsampling'] = 0  # 保持最高色度分辨率[3](@ref)
                
                # 透明通道处理
                if orig_mode in ('RGBA', 'LA'):
                    img = img.convert('RGB')
            
            # PNG特有参数
            elif orig_format == 'PNG':
                save_params['compress_level'] = 9  # 最高压缩级别[7](@ref)
            
            # 保存压缩后图片
            img.save(output_path, **save_params)
            
            # 返回压缩信息
            orig_size = os.path.getsize(input_path) / 1024
            new_size = os.path.getsize(output_path) / 1024
            ratio = (1 - new_size/orig_size) * 100
            
            return {
                'filename': os.path.basename(input_path),
                'original_size': f"{orig_size:.1f}KB",
                'compressed_size': f"{new_size:.1f}KB",
                'compression_ratio': f"{ratio:.1f}%",
                'status': '✓ 成功'
            }
    
    except Exception as e:
        return {
            'filename': os.path.basename(input_path),
            'status': f'❌ 失败: {str(e)}'
        }

def batch_compress_images(input_dir, output_dir, quality=85, max_workers=8):
    """
    批量压缩图片
    :param input_dir: 输入目录
    :param output_dir: 输出目录
    :param quality: 压缩质量 (1-95)
    :param max_workers: 最大线程数
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取所有图片文件
    img_files = []
    for f in os.listdir(input_dir):
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
            img_files.append(f)
    
    # 多线程处理
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for filename in img_files:
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            futures.append(executor.submit(smart_compress, input_path, output_path, quality))
        
        # 收集结果
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    
    # 打印压缩报告
    print("\n📊 压缩报告:")
    print("-" * 65)
    print(f"{'文件名':<20}{'原始大小':>10}{'压缩后':>10}{'压缩率':>10}{'状态':>15}")
    print("-" * 65)
    
    for res in results:
        if 'original_size' in res:
            print(f"{res['filename'][:18]:<20}"
                  f"{res['original_size']:>10}"
                  f"{res['compressed_size']:>10}"
                  f"{res['compression_ratio']:>10}"
                  f"{res['status']:>15}")
        else:
            print(f"{res['filename'][:18]:<20}{'':>30}{res['status']:>15}")
    
    print("-" * 65)
    success_count = sum(1 for r in results if 'original_size' in r)
    print(f"✅ 完成: {success_count}/{len(results)} | "
          f"失败: {len(results)-success_count}")

# 使用示例
# 修改主函数调用部分
if __name__ == "__main__":
    # 创建线程池确保顺序执行
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        # 第一阶段：尺寸调整+格式转换
        process_future = executor.submit(
            batch_process_images,
            input_dir="test/images/downloaded",
            output_dir="test/images/process_downloaded",
            new_size=(200, 200),
            target_format="PNG",
            quality=85,
            keep_aspect_ratio=False,
            max_workers=8
        )
        
        # 阻塞等待第一阶段完成
        process_future.result()
        print("\n✅ 第一阶段处理完成，开始压缩...\n")
        
        # 第二阶段：压缩处理
        compress_future = executor.submit(
            batch_compress_images,
            input_dir="test/images/process_downloaded",
            output_dir="test/images/compress_downloaded",
            quality=85,
            max_workers=8
        )
        compress_future.result()