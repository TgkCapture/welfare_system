# app/models/__init__.py
# Import every model so string-based relationships always resolve.
from app.models.group import Group, GroupSettings  # noqa: F401
from app.models.ledger import Payout, PayoutPurpose, Rate, SyncRun, YearSummary  # noqa: F401
from app.models.member import Contribution, Member, MemberAlias, PeriodSummary  # noqa: F401
from app.models.report import GeneratedReport, ReportAccessLog  # noqa: F401
from app.models.role import Role  # noqa: F401
from app.models.setting import Setting  # noqa: F401
from app.models.user import User  # noqa: F401
