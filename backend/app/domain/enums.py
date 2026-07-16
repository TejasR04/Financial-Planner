"""Framework-free enums shared across the domain, services, and persistence layers."""
from enum import Enum


class AccountType(str, Enum):
    INVESTMENT = "investment"
    DEPOSITORY = "depository"
    RETIREMENT = "retirement"
    CREDIT = "credit"
    LOAN = "loan"
    PROPERTY = "property"


class AccountStatus(str, Enum):
    CONNECTED = "connected"
    ATTENTION = "attention"
    MANUAL = "manual"


class InstitutionStatus(str, Enum):
    HEALTHY = "healthy"
    ACTION_REQUIRED = "action_required"
    ERROR = "error"


class ProviderType(str, Enum):
    PLAID = "plaid"
    MANUAL = "manual"
    CSV = "csv"


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    CONTRIBUTION = "contribution"


class TransactionStatus(str, Enum):
    CLEARED = "cleared"
    PENDING = "pending"


class AssetClass(str, Enum):
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    REAL_ESTATE = "real_estate"
    CASH = "cash"
    ALTERNATIVES = "alternatives"


class FilingStatus(str, Enum):
    SINGLE = "single"
    MARRIED_JOINT = "married_joint"
    MARRIED_SEPARATE = "married_separate"
    HEAD_OF_HOUSEHOLD = "head_of_household"


class RetirementAccountKind(str, Enum):
    TRADITIONAL_401K = "traditional_401k"
    ROTH_401K = "roth_401k"
    TRADITIONAL_IRA = "traditional_ira"
    ROTH_IRA = "roth_ira"
    HSA = "hsa"


class DebtPayoffStrategy(str, Enum):
    AVALANCHE = "avalanche"  # highest interest rate first
    SNOWBALL = "snowball"    # smallest balance first


class RecommendationEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationStatus(str, Enum):
    NEW = "new"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class InsightKind(str, Enum):
    OBSERVATION = "observation"
    ALERT = "alert"
    OPPORTUNITY = "opportunity"


class GoalStatus(str, Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    DONE = "done"


class SimulationMethod(str, Enum):
    DETERMINISTIC = "deterministic"
    MONTE_CARLO = "monte_carlo"
