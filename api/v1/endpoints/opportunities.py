# -*- coding: utf-8 -*-
"""Opportunity engine API routes."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_config_dep
from api.v1.errors import api_error
from src.config import Config
from src.extensions.opportunity import OpportunityService
from src.services.task_queue import TaskStatus as QueueTaskStatus
from src.services.task_queue import get_task_queue

router = APIRouter()


class OpportunityScanRequest(BaseModel):
    market: str = Field("all", pattern="^(cn|hk|us|all)$")
    scope: str = Field("balanced", pattern="^(balanced|etf|stock)$")
    watchlist_only: bool = False
    max_results: int = Field(10, ge=1, le=50)


class OpportunityScanAccepted(BaseModel):
    task_id: str
    trace_id: str
    status: str = "pending"
    message: str
    market: str
    scope: str
    max_results: int


class OpportunityScanTaskStatus(BaseModel):
    task_id: str
    trace_id: Optional[str] = None
    status: str
    progress: int = 0
    message: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


def _service(config: Config) -> OpportunityService:
    return OpportunityService(config=config)


def _task_not_found(task_id: str):
    return api_error(
        404,
        "opportunity_scan_task_not_found",
        f"机会扫描任务 {task_id} 不存在或已过期",
    )


@router.get("/overview")
def opportunity_overview(
    market: str = "all",
    scope: str = "balanced",
    limit: int = 10,
    account_id: Optional[int] = None,
    risk_profile: str = "balanced",
    config: Config = Depends(get_config_dep),
) -> Dict[str, Any]:
    return _service(config).overview(
        market=market,
        scope=scope,
        limit=limit,
        account_id=account_id,
        risk_profile=risk_profile,
    )


@router.post("/scan", status_code=202, response_model=OpportunityScanAccepted)
def opportunity_start_scan_task(
    request: OpportunityScanRequest,
    config: Config = Depends(get_config_dep),
) -> OpportunityScanAccepted:
    task_id = uuid.uuid4().hex
    task_queue = get_task_queue()

    def run_scan() -> Dict[str, Any]:
        task_queue.update_task_progress(task_id, 25, "正在扫描板块、ETF 与个股机会")
        result = _service(config).scan(
            market=request.market,
            scope=request.scope,
            watchlist_only=request.watchlist_only,
            max_results=request.max_results,
        )
        task_queue.update_task_progress(task_id, 90, "机会扫描完成，正在整理风险预算与数据质量")
        return result

    task = task_queue.submit_background_task(
        run_scan,
        stock_code="opportunity_scan",
        stock_name=f"{request.scope} / {request.market}",
        report_type="opportunity_scan",
        message="机会扫描任务已提交",
        task_id=task_id,
        trace_id=task_id,
    )
    return OpportunityScanAccepted(
        task_id=task.task_id,
        trace_id=task.trace_id or task.task_id,
        status=task.status.value if isinstance(task.status, QueueTaskStatus) else str(task.status),
        message=task.message or "机会扫描任务已提交",
        market=request.market,
        scope=request.scope,
        max_results=request.max_results,
    )


@router.get("/tasks/{task_id}", response_model=OpportunityScanTaskStatus)
def opportunity_scan_task_status(task_id: str) -> OpportunityScanTaskStatus:
    task = get_task_queue().get_task(task_id)
    if task is None or task.report_type != "opportunity_scan":
        raise _task_not_found(task_id)

    result = task.result if task.status == QueueTaskStatus.COMPLETED and isinstance(task.result, dict) else None
    return OpportunityScanTaskStatus(
        task_id=task.task_id,
        trace_id=task.trace_id or task.task_id,
        status=task.status.value if isinstance(task.status, QueueTaskStatus) else str(task.status),
        progress=task.progress,
        message=task.message,
        error=task.error,
        result=result,
    )
