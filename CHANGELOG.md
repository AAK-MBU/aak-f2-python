# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [semantic versioning](https://semver.org/) as described in [CONTRIBUTING.md](CONTRIBUTING.md#versioning).

## Unreleased

### Added

- `aak_f2.shared.F2Client` for reading F2: OAuth2 login, service index discovery, retries on 423/503, and reading cases, case structures, matters, documents, file content and PDF renderings.
- `aak_f2.mbu.F2Client` with the read methods of MBU's GetOrganized client (`get_case_metadata`, `document_metadata`, `download`, `convert_to_pdf`).

### Changed

### Fixed

### Development

- Unit tests for the shared and MBU clients, and read-only live tests in `tests/live` that run when F2 settings are in the environment.
