import argparse
import os
import shutil
from base import excelHelper
from base import downloadHelper
from base import renameHelper
from base import imgHelper
from core import config
from prefect import flow, task
from urllib.parse import urlparse, unquote

def parse_arguments():
    """解析命令行参数并返回字典"""
    parser = argparse.ArgumentParser(description="命令行参数解析")
    
    # 添加必须参数（根据需求调整）
    parser.add_argument("--task", type=str, required=False, help="任务名称")
    parser.add_argument("--gp", type=str, required=False, help="游戏供应商")
    parser.add_argument("--lang", type=str, required=False, help="语种")
    
    # 解析参数并转为字典
    args = parser.parse_args()
    config.ARGS = vars(args)  # 将Namespace对象转为字典，存储到全局字典中
    return config.ARGS

@task
def read_config_task():
    """读取配置文件任务"""
    gp = config.ARGS['gp']
    lang = config.ARGS['lang']
    fileName = f"gp-{gp}.xlsx"
    filePath = os.path.join(config.DEFAULT_ROOT_DIR, "config", fileName)    # 例子：../py-do/config/gp-PS.xlsx
    print(f"Reading config file: {filePath}")
    return excelHelper.read_data(filePath, lang)

@task
def download_images_task(config_data):
    """下载图片任务"""
    gp = config.ARGS['gp']
    lang = config.ARGS['lang']
    img_urls = [data['imgUrl'] for data in config_data]
    unique_img_urls = list(set(img_urls))   # 去重

    save_dir = os.path.join(config.DEFAULT_ROOT_DIR, 'download')    # 例子：../py-do/download
    target_subdir = f'{gp}-{lang}'    # 例子：PS-en
    downloadHelper.download_batch(
        urls = unique_img_urls, 
        save_dir = save_dir,
        target_subdir = target_subdir,
        del_dir_existed = True
        )
    return True

@task
def rename_images_task(config_data, downloadOK):
    """重命名图片任务"""
    gp = config.ARGS['gp']
    lang = config.ARGS['lang']
    name_map = {}
        
    for data in config_data:
        filename = data['imgName']
        if name_map.get(filename):
            name_map[filename].append(f'{data["gameId"]}.png')
        else:
            name_map[filename] = [f'{data["gameId"]}.png']

    subdir = f'{gp}-{lang}'
    src_dir = os.path.join(config.DEFAULT_ROOT_DIR, 'download', subdir)    # 例子：../py-do/download/PS-en
    renameHelper.batch_rename_with_duplicate(src_dir, name_map, None, True)
    return True

@task
def process_images_task(renameOK):
    """处理图片任务（尺寸调整 + 格式转换）"""
    gp = config.ARGS['gp']
    lang = config.ARGS['lang']
    subdir = f'{gp}-{lang}'
    src_subdir = f'rename_{subdir}'
    dst_subdir = f'process_{subdir}'
    src_dir = os.path.join(config.DEFAULT_ROOT_DIR, 'download', src_subdir)    # 例子：../py-do/download/rename_PS-en
    dst_dir = os.path.join(config.DEFAULT_ROOT_DIR, 'download', dst_subdir)    # 例子：../py-do/download/process_PS-en
    imgHelper.batch_process_images(
        input_dir=src_dir,
        output_dir=dst_dir,
        new_size=(200, 200),
        target_format="PNG",
        quality=85,
        keep_aspect_ratio=False,
        max_workers=8
    )
    return True

@task
def compress_images_task(processOK):
    """压缩图片任务"""
    gp = config.ARGS['gp']
    lang = config.ARGS['lang']
    subdir = f'{gp}-{lang}'
    src_subdir = f'process_{subdir}'
    src_dir = os.path.join(config.DEFAULT_ROOT_DIR, 'download', src_subdir)     # 例子：../py-do/download/process_PS-en
    dst_dir = os.path.join(config.DEFAULT_ROOT_DIR, f'compress/{lang}/{gp}')    # 例子：../py-do/compress/en/PS
    imgHelper.batch_compress_images(
        input_dir=src_dir,
        output_dir=dst_dir,
        quality=85,
        max_workers=8
    )
    return True

@task
def del_middle_dir(compressOK):
    # 删除中间过程产生的目录
    gp = config.ARGS['gp']
    lang = config.ARGS['lang']
    subdir = f'{gp}-{lang}'

    dest_dir_1 = os.path.join(config.DEFAULT_ROOT_DIR, 'download', f'rename_{subdir}')
    dest_dir_2 = os.path.join(config.DEFAULT_ROOT_DIR, 'download', f'process_{subdir}')

    shutil.rmtree(dest_dir_1)
    print(f"🗑️ 已删除现有目录: {dest_dir_1}")

    shutil.rmtree(dest_dir_2)
    print(f"🗑️ 已删除现有目录: {dest_dir_2}")

    return True

@flow
def process_images_flow():
    """处理图片的Prefect流"""
    if None == config.ARGS['gp']:
        print('缺少参数：gp')
        return False
    elif None == config.ARGS['lang']:
        print('缺少参数：lang')
        return False
    
    print("Processing images flow...")
    config_data = read_config_task()
    d_result = download_images_task(config_data)
    r_result = rename_images_task(config_data, d_result)
    p_result = process_images_task(r_result)
    c_result = compress_images_task(p_result)
    del_middle_dir(c_result)
    return True

@flow
def process_images_flow2():
    """处理图片的Prefect流（无下载任务）"""
    if None == config.ARGS['gp']:
        print('缺少参数：gp')
        return False
    elif None == config.ARGS['lang']:
        print('缺少参数：lang')
        return False
    
    print("Processing images flow...")
    config_data = read_config_task()
    r_result = rename_images_task(config_data, True)
    p_result = process_images_task(r_result)
    c_result = compress_images_task(p_result)
    del_middle_dir(c_result)
    return True

def main():
    print("Executing main function.")
    params = parse_arguments()
    print("args:", params)

    match params['task']:
        case "processImg":
            process_images_flow()
        case "processImg2":
            process_images_flow2()
        case _:
            print("未识别的任务，请检查参数")

def module_main():
    print("Executing module main function.")

if __name__ == "__main__":
    print("main script is run directly.")
    main()
else:
    print("main script is imported as a module.")
    module_main()

