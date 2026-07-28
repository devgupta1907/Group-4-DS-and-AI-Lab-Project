# Services Module

**Purpose:**
This directory holds centralized clients for external APIs and services, such as Large Language Models (LLMs) and Embedding models.

**Design Rationale:**
Instantiating API clients (like LangChain's GoogleGenAIEmbeddings) consumes memory and network overhead. Centralizing them here acts as a Singleton-like pattern. We initialize the LLM and Embedding models once when the server starts, and all modules import these shared instances. This optimizes performance and allows us to change model versions in a single location.