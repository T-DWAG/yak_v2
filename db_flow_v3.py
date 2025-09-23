# db_flow_v2c.py
import os, sqlite3, time, shutil, csv
from zipfile import ZipFile
from ultralytics import YOLO
from PIL import Image
from collections import defaultdict
import tkinter as tk
from tkinter import filedialog
from tqdm import tqdm

DB_FILE = "cases.db"
TARGET_CLASS = 1      # YOLO 目标类
DUP_THRESHOLD = 5     # 汉明距离阈值，<=5 认为重复

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

# ✅ dHash 实现（更快更稳健）
def dhash(path, size=8):
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

# 1. 提取（批量写入）
def extract_zip_to_db(zip_files, target_dir="all_images"):
    t0 = time.perf_counter()
    os.makedirs(target_dir, exist_ok=True)
    conn = init_db()
    cur = conn.cursor()

    for zp in tqdm(zip_files, desc="Extract all zips", unit="zip"):
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
            cur.executemany(
                "INSERT INTO images(case_id, orig_name, new_name, img_hash) VALUES (?,?,?,?)",
                data_to_insert
            )

    conn.commit()
    conn.close()
    print(f"[Extract] {len(zip_files)} zip(s) done in {time.perf_counter()-t0:.2f}s")

# 2. YOLO 分类
def run_yolo_and_update(weights="model/best.pt", img_dir="all_images"):
    t0 = time.perf_counter()
    conn = init_db()
    cur = conn.cursor()
    model = YOLO(weights)

    cur.execute("SELECT id, new_name FROM images WHERE is_yak=0")
    rows = cur.fetchall()

    for _id, fname in tqdm(rows, desc="YOLO classify", unit="img"):
        path = os.path.join(img_dir, fname)
        results = model.predict(path, verbose=False)
        cls = int(results[0].probs.top1)
        if cls == TARGET_CLASS:
            cur.execute("UPDATE images SET is_yak=1 WHERE id=?", (_id,))

    conn.commit()
    conn.close()
    print(f"[YOLO] processed {len(rows)} images in {time.perf_counter()-t0:.2f}s")

# 3. 去重（跨案件 + 每案件只保留一张）
def find_cross_case_dups(out_dir="dup_groups", csv_file="dup_groups.csv"):
    t0 = time.perf_counter()
    os.makedirs(out_dir, exist_ok=True)
    conn = init_db()
    cur = conn.cursor()

    cur.execute("SELECT id, img_hash, case_id, new_name FROM images WHERE is_yak=1")
    rows = cur.fetchall()

    dup_groups = {}
    used = set()
    gidx = 0

    # 两两比对
    for i in range(len(rows)):
        if rows[i][0] in used:
            continue
        _id1, h1, cid1, fname1 = rows[i]
        group = [(_id1, cid1, fname1, h1)]
        for j in range(i + 1, len(rows)):
            _id2, h2, cid2, fname2 = rows[j]
            if rows[j][0] in used:
                continue
            if hamming_dist(h1, h2) <= DUP_THRESHOLD and cid1 != cid2:
                group.append((_id2, cid2, fname2, h2))
        # ✅ 检查是否有跨案件
        case_ids = {cid for _, cid, _, _ in group}
        if len(case_ids) > 1:
            gidx += 1
            uniq = {}
            final_group = []
            for item in group:
                _id, cid, fname, h = item
                if cid not in uniq:  # 每个案件只保留一张
                    uniq[cid] = True
                    final_group.append(item)
            dup_groups[gidx] = final_group
            for item in final_group:
                used.add(item[0])

    # 写出CSV
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
                    try:
                        shutil.copy(src, dst)
                    except Exception as e:
                        print(f"拷贝失败: {src} -> {dst}, {e}")

    print(f"[Dedup] {len(dup_groups)} groups in {time.perf_counter()-t0:.2f}s, CSV saved: {csv_file}")
    conn.close()

# ========== 主入口 ==========
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    zip_files = filedialog.askopenfilenames(
        title="请选择要处理的 ZIP 文件",
        filetypes=[("ZIP files", "*.zip")]
    )
    
    if not zip_files:
        print("未选择文件，退出。")
    else:
        extract_zip_to_db(zip_files)
        run_yolo_and_update()
        find_cross_case_dups()
