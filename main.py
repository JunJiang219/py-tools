import argparse
from base import excelHelper
from base import downloadHelper

def parse_arguments():
    """解析命令行参数并返回字典"""
    parser = argparse.ArgumentParser(description="命令行参数解析")
    
    # 添加必须参数（根据需求调整）
    parser.add_argument("--task", type=str, required=False, help="任务名称")
    
    # 解析参数并转为字典
    args = parser.parse_args()
    return vars(args)  # 将Namespace对象转为字典

def main():
    print("Executing main function.")
    params = parse_arguments()
    print("args:", params)
    match params['task']:
        case "test":
            print("执行测试任务")
        case "train":
            print("执行训练任务")
        case _:
            print("未识别的任务，请检查参数")
            data = excelHelper.read_data("test/config/test1.xlsx")
            img_urls = [item['img_en'] for item in data if 'img_en' in item]
            downloadHelper.download_batch(img_urls, "test/images", max_workers=10)

def module_main():
    print("Executing module main function.")

if __name__ == "__main__":
    print("main script is run directly.")
    main()
else:
    print("main script is imported as a module.")
    module_main()

