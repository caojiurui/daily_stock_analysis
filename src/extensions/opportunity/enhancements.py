# -*- coding: utf-8 -*-
"""Small enhancement helpers for opportunity payload shaping."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .scoring import normalize_risk_profile

_THEME_ETF_MAP = {
    "ai算力": ("512480", "半导体ETF"),
    "算力租赁": ("516520", "云计算ETF"),
    "半导体": ("512480", "半导体ETF"),
    "芯片": ("588200", "科创芯片ETF"),
    "机器人": ("159551", "机器人ETF"),
    "新能源": ("515030", "新能源车ETF"),
    "光伏": ("515790", "光伏ETF"),
    "军工": ("512660", "军工ETF"),
    "券商": ("512000", "券商ETF"),
    "证券": ("512000", "券商ETF"),
    "银行": ("512800", "银行ETF"),
    "红利": ("515180", "红利ETF"),
    "消费": ("159928", "消费ETF"),
    "医药": ("512010", "医药ETF"),
    "创新药": ("159992", "创新药ETF"),
    "煤炭": ("515220", "煤炭ETF"),
    "有色": ("512400", "有色ETF"),
    "黄金": ("518880", "黄金ETF"),
    "沪深300": ("510300", "沪深300ETF"),
}


def normalize_match_key(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def map_theme_etf(value: str) -> Tuple[str, str]:
    normalized = normalize_match_key(value)
    if not normalized:
        return "", ""
    for theme, mapping in _THEME_ETF_MAP.items():
        theme_key = normalize_match_key(theme)
        if theme_key and (theme_key in normalized or normalized in theme_key):
            return mapping
    return "", ""


def build_cycle_view(
    *,
    score: float,
    change_pct: float,
    catalyst_scores: List[float],
    risk_profile: str = "balanced",
) -> Dict[str, Any]:
    profile = normalize_risk_profile(risk_profile)
    action_labels = {
        "conservative": {"prepare": "分批观察", "watch": "继续观察", "avoid": "暂不动作"},
        "balanced": {"prepare": "准备跟踪", "watch": "先观察", "avoid": "暂不动作"},
        "aggressive": {"prepare": "可先试错", "watch": "盯住突破", "avoid": "控制冲动"},
    }
    catalyst_strength = max((float(item) for item in catalyst_scores), default=0.0)
    if score >= 82 or (score >= 75 and catalyst_strength >= 60 and change_pct >= 2):
        return {
            "short_term": "偏强",
            "mid_term": "跟踪强化",
            "long_term": "等待回踩确认",
            "action_bias": "prepare",
            "action_label": action_labels[profile]["prepare"],
            "risk_profile": profile,
        }
    if score >= 68:
        return {
            "short_term": "观察",
            "mid_term": "主题跟踪",
            "long_term": "逐步验证",
            "action_bias": "watch",
            "action_label": action_labels[profile]["watch"],
            "risk_profile": profile,
        }
    return {
        "short_term": "偏弱",
        "mid_term": "等待改善",
        "long_term": "不急于动作",
        "action_bias": "avoid",
        "action_label": action_labels[profile]["avoid"],
        "risk_profile": profile,
    }


def build_portfolio_advice(
    *,
    instrument_type: str,
    score: float,
    data_quality: str,
    watchlist_match: bool,
    holding_match: bool,
    risk_profile: str = "balanced",
) -> Dict[str, Any]:
    profile = normalize_risk_profile(risk_profile)
    max_positions = {
        "stock": {"conservative": 2, "balanced": 3, "aggressive": 4},
        "etf": {"conservative": 4, "balanced": 5, "aggressive": 6},
    }["etf" if instrument_type == "etf" else "stock"][profile]
    note_matrix = {
        "conservative": "优先 ETF 或分批小仓跟踪" if score >= 75 else "先观察，不追高",
        "balanced": "优先小仓位试错" if score >= 75 else "先观察不追高",
        "aggressive": "可分批试错，但仍要等确认" if score >= 75 else "盯住确认信号后再动",
    }
    note = note_matrix[profile]
    if holding_match:
        note = "已有持仓，优先看加仓纪律与止盈止损"
    elif watchlist_match:
        note = "已在自选，优先等待触发条件"
    if data_quality != "good":
        note = f"{note}；数据质量一般，减少激进行动"
    return {
        "max_positions": max_positions,
        "rebalance_hint": "避免单一主题过度集中",
        "note": note,
        "risk_profile": profile,
    }


def build_tags(*, watchlist_match: bool, holding_match: bool, has_catalysts: bool) -> List[str]:
    tags: List[str] = []
    if holding_match:
        tags.append("持仓相关")
    if watchlist_match:
        tags.append("自选相关")
    if has_catalysts:
        tags.append("新闻催化")
    return tags
