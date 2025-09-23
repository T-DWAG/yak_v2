from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from typing import List
import shutil, os, io, json, threading, zipfile, pathlib, time
from . import pipeline

app = FastAPI()

# 挂载 static 静态目录
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "index.html")
    return FileResponse(index_path)

@app.get("/v2")
async def root_v2():
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "index2.html")
    return FileResponse(index_path)


# ===== 内部状态与工具函数 =====
_LOCK = threading.Lock()
_PROCESSING_THREAD: threading.Thread | None = None
_LAST_ERROR: str | None = None
_USAGE_FILE = os.path.join("license_data", "usage.json")
_LICENSE_FILE = os.path.join("license_data", "license.json")


def _ensure_dirs():
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("results", exist_ok=True)
    os.makedirs("license_data", exist_ok=True)


def _load_usage():
    _ensure_dirs()
    if os.path.exists(_USAGE_FILE):
        try:
            with open(_USAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_images_processed": 0, "runs": 0, "last_run": None}


def _save_usage(data: dict):
    _ensure_dirs()
    with open(_USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_license():
    _ensure_dirs()
    if os.path.exists(_LICENSE_FILE):
        try:
            with open(_LICENSE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"raw_file": True}
    return None


def _count_db_stats():
    import sqlite3
    stats = {"total_images": 0, "class2_images": 0}
    if not os.path.exists("cases.db"):
        return stats
    try:
        conn = sqlite3.connect("cases.db")
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM images")
        stats["total_images"] = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM images WHERE is_yak=1")
        stats["class2_images"] = cur.fetchone()[0] or 0
        conn.close()
    except Exception:
        pass
    return stats


def _count_groups():
    gdir = pathlib.Path("dup_groups")
    if not gdir.exists():
        return 0
    return sum(1 for p in gdir.iterdir() if p.is_dir() and p.name.startswith("group_"))


def _build_status_response():
    prog = pipeline.progress_snapshot()
    stats = _count_db_stats()
    groups_found = _count_groups()

    current = prog.get("current", 0) or 0
    total = prog.get("total", 0) or 0
    percent = 0
    if total > 0:
        percent = max(0, min(100, int(current * 100 / total)))

    status_flag = prog.get("status", "idle")
    is_processing = status_flag == "running"

    return {
        "is_processing": is_processing,
        "error": _LAST_ERROR,
        "current_step": prog.get("stage") or "",
        "progress": percent,
        "total_images": stats.get("total_images", 0),
        "class2_images": stats.get("class2_images", 0),
        "groups_found": groups_found,
    }


def _process_in_background(zip_paths: list[str]):
    global _LAST_ERROR
    try:
        _LAST_ERROR = None
        pipeline.PROGRESS["status"] = "running"
        pipeline._progress_set("extract", 0, len(zip_paths), "Extract all zips")
        pipeline.extract_zip_to_db(zip_paths)

        pipeline._progress_set("yolo", 0, 1, "classify")
        pipeline.run_yolo_and_update()

        pipeline._progress_set("dedup", 0, 1, "group")
        pipeline.find_cross_case_dups()

        usage = _load_usage()
        db_stats = _count_db_stats()
        usage["total_images_processed"] = db_stats.get("total_images", 0)
        usage["runs"] = int(usage.get("runs", 0)) + 1
        usage["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_usage(usage)

        pipeline.PROGRESS["status"] = "done"
        pipeline._progress_set("none", 0, 0, "")
    except Exception as e:
        _LAST_ERROR = str(e)
        pipeline.PROGRESS["status"] = "error"
        pipeline.PROGRESS["detail"] = _LAST_ERROR


# ===== API: 文件上传与处理 =====
@app.post("/upload")
async def upload(files: List[UploadFile] = File(...)):
    _ensure_dirs()
    print("[API] /upload called")
    with _LOCK:
        global _PROCESSING_THREAD
        if _PROCESSING_THREAD and _PROCESSING_THREAD.is_alive():
            return JSONResponse(status_code=429, content={"error": "已有任务在运行，请稍后再试"})

        saved = []
        for uf in files:
            fname = os.path.basename(uf.filename)
            if not fname.lower().endswith(".zip"):
                continue
            dst = os.path.join("uploads", fname)
            with open(dst, "wb") as f:
                shutil.copyfileobj(uf.file, f)
            saved.append(dst)

        if not saved:
            return JSONResponse(status_code=400, content={"error": "未上传有效的 ZIP 文件"})

        print(f"[API] starting background task with {len(saved)} zip(s)")
        _PROCESSING_THREAD = threading.Thread(target=_process_in_background, args=(saved,), daemon=True)
        _PROCESSING_THREAD.start()
        return {"ok": True, "files": [os.path.basename(p) for p in saved]}


@app.get("/status")
async def status():
    return _build_status_response()


# ===== API: 结果与下载 =====
@app.get("/results")
async def results():
    groups = []
    base = pathlib.Path("dup_groups")
    if base.exists():
        for g in sorted(p for p in base.iterdir() if p.is_dir() and p.name.startswith("group_")):
            images = []
            for img in sorted(g.iterdir()):
                if img.is_file() and img.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                    rel = str(img.as_posix())
                    images.append(rel)
            groups.append({
                "name": g.name,
                "count": len(images),
                "images": images,
            })
    return {"groups": groups}


@app.get("/image/{img_path:path}")
async def get_image(img_path: str):
    safe_root = pathlib.Path(os.getcwd()).resolve()
    target = (safe_root / img_path).resolve()
    if not str(target).startswith(str(safe_root)) or not target.exists() or not target.is_file():
        return JSONResponse(status_code=404, content={"error": "未找到图片"})
    return FileResponse(str(target))


@app.get("/download_results")
async def download_results():
    _ensure_dirs()
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        base = pathlib.Path("dup_groups")
        if base.exists():
            for p in base.rglob('*'):
                if p.is_file():
                    zf.write(p, p.relative_to(base.parent))
        csv_path = pathlib.Path("dup_groups.csv")
        if csv_path.exists():
            zf.write(csv_path, csv_path.name)
    zip_buf.seek(0)
    return StreamingResponse(zip_buf, media_type="application/zip", headers={
        "Content-Disposition": "attachment; filename=results.zip"
    })


@app.get("/download_csv")
async def download_csv():
    csv_path = pathlib.Path("dup_groups.csv")
    if not csv_path.exists():
        return JSONResponse(status_code=404, content={"error": "CSV 不存在"})
    return FileResponse(str(csv_path), media_type="text/csv", filename="dup_groups.csv")


# ===== API: 授权/使用量（简化实现） =====
@app.get("/license_stats")
async def license_stats():
    lic = _load_license()
    usage = _load_usage()
    authorized = lic is not None
    total_allowed = lic.get("total_images_allowed", 100000) if authorized and isinstance(lic, dict) else 100000
    stats = {
        "authorization_status": "authorized" if authorized else "unauthorized",
        "authorization_message": None if authorized else "未加载授权文件",
        "images_used": usage.get("total_images_processed", 0),
        "total_images_allowed": total_allowed,
        "images_remaining": max(0, total_allowed - int(usage.get("total_images_processed", 0))),
        "valid_until": (lic.get("valid_until") if authorized and isinstance(lic, dict) else None),
    }
    return stats


@app.post("/load_license")
async def load_license(license_file: UploadFile = File(...)):
    _ensure_dirs()
    try:
        content = await license_file.read()
        try:
            obj = json.loads(content.decode("utf-8"))
            with open(_LICENSE_FILE, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
        except Exception:
            with open(_LICENSE_FILE, "wb") as f:
                f.write(content)
        return {"ok": True}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.get("/export_usage_report")
async def export_usage_report():
    _ensure_dirs()
    usage = _load_usage()
    out = pathlib.Path("results") / "usage_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(usage, f, ensure_ascii=False, indent=2)
    return FileResponse(str(out), media_type="application/json", filename=out.name)


@app.get("/dual_key_info")
async def dual_key_info():
    usage = _load_usage()
    total = int(usage.get("total_images_processed", 0))
    return {
        "can_generate_key": total > 0,
        "total_images_processed": total,
    }


@app.get("/generate_client_key")
async def generate_client_key():
    usage = _load_usage()
    lic = _load_license() or {}
    payload = {
        "type": "client_usage_key",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "usage": usage,
        "license_id": lic.get("license_id") if isinstance(lic, dict) else None,
    }
    buf = io.BytesIO()
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    buf.write(data)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/json", headers={
        "Content-Disposition": "attachment; filename=client_usage_key.json"
    })


# 兼容旧接口：单文件上传 /upload-zip/
@app.post("/upload-zip/")
async def upload_zip_compat(file: UploadFile = File(...)):
    _ensure_dirs()
    print("[API] /upload-zip/ called")
    with _LOCK:
        global _PROCESSING_THREAD
        if _PROCESSING_THREAD and _PROCESSING_THREAD.is_alive():
            return JSONResponse(status_code=429, content={"error": "已有任务在运行，请稍后再试"})
        fname = os.path.basename(file.filename)
        if not fname.lower().endswith(".zip"):
            return JSONResponse(status_code=400, content={"error": "仅支持 ZIP 文件"})
        dst = os.path.join("uploads", fname)
        with open(dst, "wb") as f:
            shutil.copyfileobj(file.file, f)
        print("[API] starting background task with 1 zip")
        _PROCESSING_THREAD = threading.Thread(target=_process_in_background, args=([dst],), daemon=True)
        _PROCESSING_THREAD.start()
        return {"ok": True, "files": [fname]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
