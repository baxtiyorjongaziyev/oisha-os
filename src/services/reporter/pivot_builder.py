from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgencyRecord:
    client: str
    service_type: str
    manager: str
    designer: str
    month: str
    revenue: float
    cost: float
    status: str = "bajarildi"


@dataclass
class PivotQuery:
    row_dimension: str
    sort_by: str = "revenue"
    sort_asc: bool = False
    top_n: Optional[int] = None


@dataclass
class PivotRow:
    dimension_value: str
    count: int
    revenue: float
    cost: float
    profit: float
    margin_pct: float


@dataclass
class PivotResult:
    row_dimension: str
    rows: List[PivotRow]
    total_count: int
    total_revenue: float
    total_cost: float
    total_profit: float
    average_margin_pct: float


class AgencyPivotBuilder:
    VALID_DIMENSIONS = {"client", "service_type", "manager", "designer", "month"}
    VALID_MEASURES = {"revenue", "cost", "profit", "count", "margin_pct"}

    def build(
        self, records: List[AgencyRecord], query: PivotQuery
    ) -> PivotResult:
        dim = query.row_dimension
        if dim not in self.VALID_DIMENSIONS:
            raise ValueError(f"Notoʻgʻri oʻlcham: {dim}")

        groups: Dict[str, List[AgencyRecord]] = {}
        for rec in records:
            val = getattr(rec, dim, "Boshqa")
            groups.setdefault(str(val), []).append(rec)

        rows: List[PivotRow] = []
        tot_rev = 0.0
        tot_cost = 0.0

        for val, rec_list in groups.items():
            cnt = len(rec_list)
            rev = sum(r.revenue for r in rec_list)
            cst = sum(r.cost for r in rec_list)
            prf = rev - cst
            margin = round((prf / rev) * 100, 2) if rev > 0 else 0.0
            tot_rev += rev
            tot_cost += cst

            rows.append(
                PivotRow(
                    dimension_value=val,
                    count=cnt,
                    revenue=round(rev, 2),
                    cost=round(cst, 2),
                    profit=round(prf, 2),
                    margin_pct=margin,
                )
            )

        sort_key = query.sort_by if query.sort_by in self.VALID_MEASURES else "revenue"
        rows.sort(key=lambda r: getattr(r, sort_key, 0.0), reverse=not query.sort_asc)
        if query.top_n and query.top_n > 0:
            rows = rows[: query.top_n]

        tot_prf = round(tot_rev - tot_cost, 2)
        avg_margin = round((tot_prf / tot_rev) * 100, 2) if tot_rev > 0 else 0.0

        return PivotResult(
            row_dimension=dim,
            rows=rows,
            total_count=len(records),
            total_revenue=round(tot_rev, 2),
            total_cost=round(tot_cost, 2),
            total_profit=tot_prf,
            average_margin_pct=avg_margin,
        )
