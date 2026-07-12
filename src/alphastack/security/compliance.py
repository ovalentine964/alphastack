"""Compliance — Kenya CMA requirements, risk disclosure, ToS, data protection.

Implements compliance_mapping from architecture_security.md and
research_regulatory.md:
- Kenya CMA regulatory requirements
- Risk disclosure generation
- Terms of service templates
- Data protection (GDPR / Kenya DPA)
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------

class Jurisdiction(str, Enum):
    KENYA = "KE"
    EU = "EU"
    SOUTH_AFRICA = "ZA"
    NIGERIA = "NG"
    UK = "UK"
    US = "US"  # blocked
    GLOBAL = "GLOBAL"


class DataRegulation(str, Enum):
    KENYA_DPA = "kenya_dpa"
    GDPR = "gdpr"
    POPIA = "popia"  # South Africa
    NDPA = "ndpa"  # Nigeria
    VASP = "vasp_kenya"  # Virtual Asset Service Providers Act 2025


# Blocked jurisdictions (geo-blocking list)
BLOCKED_JURISDICTIONS: set[str] = {"US", "KP", "IR", "SY", "CU"}


# ---------------------------------------------------------------------------
# Risk Disclosure
# ---------------------------------------------------------------------------

class RiskDisclosure:
    """Generate risk disclosure text for trading products."""

    FOREX_RISK = (
        "⚠️ RISK WARNING: Trading foreign exchange on margin carries a high "
        "level of risk and may not be suitable for all investors. The high "
        "degree of leverage can work against you as well as for you. Before "
        "deciding to trade foreign exchange, you should carefully consider "
        "your investment objectives, level of experience, and risk appetite. "
        "There is a possibility that you could sustain a loss of some or all "
        "of your initial investment and therefore you should not invest money "
        "that you cannot afford to lose. You should be aware of all the risks "
        "associated with foreign exchange trading and seek advice from an "
        "independent financial advisor if you have any doubts."
    )

    CRYPTO_RISK = (
        "⚠️ CRYPTO RISK WARNING: Cryptocurrency trading is highly speculative "
        "and involves a significant risk of loss. Prices can fluctuate widely "
        "on any given day. Due to such price fluctuations, you may gain or "
        "lose value of your assets at any moment. Cryptocurrency may be "
        "subject to rapid and substantial price decreases. You should not "
        "invest more than you can afford to lose."
    )

    ALGO_RISK = (
        "⚠️ ALGORITHMIC TRADING RISK: Automated trading systems carry "
        "additional risks including but not limited to: connectivity failures, "
        "software bugs, data feed errors, unexpected market conditions, and "
        "execution delays. Past performance of any trading strategy is not "
        "indicative of future results. You remain responsible for all trades "
        "executed through your account."
    )

    LEVERAGE_RISK = (
        "⚠️ LEVERAGE RISK: Leveraged trading can amplify both gains and "
        "losses. You may lose more than your initial deposit. Ensure you "
        "understand the mechanics of leverage before trading."
    )

    PAST_PERFORMANCE = (
        "Past performance is not indicative of future results. Any "
        "hypothetical performance data shown is for illustrative purposes "
        "only and does not represent actual trading."
    )

    NOT_ADVICE = (
        "AlphaStack is a software tool and does not provide investment advice. "
        "All trading decisions are your own. You should consult a qualified "
        "financial advisor before making investment decisions."
    )

    @classmethod
    def full_disclaimer(cls, products: list[str] | None = None) -> str:
        """Generate a complete risk disclosure document."""
        products = products or ["forex"]
        sections = []
        for p in products:
            if p == "forex":
                sections.append(cls.FOREX_RISK)
            elif p == "crypto":
                sections.append(cls.CRYPTO_RISK)
            elif p == "algo":
                sections.append(cls.ALGO_RISK)
            elif p == "leverage":
                sections.append(cls.LEVERAGE_RISK)
        sections.extend([cls.PAST_PERFORMANCE, cls.NOT_ADVICE])
        return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Terms of Service generator
# ---------------------------------------------------------------------------

class TermsOfService:
    """Generate Terms of Service for AlphaStack."""

    TEMPLATE = """# Terms of Service — AlphaStack

**Effective Date:** {effective_date}
**Last Updated:** {last_updated}

## 1. Acceptance of Terms
By accessing or using AlphaStack ("the Service"), you agree to be bound by
these Terms of Service. If you do not agree, do not use the Service.

## 2. Description of Service
AlphaStack is a multi-agent AI trading system that provides automated trading
capabilities, market analysis, and portfolio management tools. The Service
connects to third-party brokers for trade execution.

## 3. Eligibility
- You must be at least 18 years old.
- You must not be a resident of a blocked jurisdiction ({blocked_jurisdictions}).
- You must have the legal capacity to enter into binding agreements.

## 4. Risk Acknowledgment
{risk_disclosure}

By using the Service, you acknowledge that you have read, understood, and
accepted the risks described above.

## 5. User Responsibilities
- You are solely responsible for all trading decisions and their outcomes.
- You must keep your account credentials secure.
- You must not use the Service for any illegal purpose.
- You must comply with all applicable laws and regulations.

## 6. No Investment Advice
AlphaStack does not provide investment, financial, tax, or legal advice.
All information provided is for educational and informational purposes only.

## 7. Fees and Payment
{fee_section}

## 8. Intellectual Property
All software, algorithms, models, and content within AlphaStack are the
intellectual property of AlphaStack and are protected by applicable laws.

## 9. Limitation of Liability
To the maximum extent permitted by law, AlphaStack shall not be liable for:
- Any trading losses incurred through use of the Service
- Indirect, incidental, consequential, or punitive damages
- Loss of profits, data, or business opportunities

## 10. Data Protection
{data_protection_section}

## 11. Termination
Either party may terminate at any time. Upon termination:
- Your access to the Service will be revoked
- Outstanding trades will be managed per your last instructions
- Data will be retained as required by law

## 12. Governing Law
These Terms are governed by the laws of the Republic of Kenya. Disputes
shall be resolved through arbitration in Nairobi, Kenya.

## 13. Dispute Resolution
Any disputes arising from these Terms shall first be attempted to be
resolved through good-faith negotiation. If unresolved within 30 days,
disputes shall be submitted to arbitration under the Nairobi Centre for
International Arbitration (NCIA) rules.

## 14. Amendments
We may update these Terms from time to time. Continued use of the Service
after changes constitutes acceptance of the updated Terms.

## 15. Contact
For questions about these Terms, contact: legal@alphastack.io
"""

    @classmethod
    def generate(
        cls,
        *,
        products: list[str] | None = None,
        fee_description: str = "Fees are as described on the pricing page at the time of purchase.",
    ) -> str:
        today = datetime.date.today().isoformat()
        return cls.TEMPLATE.format(
            effective_date=today,
            last_updated=today,
            blocked_jurisdictions=", ".join(sorted(BLOCKED_JURISDICTIONS)),
            risk_disclosure=RiskDisclosure.full_disclaimer(products),
            fee_section=fee_description,
            data_protection_section=(
                "Your personal data is processed in accordance with our Privacy "
                "Policy. We comply with the Kenya Data Protection Act 2019 and, "
                "where applicable, the EU General Data Protection Regulation (GDPR). "
                "See our Privacy Policy for full details."
            ),
        )


# ---------------------------------------------------------------------------
# Privacy Policy helper
# ---------------------------------------------------------------------------

@dataclass
class DataProcessingRecord:
    """A record of data processing activities (GDPR Art. 30)."""
    purpose: str
    categories_of_data: list[str]
    legal_basis: str
    retention_period: str
    recipients: list[str] = field(default_factory=list)
    cross_border_transfers: list[str] = field(default_factory=list)


class PrivacyPolicyBuilder:
    """Build a GDPR/Kenya DPA-compliant privacy policy."""

    DEFAULT_RECORDS: list[DataProcessingRecord] = [
        DataProcessingRecord(
            purpose="Account creation and authentication",
            categories_of_data=["Email", "Name", "Password hash", "IP address"],
            legal_basis="Contract (Art. 6(1)(b))",
            retention_period="Account lifetime + 7 years",
        ),
        DataProcessingRecord(
            purpose="Trade execution and record-keeping",
            categories_of_data=["Trade history", "Order parameters", "Broker account ID"],
            legal_basis="Contract (Art. 6(1)(b))",
            retention_period="7 years (regulatory requirement)",
        ),
        DataProcessingRecord(
            purpose="Security and fraud prevention",
            categories_of_data=["IP address", "Device fingerprint", "Login history"],
            legal_basis="Legitimate interest (Art. 6(1)(f))",
            retention_period="2 years",
        ),
        DataProcessingRecord(
            purpose="Service improvement and analytics",
            categories_of_data=["Usage patterns", "Error logs"],
            legal_basis="Legitimate interest (Art. 6(1)(f))",
            retention_period="1 year (anonymized after)",
        ),
    ]

    @classmethod
    def get_records(cls) -> list[DataProcessingRecord]:
        return cls.DEFAULT_RECORDS


# ---------------------------------------------------------------------------
# Compliance Manager
# ---------------------------------------------------------------------------

class ComplianceManager:
    """Central compliance service — geo-blocking, consent, data rights."""

    def __init__(self) -> None:
        self._consent_records: dict[str, dict[str, bool]] = {}
        self._data_access_requests: list[dict[str, Any]] = []

    # -- Geo-blocking -------------------------------------------------------

    @staticmethod
    def is_blocked_jurisdiction(country_code: str) -> bool:
        return country_code.upper() in BLOCKED_JURISDICTIONS

    @staticmethod
    def check_jurisdiction(country_code: str) -> None:
        """Raise if jurisdiction is blocked."""
        if ComplianceManager.is_blocked_jurisdiction(country_code):
            raise PermissionError(
                f"AlphaStack is not available in your jurisdiction ({country_code}). "
                "This restriction is in place for regulatory compliance."
            )

    # -- Consent management -------------------------------------------------

    def record_consent(
        self,
        user_id: str,
        consents: dict[str, bool],
    ) -> None:
        """Record user consent choices."""
        self._consent_records[user_id] = {
            **self._consent_records.get(user_id, {}),
            **consents,
            "_timestamp": True,  # type: ignore[dict-item]
        }

    def has_consent(self, user_id: str, purpose: str) -> bool:
        return self._consent_records.get(user_id, {}).get(purpose, False)

    # -- Data subject rights (GDPR / Kenya DPA) ----------------------------

    def handle_data_access_request(self, user_id: str) -> dict[str, Any]:
        """GDPR Art. 15 — Right of access."""
        request = {
            "user_id": user_id,
            "request_type": "data_access",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "status": "received",
        }
        self._data_access_requests.append(request)
        return request

    def handle_erasure_request(self, user_id: str) -> dict[str, Any]:
        """GDPR Art. 17 — Right to erasure (with legal exceptions)."""
        request = {
            "user_id": user_id,
            "request_type": "erasure",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "status": "received",
            "note": (
                "Trading records will be retained for 7 years as required by "
                "Kenya CMA regulations. Personal data not subject to legal "
                "retention will be erased within 30 days."
            ),
        }
        self._data_access_requests.append(request)
        return request

    def handle_portability_request(self, user_id: str) -> dict[str, Any]:
        """GDPR Art. 20 — Right to data portability."""
        request = {
            "user_id": user_id,
            "request_type": "portability",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "status": "received",
        }
        self._data_access_requests.append(request)
        return request

    # -- Breach notification ------------------------------------------------

    @staticmethod
    def breach_notification_deadline() -> datetime.datetime:
        """72-hour breach notification deadline (GDPR Art. 33 / Kenya DPA §43)."""
        return datetime.datetime.utcnow() + datetime.timedelta(hours=72)

    # -- CMA specific -------------------------------------------------------

    @staticmethod
    def cma_risk_disclosure_required() -> bool:
        """Kenya CMA requires risk warnings on all forex products."""
        return True

    @staticmethod
    def generate_cma_compliance_text() -> str:
        return (
            "This service is provided by a software tool and is not a "
            "CMA-licensed investment advisory service. Trading in leveraged "
            "foreign exchange products carries significant risk. The Capital "
            "Markets Authority does not regulate the software itself. Clients "
            "trade through CMA-licensed non-dealing online forex brokers. "
            "Please ensure your broker holds a valid CMA license."
        )
