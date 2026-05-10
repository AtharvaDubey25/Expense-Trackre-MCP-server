from fastmcp import FastMCP
import aiosqlite
import os
import tempfile
import json

# --------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------

TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

print(f"Database path: {DB_PATH}")

# --------------------------------------------------------------------------------
# MCP Server
# --------------------------------------------------------------------------------

mcp = FastMCP("Expense Tracker")

# --------------------------------------------------------------------------------
# Database Initialization
# --------------------------------------------------------------------------------

def init_db():
    try:
        import sqlite3

        with sqlite3.connect(DB_PATH) as c:

            # Better concurrency
            c.execute("PRAGMA journal_mode=WAL")

            c.execute("""
                CREATE TABLE IF NOT EXISTS expenses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT ''
                )
            """)

            c.commit()

        print("Database initialized successfully")

    except Exception as e:
        print(f"Database initialization error: {e}")
        raise


init_db()

# --------------------------------------------------------------------------------
# MCP Tools
# --------------------------------------------------------------------------------

@mcp.tool()
async def add_expenses(
    date: str,
    amount: int,
    category: str,
    subcategory: str = '',
    note: str = ''
):
    """
    Add a new expense entry to the database.
    """

    try:
        async with aiosqlite.connect(DB_PATH) as c:

            cur = await c.execute(
                """
                INSERT INTO expenses(
                    date,
                    amount,
                    category,
                    subcategory,
                    note
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (date, amount, category, subcategory, note)
            )

            expense_id = cur.lastrowid

            await c.commit()

            return {
                "status": "success",
                "id": expense_id,
                "message": "Expense added successfully"
            }

    except Exception as e:

        if "readonly" in str(e).lower():
            return {
                "status": "error",
                "message": "Database is in read-only mode"
            }

        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


@mcp.tool()
async def list_expenses(start_date: str, end_date: str):
    """
    List expense entries within an inclusive date range.
    """

    try:
        async with aiosqlite.connect(DB_PATH) as c:

            cur = await c.execute(
                """
                SELECT
                    id,
                    date,
                    amount,
                    category,
                    subcategory,
                    note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date)
            )

            rows = await cur.fetchall()

            cols = [d[0] for d in cur.description]

            return [dict(zip(cols, r)) for r in rows]

    except Exception as e:

        return {
            "status": "error",
            "message": f"Error listing expenses: {str(e)}"
        }


@mcp.tool()
async def summarize(
    start_date: str,
    end_date: str,
    category: str = None
):
    """
    Summarize expense entries within a date range.
    """

    try:
        async with aiosqlite.connect(DB_PATH) as c:

            query = """
                SELECT
                    category,
                    SUM(amount) AS total_amount,
                    COUNT(*) AS count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """

            params = [start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category"

            cur = await c.execute(query, params)

            rows = await cur.fetchall()

            cols = [d[0] for d in cur.description]

            return [dict(zip(cols, r)) for r in rows]

    except Exception as e:

        return {
            "status": "error",
            "message": f"Error summarizing expenses: {str(e)}"
        }


# --------------------------------------------------------------------------------
# MCP Resource
# --------------------------------------------------------------------------------

@mcp.resource("expenses:///categories", mime_type="application/json")
def categories():

    try:

        default_categories = {
            "categories": [
                "Food & Dining",
                "Transportation",
                "Shopping",
                "Entertainment",
                "Bills & Utilities",
                "Healthcare",
                "Travel",
                "Education",
                "Business",
                "Other"
            ]
        }

        try:
            with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
                return f.read()

        except FileNotFoundError:
            return json.dumps(default_categories, indent=2)

    except Exception as e:

        return json.dumps({
            "error": f"Could not load categories: {str(e)}"
        })


# --------------------------------------------------------------------------------
# Run Server
# --------------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000
    )