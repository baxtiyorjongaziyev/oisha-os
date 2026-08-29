from src.services.core.finance.gsheets.constants import *
from src.services.core.finance.gsheets.formatting import GsheetFormattingMixin
from src.services.core.finance.gsheets.client import GsheetClientMixin
from src.services.core.finance.gsheets.transactions import GsheetTransactionsMixin
from src.services.core.finance.gsheets.reporting import GsheetReportingMixin
from src.services.core.finance.gsheets.budget_salary import GsheetBudgetSalaryMixin

class HisobchiGsheetStore(
    GsheetClientMixin,
    GsheetFormattingMixin,
    GsheetTransactionsMixin,
    GsheetReportingMixin,
    GsheetBudgetSalaryMixin,
):
    """
    Hisobchi Google Sheets ma'lumotlar ombori.
    Barcha modulli mixinlarni bitta classda birlashtiradi.
    """
    pass
