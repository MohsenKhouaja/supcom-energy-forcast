# Local data policy

- `raw/`: immutable copies of original exports.
- `interim/`: audit and cleaning outputs.
- `processed/`: model-ready, versioned tables.

The contents of these folders are ignored by Git. Never commit institutional readings, invoices, account identifiers, or derived files that can disclose private source data.
