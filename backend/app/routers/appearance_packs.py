"""Local preview/confirmation for declarative appearance packs."""
import asyncio
import mimetypes

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..local_access import local_dashboard
from ..services import appearance_packs as packs

router = APIRouter(prefix='/appearance-packs', tags=['appearance-packs'])
lock = asyncio.Lock()
dashboard = [Depends(local_dashboard)]


@router.get('', dependencies=dashboard)
def listing():
    return packs.catalog()[0]


@router.get('/schema', dependencies=dashboard)
def schema():
    return packs.Manifest.model_json_schema()


@router.post('/preview', dependencies=dashboard)
async def preview(file: UploadFile = File(...)):
    content = bytearray()
    try:
        while chunk := await file.read(1024 * 1024):
            if len(content) + len(chunk) > packs.MAX_ARCHIVE:
                raise HTTPException(413, '外观包不能超过 20 MB')
            content.extend(chunk)
        async with lock:
            return await asyncio.to_thread(packs.stage, bytes(content))
    except packs.PackError as error:
        raise HTTPException(422, str(error)) from error
    finally:
        await file.close()


class Install(BaseModel):
    token: str = Field(pattern=r'^[a-f0-9]{32}$')


@router.post('/install', dependencies=dashboard)
async def install(body: Install):
    try:
        async with lock:
            return await asyncio.to_thread(packs.install, body.token)
    except packs.PackError as error:
        raise HTTPException(422, str(error)) from error


@router.delete('/{identifier}', dependencies=dashboard)
async def uninstall(identifier: str):
    try:
        async with lock:
            return await asyncio.to_thread(packs.uninstall, identifier)
    except packs.PackError as error:
        raise HTTPException(422, str(error)) from error


@router.get('/{identifier}/assets/{filename}')
def asset(identifier: str, filename: str):
    # CSS/font/image requests cannot send the dashboard header. Only validated,
    # declared appearance resources are public, never arbitrary local files.
    try:
        path = packs.asset_file(identifier, filename)
    except packs.PackError as error:
        raise HTTPException(404, str(error)) from error
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0],
                        headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-cache'})
