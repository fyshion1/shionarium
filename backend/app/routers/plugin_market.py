"""Public catalog metadata; installation is restricted to the local dashboard."""
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..local_access import local_dashboard
from ..services import plugin_market as market
from . import plugins

router = APIRouter(prefix='/plugin-market', tags=['plugin-market'], dependencies=[Depends(local_dashboard)])


@router.get('')
async def catalog():
    return await asyncio.to_thread(market.catalog)


@router.get('/jobs')
async def jobs():
    return {'items': await asyncio.to_thread(market.jobs)}


class Install(BaseModel):
    id: str
    revision: str
    accept_code: bool = False


@router.post('/install', status_code=202)
async def install(body: Install):
    async with plugins.lock:
        try:
            return await asyncio.to_thread(market.start, body.id, body.revision, body.accept_code)
        except market.MarketError as error:
            raise HTTPException(409, str(error)) from error
        except OSError as error:
            raise HTTPException(409, '无法创建安装任务，请检查本机数据目录的写入权限与磁盘空间') from error
