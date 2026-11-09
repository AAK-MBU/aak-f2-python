# aak-f2

A Python client for the F2 ESDH system.

## Installation

The package is available on [PyPI](https://pypi.org/project/aak-f2/):

```sh
pip install aak-f2
```

## Usage

F2 stores cases ("sager"), which hold matters ("akter"), which hold documents.
`aak_f2.shared.F2Client` reads all three. It logs in with OAuth2 and discovers
every URL from the F2-REST service index, so the service index URL is the only
URL it needs.

```python
from aak_f2.shared import F2Client

client = F2Client.from_env()

case = client.get_case(1046444)  # or get_case_by_number("2022 - 60")
for item in client.list_matters(case):
    matter = client.get_matter(item.id)
    for doc_item in client.list_documents(matter):
        document = client.get_document(doc_item.id)
        client.save_content(document, f"/tmp/{document.id}.{document.file_type}")
        pdf = client.get_pdf(document)  # None if F2 has no PDF version

structure = client.get_case_structure(case)  # all matters and documents at once
```

Methods that take a case, matter or document accept either its ID or an object
already read with the client.

Errors are raised as subclasses of `aak_f2.shared.F2Error`. `F2HTTPError`
carries F2's `message`, `details` and `reason_code`.

### Configuration

`F2Client.from_env()` reads these environment variables. Use
`F2Client(F2Config(...))` to configure the client in code instead.

| Variable | Required | Description |
| --- | --- | --- |
| `F2_SERVICE_INDEX_URL` | Yes | URL of the F2-REST service index. |
| `F2_CLIENT_ID` | Yes | OAuth2 client ID from the F2 service provider. |
| `F2_CLIENT_SECRET` | Yes | OAuth2 client secret from the F2 service provider. |
| `F2_USERNAME` | Yes | F2 user the client works as. |
| `F2_PASSWORD` | No | Password of the F2 user, if the installation requires it. |
| `F2_ORGANIZATION_PARTYNO` | No | Party number of the organization to log in to. |
| `F2_TIMEOUT` | No | Request timeout in seconds (default 60). |

### Department modules

`aak_f2.mbu.F2Client` extends the shared client with the method names of MBU's
GetOrganized client (`get_case_metadata`, `document_metadata`, `download`,
`convert_to_pdf`), so MBU processes can switch ESDH by changing the import.
