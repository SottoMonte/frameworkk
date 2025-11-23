# Getting Started Guide

This guide will help you configure and start a project based on this framework.

## Prerequisites

*   Python 3.9 or higher
*   `pip` (Python package manager)
*   Access to a database (optional for basic startup, but necessary for many features)

## Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd <folder-name>
    ```

2.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Linux/Mac
    # venv\Scripts\activate  # On Windows
    ```

3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

The main configuration file is `pyproject.toml`. Here you can define:

*   **Database**: Configure the `[persistence.session]` section or similar with your database credentials (e.g., Redis, SQL).
*   **Messaging**: Configure `[amessage]` for logs and communication.
*   **Authentication**: Configure `[authentication]` for providers (e.g., Supabase, GitHub).

Example of minimal configuration for console logs:
```toml
[amessage.log]
adapter = "console"
level = "debug"
```

## Starting the Application

The application can be started using the command (example based on `Procfile` or common scripts):

```bash
python src/main.py
# Or, if you use a web server like uvicorn/gunicorn:
# uvicorn src.main:app --reload
```
*(Note: Check the `Procfile` or specific project documentation for the exact startup command)*

## Running Tests

To run unit tests:

```bash
python -m unittest discover src -p "*.test.py"
```
Or run a specific test:
```bash
python src/infrastructure/authorization/verdict.test.py
```
