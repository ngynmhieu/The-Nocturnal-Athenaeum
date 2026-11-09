"""HTTP endpoints for the image module — thin; logic lives in ImageService."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from .dependencies import get_image_service
from .manager import ModelUnavailableError
from .service import ImageService

router = APIRouter()


@router.post("/v1/images/upscale")
async def upscale(request: Request, model: Optional[str] = None,
                  service: ImageService = Depends(get_image_service)):
    """Body = raw image bytes; returns the upscaled image as PNG."""
    data = await request.body()
    try:
        png = await run_in_threadpool(service.upscale_bytes, data, model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ModelUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return Response(content=png, media_type="image/png")
