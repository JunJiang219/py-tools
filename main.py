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
import pandas as pd

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
def generate_php_games_array():
    gp = config.ARGS['gp']
    lang = config.ARGS['lang']
    fileName = f"gp-{gp}.xlsx"
    excel_path = os.path.join(config.DEFAULT_ROOT_DIR, "config", fileName)    # 例子：../py-do/config/gp-PS.xlsx
    try:
        # 读取Excel（关键参数配置）
        df = pd.read_excel(
            io=excel_path,
            sheet_name=lang,
            dtype={'disable': str, 'order': float},  # 确保类型准确
            na_values=['', 'NA'],
            keep_default_na=False,
            usecols=['gameId', 'gameType', 'gameName', 'disable', 'order']
        )
        
        # 过滤disable=1的行
        df = df[df['disable'] != '1']
        
        # 处理排序（空值置后）
        df['order'] = pd.to_numeric(df['order'], errors='coerce')
        df_sorted = df.sort_values(
            by='order', 
            ascending=True,
            na_position='last'
        )
        
        # 创建输出目录
        output_file = os.path.join(config.DEFAULT_ROOT_DIR, f"games/{lang}/gp-{gp}.php")    # 例子：../py-do/games/en/gp-PS.php
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 生成PHP格式并写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("'games' => array(\n")
            for i, (game_type, group) in enumerate(df_sorted.groupby('gameType')):
                game_items = [
                    f"'{row['gameId']}' => '{row['gameName'].replace("'", "\\'")}'"
                    for _, row in group.iterrows()
                ]
                line = f"    '{game_type}' => array({', '.join(game_items)})"
                if i < len(df_sorted.groupby('gameType')) - 1:
                    line += ","
                f.write(line + "\n")
            f.write(")\n")
        
        print(f"✅ 文件已生成: {os.path.abspath(output_file)}")
        
    except FileNotFoundError:
        print(f"❌ Excel文件不存在: {excel_path}")
    except Exception as e:
        print(f"⚠️ 处理失败: {str(e)}")
    return True

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
def generate_php_games_array_flow():
    generate_php_games_array()
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
        case 'genGameName':
            generate_php_games_array_flow()
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

