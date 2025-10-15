# app/pipeline.py
import os, sqlite3, time, shutil, csv
from zipfile import ZipFile
from ultralytics import YOLO
from PIL import Image
from collections import defaultdict
from tqdm import tqdm

DB_FILE = "cases.db"
TARGET_CLASS = 1
DUP_THRESHOLD = 5

# ========== Progress State ==========
PROGRESS = {
    "status": "idle",      # idle | running | done | error
    "stage": "",           # extract | yolo | dedup | none
    "current": 0,
    "total": 0,
    "detail": "",
}


def _progress_set(stage: str, current: int, total: int, detail: str = ""):
    PROGRESS["stage"] = stage
    PROGRESS["current"] = int(current)
    PROGRESS["total"] = int(total)
    PROGRESS["detail"] = detail


def progress_snapshot():
    return dict(PROGRESS)

# ========== DB 初始化 ==========
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT,
        orig_name TEXT,
        new_name TEXT,
        is_yak INTEGER DEFAULT 0,
        img_hash TEXT
    )
    """)
    conn.commit()
    return conn

def support_gbk(zf: ZipFile):
    for n, i in list(zf.NameToInfo.items()):
        try:
            new = n.encode('cp437').decode('gbk')
            if new != n:
                i.filename = new
                del zf.NameToInfo[n]
                zf.NameToInfo[new] = i
        except:
            pass
    return zf

# ✅ dHash
def dhash(path, size=8):
    from PIL import Image
    img = Image.open(path).convert('L').resize((size + 1, size))
    px = list(img.getdata())
    diffs = []
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            diffs.append(left > right)
    return ''.join(['1' if d else '0' for d in diffs])

def hamming_dist(s1, s2):
    return sum(ch1 != ch2 for ch1, ch2 in zip(s1, s2))

# 许可量检查函数
def check_license_permission(estimated_images: int = 0) -> tuple[bool, str]:
    """检查是否允许处理图片"""
    try:
        from .utils.license_manager import license_manager
        return license_manager.check_processing_permission(estimated_images)
    except Exception as e:
        print(f"许可量检查失败: {str(e)}")
        return False, f"许可量检查失败: {str(e)}"


def count_images_in_zips(zip_files) -> int:
    """统计ZIP文件中的图片数量（不提取）"""
    total_images = 0
    print(f"[License Check] 统计图片数量...")

    for zp in zip_files:
        try:
            with support_gbk(ZipFile(zp, 'r')) as zf:
                image_names = [n for n in zf.namelist() if n.lower().endswith((".jpg",".jpeg",".png",".bmp"))]
                zip_images = len(image_names)
                total_images += zip_images
                print(f"[License Check] {os.path.basename(zp)}: {zip_images} 张图片")
        except Exception as e:
            print(f"[License Check] 无法读取 {os.path.basename(zp)}: {str(e)}")
            # 如果无法读取，跳过这个文件
            continue

    print(f"[License Check] 总计: {total_images} 张图片")
    return total_images


# 1. 提取
def extract_zip_to_db(zip_files, target_dir="all_images"):
    t0 = time.perf_counter()
    os.makedirs(target_dir, exist_ok=True)

    # 第一步：统计实际图片数量并检查许可量
    total_images = count_images_in_zips(zip_files)

    # 检查许可量
    can_process, message = check_license_permission(total_images)
    if not can_process:
        raise Exception(f"许可量不足: {message}")

    # 第二步：开始提取
    conn = init_db()
    cur = conn.cursor()

    PROGRESS["status"] = "running"
    _progress_set("extract", 0, len(zip_files), "Extract all zips")

    processed_images = 0

    for idx, zp in enumerate(tqdm(zip_files, desc="Extract all zips", unit="zip"), start=1):
        case_id = os.path.splitext(os.path.basename(zp))[0].split("_")[0]
        with support_gbk(ZipFile(zp, 'r')) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith((".jpg",".jpeg",".png",".bmp"))]
            data_to_insert = []
            for name in names:
                new_name = f"{case_id}_{os.path.basename(name)}"
                dst = os.path.join(target_dir, new_name)
                with zf.open(name) as src, open(dst, "wb") as out:
                    out.write(src.read())
                h = dhash(dst)
                data_to_insert.append((case_id, os.path.basename(name), new_name, h))
                processed_images += 1

            if data_to_insert:
                cur.executemany(
                    "INSERT INTO images(case_id, orig_name, new_name, img_hash) VALUES (?,?,?,?)",
                    data_to_insert
                )
        _progress_set("extract", idx, len(zip_files), os.path.basename(zp))

        # 每处理一个ZIP文件后检查许可量
        can_continue, message = check_license_permission(0)  # 检查当前状态
        if not can_continue:
            conn.commit()
            conn.close()
            raise Exception(f"处理过程中许可量不足: {message}")

    conn.commit()
    conn.close()
    print(f"[Extract] {len(zip_files)} zip(s), {processed_images} images done in {time.perf_counter()-t0:.2f}s")

# 2. YOLO 分类
def run_yolo_and_update(weights="model/best.pt", img_dir="all_images"):
    t0 = time.perf_counter()
    conn = init_db()
    cur = conn.cursor()
    model = YOLO(weights)

    cur.execute("SELECT id, new_name FROM images WHERE is_yak=0")
    rows = cur.fetchall()

    _progress_set("yolo", 0, len(rows), "YOLO classify")

    for i, (_id, fname) in enumerate(tqdm(rows, desc="YOLO classify", unit="img"), start=1):
        path = os.path.join(img_dir, fname)
        results = model.predict(path, verbose=False)
        cls = int(results[0].probs.top1)
        if cls == TARGET_CLASS:
            cur.execute("UPDATE images SET is_yak=1 WHERE id=?", (_id,))
        _progress_set("yolo", i, len(rows), fname)

    conn.commit()
    conn.close()
    print(f"[YOLO] processed {len(rows)} images in {time.perf_counter()-t0:.2f}s")

# 3. 去重 - 使用连通分量算法
def find_cross_case_dups(out_dir="dup_groups", csv_file="dup_groups.csv"):
    t0 = time.perf_counter()
    os.makedirs(out_dir, exist_ok=True)
    conn = init_db()
    cur = conn.cursor()

    cur.execute("SELECT id, img_hash, case_id, new_name FROM images WHERE is_yak=1")
    rows = cur.fetchall()

    # 构建相似图：邻接表表示
    n = len(rows)
    adj = [[] for _ in range(n)]

    _progress_set("dedup", 0, n * (n-1) // 2, "Building similarity graph")

    # 构建相似关系
    count = 0
    for i in range(n):
        _id1, h1, cid1, fname1 = rows[i]
        for j in range(i + 1, n):
            _id2, h2, cid2, fname2 = rows[j]
            count += 1
            if count % 100 == 0:
                _progress_set("dedup", count, n * (n-1) // 2, f"Comparing {i+1}/{n}")

            if hamming_dist(h1, h2) <= DUP_THRESHOLD and cid1 != cid2:
                adj[i].append(j)
                adj[j].append(i)

    # 使用DFS找连通分量
    visited = [False] * n
    components = []

    _progress_set("dedup", 0, n, "Finding connected components")

    for i in range(n):
        if not visited[i]:
            # DFS遍历连通分量
            component = []
            stack = [i]
            visited[i] = True

            while stack:
                node = stack.pop()
                component.append(node)
                for neighbor in adj[node]:
                    if not visited[neighbor]:
                        visited[neighbor] = True
                        stack.append(neighbor)

            # 只保留包含多个案件的连通分量
            case_ids = {rows[idx][2] for idx in component}
            if len(case_ids) > 1:
                components.append(component)
            _progress_set("dedup", i + 1, n, f"Component {len(components)} found")

    # 处理每个连通分量：每个案件只保留一张照片
    dup_groups = {}
    gidx = 0

    _progress_set("dedup", 0, len(components), "Processing components")

    for idx, component in enumerate(components):
        # 按案件号分组
        case_map = {}
        for node_idx in component:
            _id, h, cid, fname = rows[node_idx]
            if cid not in case_map:
                case_map[cid] = []
            case_map[cid].append((_id, cid, fname, h))

        # 每个案件取第一张照片
        final_group = []
        for cid, items in case_map.items():
            final_group.append(items[0])  # 取每个案件的第一张

        if len(final_group) > 1:  # 确保真正跨案件
            gidx += 1
            dup_groups[gidx] = final_group
        _progress_set("dedup", idx + 1, len(components), f"Group {gidx} processed")

    # 保存结果
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["group_id", "db_id", "case_id", "file_name", "img_hash"])
        for gidx, items in dup_groups.items():
            gdir = os.path.join(out_dir, f"group_{gidx}")
            os.makedirs(gdir, exist_ok=True)
            for _id, cid, fname, h in items:
                src = os.path.join("all_images", fname)
                dst = os.path.join(gdir, f"{_id}_{fname}")
                writer.writerow([gidx, _id, cid, fname, h])
                try:
                    os.link(src, dst)
                except FileExistsError:
                    continue
                except Exception:
                    shutil.copy(src, dst)

    print(f"[Dedup] {len(dup_groups)} groups in {time.perf_counter()-t0:.2f}s, CSV saved: {csv_file}")
    conn.close()

# 4. Orchestrator for web background
def run_all(zip_path: str):
    try:
        PROGRESS["status"] = "running"
        _progress_set("extract", 0, 1, os.path.basename(zip_path))
        extract_zip_to_db([zip_path])
        _progress_set("yolo", 0, 1, "classify")
        run_yolo_and_update()
        _progress_set("dedup", 0, 1, "group")
        find_cross_case_dups()
        PROGRESS["status"] = "done"
        _progress_set("none", 0, 0, "")
    except Exception as e:
        PROGRESS["status"] = "error"
        PROGRESS["detail"] = str(e)
        raise
