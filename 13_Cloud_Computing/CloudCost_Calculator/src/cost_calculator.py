"""Cloud cost calculation from a small JSON infrastructure description.

Pricing tables are illustrative, bundled, and static - no API calls, no
scraping. The calculator turns a resource config (compute, storage,
bandwidth, database) into line items, a monthly total, plan-comparison
savings, and budget status. Point the tables at your own negotiated rates
to make the numbers real.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOG = logging.getLogger("cloud.cost")

DEFAULT_HOURS = 730  # average hours in a month (8760 / 12)


class CostError(RuntimeError):
    """Raised for invalid configs and unknown resource/instance names."""


# --------------------------------------------------------------------------- #
# Pricing model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class InstancePricing:
    """Hourly prices for one instance/VM/DB shape."""

    name: str
    vcpus: float
    memory_gb: float
    on_demand: float
    reserved_1yr: float  # hourly effective rate
    reserved_3yr: float

    def hourly(self, plan: str) -> float:
        """Effective hourly rate for a purchase plan."""
        rates = {
            "ondemand": self.on_demand,
            "1yr": self.reserved_1yr,
            "3yr": self.reserved_3yr,
        }
        if plan not in rates:
            raise CostError(f"unknown plan {plan!r} (choose ondemand/1yr/3yr)")
        return rates[plan]


@dataclass(frozen=True)
class ProviderPricing:
    """One provider's bundled rate card."""

    provider: str
    instances: dict[str, InstancePricing]
    databases: dict[str, InstancePricing]
    storage: dict[str, float]      # class -> USD per GB-month
    bandwidth_out: float           # USD per GB egress


PROVIDERS: dict[str, ProviderPricing] = {
    "aws": ProviderPricing(
        provider="aws",
        instances={
            "t3.micro": InstancePricing("t3.micro", 2, 1, 0.0104, 0.0065, 0.0041),
            "t3.medium": InstancePricing("t3.medium", 2, 4, 0.0416, 0.0262, 0.0165),
            "m5.large": InstancePricing("m5.large", 2, 8, 0.096, 0.0605, 0.0380),
            "m5.xlarge": InstancePricing("m5.xlarge", 4, 16, 0.192, 0.1210, 0.0760),
            "c5.large": InstancePricing("c5.large", 2, 4, 0.085, 0.0536, 0.0338),
        },
        databases={
            "db.t3.micro": InstancePricing("db.t3.micro", 2, 1, 0.018, 0.0114, 0.0071),
            "db.m5.large": InstancePricing("db.m5.large", 2, 8, 0.175, 0.1105, 0.0695),
            "db.m5.xlarge": InstancePricing("db.m5.xlarge", 4, 16, 0.350, 0.2210, 0.1390),
        },
        storage={"gp3": 0.08, "gp2": 0.10, "standard": 0.023},
        bandwidth_out=0.09,
    ),
    "gcp": ProviderPricing(
        provider="gcp",
        instances={
            "e2-micro": InstancePricing("e2-micro", 2, 1, 0.0083, 0.0052, 0.0033),
            "e2-medium": InstancePricing("e2-medium", 2, 4, 0.0334, 0.0210, 0.0132),
            "e2-standard-2": InstancePricing("e2-standard-2", 2, 8, 0.0670, 0.0422, 0.0265),
            "e2-standard-4": InstancePricing("e2-standard-4", 4, 16, 0.1340, 0.0844, 0.0530),
            "e2-highcpu-2": InstancePricing("e2-highcpu-2", 2, 2, 0.0434, 0.0273, 0.0172),
        },
        databases={
            "db-g1-small": InstancePricing("db-g1-small", 1, 1.7, 0.0366, 0.0231, 0.0145),
            "db-custom-2-8192": InstancePricing("db-custom-2-8192", 2, 8, 0.1548, 0.0977, 0.0614),
            "db-custom-4-16384": InstancePricing("db-custom-4-16384", 4, 16, 0.3096, 0.1954, 0.1228),
        },
        storage={"pd-ssd": 0.17, "pd-balanced": 0.10, "pd-standard": 0.02},
        bandwidth_out=0.085,
    ),
}

PLANS = ("ondemand", "1yr", "3yr")

# Closest equivalents when comparing the same footprint across providers.
SHAPE_ALIASES: dict[str, dict[str, str]] = {
    "gcp": {
        # compute
        "t3.micro": "e2-micro",
        "t3.medium": "e2-medium",
        "m5.large": "e2-standard-2",
        "m5.xlarge": "e2-standard-4",
        "c5.large": "e2-highcpu-2",
        # database
        "db.t3.micro": "db-g1-small",
        "db.m5.large": "db-custom-2-8192",
        "db.m5.xlarge": "db-custom-4-16384",
        # storage classes
        "gp3": "pd-ssd",
        "gp2": "pd-balanced",
        "standard": "pd-standard",
    },
}


def translate_config(config: dict[str, Any], provider: str) -> dict[str, Any]:
    """Return a copy of `config` with instance/storage names mapped to `provider`."""
    aliases = SHAPE_ALIASES.get(provider.lower(), {})
    translated = json.loads(json.dumps(config))  # deep copy, JSON-safe
    translated["provider"] = provider
    for resource in translated.get("resources", []):
        if not isinstance(resource, dict):
            continue
        if "instance" in resource:
            resource["instance"] = aliases.get(
                str(resource["instance"]), resource["instance"]
            )
        if "class" in resource:
            resource["class"] = aliases.get(str(resource["class"]), resource["class"])
    return translated


# --------------------------------------------------------------------------- #
# Config and line items
# --------------------------------------------------------------------------- #
@dataclass
class LineItem:
    """One priced line of the monthly bill."""

    category: str        # compute | storage | bandwidth | database
    description: str
    quantity: str        # human unit, e.g. "3 x 730 h" or "500 GB"
    unit_price: float    # per unit
    amount: float        # quantity * unit_price (rounded at render time)
    plan: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": round(self.unit_price, 6),
            "amount": round(self.amount, 2),
            "plan": self.plan,
        }


@dataclass
class CostReport:
    """Full calculation result."""

    provider: str
    hours_per_month: int
    items: list[LineItem] = field(default_factory=list)
    budget: float | None = None

    @property
    def total(self) -> float:
        return round(sum(item.amount for item in self.items), 2)

    @property
    def by_category(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for item in self.items:
            totals[item.category] = round(
                totals.get(item.category, 0.0) + item.amount, 2
            )
        return totals

    @property
    def budget_ok(self) -> bool:
        if self.budget is None:
            return True
        return self.total <= self.budget

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "hours_per_month": self.hours_per_month,
            "items": [item.to_dict() for item in self.items],
            "by_category": self.by_category,
            "total": self.total,
            "budget": self.budget,
            "budget_ok": self.budget_ok,
        }


def load_config(path: str | Path) -> dict[str, Any]:
    """Load and minimally validate a JSON infrastructure config."""
    source = Path(path)
    if not source.is_file():
        raise CostError(f"config not found: {source}")
    try:
        config = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CostError(f"config is not valid JSON: {exc}") from exc
    if not isinstance(config, dict):
        raise CostError("config root must be a JSON object")
    if "resources" not in config or not isinstance(config["resources"], list):
        raise CostError("config must contain a 'resources' array")
    return config


# --------------------------------------------------------------------------- #
# Pricing helpers
# --------------------------------------------------------------------------- #
def get_provider(name: str) -> ProviderPricing:
    """Look up a bundled provider rate card."""
    provider = PROVIDERS.get(name.lower())
    if provider is None:
        raise CostError(
            f"unknown provider {name!r} (available: {', '.join(sorted(PROVIDERS))})"
        )
    return provider


def _plan(resource: dict[str, Any]) -> str:
    plan = str(resource.get("plan", "ondemand")).lower()
    if plan not in PLANS:
        raise CostError(f"unknown plan {plan!r} (choose {', '.join(PLANS)})")
    return plan


def _positive_number(resource: dict[str, Any], field_name: str) -> float:
    value = resource.get(field_name)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise CostError(f"resource field {field_name!r} must be a non-negative number")
    return float(value)


def _positive_int(resource: dict[str, Any], field_name: str, default: int) -> int:
    """Read an int field, falling back to `default` when absent or zero."""
    value = resource.get(field_name, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise CostError(f"resource field {field_name!r} must be a positive integer")
    return value if value > 0 else default


# --------------------------------------------------------------------------- #
# Calculation
# --------------------------------------------------------------------------- #
def price_resource(
    resource: dict[str, Any],
    provider: ProviderPricing,
    default_hours: int,
) -> LineItem:
    """Price a single resource entry from the config."""
    if not isinstance(resource, dict):
        raise CostError("each resource must be an object")
    kind = str(resource.get("type", "")).lower()

    if kind == "compute":
        name = str(resource.get("instance", ""))
        shape = provider.instances.get(name)
        if shape is None:
            raise CostError(
                f"unknown compute instance {name!r} for {provider.provider} "
                f"(available: {', '.join(sorted(provider.instances))})"
            )
        count = _positive_int(resource, "count", 1)
        hours = _positive_int(resource, "hours", default_hours)
        plan = _plan(resource)
        hourly = shape.hourly(plan)
        amount = count * hours * hourly
        return LineItem(
            category="compute",
            description=f"{count} x {name}",
            quantity=f"{count} x {hours} h @ {hourly:.4f}",
            unit_price=hourly,
            amount=amount,
            plan=plan,
        )

    if kind == "database":
        name = str(resource.get("instance", ""))
        shape = provider.databases.get(name)
        if shape is None:
            raise CostError(
                f"unknown database instance {name!r} for {provider.provider} "
                f"(available: {', '.join(sorted(provider.databases))})"
            )
        count = _positive_int(resource, "count", 1)
        hours = _positive_int(resource, "hours", default_hours)
        plan = _plan(resource)
        hourly = shape.hourly(plan)
        return LineItem(
            category="database",
            description=f"{count} x {name}",
            quantity=f"{count} x {hours} h @ {hourly:.4f}",
            unit_price=hourly,
            amount=count * hours * hourly,
            plan=plan,
        )

    if kind == "storage":
        storage_class = str(resource.get("class", "gp3"))
        price = provider.storage.get(storage_class)
        if price is None:
            raise CostError(
                f"unknown storage class {storage_class!r} for {provider.provider} "
                f"(available: {', '.join(sorted(provider.storage))})"
            )
        size = _positive_number(resource, "size_gb")
        return LineItem(
            category="storage",
            description=f"{size:g} GB {storage_class}",
            quantity=f"{size:g} GB-mo @ {price:.3f}",
            unit_price=price,
            amount=size * price,
        )

    if kind == "bandwidth":
        gb = _positive_number(resource, "gb_out")
        price = provider.bandwidth_out
        return LineItem(
            category="bandwidth",
            description=f"{gb:g} GB egress",
            quantity=f"{gb:g} GB @ {price:.3f}",
            unit_price=price,
            amount=gb * price,
        )

    raise CostError(
        f"unknown resource type {kind!r} "
        "(choose compute/storage/bandwidth/database)"
    )


def calculate(config: dict[str, Any], provider_name: str | None = None) -> CostReport:
    """Price an entire config into a CostReport."""
    name = provider_name or str(config.get("provider", "aws"))
    provider = get_provider(name)
    hours = int(config.get("hours_per_month", DEFAULT_HOURS))
    if hours <= 0 or hours > 8784:
        raise CostError("hours_per_month must be between 1 and 8784")

    budget = config.get("budget")
    if budget is not None and (
        not isinstance(budget, (int, float)) or isinstance(budget, bool) or budget < 0
    ):
        raise CostError("budget must be a non-negative number")

    report = CostReport(provider=provider.provider, hours_per_month=hours,
                        budget=float(budget) if budget is not None else None)
    for resource in config["resources"]:
        report.items.append(price_resource(resource, provider, hours))
    LOG.info("calculated %s: %d items, total %.2f",
             provider.provider, len(report.items), report.total)
    return report


def plan_comparison(config: dict[str, Any], provider_name: str | None = None) -> dict[str, float]:
    """Total the config under each purchase plan (compute/database swap)."""
    totals: dict[str, float] = {}
    for plan in PLANS:
        variant = json.loads(json.dumps(config))  # deep copy, JSON-safe
        for resource in variant.get("resources", []):
            if isinstance(resource, dict) and resource.get("type") in ("compute", "database"):
                resource["plan"] = plan
        totals[plan] = calculate(variant, provider_name).total
    return totals


def savings_tips(report: CostReport) -> list[str]:
    """Concrete savings advice based on the current report."""
    tips: list[str] = []
    tipped: set[str] = set()
    for item in report.items:
        if item.category not in ("compute", "database"):
            continue
        if item.category in tipped or item.plan != "ondemand":
            continue
        # find the hourly rate of the same shape under reservations
        provider = get_provider(report.provider)
        table = provider.instances if item.category == "compute" else provider.databases
        shape_name = item.description.split(" x ", 1)[-1]
        shape = table.get(shape_name)
        if shape is None:
            continue
        count = int(item.description.split(" x ", 1)[0])
        hours = report.hours_per_month
        current = count * hours * shape.on_demand
        for plan, label in (("1yr", "1-year"), ("3yr", "3-year")):
            alternative = count * hours * shape.hourly(plan)
            saved = current - alternative
            if saved > 0:
                tips.append(
                    f"Move {count} x {shape_name} ({item.category}) to a "
                    f"{label} reservation: save ${saved:.2f}/mo "
                    f"({saved / current * 100:.0f}%)."
                )
        tipped.add(item.category)  # one tip-set per category keeps output readable
    if any(i.category == "bandwidth" for i in report.items):
        tips.append("Cache or compress egress-heavy responses to cut bandwidth cost.")
    storage_total = report.by_category.get("storage", 0.0)
    if storage_total > 50:
        tips.append(
            f"Storage is ${storage_total:.2f}/mo - review snapshots and "
            "lifecycle old objects to a cheaper class."
        )
    return tips


def render_report(report: CostReport) -> str:
    """Human-readable bill used by the CLI and demo."""
    lines = [
        f"Provider : {report.provider}",
        f"Hours/mo : {report.hours_per_month}",
        "",
        f"{'Category':<11} {'Description':<28} {'Amount':>10}",
        "-" * 53,
    ]
    for item in report.items:
        plan = f" [{item.plan}]" if item.plan else ""
        lines.append(
            f"{item.category:<11} {item.description + plan:<28} "
            f"{item.amount:>10.2f}"
        )
    lines.append("-" * 53)
    lines.append(f"{'TOTAL':<40} {report.total:>10.2f} USD/mo")

    lines.append("")
    lines.append("By category: " + ", ".join(
        f"{k}=${v:.2f}" for k, v in sorted(report.by_category.items())
    ))

    if report.budget is not None:
        pct = (report.total / report.budget * 100) if report.budget else 0.0
        status = "OK" if report.budget_ok else "OVER BUDGET"
        lines.append(
            f"Budget   : ${report.budget:.2f}/mo -> "
            f"{report.total:.2f} ({pct:.1f}%) [{status}]"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def demo_config() -> dict[str, Any]:
    """A small but realistic web-app footprint (illustrative rates)."""
    return {
        "provider": "aws",
        "hours_per_month": DEFAULT_HOURS,
        "budget": 600,
        "resources": [
            {"type": "compute", "instance": "t3.medium", "count": 3, "plan": "ondemand"},
            {"type": "compute", "instance": "m5.large", "count": 1, "plan": "ondemand"},
            {"type": "database", "instance": "db.m5.large", "count": 1, "plan": "ondemand"},
            {"type": "storage", "class": "gp3", "size_gb": 500},
            {"type": "storage", "class": "standard", "size_gb": 2000},
            {"type": "bandwidth", "gb_out": 2000},
        ],
    }


def run_demo() -> int:
    """Price the bundled sample infrastructure - fully offline."""
    print("=" * 60)
    print(" CLOUD COST CALCULATOR - offline demo")
    print(" Illustrative bundled rates - no API calls, no scraping.")
    print("=" * 60)

    config = demo_config()
    report = calculate(config)

    print()
    print(render_report(report))

    print("\nPlan comparison for compute + database:")
    comparison = plan_comparison(config)
    baseline = comparison["ondemand"]
    for plan, total in comparison.items():
        delta = total - baseline
        note = " (baseline)" if plan == "ondemand" else f" ({delta:+.2f} vs ondemand)"
        print(f"  {plan:<9} ${total:>8.2f}/mo{note}")

    print("\nSavings tips:")
    tips = savings_tips(report)
    for tip in tips:
        print(f"  - {tip}")
    if not tips:
        print("  - Nothing obvious; you are already on a lean plan.")

    # same footprint on a second provider (closest shapes), for context
    gcp_report = calculate(translate_config(config, "gcp"))
    print(f"\nSame footprint on gcp (closest shapes): ${gcp_report.total:.2f}/mo")

    print("\nDemo completed successfully.")
    return 0
