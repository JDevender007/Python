"""CRUD operations and reporting queries for the CRM System."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any


# --------------------------------------------------------------------------- #
# Customers
# --------------------------------------------------------------------------- #
def add_customer(
    conn: sqlite3.Connection,
    *,
    name: str,
    email: str,
    phone: str,
    company: str = "",
    created_on: str | None = None,
) -> int:
    """Create a customer and return its id."""
    cur = conn.execute(
        """
        INSERT INTO customers (name, email, phone, company, created_on)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name.strip(), email.strip(), phone.strip(), company.strip(),
         created_on or date.today().isoformat()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_customers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Customers with their interaction and deal counts."""
    return conn.execute(
        """
        SELECT c.id, c.name, c.email, c.phone, c.company, c.created_on,
               (SELECT COUNT(*) FROM interactions i WHERE i.customer_id = c.id) AS interactions,
               (SELECT COUNT(*) FROM deals d WHERE d.customer_id = c.id) AS deals
        FROM customers c
        ORDER BY c.name
        """
    ).fetchall()


def get_customer(conn: sqlite3.Connection, customer_id: int) -> sqlite3.Row | None:
    """Fetch one customer with their open deal value."""
    return conn.execute(
        """
        SELECT c.*,
               COALESCE(SUM(CASE WHEN d.stage NOT IN ('won', 'lost') THEN d.value ELSE 0 END), 0) AS open_pipeline,
               COALESCE(SUM(CASE WHEN d.stage = 'won' THEN d.value ELSE 0 END), 0) AS won_value
        FROM customers c
        LEFT JOIN deals d ON d.customer_id = c.id
        WHERE c.id = ?
        GROUP BY c.id
        """,
        (customer_id,),
    ).fetchone()


def search_customers(conn: sqlite3.Connection, term: str) -> list[sqlite3.Row]:
    """Case-insensitive search over name, email, phone and company."""
    like = f"%{term.strip()}%"
    return conn.execute(
        """
        SELECT id, name, email, phone, company
        FROM customers
        WHERE name LIKE ? COLLATE NOCASE
           OR email LIKE ? COLLATE NOCASE
           OR phone LIKE ? COLLATE NOCASE
           OR company LIKE ? COLLATE NOCASE
        ORDER BY name
        """,
        (like, like, like, like),
    ).fetchall()


# --------------------------------------------------------------------------- #
# Leads
# --------------------------------------------------------------------------- #
def add_lead(
    conn: sqlite3.Connection,
    *,
    name: str,
    email: str,
    source: str = "inbound",
    score: int = 0,
    created_on: str | None = None,
) -> int:
    """Create a lead in the 'new' state."""
    cur = conn.execute(
        """
        INSERT INTO leads (customer_id, name, email, source, status, score, created_on)
        VALUES (NULL, ?, ?, ?, 'new', ?, ?)
        """,
        (name.strip(), email.strip(), source.strip(), int(score),
         created_on or date.today().isoformat()),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_lead_status(conn: sqlite3.Connection, lead_id: int, status: str) -> bool:
    """Move a lead through the funnel."""
    allowed = {"new", "contacted", "qualified", "converted", "lost"}
    if status not in allowed:
        raise ValueError(f"invalid status: {status}")
    cur = conn.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
    conn.commit()
    return cur.rowcount > 0


def convert_lead(conn: sqlite3.Connection, lead_id: int, *, phone: str, company: str = "") -> int | None:
    """Convert a lead into a customer and link the two rows.

    Returns the new customer id, or None when the lead does not exist.
    """
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if lead is None:
        return None

    customer_id = add_customer(
        conn,
        name=lead["name"],
        email=lead["email"],
        phone=phone,
        company=company,
    )
    conn.execute(
        "UPDATE leads SET status = 'converted', customer_id = ? WHERE id = ?",
        (customer_id, lead_id),
    )
    conn.commit()
    return customer_id


def list_leads(conn: sqlite3.Connection, status: str | None = None) -> list[sqlite3.Row]:
    """Leads, optionally filtered by funnel status."""
    sql = "SELECT id, name, email, source, status, score, created_on FROM leads"
    params: tuple = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY score DESC, id"
    return conn.execute(sql, params).fetchall()


# --------------------------------------------------------------------------- #
# Interactions & follow-ups
# --------------------------------------------------------------------------- #
def log_interaction(
    conn: sqlite3.Connection,
    customer_id: int,
    kind: str,
    summary: str,
    created_on: str | None = None,
) -> int:
    """Record a call/email/meeting/note against a customer."""
    if kind not in {"call", "email", "meeting", "note"}:
        raise ValueError(f"invalid interaction kind: {kind}")
    cur = conn.execute(
        """
        INSERT INTO interactions (customer_id, kind, summary, created_on)
        VALUES (?, ?, ?, ?)
        """,
        (customer_id, kind, summary.strip(), created_on or date.today().isoformat()),
    )
    conn.commit()
    return int(cur.lastrowid)


def interaction_history(conn: sqlite3.Connection, customer_id: int) -> list[sqlite3.Row]:
    """Everything logged for one customer, newest first."""
    return conn.execute(
        """
        SELECT kind, summary, created_on
        FROM interactions
        WHERE customer_id = ?
        ORDER BY created_on DESC, id DESC
        """,
        (customer_id,),
    ).fetchall()


def follow_ups(conn: sqlite3.Connection, days: int = 7) -> list[sqlite3.Row]:
    """Deals closing within N days that are not won/lost yet."""
    today = date.today()
    horizon = (today + timedelta(days=max(0, days))).isoformat()
    return conn.execute(
        """
        SELECT d.id, d.title, d.value, d.stage, d.close_on, c.name AS customer_name
        FROM deals d
        JOIN customers c ON c.id = d.customer_id
        WHERE d.stage NOT IN ('won', 'lost')
          AND d.close_on <= ?
        ORDER BY d.close_on
        """,
        (horizon,),
    ).fetchall()


# --------------------------------------------------------------------------- #
# Deals & pipeline
# --------------------------------------------------------------------------- #
def add_deal(
    conn: sqlite3.Connection,
    *,
    customer_id: int,
    title: str,
    value: float,
    stage: str = "prospecting",
    close_on: str | None = None,
) -> int:
    """Create a deal."""
    if stage not in {"prospecting", "proposal", "negotiation", "won", "lost"}:
        raise ValueError(f"invalid stage: {stage}")
    cur = conn.execute(
        """
        INSERT INTO deals (customer_id, title, value, stage, close_on)
        VALUES (?, ?, ?, ?, ?)
        """,
        (customer_id, title.strip(), float(value), stage,
         close_on or date.today().isoformat()),
    )
    conn.commit()
    return int(cur.lastrowid)


def move_deal(conn: sqlite3.Connection, deal_id: int, stage: str) -> bool:
    """Update a deal's pipeline stage."""
    if stage not in {"prospecting", "proposal", "negotiation", "won", "lost"}:
        raise ValueError(f"invalid stage: {stage}")
    cur = conn.execute("UPDATE deals SET stage = ? WHERE id = ?", (stage, deal_id))
    conn.commit()
    return cur.rowcount > 0


def pipeline_summary(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Deal count and value grouped by stage."""
    return conn.execute(
        """
        SELECT stage,
               COUNT(*) AS deals,
               SUM(value) AS value
        FROM deals
        GROUP BY stage
        ORDER BY CASE stage
                    WHEN 'prospecting' THEN 1
                    WHEN 'proposal' THEN 2
                    WHEN 'negotiation' THEN 3
                    WHEN 'won' THEN 4
                    ELSE 5
                 END
        """
    ).fetchall()


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def lead_funnel(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Leads grouped by status."""
    return conn.execute(
        """
        SELECT status, COUNT(*) AS leads, ROUND(AVG(score), 1) AS avg_score
        FROM leads
        GROUP BY status
        ORDER BY leads DESC
        """
    ).fetchall()


def kpi_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Headline CRM numbers used by the demo report."""
    row = conn.execute(
        """
        SELECT (SELECT COUNT(*) FROM customers) AS customers,
               (SELECT COUNT(*) FROM leads) AS leads,
               (SELECT COUNT(*) FROM leads WHERE status = 'converted') AS converted,
               (SELECT COUNT(*) FROM interactions) AS interactions,
               (SELECT COALESCE(SUM(value), 0) FROM deals WHERE stage = 'won') AS won_value,
               (SELECT COALESCE(SUM(value), 0) FROM deals
                 WHERE stage NOT IN ('won', 'lost')) AS open_pipeline
        """
    ).fetchone()
    return dict(row)


def top_customers(conn: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    """Customers ranked by won + open deal value."""
    return conn.execute(
        """
        SELECT c.name, c.company,
               COALESCE(SUM(d.value), 0) AS total_value,
               COUNT(d.id) AS deals
        FROM customers c
        LEFT JOIN deals d ON d.customer_id = c.id
        GROUP BY c.id
        ORDER BY total_value DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
