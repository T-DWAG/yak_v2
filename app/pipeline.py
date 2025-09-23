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

# 1. 提取
def extract_zip_to_db(zip_files, target_dir="all_images"):
    t0 = time.perf_counter()
    os.makedirs(target_dir, exist_ok=True)
    conn = init_db()
    cur = conn.cursor()

    PROGRESS["status"] = "running"
    _progress_set("extract", 0, len(zip_files), "Extract all zips")

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
            if data_to_insert:
                cur.executemany(
                    "INSERT INTO images(case_id, orig_name, new_name, img_hash) VALUES (?,?,?,?)",
                    data_to_insert
                )
        _progress_set("extract", idx, len(zip_files), os.path.basename(zp))

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

# 3. 去重
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

    _progress_set("dedup", 0, len(rows), "Pairwise compare")

    # 两两比对，并在组完成后做“跨案件 + 每案件只保留一张”
    for i in range(len(rows)):
        if rows[i][0] in used:
            _progress_set("dedup", i + 1, len(rows), "skip used")
            continue
        _id1, h1, cid1, fname1 = rows[i]
        group = [(_id1, cid1, fname1, h1)]
        for j in range(i + 1, len(rows)):
            _id2, h2, cid2, fname2 = rows[j]
            if rows[j][0] in used:
                continue
            if hamming_dist(h1, h2) <= DUP_THRESHOLD and cid1 != cid2:
                group.append((_id2, cid2, fname2, h2))
        # 仅当真正跨案件时，生成最终分组，并对每案件只保留一张
        case_ids = {cid for _, cid, _, _ in group}
        if len(case_ids) > 1:
            gidx += 1
            uniq = {}
            final_group = []
            for item in group:
                _id, cid, fname, h = item
                if cid not in uniq:
                    uniq[cid] = True
                    final_group.append(item)
            dup_groups[gidx] = final_group
            for item in final_group:
                used.add(item[0])
        _progress_set("dedup", i + 1, len(rows), fname1)

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
