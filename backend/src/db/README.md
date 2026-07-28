# Database Module

**Purpose:**
This directory manages centralized connections to all databases (e.g., ChromaDB, SQL).

**Design Rationale:**
Databases are stateful, shared resources. By centralizing the connection logic here, we ensure that the application uses connection pooling (for SQL) and avoids file-lock collisions (for local ChromaDB). This prevents multiple modules from trying to initialize the database simultaneously, which would crash the application or exhaust system memory.