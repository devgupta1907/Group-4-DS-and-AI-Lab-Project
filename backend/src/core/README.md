# Core Module

**Purpose:** 
This directory contains application-wide, global configurations and utilities. 

**Design Rationale:**
We will centralize our environment variables and global constants here. This ensures that sensitive information (like API keys) and global paths are loaded exactly once and shared securely across all modules, preventing code duplication and configuration drift.