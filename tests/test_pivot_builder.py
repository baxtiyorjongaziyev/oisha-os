import pytest
from src.services.reporter.pivot_builder import (
    AgencyPivotBuilder,
    PivotQuery,
    AgencyRecord,
)

def test_pivot_grouping():
    builder = AgencyPivotBuilder()
    records = [
        AgencyRecord("Chust Pichoqlari", "Brending", "Farrux", "Alisher", "2026-09", 50000000.0, 15000000.0),
        AgencyRecord("Safia Bakery", "Qadoq", "Farrux", "Alisher", "2026-09", 40000000.0, 10000000.0),
    ]
    query = PivotQuery(row_dimension="service_type", sort_by="profit", sort_asc=False)
    res = builder.build(records, query)
    assert res.total_count == 2
    assert res.total_revenue == 90000000.0
