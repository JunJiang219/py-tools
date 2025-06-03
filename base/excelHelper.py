import pandas as pd

def read_data(file_path: str, sheet_name: int | str = 0) -> list:
    """
    读取Excel文件并返回数据列表
    :param file_path: Excel文件路径
    :return: 数据列表
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    return df.to_dict('records')

# 使用示例
if __name__ == "__main__":
    file_path = "test/config/test1.xlsx"  # 替换为实际文件路径
    data = read_data(file_path, sheet_name=0)  # 读取第一个工作表
    print(data)  # 打印读取的数据