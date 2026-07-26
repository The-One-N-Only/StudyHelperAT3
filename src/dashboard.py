"""Personal research dashboard analytics."""

import time
from datetime import datetime, timedelta

from . import db


def get_dashboard_data(user_id: int) -> dict:
    """Aggregate dashboard analytics for a user."""
    int(time.time())
    week_ago = int((datetime.now() - timedelta(days=7)).timestamp())
    int((datetime.now() - timedelta(days=30)).timestamp())

    # Workspace stats
    workspaces = db.get_user_workspaces(user_id)
    active_workspaces = [w for w in workspaces if w.get("time_updated", 0) > week_ago]

    # Source stats
    all_items = []
    for ws in workspaces:
        items = db.get_workspace_items(user_id, ws["id"])
        all_items.extend(items)

    recent_items = [i for i in all_items if i.get("time_added", 0) > week_ago]

    # Citation count
    citations = sum(1 for i in all_items if i.get("citation_apa"))

    # Domain diversity
    domains = {}
    for item in all_items:
        url = item.get("source_url", "")
        if url:
            import re
            match = re.search(r'https?://([^/]+)', url)
            if match:
                domain = match.group(1)
                domains[domain] = domains.get(domain, 0) + 1

    total = sum(domains.values()) or 1
    diversity = min(1.0, len(domains) / max(total, 1) * 10)  # Heuristic

    return {
        "total_workspaces": len(workspaces),
        "active_workspaces_7d": len(active_workspaces),
        "total_sources": len(all_items),
        "sources_added_7d": len(recent_items),
        "total_citations": citations,
        "domain_diversity": round(diversity, 2),
        "domain_count": len(domains),
        "top_domains": sorted(domains.items(), key=lambda x: -x[1])[:5],
        "ai_usage": db.get_user_usage(user_id, 30) if hasattr(db, "get_user_usage") else [],
    }
