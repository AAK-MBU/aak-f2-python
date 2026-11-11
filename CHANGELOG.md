# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [semantic versioning](https://semver.org/) as described in [CONTRIBUTING.md](CONTRIBUTING.md#versioning).

## Unreleased

### Added

- `aak_f2.shared.F2Client` for reading F2: OAuth2 login, service index discovery, retries on 423/503, and reading cases, case structures, matters, documents, file content and PDF renderings, and saving file content or PDF renderings to a file (`save_content`, `save_pdf`).
- Filtered search for cases and matters (`search_cases`, `search_matters`) and party lookup by ID, CPR/CVR number and login (`get_party`, `get_party_by_cpr`, `get_party_by_login`) in `aak_f2.shared`.
- Full text search for cases and matters (`fulltext_search_cases`, `fulltext_search_matters`) with a `count` for the maximum number of hits, using the URL template from the OpenSearch description behind F2's `case-search` and `matter-search` services (`opensearch_template`).
- `request` and `get_xml` in `aak_f2.shared.F2Client` for calling any F2-REST link or URL with the client's authentication, retries and error handling.
- `service_index` and `service_url` in `aak_f2.shared.F2Client` to list the services in F2's service index and fill their URL templates.
- Creating cases, matters and documents and updating cases and matters in `aak_f2.shared.F2Client` (`create_case`, `create_matter`, `create_document`, `update_case`, `update_matter`) using F2's Post-Once-Exactly pattern, with `F2AccessWarning` when a matter is only visible to its (missing) involved parties.
- `journal_plan_code` (KLE number) and `process_instruction_code` (KLE handlingsfacet) in `create_case` and `update_case`, and `journal_plan` and `process_instruction` on `Case`.
- `upload_document` in `aak_f2.mbu.F2Client`, creating a matter per upload unless `matter_id` is given.
- `contact_lookup` in `aak_f2.mbu.F2Client`.
- `F2NotFoundError` (404) and `F2AccessDeniedError` (403) as subclasses of `F2HTTPError`.
- `aak_f2.mbu.F2Client` with the read methods of MBU's GetOrganized client (`get_case_metadata`, `document_metadata`, `download`, `convert_to_pdf`).

### Changed

### Fixed

### Development

- Unit tests for the shared and MBU clients, and read-only live tests in `tests/live` that run when F2 settings are in the environment.
