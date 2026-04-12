from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ai_hotspot_monitor.cli import build_markdown_report, build_report_payload, _configure_logging
from ai_hotspot_monitor.config import load_sources
from ai_hotspot_monitor.pipeline import AiHotspotEvaluator, MonitorPipeline
from ai_hotspot_monitor.resume import load_resume_text


LOGGER = logging.getLogger("ai_hotspot_monitor")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIEWER_DIR = PROJECT_ROOT / "viewer"
PRESET_SOURCES = {
    "curated": PROJECT_ROOT / "sources.curated.json",
    "example": PROJECT_ROOT / "sources.example.json",
    "premium": PROJECT_ROOT / "sources.premium.example.json",
}

app = FastAPI(title="SignalRank AI API", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/run")
async def run_pipeline(
    resume_file: UploadFile = File(...),
    sources_file: UploadFile | None = File(default=None),
    sources_preset: str = Form("curated"),
    per_source_limit: int = Form(8),
    top_n: int = Form(30),
    min_relevance: float = Form(32.0),
    min_quality: float = Form(30.0),
    heavyweight_impact: float = Form(68.0),
    ai_evaluate: bool = Form(False),
    ai_expand_resume: bool = Form(False),
    ai_top_k: int = Form(8),
    ai_candidate_pool: int = Form(20),
    generation_api: str = Form("responses"),
    ai_model: str = Form("gpt-5-mini"),
    openai_api_key: str = Form(""),
    openai_api_key_env: str = Form("OPENAI_API_KEY"),
    openai_base_url: str = Form(""),
    embedding_model: str = Form("text-embedding-3-small"),
    embedding_api_key: str = Form(""),
    embedding_api_key_env: str = Form("OPENAI_EMBEDDING_API_KEY"),
    embedding_base_url: str = Form(""),
    chat_timeout: int = Form(300),
    embedding_timeout: int = Form(60),
    log_level: str = Form("INFO"),
) -> JSONResponse:
    _configure_logging(log_level)
    try:
        with tempfile.TemporaryDirectory(prefix="signalrank-web-") as temp_dir:
            temp_path = Path(temp_dir)
            resume_path = temp_path / resume_file.filename
            resume_path.write_bytes(await resume_file.read())

            if sources_file is not None and sources_file.filename:
                sources_path = temp_path / sources_file.filename
                sources_path.write_bytes(await sources_file.read())
            else:
                sources_path = PRESET_SOURCES.get(sources_preset, PRESET_SOURCES["curated"])

            if not sources_path.exists():
                raise HTTPException(status_code=400, detail=f"Sources config not found: {sources_path}")

            resume_text = load_resume_text(resume_path)
            sources = load_sources(sources_path)

            ai_evaluator = None
            if ai_evaluate:
                ai_evaluator = AiHotspotEvaluator(
                    chat_api_key=openai_api_key or None,
                    chat_api_key_env=openai_api_key_env,
                    chat_model=ai_model,
                    embedding_model=embedding_model,
                    generation_api=generation_api,
                    chat_base_url=openai_base_url or None,
                    embedding_api_key=embedding_api_key or None,
                    embedding_api_key_env=embedding_api_key_env,
                    embedding_base_url=embedding_base_url or None,
                    chat_timeout=chat_timeout,
                    embedding_timeout=embedding_timeout,
                    logger=LOGGER,
                )

            pipeline = MonitorPipeline(ai_evaluator=ai_evaluator, logger=LOGGER)
            result = pipeline.run(
                resume_text=resume_text,
                sources=sources,
                per_source_limit=per_source_limit,
                min_relevance=min_relevance,
                min_quality=min_quality,
                heavyweight_impact=heavyweight_impact,
                top_n=top_n,
                ai_top_k=ai_top_k,
                ai_candidate_pool=ai_candidate_pool,
                ai_expand_resume=ai_expand_resume,
            )
            payload = build_report_payload(result)
            markdown = build_markdown_report(
                result,
                payload,
                str(Path(sources_path).resolve()),
                {
                    "min_relevance": min_relevance,
                    "min_quality": min_quality,
                    "heavyweight_impact": heavyweight_impact,
                },
            )

            saved = _persist_api_report(payload, markdown)
            return JSONResponse(
                {
                    "ok": True,
                    "report": payload,
                    "markdown": markdown,
                    "saved_files": saved,
                }
            )
    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.exception("Web pipeline run failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/reports/{filename}")
def get_report_file(filename: str):
    reports_dir = PROJECT_ROOT / "reports_web"
    path = reports_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    media_type = "application/json" if path.suffix == ".json" else "text/markdown"
    return FileResponse(path, media_type=media_type, filename=path.name)


def _persist_api_report(payload: dict, markdown: str) -> dict[str, str]:
    reports_dir = PROJECT_ROOT / "reports_web"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = payload["generated_at"].replace(":", "").replace("-", "").replace("+00:00", "Z")
    json_name = f"ai_hotspots_{timestamp}.json"
    md_name = f"ai_hotspots_{timestamp}.md"
    json_path = reports_dir / json_name
    md_path = reports_dir / md_name
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "json": f"/api/reports/{json_name}",
        "markdown": f"/api/reports/{md_name}",
    }


def run_dev_server() -> None:
    import uvicorn

    host = os.getenv("SIGNALRANK_HOST", "127.0.0.1")
    port = int(os.getenv("SIGNALRANK_PORT", "8000"))
    uvicorn.run("ai_hotspot_monitor.api:app", host=host, port=port, reload=False)


if VIEWER_DIR.exists():
    app.mount("/", StaticFiles(directory=str(VIEWER_DIR), html=True), name="viewer")
