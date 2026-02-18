import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import app.crud.groups as crud_groups
from app.crud.report import get_full_report
from app.database import get_db
from app.schemas.report import ReportOut
from app.services.report_transfer import export_report, import_report

router = APIRouter(prefix="/transfer", tags=["transfer"])


@router.get("/export/{report_id}")
def export_report_endpoint(report_id: int, db: Session = Depends(get_db)):
    """Export a complete report (data + files) as a ZIP archive."""
    report = get_full_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    file_obj, filename = export_report(db, report_id)
    if file_obj is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return StreamingResponse(
        file_obj,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=ReportOut)
def import_report_endpoint(
    group_id: int = Query(..., description="Target group ID"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import a report from a previously exported ZIP archive."""
    group = crud_groups.get(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload must be a .zip file")

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    try:
        with os.fdopen(tmp_fd, "wb") as tmp:
            while chunk := file.file.read(8 * 1024 * 1024):
                tmp.write(chunk)

        try:
            new_report = import_report(db, tmp_path, group_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return new_report
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
