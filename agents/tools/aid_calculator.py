"""Aid Calculator Tool - Story 2.2

Computes total cost of attendance, expected family contribution,
and net price after aid for college planning.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AidType(Enum):
    """Types of financial aid."""
    GRANT = "grant"  # Free money, no repayment
    SCHOLARSHIP = "scholarship"  # Merit or need-based, no repayment
    WORK_STUDY = "work_study"  # Earn through employment
    LOAN_SUBSIDIZED = "loan_subsidized"  # Federal, interest paid during school
    LOAN_UNSUBSIDIZED = "loan_unsubsidized"  # Federal, interest accrues
    LOAN_PARENT = "loan_parent"  # Parent PLUS loans
    LOAN_PRIVATE = "loan_private"  # Private loans


class SchoolType(Enum):
    """Types of schools for cost estimation."""
    PUBLIC_IN_STATE = "public_in_state"
    PUBLIC_OUT_STATE = "public_out_state"
    PRIVATE = "private"
    COMMUNITY = "community"


@dataclass
class AidAward:
    """A single financial aid award."""
    name: str
    aid_type: AidType
    amount: float
    renewable: bool = False
    years: int = 1
    conditions: str = ""


@dataclass
class CostBreakdown:
    """Breakdown of cost of attendance."""
    tuition: float = 0.0
    fees: float = 0.0
    room_board: float = 0.0
    books_supplies: float = 0.0
    personal_expenses: float = 0.0
    transportation: float = 0.0

    @property
    def total(self) -> float:
        """Total cost of attendance."""
        return (
            self.tuition + self.fees + self.room_board +
            self.books_supplies + self.personal_expenses + self.transportation
        )


@dataclass
class AidSummary:
    """Summary of financial aid analysis."""
    total_cost: float
    total_grants: float  # Free money
    total_scholarships: float  # Free money
    total_work_study: float
    total_loans: float
    net_price: float  # What you actually pay (cost - free money)
    out_of_pocket: float  # Net price - work study
    total_debt_4_years: float  # Projected 4-year loan debt
    monthly_payment_estimate: float  # Estimated monthly payment after graduation


@dataclass
class SchoolComparison:
    """Comparison data for multiple schools."""
    school_name: str
    summary: AidSummary
    rank_by_net_price: int = 0
    rank_by_debt: int = 0


# Average costs by school type (2024-2025 estimates)
AVERAGE_COSTS: Dict[SchoolType, CostBreakdown] = {
    SchoolType.PUBLIC_IN_STATE: CostBreakdown(
        tuition=11_000,
        fees=1_500,
        room_board=12_000,
        books_supplies=1_200,
        personal_expenses=2_500,
        transportation=1_500,
    ),
    SchoolType.PUBLIC_OUT_STATE: CostBreakdown(
        tuition=24_000,
        fees=1_500,
        room_board=12_000,
        books_supplies=1_200,
        personal_expenses=2_500,
        transportation=2_000,
    ),
    SchoolType.PRIVATE: CostBreakdown(
        tuition=42_000,
        fees=1_800,
        room_board=15_000,
        books_supplies=1_200,
        personal_expenses=2_500,
        transportation=1_500,
    ),
    SchoolType.COMMUNITY: CostBreakdown(
        tuition=4_000,
        fees=800,
        room_board=0,  # Usually commuter
        books_supplies=1_200,
        personal_expenses=2_500,
        transportation=2_000,
    ),
}


class AidCalculatorTool:
    """Tool for calculating financial aid and cost of attendance.

    Acceptance Criteria:
    - aid_calculator computes total cost of attendance
    """

    def __init__(self, falkordb_client=None):
        """Initialize aid calculator tool.

        Args:
            falkordb_client: FalkorDB client for school data
        """
        self.falkordb = falkordb_client

    async def calculate_cost_of_attendance(
        self,
        school_type: SchoolType = SchoolType.PUBLIC_IN_STATE,
        custom_costs: Optional[CostBreakdown] = None,
    ) -> CostBreakdown:
        """Calculate total cost of attendance.

        Args:
            school_type: Type of school
            custom_costs: Optional custom cost breakdown

        Returns:
            CostBreakdown with all costs
        """
        if custom_costs:
            return custom_costs

        return AVERAGE_COSTS.get(
            school_type,
            AVERAGE_COSTS[SchoolType.PUBLIC_IN_STATE]
        )

    async def calculate_aid_summary(
        self,
        cost: CostBreakdown,
        aid_awards: List[AidAward],
        years: int = 4,
    ) -> AidSummary:
        """Calculate comprehensive aid summary.

        Args:
            cost: Cost of attendance breakdown
            aid_awards: List of aid awards
            years: Number of years to project

        Returns:
            AidSummary with all calculations
        """
        total_grants = 0.0
        total_scholarships = 0.0
        total_work_study = 0.0
        total_loans = 0.0

        for award in aid_awards:
            if award.aid_type == AidType.GRANT:
                total_grants += award.amount
            elif award.aid_type == AidType.SCHOLARSHIP:
                total_scholarships += award.amount
            elif award.aid_type == AidType.WORK_STUDY:
                total_work_study += award.amount
            elif award.aid_type in (
                AidType.LOAN_SUBSIDIZED,
                AidType.LOAN_UNSUBSIDIZED,
                AidType.LOAN_PARENT,
                AidType.LOAN_PRIVATE,
            ):
                total_loans += award.amount

        total_cost = cost.total
        free_money = total_grants + total_scholarships
        net_price = max(0, total_cost - free_money)
        out_of_pocket = max(0, net_price - total_work_study)

        # Calculate 4-year debt projection
        annual_loans = total_loans
        total_debt_4_years = 0.0

        for year in range(years):
            # Assume renewable aid stays same, loans increase slightly
            year_debt = annual_loans * (1 + 0.02 * year)  # 2% increase per year
            total_debt_4_years += year_debt

        # Calculate monthly payment (10-year repayment, ~6% interest)
        monthly_payment = self._calculate_monthly_payment(
            total_debt_4_years,
            interest_rate=0.06,
            years=10,
        )

        return AidSummary(
            total_cost=total_cost,
            total_grants=total_grants,
            total_scholarships=total_scholarships,
            total_work_study=total_work_study,
            total_loans=total_loans,
            net_price=net_price,
            out_of_pocket=out_of_pocket,
            total_debt_4_years=total_debt_4_years,
            monthly_payment_estimate=monthly_payment,
        )

    def _calculate_monthly_payment(
        self,
        principal: float,
        interest_rate: float,
        years: int,
    ) -> float:
        """Calculate monthly loan payment.

        Args:
            principal: Loan amount
            interest_rate: Annual interest rate (e.g., 0.06 for 6%)
            years: Repayment period in years

        Returns:
            Monthly payment amount
        """
        if principal <= 0:
            return 0.0

        monthly_rate = interest_rate / 12
        num_payments = years * 12

        if monthly_rate == 0:
            return principal / num_payments

        payment = principal * (
            monthly_rate * (1 + monthly_rate) ** num_payments
        ) / (
            (1 + monthly_rate) ** num_payments - 1
        )

        return round(payment, 2)

    async def compare_schools(
        self,
        schools: List[Dict[str, Any]],
    ) -> List[SchoolComparison]:
        """Compare financial aid across multiple schools.

        Args:
            schools: List of school data with costs and aid

        Returns:
            List of SchoolComparison objects, ranked
        """
        comparisons = []

        for school in schools:
            cost = CostBreakdown(
                tuition=school.get('tuition', 0),
                fees=school.get('fees', 0),
                room_board=school.get('room_board', 0),
                books_supplies=school.get('books_supplies', 1200),
                personal_expenses=school.get('personal_expenses', 2500),
                transportation=school.get('transportation', 1500),
            )

            aid_awards = []
            for aid in school.get('aid', []):
                aid_awards.append(AidAward(
                    name=aid.get('name', ''),
                    aid_type=AidType(aid.get('type', 'grant')),
                    amount=aid.get('amount', 0),
                ))

            summary = await self.calculate_aid_summary(cost, aid_awards)

            comparison = SchoolComparison(
                school_name=school.get('name', ''),
                summary=summary,
            )
            comparisons.append(comparison)

        # Rank by net price
        sorted_by_price = sorted(comparisons, key=lambda x: x.summary.net_price)
        for i, comp in enumerate(sorted_by_price):
            comp.rank_by_net_price = i + 1

        # Rank by debt
        sorted_by_debt = sorted(
            comparisons, key=lambda x: x.summary.total_debt_4_years
        )
        for i, comp in enumerate(sorted_by_debt):
            comp.rank_by_debt = i + 1

        # Return sorted by net price
        return sorted_by_price

    async def estimate_efc(
        self,
        household_income: float,
        household_size: int,
        assets: float = 0,
        num_in_college: int = 1,
    ) -> float:
        """Estimate Expected Family Contribution (EFC).

        Note: This is a simplified estimate. Actual EFC uses the
        Federal Methodology formula which is more complex.

        Args:
            household_income: Total household income
            household_size: Number of people in household
            assets: Total reportable assets
            num_in_college: Number of family members in college

        Returns:
            Estimated EFC
        """
        # Simplified EFC calculation
        # In reality, this depends on many more factors

        # Income protection allowance (rough estimate)
        income_protection = 20000 + (household_size - 2) * 5000

        # Available income (after taxes and allowances)
        available_income = max(0, household_income - income_protection) * 0.22

        # Asset contribution (5.64% of assets above protection)
        asset_protection = 10000 * household_size
        available_assets = max(0, assets - asset_protection) * 0.0564

        # Total parent contribution
        parent_contribution = available_income + available_assets

        # Divide by number in college
        efc = parent_contribution / num_in_college

        return round(efc, 0)

    async def calculate_unmet_need(
        self,
        cost_of_attendance: float,
        efc: float,
        total_aid: float,
    ) -> float:
        """Calculate unmet financial need.

        Args:
            cost_of_attendance: Total COA
            efc: Expected Family Contribution
            total_aid: Total aid received

        Returns:
            Unmet need (gap between need and aid)
        """
        demonstrated_need = max(0, cost_of_attendance - efc)
        unmet_need = max(0, demonstrated_need - total_aid)
        return unmet_need

    def format_aid_summary(self, summary: AidSummary) -> str:
        """Format aid summary as human-readable text.

        Args:
            summary: AidSummary object

        Returns:
            Formatted string
        """
        return f"""
Financial Aid Summary
=====================

Total Cost of Attendance: ${summary.total_cost:,.0f}

Free Money (No Repayment):
  - Grants: ${summary.total_grants:,.0f}
  - Scholarships: ${summary.total_scholarships:,.0f}
  - Total Free: ${(summary.total_grants + summary.total_scholarships):,.0f}

Work Study: ${summary.total_work_study:,.0f}

Loans: ${summary.total_loans:,.0f}

Your Numbers:
  - Net Price (after free money): ${summary.net_price:,.0f}
  - Out of Pocket: ${summary.out_of_pocket:,.0f}

4-Year Projection:
  - Total Debt: ${summary.total_debt_4_years:,.0f}
  - Monthly Payment (after graduation): ${summary.monthly_payment_estimate:,.0f}
""".strip()
