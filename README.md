# SQLAlchemy RDS IAM Authentication

A Python library that provides IAM authentication support for Amazon RDS databases using SQLAlchemy. This library makes it easy to use IAM authentication with your RDS databases while maintaining the flexibility and power of SQLAlchemy.

## Features

- IAM authentication support for PostgreSQL RDS databases
- Seamless integration with SQLAlchemy
- Automatic token generation and renewal
- Type hints for better IDE support
- Modular design for easy extension to other RDS database engines
- Thread-safe token caching with configurable timeout

## Installation

```bash
pip install sqlalchemy-rds-iam
```

## Quick Start

```python
from sqlalchemy import create_engine
from sqlalchemy_rds_iam import RDSIAMAuth

# Create the auth handler
auth = RDSIAMAuth()

# Create an engine
engine = create_engine(
    "postgresql+psycopg2://user@your-rds-instance.region.rds.amazonaws.com:5432/dbname"
)

# Register the auth handler with the engine
auth.register_for_engine(engine)

# Use the engine as normal - IAM tokens will be automatically generated and renewed
with engine.connect() as conn:
    result = conn.execute("SELECT 1")
```

## Detailed Usage

### Basic Configuration

The `RDSIAMAuth` class can be configured with several options:

```python
from sqlalchemy import create_engine
from sqlalchemy_rds_iam import RDSIAMAuth

# Configure the auth handler
auth = RDSIAMAuth(
    region_name="us-west-2",  # Optional: AWS region, will be extracted from endpoint if not provided
    cache_timeout=600,        # Optional: Token cache timeout in seconds (default: 600)
    boto_session=None        # Optional: Custom boto3 session for AWS credentials
)

# Create and configure the engine
engine = create_engine(
    "postgresql+psycopg2://user@your-rds-instance.us-west-2.rds.amazonaws.com:5432/dbname"
)
auth.register_for_engine(engine)
```

### How It Works

The library uses SQLAlchemy's event system to provide IAM tokens:

1. When a new database connection is needed, SQLAlchemy triggers a `do_connect` event
2. The auth handler generates an IAM authentication token using AWS credentials
3. The token is cached for the configured timeout period (default: 10 minutes)
4. The token is automatically used as the password for the connection
5. When the token expires, a new one is generated automatically

### Token Caching

Tokens are cached by default to minimize AWS API calls:

- Each unique combination of username, host, port, and region gets its own cached token
- Tokens expire after the configured timeout (default: 10 minutes)
- Cache is thread-safe for use in multi-threaded applications

### AWS Credentials

The library uses boto3's credential resolution:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. Shared credential file (`~/.aws/credentials`)
3. IAM role credentials (when running on EC2 or ECS)

You can also provide a custom boto3 session:

```python
import boto3

session = boto3.Session(profile_name='custom-profile')
auth = RDSIAMAuth(boto_session=session)
engine = create_engine(
    "postgresql+psycopg2://user@your-rds-instance.us-west-2.rds.amazonaws.com:5432/dbname"
)
auth.register_for_engine(engine)
```

## Documentation

For detailed documentation, please visit [sqlalchemy-rds-iam.readthedocs.io](https://sqlalchemy-rds-iam.readthedocs.io).

## Development

### Setup

1. Clone the repository:
```bash
git clone https://github.com/jjshanks/sqlalchemy-rds-iam.git
cd sqlalchemy-rds-iam
```

2. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

3. Install dependencies and set up development environment:
```bash
poetry install
```

### Running Tests

```bash
poetry run pytest
```

### Code Quality

We use several tools to maintain code quality:

```bash
# Format code
poetry run black .
poetry run isort .

# Type checking
poetry run mypy src/sqlalchemy_rds_iam

# Linting
poetry run ruff check .

# Run all pre-commit hooks
poetry run pre-commit run --all-files
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
