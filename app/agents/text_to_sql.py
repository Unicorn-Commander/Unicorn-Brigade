"""
Natural Language to SQL Agent

Converts natural language questions to safe, read-only SQL queries,
executes them against PostgreSQL, and provides structured results with explanations.
"""

import re
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm.ops_center_client import OpsCenterLLMClient
from app.db.database import engine

logger = logging.getLogger(__name__)


# SQL injection patterns to block
SQL_INJECTION_PATTERNS = [
    r";\s*DROP\s+",
    r";\s*DELETE\s+",
    r";\s*UPDATE\s+",
    r";\s*INSERT\s+",
    r";\s*ALTER\s+",
    r";\s*CREATE\s+",
    r";\s*TRUNCATE\s+",
    r";\s*GRANT\s+",
    r";\s*REVOKE\s+",
    r"--",  # SQL comments
    r"/\*",  # Block comments
    r"UNION\s+SELECT",  # Union injection
    r"INTO\s+OUTFILE",
    r"INTO\s+DUMPFILE",
    r"LOAD_FILE",
    r"pg_sleep",
    r"waitfor\s+delay",
    r"benchmark\s*\(",
    r"exec\s*\(",
    r"execute\s*\(",
    r"xp_cmdshell",
]

# Dangerous keywords that indicate mutation
MUTATION_KEYWORDS = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "VACUUM",
    "REINDEX",
    "CLUSTER",
    "COPY",
    "LOCK",
]


class QuerySafetyLevel(Enum):
    """Safety classification for SQL queries"""
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"


@dataclass
class SQLQueryResult:
    """Result from SQL query execution"""
    success: bool
    sql: str
    columns: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    truncated: bool = False


@dataclass
class TextToSQLResponse:
    """Complete response from text-to-SQL agent"""
    question: str
    sql: str
    result: SQLQueryResult
    explanation: Optional[str] = None
    schema_context: Optional[str] = None
    safety_level: QuerySafetyLevel = QuerySafetyLevel.SAFE


class TextToSQLAgent(BaseAgent):
    """
    Agent that converts natural language to SQL queries.

    Features:
    - Schema-aware SQL generation using LLM
    - SQL injection prevention
    - Read-only query enforcement (SELECT only)
    - Query timeout and row limits
    - Natural language result explanation
    """

    # Configuration
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_ROW_LIMIT = 1000
    MAX_ROW_LIMIT = 10000

    def __init__(
        self,
        memory_manager=None,
        llm_client: Optional[OpsCenterLLMClient] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        row_limit: int = DEFAULT_ROW_LIMIT,
        model: str = "openai/gpt-4o-mini",
    ):
        super().__init__("TextToSQLAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.timeout_seconds = timeout_seconds
        self.row_limit = min(row_limit, self.MAX_ROW_LIMIT)
        self.model = model
        self._schema_cache: Optional[str] = None
        self._schema_cache_time: float = 0
        self._schema_cache_ttl: float = 300  # 5 minutes

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute text-to-SQL task.

        Args:
            task: Dict containing:
                - question: Natural language question
                - explain: Whether to include explanation (default: True)
                - row_limit: Override default row limit
                - user_id: User ID for context

        Returns:
            Dict with SQL, results, and optional explanation
        """
        question = task.get("question", task.get("task", ""))
        explain = task.get("explain", True)
        row_limit = min(task.get("row_limit", self.row_limit), self.MAX_ROW_LIMIT)
        user_id = task.get("user_id", "system")

        logger.info(f"TextToSQL processing question: {question[:100]}...")

        try:
            # Step 1: Get database schema for context
            schema = await self.get_schema()

            # Step 2: Generate SQL from natural language
            sql = await self.generate_sql(question, schema)

            # Step 3: Validate and execute query
            result = await self.execute_query(sql, row_limit=row_limit)

            # Step 4: Generate explanation if requested
            explanation = None
            if explain and result.success:
                explanation = await self.explain_results(result, question)

            response = TextToSQLResponse(
                question=question,
                sql=sql,
                result=result,
                explanation=explanation,
                schema_context=schema[:500] + "..." if len(schema) > 500 else schema,
            )

            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "completed" if result.success else "error",
                "question": response.question,
                "sql": response.sql,
                "results": response.result.rows,
                "columns": response.result.columns,
                "row_count": response.result.row_count,
                "truncated": response.result.truncated,
                "explanation": response.explanation,
                "execution_time_ms": response.result.execution_time_ms,
                "error": response.result.error,
                "safety_level": response.safety_level.value,
            }

        except Exception as e:
            logger.error(f"TextToSQL error: {e}")
            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "error",
                "question": question,
                "sql": "",
                "results": [],
                "columns": [],
                "row_count": 0,
                "error": str(e),
            }

    async def get_schema(self, force_refresh: bool = False) -> str:
        """
        Retrieve database schema for LLM context.

        Returns formatted schema information including:
        - Table names and columns
        - Column types
        - Primary keys and foreign keys

        Uses caching to avoid repeated queries.
        """
        import time

        now = time.time()
        if not force_refresh and self._schema_cache and (now - self._schema_cache_time) < self._schema_cache_ttl:
            return self._schema_cache

        logger.info("Fetching database schema...")

        schema_query = """
        SELECT
            t.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default,
            CASE
                WHEN pk.constraint_type = 'PRIMARY KEY' THEN true
                ELSE false
            END as is_primary_key,
            fk.foreign_table_name,
            fk.foreign_column_name
        FROM information_schema.tables t
        JOIN information_schema.columns c
            ON t.table_name = c.table_name AND t.table_schema = c.table_schema
        LEFT JOIN (
            SELECT kcu.table_name, kcu.column_name, tc.constraint_type
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.table_constraints tc
                ON kcu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
        ) pk ON c.table_name = pk.table_name AND c.column_name = pk.column_name
        LEFT JOIN (
            SELECT
                kcu.table_name,
                kcu.column_name,
                ccu.table_name as foreign_table_name,
                ccu.column_name as foreign_column_name
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.table_constraints tc
                ON kcu.constraint_name = tc.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
        ) fk ON c.table_name = fk.table_name AND c.column_name = fk.column_name
        WHERE t.table_schema = 'public'
            AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name, c.ordinal_position;
        """

        try:
            async with engine.connect() as conn:
                result = await conn.execute(text(schema_query))
                rows = result.fetchall()

            # Format schema for LLM
            tables = {}
            for row in rows:
                table_name = row[0]
                if table_name not in tables:
                    tables[table_name] = {
                        "columns": [],
                        "primary_keys": [],
                        "foreign_keys": [],
                    }

                col_info = {
                    "name": row[1],
                    "type": row[2],
                    "nullable": row[3] == "YES",
                    "default": row[4],
                }
                tables[table_name]["columns"].append(col_info)

                if row[5]:  # is_primary_key
                    tables[table_name]["primary_keys"].append(row[1])

                if row[6]:  # foreign_table_name
                    tables[table_name]["foreign_keys"].append({
                        "column": row[1],
                        "references": f"{row[6]}.{row[7]}",
                    })

            # Format as readable text
            schema_text = "DATABASE SCHEMA:\n\n"
            for table_name, table_info in tables.items():
                schema_text += f"Table: {table_name}\n"
                schema_text += "Columns:\n"
                for col in table_info["columns"]:
                    pk_marker = " [PK]" if col["name"] in table_info["primary_keys"] else ""
                    nullable = " (nullable)" if col["nullable"] else " (required)"
                    schema_text += f"  - {col['name']}: {col['type']}{pk_marker}{nullable}\n"

                if table_info["foreign_keys"]:
                    schema_text += "Foreign Keys:\n"
                    for fk in table_info["foreign_keys"]:
                        schema_text += f"  - {fk['column']} -> {fk['references']}\n"

                schema_text += "\n"

            self._schema_cache = schema_text
            self._schema_cache_time = now

            logger.info(f"Schema fetched: {len(tables)} tables")
            return schema_text

        except Exception as e:
            logger.error(f"Error fetching schema: {e}")
            return "Error fetching schema. Please use common table names like 'agents', 'tools', 'users'."

    async def generate_sql(self, question: str, schema: Optional[str] = None) -> str:
        """
        Generate SQL query from natural language question.

        Uses LLM to convert question to SQL with schema context.
        Enforces read-only constraints.

        Args:
            question: Natural language question
            schema: Database schema context (fetched if not provided)

        Returns:
            Generated SQL query string
        """
        if not schema:
            schema = await self.get_schema()

        system_prompt = """You are a SQL query generator for PostgreSQL. Your job is to convert natural language questions into safe, read-only SQL queries.

RULES:
1. ONLY generate SELECT queries - no INSERT, UPDATE, DELETE, DROP, ALTER, or any data-modifying statements
2. Always use explicit column names, avoid SELECT *
3. Use appropriate JOINs when relating tables
4. Add LIMIT clause when the query might return many rows (default LIMIT 100)
5. Use parameterized patterns where possible (e.g., WHERE column = 'value')
6. Return ONLY the SQL query, no explanations or markdown

SAFETY:
- Never generate queries that modify data
- Never use subqueries with side effects
- Never access system tables or pg_* tables
- Never use functions like pg_sleep, dblink, etc.

OUTPUT FORMAT:
Return only the SQL query, nothing else. No markdown code blocks, no explanations."""

        user_prompt = f"""Given this database schema:

{schema}

Convert this question to a SQL query:
"{question}"

Return only the SQL query."""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=self.model,
                temperature=0.1,  # Low temperature for precise SQL
                max_tokens=1000,
            )

            sql = self.llm_client.get_response_content(response).strip()

            # Clean up common LLM response issues
            sql = self._clean_sql_response(sql)

            # Validate the generated SQL
            safety = self._validate_sql_safety(sql)
            if safety == QuerySafetyLevel.DANGEROUS:
                raise ValueError(f"Generated SQL contains dangerous operations: {sql[:100]}")

            logger.info(f"Generated SQL: {sql[:200]}...")
            return sql

        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            raise ValueError(f"Failed to generate SQL: {str(e)}")

    def _clean_sql_response(self, sql: str) -> str:
        """Clean up LLM response to extract pure SQL."""
        # Remove markdown code blocks
        sql = re.sub(r"```sql\s*", "", sql)
        sql = re.sub(r"```\s*", "", sql)

        # Remove leading/trailing whitespace
        sql = sql.strip()

        # Remove any trailing semicolons (we'll add if needed)
        sql = sql.rstrip(";")

        # Ensure single query (take first statement if multiple)
        if ";" in sql:
            sql = sql.split(";")[0]

        return sql.strip()

    def _validate_sql_safety(self, sql: str) -> QuerySafetyLevel:
        """
        Validate SQL query for safety.

        Checks for:
        - SQL injection patterns
        - Mutation keywords
        - Suspicious patterns

        Returns:
            QuerySafetyLevel indicating safety of the query
        """
        sql_upper = sql.upper()

        # Check for dangerous patterns
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                logger.warning(f"SQL injection pattern detected: {pattern}")
                return QuerySafetyLevel.DANGEROUS

        # Check for mutation keywords
        for keyword in MUTATION_KEYWORDS:
            # Match keyword at word boundary
            if re.search(rf"\b{keyword}\b", sql_upper):
                logger.warning(f"Mutation keyword detected: {keyword}")
                return QuerySafetyLevel.DANGEROUS

        # Verify it starts with SELECT (after stripping)
        if not sql_upper.strip().startswith("SELECT"):
            # Could be WITH (CTE) followed by SELECT
            if not (sql_upper.strip().startswith("WITH") and "SELECT" in sql_upper):
                logger.warning("Query does not start with SELECT")
                return QuerySafetyLevel.DANGEROUS

        # Check for suspicious patterns (not blocking, just flagging)
        suspicious_patterns = [
            r"information_schema",
            r"pg_catalog",
            r"pg_stat",
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                logger.info(f"Suspicious pattern detected: {pattern}")
                return QuerySafetyLevel.SUSPICIOUS

        return QuerySafetyLevel.SAFE

    async def execute_query(
        self,
        sql: str,
        row_limit: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> SQLQueryResult:
        """
        Execute SQL query with safety checks.

        Args:
            sql: SQL query to execute
            row_limit: Maximum rows to return
            timeout: Query timeout in seconds

        Returns:
            SQLQueryResult with query results or error
        """
        import time

        row_limit = row_limit or self.row_limit
        timeout = timeout or self.timeout_seconds

        # Validate safety
        safety = self._validate_sql_safety(sql)
        if safety == QuerySafetyLevel.DANGEROUS:
            return SQLQueryResult(
                success=False,
                sql=sql,
                error="Query rejected: contains dangerous operations",
            )

        # Add LIMIT if not present
        sql_upper = sql.upper()
        if "LIMIT" not in sql_upper:
            sql = f"{sql} LIMIT {row_limit}"
        else:
            # Extract and enforce our limit
            limit_match = re.search(r"LIMIT\s+(\d+)", sql_upper)
            if limit_match:
                existing_limit = int(limit_match.group(1))
                if existing_limit > row_limit:
                    sql = re.sub(
                        r"LIMIT\s+\d+",
                        f"LIMIT {row_limit}",
                        sql,
                        flags=re.IGNORECASE,
                    )

        start_time = time.time()

        try:
            # Execute with timeout
            async def run_query():
                async with engine.connect() as conn:
                    # Set statement timeout
                    await conn.execute(text(f"SET statement_timeout = '{timeout * 1000}'"))
                    result = await conn.execute(text(sql))
                    rows = result.fetchall()
                    columns = list(result.keys()) if result.keys() else []
                    return rows, columns

            rows, columns = await asyncio.wait_for(
                run_query(),
                timeout=timeout + 1,  # Slightly longer than statement timeout
            )

            execution_time = (time.time() - start_time) * 1000

            # Convert rows to dicts
            result_rows = [dict(zip(columns, row)) for row in rows]

            # Check if we hit the limit (might be truncated)
            truncated = len(result_rows) >= row_limit

            logger.info(f"Query executed: {len(result_rows)} rows in {execution_time:.2f}ms")

            return SQLQueryResult(
                success=True,
                sql=sql,
                columns=columns,
                rows=result_rows,
                row_count=len(result_rows),
                execution_time_ms=execution_time,
                truncated=truncated,
            )

        except asyncio.TimeoutError:
            logger.error(f"Query timeout after {timeout}s")
            return SQLQueryResult(
                success=False,
                sql=sql,
                error=f"Query timed out after {timeout} seconds",
            )
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return SQLQueryResult(
                success=False,
                sql=sql,
                error=str(e),
            )

    async def explain_results(
        self,
        result: SQLQueryResult,
        question: str,
    ) -> str:
        """
        Generate natural language explanation of query results.

        Uses LLM to create a human-readable summary of the results
        in context of the original question.

        Args:
            result: Query results
            question: Original natural language question

        Returns:
            Natural language explanation
        """
        if not result.success:
            return f"The query failed with error: {result.error}"

        if not result.rows:
            return "The query returned no results."

        # Prepare sample of results for LLM
        sample_rows = result.rows[:10]
        sample_text = json.dumps(sample_rows, indent=2, default=str)

        system_prompt = """You are a data analyst assistant. Your job is to explain SQL query results in clear, natural language.

GUIDELINES:
1. Summarize the key findings
2. Highlight important numbers and trends
3. Answer the original question directly
4. Keep explanations concise but informative
5. If results seem incomplete (truncated), mention this"""

        user_prompt = f"""Original Question: "{question}"

SQL Query: {result.sql}

Results ({result.row_count} rows{', truncated' if result.truncated else ''}):
{sample_text}

Please explain these results in a clear, natural way that answers the original question."""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=self.model,
                temperature=0.5,
                max_tokens=500,
            )

            explanation = self.llm_client.get_response_content(response).strip()
            logger.info("Generated explanation for results")
            return explanation

        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            return f"Query returned {result.row_count} rows."

    async def ask(
        self,
        question: str,
        explain: bool = True,
        row_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Convenience method for simple question answering.

        Args:
            question: Natural language question
            explain: Whether to include explanation
            row_limit: Maximum rows to return

        Returns:
            Dict with results and explanation
        """
        return await self.execute({
            "question": question,
            "explain": explain,
            "row_limit": row_limit or self.row_limit,
        })


# Singleton instance for route handlers
_agent_instance: Optional[TextToSQLAgent] = None


def get_text_to_sql_agent(llm_client: Optional[OpsCenterLLMClient] = None) -> TextToSQLAgent:
    """Get or create singleton TextToSQLAgent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = TextToSQLAgent(llm_client=llm_client)
    return _agent_instance
