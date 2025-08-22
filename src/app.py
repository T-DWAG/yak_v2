"""
Linus风格优化的牦牛图片分析系统 - 带授权控制
"Talk is cheap. Show me the code." - 简洁、实用、零破坏
"""

import os
import sys
import json
import tempfile
import shutil
import threading
import uuid
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import zipfile
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.append('..')

# 修复模型路径
import group3
group3.YOLO_MODEL_PATH = r"..\models\best.pt"

from group3 import (
    load_yolo_model, 
    classify_images_with_yolo,
    extract_zip_files,
    calculate_image_hash,
    extract_business_id
)

# 导入授权管理器
from license_manager_simple import LicenseManager

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FOLDER'] = 'results'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

# Linus风格：简洁的全局状态管理
processing_status = {
    'is_processing': False,
    'current_step': '',
    'progress': 0,
    'total_images': 0,
    'class2_images': 0,
    'groups_found': 0,
    'error': None,
    'session_id': '',
    'start_time': '',
    'authorization_status': 'checking'
}

# 全局实例
yolo_model = None
license_manager = LicenseManager()

def init_system():
    """系统初始化 - 模型加载 + 授权检查"""
    global yolo_model
    
    # 检查授权状态
    auth_ok, auth_msg = license_manager.check_authorization()
    processing_status['authorization_status'] = 'authorized' if auth_ok else 'unauthorized'
    
    if not auth_ok:
        processing_status['error'] = f"授权检查失败: {auth_msg}"
        logger.error(f"授权检查失败: {auth_msg}")
        return
    
    # 加载YOLO模型
    yolo_model = load_yolo_model()
    if yolo_model is None:
        processing_status['error'] = "YOLO模型加载失败"
        logger.error("YOLO模型加载失败")
    else:
        logger.info("系统初始化完成：授权正常，模型已加载")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if processing_status['is_processing']:
        return jsonify({'error': '正在处理中，请稍后再试'}), 400
    
    if 'files' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    # 清理旧文件
    for f in os.listdir(app.config['UPLOAD_FOLDER']):
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f))
    
    uploaded_files = []
    for file in files:
        if file and file.filename.endswith('.zip'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            uploaded_files.append(filename)
    
    if not uploaded_files:
        return jsonify({'error': '请上传ZIP文件'}), 400
    
    # 启动后台处理
    thread = threading.Thread(target=process_images)
    thread.start()
    
    return jsonify({
        'message': '文件上传成功，开始处理',
        'files': uploaded_files
    })

def process_images():
    global processing_status
    
    # 生成会话ID和记录开始时间
    session_id = str(uuid.uuid4())
    start_time = datetime.now().isoformat()
    
    processing_status = {
        'is_processing': True,
        'current_step': '提取图片',
        'progress': 10,
        'total_images': 0,
        'class2_images': 0,
        'groups_found': 0,
        'error': None,
        'session_id': session_id,
        'start_time': start_time
    }
    
    try:
        # 清理结果目录
        results_dir = app.config['RESULTS_FOLDER']
        if os.path.exists(results_dir):
            shutil.rmtree(results_dir)
        os.makedirs(results_dir)
        
        # 提取ZIP文件（确保保留source_zip信息）
        processing_status['current_step'] = '提取ZIP文件中的图片'
        image_infos, temp_dirs = extract_zip_files(app.config['UPLOAD_FOLDER'])
        
        # 确保每个image_info包含source_zip信息
        for info in image_infos:
            if 'source_zip' not in info:
                # 从路径推断source_zip
                info['source_zip'] = 'unknown.zip'
        
        processing_status['total_images'] = len(image_infos)
        processing_status['progress'] = 30
        
        if not image_infos:
            raise Exception("未找到图片文件")
        
        # YOLO分类
        processing_status['current_step'] = 'YOLO模型分类中'
        class2_images = classify_images_with_yolo(yolo_model, image_infos)
        processing_status['class2_images'] = len(class2_images)
        processing_status['progress'] = 60
        
        if not class2_images:
            raise Exception("未找到class2图片")
        
        # 计算哈希值和分组
        processing_status['current_step'] = '计算相似度并分组'
        groups = process_similarity(class2_images)
        processing_status['groups_found'] = len(groups)
        processing_status['progress'] = 90
        
        # 保存结果
        save_results(groups)
        
        # 清理临时文件
        for temp_dir in temp_dirs:
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        
        processing_status['progress'] = 100
        processing_status['current_step'] = '处理完成'
        
        # 记录使用量 - Linus风格：直接有效
        end_time = datetime.now().isoformat()
        images_processed = processing_status['total_images']
        
        if images_processed > 0:
            license_manager.record_usage(
                images_processed=images_processed,
                session_id=session_id,
                start_time=start_time,
                end_time=end_time
            )
            logger.info(f"已记录使用量: {images_processed} 张图片, 会话ID: {session_id}")
        
    except Exception as e:
        processing_status['error'] = str(e)
        # 即使出错也记录使用量（如果有处理图片的话）
        if processing_status.get('total_images', 0) > 0:
            end_time = datetime.now().isoformat()
            license_manager.record_usage(
                images_processed=processing_status['total_images'],
                session_id=session_id,
                start_time=start_time,
                end_time=end_time
            )
    finally:
        processing_status['is_processing'] = False

def process_similarity(image_infos):
    """使用group3的跨案件号相似度检测逻辑"""
    from collections import defaultdict
    import imagehash
    
    HASH_SIZE = 8
    HASH_THRESHOLD = 5
    
    # 按案件号分组并计算哈希值
    case_groups = defaultdict(list)
    
    for image_info in image_infos:
        # 从ZIP文件名中提取案件号（这是关键！）
        zip_filename = image_info.get('source_zip', '')
        case_id = extract_business_id(zip_filename)
        
        if case_id:  # 只处理能识别案件号的图片
            hash_value = calculate_image_hash(image_info)
            if hash_value is not None:
                case_groups[case_id].append({
                    'hash': hash_value,
                    'info': image_info,
                    'case_id': case_id
                })
    
    # 找出跨案件号的相似图片
    cross_case_duplicates = []
    case_ids = list(case_groups.keys())
    
    for i, case1 in enumerate(case_ids):
        for j, case2 in enumerate(case_ids):
            if i < j:  # 避免重复比较 (A vs B 和 B vs A)
                # 在case1和case2之间找相似图片
                for img1_data in case_groups[case1]:
                    for img2_data in case_groups[case2]:
                        distance = img1_data['hash'] - img2_data['hash']
                        if distance <= HASH_THRESHOLD:
                            cross_case_duplicates.append([img1_data, img2_data])
    
    # 将跨案件号重复转换为组格式
    groups = defaultdict(list)
    for group_id, (img1_data, img2_data) in enumerate(cross_case_duplicates, 1):
        groups[group_id].extend([img1_data['info'], img2_data['info']])
    
    return dict(groups)

def save_results(groups):
    import csv
    import re
    
    results_dir = app.config['RESULTS_FOLDER']
    csv_data = []
    csv_headers = ['组别', '序号', '案件号', '原始文件名', '新文件名', '来源ZIP', 'ZIP内路径', '相似度组大小']
    
    for group_id, images in groups.items():
        group_dir = os.path.join(results_dir, f'group_{group_id}')
        os.makedirs(group_dir, exist_ok=True)
        
        for i, image_info in enumerate(images):
            # 提取案件号（使用group3的方法从ZIP文件名中提取）
            source_zip = image_info.get('source_zip', '')
            case_number = extract_business_id(source_zip)
            
            # 生成新文件名：案件号_组号_序号_原文件名
            original_filename = os.path.basename(image_info['path'])
            name, ext = os.path.splitext(original_filename)
            
            if case_number:
                new_filename = f'{case_number}_g{group_id}_{i+1}_{name}{ext}'
            else:
                new_filename = f'unknown_g{group_id}_{i+1}_{name}{ext}'
            
            # 清理文件名中的非法字符
            new_filename = re.sub(r'[<>:"/\\|?*]', '_', new_filename)
            
            dest_path = os.path.join(group_dir, new_filename)
            shutil.copy2(image_info['path'], dest_path)
            
            # 添加到CSV数据
            csv_data.append([
                f'group_{group_id}',
                i + 1,
                case_number or 'unknown',
                original_filename,
                new_filename,
                source_zip,
                image_info.get('relative_path', ''),
                len(images)
            ])
    
    # 生成CSV文件
    csv_path = os.path.join(results_dir, '跨案件号相似图片记录.csv')
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(csv_headers)
            writer.writerows(csv_data)
        print(f'CSV记录已生成: {csv_path}')
    except Exception as e:
        print(f'生成CSV文件时出错: {e}')


@app.route('/status')
def get_status():
    return jsonify(processing_status)

@app.route('/results')
def get_results():
    results_dir = app.config['RESULTS_FOLDER']
    if not os.path.exists(results_dir):
        return jsonify({'groups': []})
    
    groups = []
    for group_name in sorted(os.listdir(results_dir)):
        group_path = os.path.join(results_dir, group_name)
        if os.path.isdir(group_path):
            images = []
            for img_name in sorted(os.listdir(group_path)):
                if img_name.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    # 返回相对路径用于访问
                    images.append(f'{group_name}/{img_name}')
            groups.append({
                'name': group_name,
                'count': len(images),
                'images': images[:5]  # 只返回前5张预览
            })
    
    return jsonify({'groups': groups})

@app.route('/image/<path:filename>')
def serve_image(filename):
    """提供图片文件访问"""
    return send_file(os.path.join(app.config['RESULTS_FOLDER'], filename))

@app.route('/download_results')
def download_results():
    results_dir = app.config['RESULTS_FOLDER']
    if not os.path.exists(results_dir) or not os.listdir(results_dir):
        return jsonify({'error': '没有结果可下载'}), 404
    
    # 创建ZIP文件
    zip_path = os.path.join(tempfile.gettempdir(), 'results.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(results_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, results_dir)
                zipf.write(file_path, arcname)
    
    return send_file(zip_path, as_attachment=True, download_name='相似图片分组结果.zip')

@app.route('/download_csv')
def download_csv():
    """单独下载CSV文件"""
    csv_path = os.path.join(app.config['RESULTS_FOLDER'], '跨案件号相似图片记录.csv')
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True, download_name='跨案件号相似图片记录.csv', mimetype='text/csv')
    else:
        return jsonify({'error': 'CSV文件不存在'}), 404

@app.route('/license_stats')
def get_license_stats():
    """获取授权和使用量统计 - Linus风格：直接返回数据"""
    try:
        stats = license_manager.get_usage_stats()
        auth_ok, auth_msg = license_manager.check_authorization()
        
        stats.update({
            'authorization_status': 'authorized' if auth_ok else 'unauthorized',
            'authorization_message': auth_msg
        })
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"获取授权统计失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/usage_report')
def get_usage_report():
    """生成使用量报告"""
    try:
        report = license_manager.generate_usage_report()
        if report:
            return jsonify({'report': report})
        else:
            return jsonify({'error': '没有使用记录'}), 404
    except Exception as e:
        logger.error(f"生成使用量报告失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/export_usage_report')
def export_usage_report():
    """导出使用量报告文件"""
    try:
        report_file = license_manager.export_usage_report_file()
        if report_file and os.path.exists(report_file):
            return send_file(report_file, as_attachment=True, 
                           download_name=f'usage_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        else:
            return jsonify({'error': '报告生成失败'}), 500
    except Exception as e:
        logger.error(f"导出使用量报告失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/load_license', methods=['POST'])
def load_license():
    """加载新的授权文件"""
    try:
        if 'license_file' not in request.files:
            return jsonify({'error': '没有上传授权文件'}), 400
        
        file = request.files['license_file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        # 读取授权文件内容
        license_content = file.read().decode('utf-8')
        
        # 加载授权
        if license_manager.load_private_license(license_content):
            return jsonify({'message': '授权文件加载成功'})
        else:
            return jsonify({'error': '授权文件格式错误或验证失败'}), 400
            
    except Exception as e:
        logger.error(f"加载授权文件失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate_client_key')
def generate_client_key():
    """生成客户端钥匙（甲方发送给乙方）"""
    try:
        from dual_key_system import DualKeySystem
        
        dual_key = DualKeySystem()
        usage_stats = dual_key.get_client_usage_summary()
        
        if usage_stats.get('total_images_processed', 0) == 0:
            return jsonify({'error': '没有使用记录，请先运行一些图片处理任务'}), 400
        
        client_key = dual_key.create_client_key(usage_stats)
        
        if client_key:
            # 保存到临时文件
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
            temp_file.write(client_key)
            temp_file.close()
            
            # 返回下载链接
            return send_file(temp_file.name, as_attachment=True, 
                           download_name=f'client_usage_key_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
                           mimetype='application/json')
        else:
            return jsonify({'error': '客户端钥匙生成失败'}), 500
            
    except Exception as e:
        logger.error(f"生成客户端钥匙失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/dual_key_info')
def get_dual_key_info():
    """获取双钥匙系统信息"""
    try:
        from dual_key_system import DualKeySystem
        
        dual_key = DualKeySystem()
        usage_stats = dual_key.get_client_usage_summary()
        
        info = {
            'has_usage_data': usage_stats.get('total_images_processed', 0) > 0,
            'total_images_processed': usage_stats.get('total_images_processed', 0),
            'total_sessions': usage_stats.get('total_records', 0),
            'client_ip': dual_key._get_client_ip(),
            'can_generate_key': usage_stats.get('total_images_processed', 0) > 0
        }
        
        return jsonify(info)
        
    except Exception as e:
        logger.error(f"获取双钥匙信息失败: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_system()
    app.run(debug=True, host='0.0.0.0', port=5000)