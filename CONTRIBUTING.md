# Contributing to SQListo

Contributions from researchers, developers and users are welcome.

## Reporting Issues

Please use the GitHub Issues section to report bugs, installation problems or unexpected scientific results.

When reporting an issue, include:

- SQListo version.
- Operating system.
- Python version.
- Relevant command and error message.
- A minimal reproducible example, when possible.

Do not include confidential research data, credentials or unpublished datasets without authorization.

## Development

Fork the repository and create a dedicated development branch.

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the regression tests:

```bash
python -m unittest discover -s tests -v
```

Submit changes through a pull request.

## Scientific Contributions

Changes affecting chemical analysis, molecular fragmentation, kinetic models or numerical methods should include:

- A description of the scientific methodology.
- Relevant references, where applicable.
- Validation against reproducible examples.
- Regression tests when appropriate.

## Licensing

Contributions to the source code are accepted under the MIT License, subject to the contributor having the necessary rights.

Scientific datasets and external software may be subject to separate licensing conditions.
