"""API endpoints for interview evaluation reports and PDF generation."""
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.services.report_service import report_service

router = APIRouter(prefix="/api/report", tags=["Report"])


@router.get("/{sid}", response_model=Dict[str, Any])
async def get_report_json(sid: str, db: Session = Depends(get_db)):
    """Retrieve full evaluation report including radar scores, timeline deductions, and summary."""
    try:
        return await report_service.generate_report(sid, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {e}")


@router.get("/{sid}/pdf")
async def download_report_pdf(sid: str, db: Session = Depends(get_db)):
    """Generate and download formatted evaluation report PDF."""
    try:
        report_data = await report_service.generate_report(sid, db)
        pdf_bytes = report_service.generate_pdf_report(report_data)
        filename = f"PLUTO_vProctor_Report_{sid}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {e}")
