import os
import shutil
import zipfile
import tempfile
import csv
from PIL import Image
import imagehash
from collections import defaultdict
import logging
import glob

# 尝试导入YOLO，如果失败则创建虚拟类
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    logger.warning("YOLO not available, using mock implementation")
    YOLO_AVAILABLE = False
    
    class MockYOLO:
        def __init__(self, model_path):
            self.model_path = model_path
        
        def predict(self, image_path, **kwargs):
            # 返回虚拟分类结果
            return [MockResult()]
    
    class MockResult:
        def __init__(self):
            self.names = {0: 'yak', 1: 'other'}
            self.probs = MockProbs()
    
    class MockProbs:
        def __init__(self):
            self.top1 = 0  # 假设都是牦牛
            self.top1conf = 0.85
    
    YOLO = MockYOLO

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置参数 - Docker友好的路径
INPUT_DIR = os.environ.get('INPUT_DIR', './uploads')  # Docker环境使用相对路径
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', './results')  # 输出目录
HASH_SIZE = 8  # 哈希大小（8=64位哈希）
HASH_THRESHOLD = 5  # 汉明距离阈值（≤5视为相似）
SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')  # 支持的图片格式
YOLO_MODEL_PATH = os.environ.get('YOLO_MODEL_PATH', './data/best.pt')  # YOLO模型路径
CLASS2_CONFIDENCE_THRESHOLD = 0.5  # class2置信度阈值

def load_yolo_model():
    """加载YOLO分类模型"""
    if not YOLO_AVAILABLE:
        logger.info("Using mock YOLO implementation for Docker demo")
        return YOLO("mock_model.pt")
    
    if not os.path.exists(YOLO_MODEL_PATH):
        logger.warning(f"YOLO模型文件不存在: {YOLO_MODEL_PATH}")
        logger.info("Using mock YOLO implementation")
        return YOLO("mock_model.pt")
    
    try:
        model = YOLO(YOLO_MODEL_PATH)
        logger.info(f"YOLO模型加载成功: {YOLO_MODEL_PATH}")
        return model
    except Exception as e:
        logger.error(f"加载YOLO模型失败: {str(e)}")
        logger.info("Using mock YOLO implementation")
        return YOLO("mock_model.pt")

def classify_images_with_yolo(model, image_paths):
    """使用YOLO模型对图片进行分类，筛选出class2图片"""
    if model is None:
        logger.error("YOLO模型未加载，跳过分类步骤")
        return image_paths
    
    logger.info("开始使用YOLO模型进行图片分类...")
    class2_images = []
    total_images = len(image_paths)
    
    for i, image_info in enumerate(image_paths):
        try:
            # 预测单张图片
            results = model(image_info['path'])
            result = results[0]  # 获取第一个结果
            
            if result.probs is not None:
                # 获取class1和class2的概率
                class1_prob = result.probs.data[0].item()
                class2_prob = result.probs.data[1].item()
                
                # 如果class2概率大于阈值，则保留该图片
                if class2_prob >= CLASS2_CONFIDENCE_THRESHOLD:
                    class2_images.append(image_info)
                    logger.info(f"图片 {i+1}/{total_images}: {os.path.basename(image_info['path'])} - class2概率: {class2_prob:.3f} ✓")
                else:
                    logger.info(f"图片 {i+1}/{total_images}: {os.path.basename(image_info['path'])} - class2概率: {class2_prob:.3f} ✗ (低于阈值)")
            else:
                logger.warning(f"图片 {i+1}/{total_images}: {os.path.basename(image_info['path'])} - 无法获取预测结果")
                
        except Exception as e:
            logger.error(f"预测图片时出错 {image_info['path']}: {str(e)}")
            continue
    
    logger.info(f"YOLO分类完成！从 {total_images} 张图片中筛选出 {len(class2_images)} 张class2图片")
    return class2_images

def extract_zip_files(zip_dir):
    """从指定目录提取所有zip文件中的图片"""
    image_paths = []
    temp_dirs = []
    
    # 遍历目录中的所有zip文件
    for root, _, files in os.walk(zip_dir):
        for file in files:
            if file.lower().endswith('.zip'):
                zip_path = os.path.join(root, file)
                logger.info(f"正在处理zip文件: {zip_path}")
                
                try:
                    # 创建临时目录
                    temp_dir = tempfile.mkdtemp(prefix=f"zip_extract_{os.path.splitext(file)[0]}_")
                    temp_dirs.append(temp_dir)
                    
                    # 解压zip文件，处理中文编码
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        # 获取zip文件中的文件列表
                        for zip_info in zip_ref.infolist():
                            try:
                                # 尝试不同的编码方式处理文件名
                                filename = None
                                for encoding in ['utf-8', 'gbk', 'gb2312', 'cp437']:
                                    try:
                                        filename = zip_info.filename.encode('cp437').decode(encoding)
                                        break
                                    except (UnicodeDecodeError, UnicodeEncodeError):
                                        continue
                                
                                if filename is None:
                                    # 如果所有编码都失败，使用原始文件名
                                    filename = zip_info.filename
                                
                                # 解压单个文件
                                zip_ref.extract(zip_info, temp_dir)
                                
                                # 如果文件名包含中文且需要重命名
                                if filename != zip_info.filename:
                                    old_path = os.path.join(temp_dir, zip_info.filename)
                                    new_path = os.path.join(temp_dir, filename)
                                    if os.path.exists(old_path):
                                        # 确保目标目录存在
                                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                                        os.rename(old_path, new_path)
                                
                            except Exception as e:
                                logger.warning(f"处理zip文件中的文件 {zip_info.filename} 时出错: {str(e)}")
                                continue
                    
                    # 收集解压后的图片文件
                    for extract_root, _, extract_files in os.walk(temp_dir):
                        for extract_file in extract_files:
                            if extract_file.lower().endswith(SUPPORTED_FORMATS):
                                full_path = os.path.join(extract_root, extract_file)
                                # 记录原始zip文件的完整路径
                                original_zip_path = os.path.join(root, file)
                                # 图片在zip文件中的相对路径（处理中文编码）
                                relative_path = os.path.relpath(full_path, temp_dir)
                                # 尝试修复相对路径中的中文乱码
                                try:
                                    path_parts = relative_path.split('\\')
                                    fixed_parts = []
                                    for part in path_parts:
                                        if '╨' in part or '╧' in part or '╥' in part:
                                            # 修复GBK编码问题
                                            fixed_part = part.encode('latin1').decode('gbk', errors='ignore')
                                        else:
                                            fixed_part = part
                                        fixed_parts.append(fixed_part)
                                    relative_path = '\\'.join(fixed_parts)
                                except:
                                    pass  # 如果修复失败，保持原路径
                                image_paths.append({
                                    'path': full_path,
                                    'source_zip': file,
                                    'original_zip_path': original_zip_path,
                                    'relative_path': relative_path
                                })
                                
                except Exception as e:
                    logger.error(f"处理zip文件 {zip_path} 时出错: {str(e)}")
                    continue
    
    logger.info(f"共提取了 {len(image_paths)} 张图片")
    return image_paths, temp_dirs

def calculate_image_hash(image_info):
    """计算单张图片的哈希值"""
    try:
        with Image.open(image_info['path']) as img:
            # 转换为RGB模式（避免RGBA模式问题）
            img = img.convert('RGB')
            # 计算感知哈希
            h = imagehash.phash(img, hash_size=HASH_SIZE)
            return h
    except Exception as e:
        logger.error(f"计算图片哈希值时出错 {image_info['path']}: {str(e)}")
        return None

def extract_business_id(path_or_filename):
    """从文件路径或ZIP文件名中提取案件号 - 只取__前面的部分作为真正的案件号"""
    try:
        # 如果是完整路径，提取文件名
        if '\\' in path_or_filename or '/' in path_or_filename:
            filename = os.path.basename(path_or_filename)
        else:
            filename = path_or_filename
        
        # 去除文件扩展名
        filename = os.path.splitext(filename)[0]
        
        # 核心逻辑：从案件号格式中提取真正的案件号
        # DQIHG0180125052193__20250819151615 -> DQIHG0180125052193
        if '__' in filename:
            case_number = filename.split('__')[0]
            logger.debug(f"提取案件号: {filename} -> {case_number}")
            return case_number
        
        # 如果没有__分隔符，检查是否包含DQIH开头的案件号
        import re
        match = re.search(r'DQIH[A-Z0-9]+', filename)
        if match:
            case_number = match.group(0)
            logger.debug(f"正则提取案件号: {filename} -> {case_number}")
            return case_number
        
        # 对于其他格式，记录但不处理（因为无法确定案件号）
        logger.warning(f"无法提取案件号，跳过文件: {filename}")
        return None
        
    except Exception as e:
        logger.error(f"提取案件号时出错 {path_or_filename}: {str(e)}")
        return None

def find_cross_case_similar_photos():
    """找出跨业务号的相似图片"""
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 加载YOLO模型
    yolo_model = load_yolo_model()
    
    # 提取zip文件中的图片
    image_infos, temp_dirs = extract_zip_files(INPUT_DIR)
    
    if not image_infos:
        logger.warning("没有找到任何图片文件")
        return
    
    # 使用YOLO模型筛选class2图片
    class2_images = classify_images_with_yolo(yolo_model, image_infos)
    
    if not class2_images:
        logger.warning("没有找到任何class2图片")
        return
    
    # 按案件号分组并计算哈希值
    logger.info("正在按案件号分组并计算哈希值...")
    case_groups = defaultdict(list)
    
    for image_info in class2_images:
        # 从ZIP文件名中提取案件号（这是关键！）
        zip_filename = image_info['source_zip']
        case_id = extract_business_id(zip_filename)
        
        if case_id:  # 只处理能识别案件号的图片
            hash_value = calculate_image_hash(image_info)
            if hash_value is not None:
                case_groups[case_id].append({
                    'hash': hash_value,
                    'info': image_info,
                    'case_id': case_id
                })
            else:
                logger.warning(f"无法计算哈希值: {image_info['path']}")
        else:
            logger.warning(f"无法从ZIP文件名提取案件号: {zip_filename}")
    
    logger.info(f"成功分组 {len(case_groups)} 个案件号")
    for case_id, images in case_groups.items():
        logger.info(f"案件号 {case_id}: {len(images)} 张图片")
    
    # 找出跨案件号的相似图片
    logger.info("正在查找跨案件号相似图片...")
    cross_case_duplicates = []
    case_ids = list(case_groups.keys())
    
    for i, case1 in enumerate(case_ids):
        for j, case2 in enumerate(case_ids):
            if i < j:  # 避免重复比较 (A vs B 和 B vs A)
                logger.info(f"比较案件号: {case1} vs {case2}")
                
                # 在case1和case2之间找相似图片
                for img1_data in case_groups[case1]:
                    for img2_data in case_groups[case2]:
                        distance = img1_data['hash'] - img2_data['hash']
                        if distance <= HASH_THRESHOLD:
                            cross_case_duplicates.append([img1_data, img2_data])
                            logger.info(f"发现跨案件号相似图片: {case1} <-> {case2}, 距离: {distance}")
    
    logger.info(f"共发现 {len(cross_case_duplicates)} 对跨案件号相似图片")
    
    if not cross_case_duplicates:
        logger.info("没有发现跨案件号相似图片")
        return
    
    # 保存结果
    logger.info("正在保存跨案件号相似图片...")
    
    # 准备CSV数据
    csv_data = []
    csv_headers = ['组别', '序号', '案件号', '原始文件名', '新文件名', '原始ZIP路径', '来源ZIP文件', 'ZIP内相对路径', '目标路径', 'YOLO分类结果', '汉明距离']
    
    for group_id, (img1_data, img2_data) in enumerate(cross_case_duplicates, 1):
        # 创建组目录
        group_dir = os.path.join(OUTPUT_DIR, f"cross_case_group_{group_id:03d}")
        os.makedirs(group_dir, exist_ok=True)
        
        # 处理两张相似图片
        for seq_id, img_data in enumerate([img1_data, img2_data], 1):
            try:
                image_info = img_data['info']
                case_id = img_data['case_id']
                
                # 获取原始文件名
                filename = os.path.basename(image_info['path'])
                name, ext = os.path.splitext(filename)
                
                # 获取zip文件名（不含扩展名）
                zip_name = os.path.splitext(image_info['source_zip'])[0]
                
                # 构建新文件名
                new_name = f"{group_id:03d}_{seq_id:03d}_{case_id}_{zip_name}_{name}{ext}"
                
                # 清理文件名中的非法字符
                new_name = "".join(c for c in new_name if c.isalnum() or c in ('_', '-', '.', '(', ')', '['))
                
                # 复制文件
                dest_path = os.path.join(group_dir, new_name)
                shutil.copy2(image_info['path'], dest_path)
                
                # 计算汉明距离
                distance = img1_data['hash'] - img2_data['hash']
                
                # 添加到CSV数据
                csv_data.append([
                    f"cross_case_group_{group_id:03d}",  # 组别
                    seq_id,  # 序号
                    case_id,  # 案件号
                    filename,  # 原始文件名
                    new_name,  # 新文件名
                    image_info['original_zip_path'],  # 原始ZIP路径
                    image_info['source_zip'],  # 来源ZIP文件
                    image_info['relative_path'],  # ZIP内相对路径
                    dest_path,  # 目标路径
                    "class2",  # YOLO分类结果
                    distance  # 汉明距离
                ])
                
            except Exception as e:
                logger.error(f"复制文件时出错 {img_data['info']['path']}: {str(e)}")
    
    # 生成CSV文件
    csv_path = os.path.join(OUTPUT_DIR, "跨案件号相似图片记录.csv")
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(csv_headers)
            writer.writerows(csv_data)
        logger.info(f"CSV记录文件已生成: {csv_path}")
    except Exception as e:
        logger.error(f"生成CSV文件时出错: {str(e)}")
    
    # 清理临时目录
    logger.info("正在清理临时文件...")
    for temp_dir in temp_dirs:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"清理临时目录时出错 {temp_dir}: {str(e)}")
    
    logger.info(f"完成！共找到 {len(cross_case_duplicates)} 对跨案件号相似图片")
    logger.info(f"结果保存在: {OUTPUT_DIR}")

if __name__ == "__main__":
    find_cross_case_similar_photos()