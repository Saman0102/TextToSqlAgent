You are an expert AI Engineer and Python Developer specializing in agentic workflows
(e.g., LangGraph, AutoGen) and database engineering.

**Objective**
Generate a production-ready, agentic Text-to-SQL application in a single response. The
system should take a natural language query from a user, plan the necessary database
operations, generate SQL, validate it, execute it securely, and summarize the results back
to the user in natural language.

Provide the complete code for the project following the exact directory structure and
database schema provided below.

**Response Requirements**

- Split the response into clear parts if needed (e.g., overview, code, run steps).
- Output full code for every file listed below. No placeholders or omissions.
- Use file path headers before each code block, for example: ### app/agents/planner.py
- Keep everything ASCII-only. Avoid Unicode bullets or special symbols.

### 1. Directory Structure to Generate

```text
app/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── agents/
│   ├── __init__.py
│   ├── executor.py        # Executes the validated SQL query safely
│   ├── llm.py             # Centralized LLM configuration/instantiation
│   ├── planner.py         # Analyzes user query and decides tables/columns
│   ├── sql_generator.py   # Generates PostgreSQL query from plan and schema
│   ├── summarizer.py      # Converts DB JSON results to natural language
│   └── validator.py       # Validates SQL and checks for destructive ops
├── graph/
│   ├── __init__.py
│   └── workflow.py        # State machine / agentic flow
├── prompts/
│   └── __init__.py        # Centralized system prompts
├── sql/
│   └── seed.sql           # Provided below
├── tools/
│   ├── __init__.py
│   └── db_tools.py        # DB connection logic and query execution tools
├── __init__.py
├── config.py              # Env var loading (DB connection strings, API keys)
├── db.py                  # SQLAlchemy engine/session setup
├── main.py                # FastAPI or main entry point to trigger workflow
└── streamlit_app.py       # Streamlit chat UI for the user
```

### 2. Database Schema (app/sql/seed.sql)

The database is PostgreSQL. Use the following schema for prompts and DB setup:

```sql
-- Drop tables safely (order + CASCADE matters)
DROP TABLE IF EXISTS orderdetails CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS offices CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS productlines CASCADE;

-- Tables
CREATE TABLE productlines (
	"productLine" VARCHAR(50) PRIMARY KEY,
	"textDescription" VARCHAR(4000),
	"htmlDescription" TEXT,
	"image" BYTEA
);

CREATE TABLE products (
	"productCode" VARCHAR(15) PRIMARY KEY,
	"productName" VARCHAR(70) NOT NULL,
	"productLine" VARCHAR(50) NOT NULL,
	"productScale" VARCHAR(10) NOT NULL,
	"productVendor" VARCHAR(50) NOT NULL,
	"productDescription" TEXT NOT NULL,
	"quantityInStock" INTEGER NOT NULL,
	"buyPrice" NUMERIC(10,2) NOT NULL,
	"MSRP" NUMERIC(10,2) NOT NULL,
	FOREIGN KEY ("productLine") REFERENCES productlines("productLine")
);

CREATE TABLE offices (
	"officeCode" VARCHAR(10) PRIMARY KEY,
	"city" VARCHAR(50) NOT NULL,
	"phone" VARCHAR(50) NOT NULL,
	"addressLine1" VARCHAR(50) NOT NULL,
	"addressLine2" VARCHAR(50),
	"state" VARCHAR(50),
	"country" VARCHAR(50) NOT NULL,
	"postalCode" VARCHAR(15) NOT NULL,
	"territory" VARCHAR(10) NOT NULL
);

CREATE TABLE employees (
	"employeeNumber" INTEGER PRIMARY KEY,
	"lastName" VARCHAR(50) NOT NULL,
	"firstName" VARCHAR(50) NOT NULL,
	"extension" VARCHAR(10) NOT NULL,
	"email" VARCHAR(100) NOT NULL,
	"officeCode" VARCHAR(10) NOT NULL,
	"reportsTo" INTEGER,
	"jobTitle" VARCHAR(50) NOT NULL,
	FOREIGN KEY ("reportsTo") REFERENCES employees("employeeNumber"),
	FOREIGN KEY ("officeCode") REFERENCES offices("officeCode")
);

CREATE TABLE customers (
	"customerNumber" INTEGER PRIMARY KEY,
	"customerName" VARCHAR(50) NOT NULL,
	"contactLastName" VARCHAR(50) NOT NULL,
	"contactFirstName" VARCHAR(50) NOT NULL,
	"phone" VARCHAR(50) NOT NULL,
	"addressLine1" VARCHAR(50) NOT NULL,
	"addressLine2" VARCHAR(50),
	"city" VARCHAR(50) NOT NULL,
	"state" VARCHAR(50),
	"postalCode" VARCHAR(15),
	"country" VARCHAR(50) NOT NULL,
	"salesRepEmployeeNumber" INTEGER,
	"creditLimit" NUMERIC(10,2),
	FOREIGN KEY ("salesRepEmployeeNumber") REFERENCES employees("employeeNumber")
);

CREATE TABLE payments (
	"customerNumber" INTEGER,
	"checkNumber" VARCHAR(50),
	"paymentDate" DATE NOT NULL,
	"amount" NUMERIC(10,2) NOT NULL,
	PRIMARY KEY ("customerNumber", "checkNumber"),
	FOREIGN KEY ("customerNumber") REFERENCES customers("customerNumber")
);

CREATE TABLE orders (
	"orderNumber" INTEGER PRIMARY KEY,
	"orderDate" DATE NOT NULL,
	"requiredDate" DATE NOT NULL,
	"shippedDate" DATE,
	"status" VARCHAR(15) NOT NULL,
	"comments" TEXT,
	"customerNumber" INTEGER NOT NULL,
	FOREIGN KEY ("customerNumber") REFERENCES customers("customerNumber")
);

CREATE TABLE orderdetails (
	"orderNumber" INTEGER,
	"productCode" VARCHAR(15),
	"quantityOrdered" INTEGER NOT NULL,
	"priceEach" NUMERIC(10,2) NOT NULL,
	"orderLineNumber" SMALLINT NOT NULL,
	PRIMARY KEY ("orderNumber", "productCode"),
	FOREIGN KEY ("orderNumber") REFERENCES orders("orderNumber"),
	FOREIGN KEY ("productCode") REFERENCES products("productCode")
);
```

### 3. Agentic Workflow Instructions

Implement a state-based agent workflow (standard Python dataclasses/typing or
LangGraph). The state must track: user_query, plan, generated_sql, is_valid_sql,
execution_results, final_answer, and errors.

Workflow steps:

1. Planner Agent: Analyze user_query and schema. Output a strategic plan.
2. SQL Generator Agent: Use the plan to write a strict PostgreSQL query.
3. Validator Agent: Check for syntax issues and enforce read-only queries
   (no DROP, DELETE, UPDATE, INSERT). If invalid, loop back to the Generator
   with error feedback.
4. Executor Agent: Run validated SQL against Postgres using db_tools.py and
   capture results as JSON/dicts.
5. Summarizer Agent: Convert query + results into a friendly response.

### 4. Implementation Requirements

- Docker and Compose: Provide a Dockerfile for the Python app and a
  docker-compose.yml that runs both the Streamlit app and PostgreSQL initialized
  with seed.sql.
- Environment Variables: Use config.py to load DATABASE_URL and an API key
  (OPENAI_API_KEY or GEMINI_API_KEY).
- Database Connection: Use SQLAlchemy or psycopg2 in db.py and db_tools.py.
- Security: Always parameterize queries and block destructive SQL.
- Complete Code: Output full code for every file in the structure above.
