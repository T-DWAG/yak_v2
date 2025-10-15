from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from typing import List
import shutil, os, io, json, threading, zipfile, pathlib, time
from . import pipeline
from .utils.license_manager import license_manager

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

@app.get("/v3")
async def root_v2():
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "index3.html")
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


def _check_license_at_startup():
    """启动时检查授权"""
    is_valid, message, license_data = license_manager.validate_current_license()
    if not is_valid:
        print(f"⚠️  授权检查失败: {message}")
        print("⚠️  系统将以未授权模式运行，部分功能受限")
        return False
    else:
        print(f"✅ 授权检查通过: {license_data.get('license_id', 'Unknown')}")
        print(f"   许可图片数量: {license_data.get('total_images_allowed', 0)}")
        print(f"   有效期至: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(license_data.get('expires_at', 0)))}")
        return True


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
    session_id = None

    try:
        _LAST_ERROR = None

        # 检查授权
        is_valid, message, _ = license_manager.validate_current_license()
        if not is_valid:
            raise Exception(f"授权无效: {message}")

        # 开始处理会话
        session_id = license_manager.start_processing_session()
        if not session_id:
            raise Exception("无法创建处理会话")

        pipeline.PROGRESS["status"] = "running"
        pipeline._progress_set("extract", 0, len(zip_paths), "Extract all zips")
        pipeline.extract_zip_to_db(zip_paths)

        pipeline._progress_set("yolo", 0, 1, "classify")
        pipeline.run_yolo_and_update()

        pipeline._progress_set("dedup", 0, 1, "group")
        pipeline.find_cross_case_dups()

        # 获取处理的图片数量
        db_stats = _count_db_stats()
        processed_images = db_stats.get("total_images", 0)

        # 结束处理会话，更新使用统计
        if session_id:
            license_manager.end_processing_session(session_id, processed_images)

        pipeline.PROGRESS["status"] = "done"
        pipeline._progress_set("none", 0, 0, "")

    except Exception as e:
        _LAST_ERROR = str(e)
        pipeline.PROGRESS["status"] = "error"
        pipeline.PROGRESS["detail"] = _LAST_ERROR

        # 如果出错且会话已创建，也要结束会话
        if session_id:
            try:
                db_stats = _count_db_stats()
                processed_images = db_stats.get("total_images", 0)
                license_manager.end_processing_session(session_id, processed_images)
            except:
                pass


# ===== API: 文件上传与处理 =====
@app.post("/upload")
async def upload(files: List[UploadFile] = File(...)):
    _ensure_dirs()
    print("[API] /upload called")

    # 检查授权状态
    is_valid, message, _ = license_manager.validate_current_license()
    if not is_valid:
        return JSONResponse(status_code=403, content={"error": f"授权无效: {message}"})

    with _LOCK:
        global _PROCESSING_THREAD
        if _PROCESSING_THREAD and _PROCESSING_THREAD.is_alive():
            return JSONResponse(status_code=429, content={"error": "已有任务在运行，请稍后再试"})

        # 注意：这里不再进行预估，实际的图片数量检查在pipeline.py中进行
        # 这样可以避免预估不准导致的误判问题

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
    return license_manager.get_license_status()


@app.post("/load_license")
async def load_license(license_file: UploadFile = File(...)):
    _ensure_dirs()
    try:
        content = await license_file.read()
        license_data = json.loads(content.decode("utf-8"))

        # 保存授权文件
        success = license_manager.save_license(license_data)
        if not success:
            return JSONResponse(status_code=500, content={"error": "保存授权文件失败"})

        # 验证授权文件
        is_valid, message, _ = license_manager.validate_current_license()
        if not is_valid:
            return JSONResponse(status_code=400, content={"error": f"授权文件无效: {message}"})

        return {"ok": True, "message": "授权文件加载成功"}
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": "授权文件格式错误"})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.get("/export_usage_report")
async def export_usage_report():
    _ensure_dirs()
    usage_stats = license_manager.get_usage_stats()

    # 添加授权状态信息
    license_status = license_manager.get_license_status()
    usage_stats["license_status"] = license_status

    out = pathlib.Path("results") / "usage_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(usage_stats, f, ensure_ascii=False, indent=2)
    return FileResponse(str(out), media_type="application/json", filename=out.name)


@app.get("/dual_key_info")
async def dual_key_info():
    can_generate = license_manager.can_generate_client_key()
    usage_stats = license_manager.get_usage_stats()

    return {
        "can_generate_key": can_generate,
        "total_images_processed": usage_stats.get("total_images_processed", 0),
    }


@app.get("/generate_client_key")
async def generate_client_key():
    try:
        from .utils.client_key import generate_client_key

        # 检查是否可以生成客户端钥匙
        if not license_manager.can_generate_client_key():
            return JSONResponse(status_code=403, content={"error": "暂无处理记录，无法生成客户端钥匙"})

        # 生成客户端钥匙
        client_key = generate_client_key()

        # 返回文件下载
        buf = io.BytesIO()
        data = json.dumps(client_key, ensure_ascii=False, indent=2).encode("utf-8")
        buf.write(data)
        buf.seek(0)

        return StreamingResponse(buf, media_type="application/json", headers={
            "Content-Disposition": "attachment; filename=client_usage_key.json"
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"生成客户端钥匙失败: {str(e)}"})


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
    # 启动时检查授权
    _check_license_at_startup()

    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
